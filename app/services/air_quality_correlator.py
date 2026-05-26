"""
Correlation between mangrove health (NDVI) and local air quality (NO2/SO2).
Provides indicative estimates when GEE Sentinel-5P data is unavailable.
"""
import logging

logger = logging.getLogger(__name__)

# WHO Air Quality Guidelines 2021
WHO = {
    'no2_annual': 10,    # µg/m³ annual mean
    'no2_daily': 25,     # µg/m³ 24-hour mean
    'so2_daily': 40,     # µg/m³ 24-hour mean
}

# NDVI thresholds for healthy mangroves
NDVI_LEVELS = {'excellent': 0.75, 'good': 0.60, 'moderate': 0.45, 'poor': 0.30}


def assess_from_ndvi(ndvi: float) -> dict:
    """
    Indicative air quality estimate from NDVI score.
    Based on published vegetation-AQ correlations for coastal zones.
    """
    if ndvi >= NDVI_LEVELS['excellent']:
        label, no2, so2, aq = 'Excellent', 8, 12, 'Good'
        desc = 'High NDVI indicates healthy canopy actively filtering coastal air pollutants.'
    elif ndvi >= NDVI_LEVELS['good']:
        label, no2, so2, aq = 'Good', 14, 22, 'Moderate'
        desc = 'Healthy canopy providing moderate air quality improvement to surrounding area.'
    elif ndvi >= NDVI_LEVELS['moderate']:
        label, no2, so2, aq = 'Moderate', 22, 35, 'Moderate-Poor'
        desc = 'Declining coverage may correlate with reduced pollutant buffering capacity.'
    else:
        label, no2, so2, aq = 'Poor', 32, 55, 'Poor'
        desc = 'Stressed vegetation with reduced capacity to filter coastal air pollutants.'
    return {
        'ndvi': ndvi,
        'health_label': label,
        'no2_ug_m3': no2,
        'so2_ug_m3': so2,
        'aq_index': aq,
        'description': desc,
        'no2_x_who': round(no2 / WHO['no2_annual'], 1),
        'so2_x_who': round(so2 / WHO['so2_daily'], 1),
        'no2_ok': no2 <= WHO['no2_annual'],
        'so2_ok': so2 <= WHO['so2_daily'],
        'note': 'Indicative estimate. Use Sentinel-5P GEE data for precise values.',
    }


def interpret_sentinel5p(no2_mol_m2: float, so2_mol_m2: float) -> dict:
    """Convert Sentinel-5P column density to approximate surface concentrations."""
    import math
    no2_ug = no2_mol_m2 * 1e4 * 46.005 / 6.022e23 * 1e9
    so2_ug = so2_mol_m2 * 1e4 * 64.066 / 6.022e23 * 1e9
    return {
        'no2_mol_m2': no2_mol_m2,
        'so2_mol_m2': so2_mol_m2,
        'no2_ug_m3': round(no2_ug, 2),
        'so2_ug_m3': round(so2_ug, 2),
        'no2_x_who': round(no2_ug / WHO['no2_annual'], 1),
        'so2_x_who': round(so2_ug / WHO['so2_daily'], 1),
        'no2_status': 'Within WHO limits' if no2_ug <= WHO['no2_annual'] else 'Above WHO limit',
        'so2_status': 'Within WHO limits' if so2_ug <= WHO['so2_daily'] else 'Above WHO limit',
    }
