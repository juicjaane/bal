import ee
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import base64
import os
import json
import logging
from io import BytesIO

logger = logging.getLogger(__name__)
_ee_initialized = False

def init_earth_engine():
    global _ee_initialized
    if _ee_initialized:
        return True
    try:
        service_account = os.environ.get('GEE_SERVICE_ACCOUNT')
        project = os.environ.get('GEE_PROJECT', 'ee-ankithareddy2210178')
        
        creds_json = os.environ.get('GEE_CREDENTIALS_JSON')
        creds_path = os.environ.get('GEE_CREDENTIALS_PATH')
        
        if creds_json:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(creds_json)
                tmp_path = f.name
            credentials = ee.ServiceAccountCredentials(service_account, tmp_path)
            os.unlink(tmp_path)
        elif creds_path and os.path.exists(creds_path):
            credentials = ee.ServiceAccountCredentials(service_account, creds_path)
        else:
            logger.warning("No GEE credentials found.")
            return False
        
        ee.Initialize(credentials, project=project)
        _ee_initialized = True
        return True
    except Exception as e:
        logger.error(f"Earth Engine initialization failed: {e}")
        return False

def get_coordinates(location_name):
    geolocator = Nominatim(user_agent="blue-ai-app")
    try:
        location = geolocator.geocode(location_name)
        if location:
            return (location.latitude, location.longitude)
        raise ValueError(f"Location not found: {location_name}")
    except GeocoderTimedOut:
        return get_coordinates(location_name)

def calculate_aoi(location_name):
    lat, lon = get_coordinates(location_name)
    delta = 0.5
    aoi = ee.Geometry.Polygon([[
        [lon - delta, lat - delta],
        [lon + delta, lat - delta],
        [lon + delta, lat + delta],
        [lon - delta, lat + delta],
        [lon - delta, lat - delta]
    ]])
    return aoi, (lat, lon)

def add_ee_layer(self, ee_image_object, vis_params, name, show=True):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Google Earth Engine',
        name=name,
        overlay=True,
        control=True,
        show=show
    ).add_to(self)

folium.Map.add_ee_layer = add_ee_layer

def calculate_area(image, aoi):
    pixel_area = image.multiply(ee.Image.pixelArea()).rename('area')
    stats = pixel_area.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=aoi,
        scale=30,
        maxPixels=1e9
    )
    return stats.get('area').getInfo()

def encode_image_to_base64(buf):
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

def save_chart_to_base64(data, labels, title, xlabel, ylabel, color='#00b4b6'):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(labels, data, marker='o', linestyle='-', color=color, linewidth=2, markersize=6)
    ax.fill_between(labels, data, alpha=0.1, color=color)
    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    return encode_image_to_base64(buf)

def generate_mangrove_report(area: str):
    if not init_earth_engine():
        return None, {"error": "Earth Engine not configured"}
    
    try:
        aoi, aoi_center = calculate_aoi(area)
        
        extent_raster = ee.ImageCollection(
            "projects/earthengine-legacy/assets/projects/sat-io/open-datasets/GMW/extent/GMW_V3"
        ).filterBounds(aoi)
        change_raster = ee.ImageCollection(
            "projects/earthengine-legacy/assets/projects/sat-io/open-datasets/GMW/change/change_f1996"
        ).filterBounds(aoi)
        
        extent_vis = {'opacity': 1, 'bands': ['b1'], 'min': 1, 'max': 1, 'palette': ['228B22']}
        change_vis = {'opacity': 1, 'bands': ['b1'], 'min': 1, 'max': 2, 'palette': ['#ff0000', '#0000ff']}
        
        my_map = folium.Map(location=aoi_center, zoom_start=11, tiles='OpenStreetMap')
        
        years = [1996, 2007, 2008, 2009, 2010, 2015, 2016, 2017, 2018, 2019, 2020]
        for year in years:
            image = extent_raster.filterDate(f'{year}-01-01', f'{year}-12-31').first()
            my_map.add_ee_layer(image, extent_vis, f'Mangrove Area {year}', show=(year == 2020))
        
        my_map.add_ee_layer(
            change_raster.sort('system:time_end', False).first(),
            change_vis, 'Change: Loss (red) / Gain (blue) 1996-2020', show=True
        )
        folium.LayerControl().add_to(my_map)
        map_html = my_map._repr_html_()
        
        tree_density = 500
        areas, num_trees = [], []
        for year in years:
            image = extent_raster.filterDate(f'{year}-01-01', f'{year}-12-31').first()
            area_m2 = calculate_area(image, aoi)
            area_km2 = area_m2 / 1e6
            areas.append(area_km2)
            num_trees.append(area_km2 * tree_density)
        
        survival_rates = [1.0]
        for i in range(1, len(num_trees)):
            rate = num_trees[i] / num_trees[i-1] if num_trees[i-1] > 0 else 0
            survival_rates.append(rate)
        
        report_data = {
            'area_chart': save_chart_to_base64(areas, years, f'Mangrove Area Over Time — {area}', 'Year', 'Area (km²)'),
            'tree_chart': save_chart_to_base64(num_trees, years, f'Estimated Tree Count — {area}', 'Year', 'Number of Trees'),
            'survival_chart': save_chart_to_base64(survival_rates, years, f'Tree Survival Rate — {area}', 'Year', 'Survival Rate', color='#ff6b35'),
            'current_area': round(areas[-1], 2) if areas else 0,
            'current_trees': int(num_trees[-1]) if num_trees else 0,
            'carbon_sequestered': round((areas[-1] * 6.7) if areas else 0, 1),
        }
        
        return map_html, report_data
    except Exception as e:
        logger.error(f"Mangrove report generation failed: {e}")
        return None, {"error": str(e)}

def generate_air_quality_report(area: str):
    if not init_earth_engine():
        return None, "Earth Engine not configured"
    
    try:
        aoi = calculate_aoi(area)[0]
        
        def get_monthly_concentration(collection, band):
            s5p = ee.ImageCollection(collection).select(band).filterBounds(aoi)
            months = ee.List.sequence(1, 12)
            
            def monthly_mean(month):
                start = ee.Date.fromYMD(2022, month, 1)
                end = start.advance(1, 'month')
                mean = s5p.filterDate(start, end).mean().reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=aoi, scale=1000, bestEffort=True
                )
                return ee.Feature(None, {'month': start.format('YYYY-MM'), 'value': mean.get(band)})
            
            return ee.FeatureCollection(months.map(monthly_mean)).getInfo()
        
        no2_data = get_monthly_concentration('COPERNICUS/S5P/NRTI/L3_NO2', 'NO2_column_number_density')
        so2_data = get_monthly_concentration('COPERNICUS/S5P/NRTI/L3_SO2', 'SO2_column_number_density')
        
        months = [f['properties']['month'] for f in no2_data['features']]
        no2_values = [f['properties']['value'] for f in no2_data['features']]
        so2_values = [f['properties']['value'] for f in so2_data['features']]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(months, no2_values, marker='o', color='#7c3aed', label='NO₂', linewidth=2)
        ax.plot(months, so2_values, marker='s', color='#f59e0b', label='SO₂', linewidth=2)
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Mean Concentration (mol/m²)', fontsize=12)
        ax.set_title(f'NO₂ & SO₂ Air Quality — {area} (2022)', fontsize=14, fontweight='bold')
        ax.legend(fontsize=12)
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        return encode_image_to_base64(buf), None
    except Exception as e:
        logger.error(f"Air quality report failed: {e}")
        return None, str(e)
