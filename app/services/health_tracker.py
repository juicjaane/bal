"""
Patch Health Tracker — translates GEE satellite data into actionable health signals.
Uses NDVI change detection to classify patch health as IMPROVING / STABLE / DECLINING.
Uncertainty is shown in the detailed view; only the traffic light is shown on the card.
"""
import ee
import logging
import os

logger = logging.getLogger(__name__)

HEALTH_IMPROVING = 'improving'
HEALTH_STABLE = 'stable'
HEALTH_DECLINING = 'declining'
HEALTH_UNKNOWN = 'unknown'

HEALTH_COLORS = {
    HEALTH_IMPROVING: '#16a34a',   # green
    HEALTH_STABLE: '#ca8a04',      # yellow/amber
    HEALTH_DECLINING: '#dc2626',   # red
    HEALTH_UNKNOWN: '#6b7280',     # gray
}

HEALTH_ICONS = {
    HEALTH_IMPROVING: '📈',
    HEALTH_STABLE: '📊',
    HEALTH_DECLINING: '📉',
    HEALTH_UNKNOWN: '❓',
}

HEALTH_LABELS = {
    HEALTH_IMPROVING: 'Improving',
    HEALTH_STABLE: 'Stable',
    HEALTH_DECLINING: 'Declining',
    HEALTH_UNKNOWN: 'No Data',
}

def classify_ndvi_trend(current_ndvi: float, baseline_ndvi: float, threshold_pct: float = 0.08) -> str:
    """
    Classify health based on NDVI change.
    threshold_pct: fractional change required to be classified as improving/declining (default 8%)
    """
    if baseline_ndvi == 0:
        return HEALTH_UNKNOWN
    change = (current_ndvi - baseline_ndvi) / abs(baseline_ndvi)
    if change > threshold_pct:
        return HEALTH_IMPROVING
    elif change < -threshold_pct:
        return HEALTH_DECLINING
    return HEALTH_STABLE

def get_ndvi_for_area(aoi: ee.Geometry, date_str: str, days_window: int = 30) -> float:
    """
    Get mean NDVI for an area over a time window using Sentinel-2.
    Returns mean NDVI value or 0.0 on failure.
    """
    try:
        start = ee.Date(date_str)
        end = start.advance(days_window, 'day')
        
        s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterBounds(aoi)
              .filterDate(start, end)
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))
        
        if s2.size().getInfo() == 0:
            return 0.0
        
        median_img = s2.median()
        ndvi = median_img.normalizedDifference(['B8', 'B4']).rename('NDVI')
        
        stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=10,
            maxPixels=1e8
        )
        val = stats.get('NDVI').getInfo()
        return float(val) if val is not None else 0.0
    except Exception as e:
        logger.error(f"NDVI fetch error: {e}")
        return 0.0

def assess_patch_health(area_name: str) -> dict:
    """
    Full patch health assessment for a named area.
    Returns a dict with health status, NDVI values, trend, and metadata.
    """
    from .earth_engine import init_earth_engine, get_coordinates, calculate_aoi
    
    if not init_earth_engine():
        return {
            'status': HEALTH_UNKNOWN,
            'label': HEALTH_LABELS[HEALTH_UNKNOWN],
            'color': HEALTH_COLORS[HEALTH_UNKNOWN],
            'icon': HEALTH_ICONS[HEALTH_UNKNOWN],
            'error': 'Earth Engine not configured',
        }
    
    try:
        aoi, _ = calculate_aoi(area_name)
        
        import datetime
        now = datetime.datetime.utcnow()
        
        # Current window: last 30 days
        current_date = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        # Baseline: 90 days ago (30-day window)
        baseline_date = (now - datetime.timedelta(days=120)).strftime('%Y-%m-%d')
        
        current_ndvi = get_ndvi_for_area(aoi, current_date, 30)
        baseline_ndvi = get_ndvi_for_area(aoi, baseline_date, 30)
        
        status = classify_ndvi_trend(current_ndvi, baseline_ndvi)
        
        # Calculate percentage change for display
        if baseline_ndvi > 0:
            change_pct = round((current_ndvi - baseline_ndvi) / abs(baseline_ndvi) * 100, 1)
        else:
            change_pct = 0
        
        return {
            'status': status,
            'label': HEALTH_LABELS[status],
            'color': HEALTH_COLORS[status],
            'icon': HEALTH_ICONS[status],
            'current_ndvi': round(current_ndvi, 3),
            'baseline_ndvi': round(baseline_ndvi, 3),
            'change_pct': change_pct,
            'change_direction': '↑' if change_pct > 0 else ('↓' if change_pct < 0 else '→'),
            'area': area_name,
            'assessment_period': '90-day trend vs. 30-day baseline',
            'data_source': 'Copernicus Sentinel-2 SR (ESA)',
        }
    except Exception as e:
        logger.error(f"Patch health assessment failed: {e}")
        return {
            'status': HEALTH_UNKNOWN,
            'label': HEALTH_LABELS[HEALTH_UNKNOWN],
            'color': HEALTH_COLORS[HEALTH_UNKNOWN],
            'icon': HEALTH_ICONS[HEALTH_UNKNOWN],
            'error': str(e),
        }
