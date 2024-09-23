import datetime
# import logging
import pprint

import ee
import pytest

import openet.sims as sims
import openet.sims.utils as utils
# TODO: import utils from openet.core
# import openet.core.utils as utils


COLL_ID = 'LANDSAT/LC08/C02/T1_L2/'
SCENE_ID = 'LC08_044033_20170716'
SCENE_DT = datetime.datetime.strptime(SCENE_ID[-8:], '%Y%m%d')
SCENE_DATE = SCENE_DT.strftime('%Y-%m-%d')
SCENE_DOY = int(SCENE_DT.strftime('%j'))
SCENE_TIME = utils.millis(SCENE_DT)
# SCENE_TIME = utils.getinfo(ee.Date(SCENE_DATE).millis())


# Should these be test fixtures instead?
# I'm not sure how to make them fixtures and allow input parameters
def input_image(red=0.1, nir=0.9):
    """Construct a fake input image with renamed bands"""
    return ee.Image.constant([red, nir]).rename(['red', 'nir'])\
        .set({'system:time_start': ee.Date(SCENE_DATE).millis()})


def default_image(ndvi=0.8):
    return ee.Image.constant([ndvi]).rename(['ndvi'])\
        .set({
            'system:index': SCENE_ID,
            'system:time_start': ee.Date(SCENE_DATE).millis(),
            'system:id': COLL_ID + SCENE_ID,
        })


# Setting et_reference_source and et_reference_band on the default image to
# simplify testing but these do not have defaults in the Image class init
def default_image_args(ndvi=0.8,
                       et_reference_source='IDAHO_EPSCOR/GRIDMET',
                       et_reference_band='etr',
                       et_reference_factor=0.85,
                       et_reference_resample='nearest',
                       crop_type_source='USDA/NASS/CDL',
                       crop_type_remap='CDL',
                       crop_type_kc_flag=False,
                       crop_type_annual_skip_flag=False,
                       mask_non_ag_flag=False,
                       water_kc_flag=True,
                       # reflectance_type='SR',
                       ):
    return {
        'image': default_image(ndvi=ndvi),
        'et_reference_source': et_reference_source,
        'et_reference_band': et_reference_band,
        'et_reference_factor': et_reference_factor,
        'et_reference_resample': et_reference_resample,
        'crop_type_source': crop_type_source,
        'crop_type_remap': crop_type_remap,
        'crop_type_kc_flag': crop_type_kc_flag,
        'crop_type_annual_skip_flag': crop_type_annual_skip_flag,
        'mask_non_ag_flag': mask_non_ag_flag,
        'water_kc_flag': water_kc_flag,
        # 'reflectance_type': reflectance_type,
    }


def default_image_obj(ndvi=0.8,
                      et_reference_source='IDAHO_EPSCOR/GRIDMET',
                      et_reference_band='etr',
                      et_reference_factor=0.85,
                      et_reference_resample='nearest',
                      crop_type_source='USDA/NASS/CDL',
                      crop_type_remap='CDL',
                      crop_type_kc_flag=False,
                      crop_type_annual_skip_flag=False,
                      mask_non_ag_flag=False,
                      water_kc_flag=True,
                      # reflectance_type='SR',
                      ):
    return sims.Image(**default_image_args(
        ndvi=ndvi,
        et_reference_source=et_reference_source,
        et_reference_band=et_reference_band,
        et_reference_factor=et_reference_factor,
        et_reference_resample=et_reference_resample,
        crop_type_source=crop_type_source,
        crop_type_remap=crop_type_remap,
        crop_type_kc_flag=crop_type_kc_flag,
        crop_type_annual_skip_flag=crop_type_annual_skip_flag,
        mask_non_ag_flag=mask_non_ag_flag,
        water_kc_flag=water_kc_flag,
        # reflectance_type=reflectance_type,
    ))


def test_Image_init_default_parameters():
    m = sims.Image(image=default_image())
    assert m.et_reference_source == None
    assert m.et_reference_band == None
    assert m.et_reference_factor == None
    assert m.et_reference_resample == None
    # assert m.crop_type_source == 'USDA/NASS/CDL'
    # assert m.crop_type_remap == 'CDL'
    # assert m.crop_type_kc_flag == False
    # assert m.crop_type_annual_skip_flag == False
    # assert m.mask_non_ag_flag == False
    assert m.reflectance_type == 'SR'


def test_Image_init_calculated_properties():
    m = default_image_obj()
    assert utils.getinfo(m._time_start) == SCENE_TIME
    assert utils.getinfo(m._index) == SCENE_ID


def test_Image_init_date_properties():
    m = default_image_obj()
    assert utils.getinfo(m._date)['value'] == SCENE_TIME
    assert utils.getinfo(m._year) == int(SCENE_DATE.split('-')[0])
    assert utils.getinfo(m._start_date)['value'] == SCENE_TIME
    assert utils.getinfo(m._end_date)['value'] == utils.millis(
        SCENE_DT + datetime.timedelta(days=1))


@pytest.mark.parametrize(
    'red, nir, expected',
    [
        [0.2, 9.0 / 55, -0.1],
        [0.2, 0.2,  0.0],
        [0.1, 11.0 / 90,  0.1],
        [0.2, 0.3, 0.2],
        [0.1, 13.0 / 70, 0.3],
        [0.3, 0.7, 0.4],
        [0.2, 0.6, 0.5],
        [0.2, 0.8, 0.6],
        [0.1, 17.0 / 30, 0.7],
        [0.1, 0.9, 0.8],
    ]
)
def test_Image_static_ndvi_calculation(red, nir, expected, tol=0.000001):
    output = utils.constant_image_value(
        sims.Image._ndvi(input_image(red=red, nir=nir)))
    assert abs(output['ndvi'] - expected) <= tol


def test_Image_static_ndvi_band_name():
    output = utils.getinfo(sims.Image._ndvi(input_image()))
    assert output['bands'][0]['id'] == 'ndvi'


def test_Image_ndvi_properties():
    """Test if properties are set on the ndvi image"""
    output = utils.getinfo(default_image_obj().ndvi)
    assert output['bands'][0]['id'] == 'ndvi'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_ndvi_constant_value(ndvi=0.8, expected=0.8, tol=0.0001):
    output = utils.constant_image_value(default_image_obj(ndvi=ndvi).ndvi)
    assert abs(output['ndvi'] - expected) <= tol


def test_Image_fc_properties():
    """Test if properties are set on the fc image"""
    output = utils.getinfo(default_image_obj().fc)
    assert output['bands'][0]['id'] == 'fc'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_crop_type_properties():
    """Test if properties are set on the crop type image"""
    output = utils.getinfo(default_image_obj().crop_type)
    assert output['bands'][0]['id'] == 'crop_type'
    # assert output['properties']['system:index'] == SCENE_ID
    # assert output['properties']['system:time_start'] == SCENE_TIME
    # assert output['properties']['image_id'] == COLL_ID + SCENE_ID


@pytest.mark.parametrize(
    'crop_type_source, xy, expected',
    [
        # Test spots around the Five Points CIMIS station
        ['USDA/NASS/CDL/2016', [-120.1130, 36.3360], 36],
        ['USDA/NASS/CDL/2016', [-120.1073, 36.3309], 69],
        ['USDA/NASS/CDL/2016', [-120.1080, 36.3459], 204],
        # Test a spot that has different CDL values through time
        ['USDA/NASS/CDL/2016', [-120.5953, 36.8721], 209],
        ['USDA/NASS/CDL/2017', [-120.5953, 36.8721], 24],
        ['USDA/NASS/CDL/2018', [-120.5953, 36.8721], 213],
        # Default image year is 2017 so value should match 2017 CDL
        ['USDA/NASS/CDL', [-120.5953, 36.8721], 24],
        ['projects/openet/crop_type/annual_provisional', [-120.125, 36.3893], 47],
    ]
)
def test_Image_crop_type_point_value(crop_type_source, xy, expected):
    output = utils.point_image_value(default_image_obj(
        crop_type_source=crop_type_source).crop_type, xy)
    assert output['crop_type'] == expected


def test_Image_crop_class_properties():
    """Test if properties are set on the crop type image"""
    output = utils.getinfo(default_image_obj().crop_class)
    assert output['bands'][0]['id'] == 'crop_class'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


@pytest.mark.parametrize(
    'xy, expected',
    [
        # Test spots around the Five Points CIMIS station
        [[-120.113, 36.336], 1],
        [[-120.1073, 36.3309], 2],
        [[-120.108, 36.3459], 3],
    ]
)
def test_Image_crop_class_point_value(xy, expected):
    output = utils.point_image_value(default_image_obj(
        crop_type_source='USDA/NASS/CDL/2016').crop_class, xy)
    assert output['crop_class'] == expected


def test_Image_kc_properties():
    """Test if properties are set on the kc image"""
    output = utils.getinfo(default_image_obj().kc)
    assert output['bands'][0]['id'] == 'kc'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_et_fraction_properties():
    """Test if properties are set on the ET fraction image"""
    output = utils.getinfo(default_image_obj().et_fraction)
    assert output['bands'][0]['id'] == 'et_fraction'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_et_fraction_constant_value():
    # ET fraction method returns Kc
    output = utils.constant_image_value(default_image_obj(
        ndvi=0.8, crop_type_source=1).et_fraction)
    assert abs(output['et_fraction'] - 0.9859994736) <= 0.0001


def test_Image_et_reference_constant_value(et_reference=10.0, tol=0.0001):
    output = utils.constant_image_value(default_image_obj(
        et_reference_source=et_reference,
        et_reference_factor=0.85).et_reference)
    assert abs(output['et_reference'] - et_reference * 0.85) <= tol


def test_Image_et_reference_properties():
    """Test if properties are set on the reference ET image"""
    output = utils.getinfo(default_image_obj().et_reference)
    assert output['bands'][0]['id'] == 'et_reference'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_et_reference_source_exception():
    """Test that an Exception is raise for an invalid image ID"""
    with pytest.raises(Exception):
        utils.getinfo(default_image_obj(et_reference_source=None).et_reference)


# CGM - I'm not sure why this is commented out
# def test_Image_et_reference_band_exception():
#     """Test that an Exception is raise for an invalid et_reference band name"""
#     with pytest.raises(Exception):
#         utils.getinfo(default_image_obj(et_reference_band=None).et_reference)


def test_Image_et_properties():
    """Test if properties are set on the ET image"""
    output = utils.getinfo(default_image_obj().et)
    assert output['bands'][0]['id'] == 'et'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_et_constant_value():
    output = utils.constant_image_value(default_image_obj(
        et_reference_source=10, et_reference_factor=1.0, crop_type_source=1).et)
    assert abs(output['et'] - 10 * 0.986) <= 0.0001


def test_Image_mask_properties():
    """Test if properties are set on the time image"""
    output = utils.getinfo(default_image_obj().mask)
    assert output['bands'][0]['id'] == 'mask'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_mask_constant_value():
    output = utils.constant_image_value(default_image_obj(
        crop_type_source=1).mask)
    assert output['mask'] == 1


def test_Image_time_properties():
    """Test if properties are set on the time image"""
    output = utils.getinfo(default_image_obj().time)
    assert output['bands'][0]['id'] == 'time'
    assert output['properties']['system:index'] == SCENE_ID
    assert output['properties']['system:time_start'] == SCENE_TIME
    assert output['properties']['image_id'] == COLL_ID + SCENE_ID


def test_Image_time_constant_value():
    output = utils.constant_image_value(default_image_obj(
        crop_type_source=1).time)
    assert output['time'] == SCENE_TIME


def test_Image_calculate_variables_default():
    output = utils.getinfo(default_image_obj().calculate())
    assert set([x['id'] for x in output['bands']]) == set(['et'])


def test_Image_calculate_variables_custom():
    variables = ['ndvi']
    output = utils.getinfo(default_image_obj().calculate(variables))
    assert set([x['id'] for x in output['bands']]) == set(variables)


def test_Image_calculate_variables_all():
    variables = ['et', 'et_fraction', 'et_reference', 'fc', 'kc', 'mask',
                 'ndvi', 'time']
    output = utils.getinfo(default_image_obj().calculate(variables=variables))
    assert set([x['id'] for x in output['bands']]) == set(variables)


def test_Image_from_landsat_c2_sr_default_image():
    """Test that the classmethod is returning a class object"""
    output = sims.Image.from_landsat_c2_sr(input_image())
    assert type(output) == type(default_image_obj())


@pytest.mark.parametrize(
    'image_id',
    [
        # 'LANDSAT/LT04/C02/T1_L2/LT04_044033_19830812',
        'LANDSAT/LT05/C02/T1_L2/LT05_044033_20110716',
        'LANDSAT/LE07/C02/T1_L2/LE07_044033_20170708',
        'LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716',
        'LANDSAT/LC09/C02/T1_L2/LC09_044033_20220127',
    ]
)
def test_Image_from_landsat_c2_sr_image_id(image_id):
    """Test instantiating the class from a Landsat image ID"""
    output = utils.getinfo(sims.Image.from_landsat_c2_sr(image_id).ndvi)
    assert output['properties']['system:index'] == image_id.split('/')[-1]


def test_Image_from_landsat_c2_sr_image():
    """Test instantiating the class from a Landsat ee.Image"""
    image_id = 'LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716'
    output = utils.getinfo(sims.Image.from_landsat_c2_sr(
        ee.Image(image_id)).ndvi)
    assert output['properties']['system:index'] == image_id.split('/')[-1]


def test_Image_from_landsat_c2_sr_kc():
    """Test if ET fraction can be built from a Landsat images"""
    image_id = 'LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716'
    output = utils.getinfo(sims.Image.from_landsat_c2_sr(image_id).kc)
    assert output['properties']['system:index'] == image_id.split('/')[-1]


def test_Image_from_landsat_c2_sr_et():
    """Test if ET can be built from a Landsat images"""
    image_id = 'LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716'
    output = utils.getinfo(sims.Image.from_landsat_c2_sr(
        image_id, et_reference_source='IDAHO_EPSCOR/GRIDMET',
        et_reference_band='etr').et)
    assert output['properties']['system:index'] == image_id.split('/')[-1]


def test_Image_from_landsat_c2_sr_exception():
    """Test that an Exception is raise for an invalid image ID"""
    with pytest.raises(Exception):
        utils.getinfo(sims.Image.from_landsat_c2_sr(ee.Image('FOO')).ndvi)


def test_Image_from_landsat_c2_sr_scaling():
    """Test if Landsat SR images images are being scaled"""
    sr_img = ee.Image('LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716')
    # CGM - These reflectances should correspond to 0.1 for RED and 0.2 for NIR
    input_img = ee.Image.constant([10909, 10909, 10909, 14545, 10909, 10909,
                                   44177.6, 21824, 0]) \
        .rename(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7',
                 'ST_B10', 'QA_PIXEL', 'QA_RADSAT']) \
        .set({'SPACECRAFT_ID': ee.String(sr_img.get('SPACECRAFT_ID')),
              'system:id': ee.String(sr_img.get('system:id')),
              'system:index': ee.String(sr_img.get('system:index')),
              'system:time_start': ee.Number(sr_img.get('system:time_start'))})

    output = utils.constant_image_value(
        sims.Image.from_landsat_c2_sr(input_img).ndvi)
    assert abs(output['ndvi'] - 0.333) <= 0.01


def test_Image_from_landsat_c2_sr_reflectance_type():
    """Test if reflectance_type property is being set"""
    image_id = 'LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716'
    assert sims.Image.from_landsat_c2_sr(image_id).reflectance_type == 'SR'


def test_Image_from_landsat_c2_sr_cloud_mask_args():
    """Test if the cloud_mask_args parameter can be set (not if it works)"""
    image_id = 'LANDSAT/LC08/C02/T1_L2/LC08_038031_20130828'
    output = sims.Image.from_landsat_c2_sr(
        image_id, cloudmask_args={'snow_flag': True, 'cirrus_flag': True})
    assert type(output) == type(default_image_obj())


@pytest.mark.parametrize(
    'image_id',
    [
        'LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716',
    ]
)
def test_Image_from_image_id(image_id):
    """Test instantiating the class using the from_image_id method"""
    output = utils.getinfo(sims.Image.from_image_id(image_id).ndvi)
    assert output['properties']['system:index'] == image_id.split('/')[-1]
    assert output['properties']['image_id'] == image_id


def test_Image_from_method_kwargs():
    """Test that the init parameters can be passed through the helper methods"""
    assert sims.Image.from_landsat_c1_sr(
        'LANDSAT/LC08/C02/T1_L2/LC08_042035_20150713',
        et_reference_band='FOO').et_reference_band == 'FOO'
