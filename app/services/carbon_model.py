"""
Blue Carbon sequestration model for mangrove areas.
Methodology: IPCC Wetlands Supplement 2013, Donato et al. 2011.
"""

# Blue Carbon stocks (tC/ha) - IPCC Wetlands Supplement 2013 Table 4.2
_STOCKS = {
    'biomass_above': 70,    # above-ground biomass, Southeast Asia average
    'biomass_below': 23,    # below-ground (~33% of above)
    'soil_organic': 392,    # soil organic carbon, top 1 m
}

_SEQ_RATE_TC_HA_YR = 6.3    # tC/ha/year, Donato et al. 2011 (conservative)
_CO2_PER_TC = 3.67           # tCO2e per tC
_TREE_DENSITY_HA = 2500      # trees/ha, dense plantation average
_TREE_COST_INR = 10.0        # rough cost per sapling


def estimate_carbon(area_km2: float, years: int = 1) -> dict:
    area_ha = area_km2 * 100
    annual_tc = _SEQ_RATE_TC_HA_YR * area_ha
    annual_tco2 = annual_tc * _CO2_PER_TC
    total_stock_tc = sum(_STOCKS.values()) * area_ha
    return {
        'area_km2': area_km2,
        'area_ha': round(area_ha, 1),
        'annual_seq_tc': round(annual_tc, 1),
        'annual_seq_tco2': round(annual_tco2, 1),
        'cumulative_seq_tco2': round(annual_tco2 * years, 1),
        'total_stock_tc': round(total_stock_tc, 0),
        'total_stock_tco2': round(total_stock_tc * _CO2_PER_TC, 0),
        'above_stock_tc': round(_STOCKS['biomass_above'] * area_ha, 0),
        'soil_stock_tc': round(_STOCKS['soil_organic'] * area_ha, 0),
        'estimated_trees': int(area_ha * _TREE_DENSITY_HA),
        'seq_rate_tco2_ha_yr': round(_SEQ_RATE_TC_HA_YR * _CO2_PER_TC, 1),
        'years': years,
        'methodology': 'IPCC Wetlands Supplement 2013 / Donato et al. 2011',
    }


def trees_to_carbon(tree_count: int, years: int = 1) -> dict:
    area_ha = tree_count / _TREE_DENSITY_HA
    return estimate_carbon(area_ha / 100, years=years)


def donation_to_carbon(amount_inr: float) -> dict:
    trees = int(amount_inr / _TREE_COST_INR)
    result = trees_to_carbon(trees)
    result['donation_inr'] = amount_inr
    result['cost_per_tree_inr'] = _TREE_COST_INR
    return result
