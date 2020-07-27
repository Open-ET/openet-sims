import ee
import pytest
import pandas as pd
import numpy as np

import openet.sims as sims
import openet.sims.utils as utils

ee.Initialize()

COLLECTIONS = ['LANDSAT/LC08/C01/T1_SR', 'LANDSAT/LE07/C01/T1_SR']
VARIABLES = {'et', 'et_fraction', 'et_reference'}

et_palette = [
        'DEC29B', 'E6CDA1', 'EDD9A6', 'F5E4A9', 'FFF4AD', 'C3E683', '6BCC5C', 
        '3BB369', '20998F', '1C8691', '16678A', '114982', '0B2C7A']

et_reference_source = 'projects/climate-engine/cimis/daily'
et_reference_band = 'ETo'
et_reference_factor = 1.0

start_date = '2017-01-01'
end_date = '2017-01-21'

def get_point_ts(test_xy):
    test_point = ee.Geometry.Point(test_xy)
    model_obj = sims.Collection(
        collections=COLLECTIONS,
        et_reference_source=et_reference_source,
        et_reference_band=et_reference_band,
        et_reference_factor=et_reference_factor,
        start_date=start_date,
        end_date=end_date,
        geometry=test_point,
        cloud_cover_max=70,
        # filter_args={},
    )
    
    wb = model_obj.run_water_balance(
        variables=['et', 'et_reference', 'et_fraction'],
        bare_soil=True
    )
    
    wb = ee.List(wb)
    ls = ee.List([{'duh': 0}])
    
    def get_point_values(img, ls):
        img = ee.Image(img)
        ls = ee.List(ls)
        vals = utils.point_image_value(img, test_xy, get_info=False)
        return ls.add(vals)
    
    wb = wb.remove(wb.get(0))
    wb_bands = wb.map(lambda x: ee.Image(x).select('pr', 'et_reference', 'etc'))
    
    point_values = wb_bands.iterate(get_point_values, ls)
    point_values = ee.List(point_values)
    point_values = point_values.remove(point_values.get(0))
    return point_values


def print_params_for_spreadsheet(test_xy):
    z_e = .1
    
    wilting_point = ee.Image('users/dohertyconor/Wp_p44_r33_clip')
    print('wp: ' + str(utils.point_image_value(wilting_point, test_xy)))
    
    field_capacity = ee.Image('users/dohertyconor/Fc_p44_r33_clip')
    print('fc: ' + str(utils.point_image_value(field_capacity, test_xy)))
    
    awc = field_capacity.subtract(wilting_point)
    
    tew = field_capacity.expression(
        '1000*(b()-0.5*wp)*z_e',
        {'wp': wilting_point, 'z_e': z_e}
    )
    print('tew: ' + str(utils.point_image_value(tew, test_xy)))
    
    # Readily evaporable water (mm)
    rew = awc.expression('0.8+54.4*b()')
    rew = rew.where(rew.gt(tew), tew)
    print('rew: ' + str(utils.point_image_value(rew, test_xy)))


def make_point_df(point_coll):
    point_info = point_coll.getInfo()
    df = pd.DataFrame(columns=point_info[0].keys())
    df = df.append(point_info, ignore_index=True)
    return df


test_pts = [
    ([-121.5265, 38.7399],
        np.array([0.83, 0.93, 0.58, 0.69, 1.01, 0.97, 0.42, 1.02, 1.24, 0.82, 1.1,
            0.54, 1.57, 0.89, 0.65, 0.73, 0.64, 0.88, 1.28, 1.45])),
    ([-122.0433, 39.0317],
        np.array([0.67, 0.98, 0.49, 0.7 , 1.29, 0.97, 0.38, 0.75, 1.14, 0.88, 1.18,
            0.65, 1.94, 0.97, 0.72, 0.79, 0.52, 0.56, 1.21, 1.22]))]

def test_etc():
    """
    Check water balance time series point values. Validation data come from
    putting precip, eto, wp, fc into Rick Allen's metric water balance spreadsheet.
    """
    for pt, etc_valid in test_pts:
        print(pt)
        point_ts = get_point_ts(pt)
        df = make_point_df(point_ts)
        etc_diff = (df.etc - etc_valid).to_numpy()

        assert np.linalg.norm(etc_diff) < .001*etc_diff.size
