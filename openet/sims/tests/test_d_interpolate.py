import pprint

import ee
import pytest

import openet.sims.interpolate as interpolate
import openet.sims.utils as utils
from openet.sims.image import Image


def scene_coll(variables, et_fraction=0.4, et=5, ndvi=0.6):
    """Return a generic scene collection to test scene interpolation functions

    Parameters
    ----------
    variables : list
        The variables to return in the collection
    et_fraction : float
    et : float
    ndvi : float

    Returns
    -------
    ee.ImageCollection

    """
    img = ee.Image('LANDSAT/LC08/C01/T1_SR/LC08_044033_20170716') \
        .select(['B2']).double().multiply(0)
    mask = img.add(1).updateMask(1).uint8()

    time1 = ee.Number(ee.Date.fromYMD(2017, 7, 8).millis())
    time2 = ee.Number(ee.Date.fromYMD(2017, 7, 16).millis())
    time3 = ee.Number(ee.Date.fromYMD(2017, 7, 24).millis())

    # Mask and time bands currently get added on to the scene collection
    #   and images are unscaled just before interpolating in the export tool
    scene_img = ee.Image([img.add(et_fraction), img.add(et), img.add(ndvi), mask])\
        .rename(['et_fraction', 'et', 'ndvi', 'mask'])
    scene_coll = ee.ImageCollection([
        scene_img.addBands([img.add(time1).rename('time')]) \
            .set({'system:index': 'LE07_044033_20170708',
                  'system:time_start': time1}),
        scene_img.addBands([img.add(time2).rename('time')]) \
            .set({'system:index': 'LC08_044033_20170716',
                  'system:time_start': time2}),
        scene_img.addBands([img.add(time3).rename('time')]) \
            .set({'system:index': 'LE07_044033_20170724',
                  'system:time_start': time3}),
    ])
    return scene_coll.select(variables)


def test_from_scene_et_fraction_daily_values(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi', 'time', 'mask']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi'],
        interp_args={'interp_method': 'linear', 'interp_days': 32,},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily')

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=10)
    assert abs(output['ndvi']['2017-07-10'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-10'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-10'] - 8.0) <= tol
    assert abs(output['et']['2017-07-10'] - (8.0 * 0.4)) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_fraction']['2017-07-31'] - 0.4) <= tol
    assert '2017-08-01' not in output['et_fraction'].keys()
    # assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_monthly_values(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi', 'time', 'mask']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='monthly')

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=10)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 232.3) <= tol
    assert abs(output['et']['2017-07-01'] - (232.3 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_custom_values(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi', 'time', 'mask']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='custom')

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=10)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 232.3) <= tol
    assert abs(output['et']['2017-07-01'] - (232.3 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_monthly_et_reference_factor(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi', 'time', 'mask']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 0.5,
                    'et_reference_resample': 'nearest'},
        t_interval='monthly')

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=10)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 232.3 * 0.5) <= tol
    assert abs(output['et']['2017-07-01'] - (232.3 * 0.5 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


# CGM - Resampling is not being applied so this should be equal to nearest
def test_from_scene_et_fraction_monthly_et_reference_resample(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi', 'time', 'mask']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'bilinear'},
        t_interval='monthly')

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=10)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 232.3) <= tol
    assert abs(output['et']['2017-07-01'] - (232.3 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3

def test_water_balance(tol=0.0001):
    TEST_POINT = (-121.5265, 38.7399)
    et_reference_source = 'projects/climate-engine/cimis/daily'
    et_reference_band = 'ETo'
    start_date = '2018-03-01'
    end_date = '2018-04-01'

    ls8 = ee.ImageCollection('LANDSAT/LC08/C01/T1_SR')\
            .filterDate(start_date, end_date)\
            .filterBounds(ee.Geometry.Point(TEST_POINT))

    ls7 = ee.ImageCollection('LANDSAT/LE07/C01/T1_SR')\
            .filterDate(start_date, end_date)\
            .filterBounds(ee.Geometry.Point(TEST_POINT))

    ls = ls7.merge(ls8)

    zero = ls.first().select(['B2']).double().multiply(0)


    def make_et_frac(img):
        et_img = Image.from_landsat_c1_sr(img,
                    et_reference_source=et_reference_source, 
                    et_reference_band=et_reference_band)\
                .calculate(['ndvi', 'et_reference', 'et_fraction', 'et'])
        time = ee.Number(img.get('system:time_start'))
        et_img = et_img.addBands([zero.add(time).rename('time')])
        return et_img

    test_imgs = ls.map(make_et_frac)
    normal_coll = interpolate.from_scene_et_fraction(
        test_imgs,
        start_date=start_date,
        end_date=end_date,
        variables=['et_reference', 'et_fraction', 'et'],
        interp_args={'interp_method': 'linear', 'interp_days': 14},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily')

    wb_coll = interpolate.from_scene_et_fraction(
        test_imgs,
        start_date=start_date,
        end_date=end_date,
        variables=['et_reference', 'et_fraction', 'ke', 'et'],
        interp_args={'interp_method': 'linear', 'interp_days': 14,
                     'water_balance': True},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily')

    normal = utils.point_coll_value(normal_coll, TEST_POINT, scale=30)
    wb = utils.point_coll_value(wb_coll, TEST_POINT, scale=30)

    for date in normal['et'].keys():
        assert wb['et'][date] >= normal['et'][date]
