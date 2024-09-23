import pprint

import ee
import pytest

import openet.sims.data as data
import openet.sims.model as model
import openet.sims.utils as utils

# DATE = '2017-07-16'
YEAR = 2017
DOY = 197


# CGM - Should these be test fixtures instead?
#   I'm not sure how to make them fixtures and allow input parameters
# CGM - Setting default crop_type_source to 2017 image to simplify testing
#   but the default in the Model class init is the full collection
def default_model_args(year=YEAR, doy=DOY, crop_type_remap='CDL',
                       crop_type_source=f'USDA/NASS/CDL/{YEAR}',
                       crop_type_kc_flag=False,
                       crop_type_annual_skip_flag=False,
                       mask_non_ag_flag=False,
                       water_kc_flag=True,
                       reflectance_type='SR',
                       ):
    return {
        'year': year, 'doy': doy,
        'crop_type_source': crop_type_source,
        'crop_type_remap': crop_type_remap,
        'crop_type_kc_flag': crop_type_kc_flag,
        'crop_type_annual_skip_flag': crop_type_annual_skip_flag,
        'mask_non_ag_flag': mask_non_ag_flag,
        'water_kc_flag': water_kc_flag,
        'reflectance_type': reflectance_type,
    }


def default_model_obj(year=YEAR, doy=DOY, crop_type_remap='CDL',
                      crop_type_source=f'USDA/NASS/CDL/{YEAR}',
                      crop_type_kc_flag=False,
                      crop_type_annual_skip_flag=False,
                      mask_non_ag_flag=False,
                      water_kc_flag=True,
                      reflectance_type='SR',
                      ):
    return model.Model(**default_model_args(
        year=ee.Number(year), doy=ee.Number(doy),
        crop_type_source=crop_type_source,
        crop_type_remap=crop_type_remap,
        crop_type_kc_flag=crop_type_kc_flag,
        crop_type_annual_skip_flag=crop_type_annual_skip_flag,
        mask_non_ag_flag=mask_non_ag_flag,
        water_kc_flag=water_kc_flag,
        reflectance_type=reflectance_type,
    ))


def test_crop_data_image():
    output = utils.constant_image_value(model.crop_data_image(
        param_name='crop_class',
        crop_type=ee.Image.constant(9).rename(['crop_class']),
        crop_data={9: {'crop_class': 10}}))
    assert output['crop_class'] == 10


def test_crop_data_image_int_scalar():
    # Test that floating point values are scaled to int before remapping
    output = utils.constant_image_value(model.crop_data_image(
        param_name='m_l', crop_type=ee.Image.constant(9).rename(['m_l']),
        crop_data={9: {'m_l': 0.01}}))
    assert output['m_l'] == 0.01


def test_crop_data_image_default_value():
    output = utils.constant_image_value(model.crop_data_image(
        param_name='crop_class',
        crop_type=ee.Image.constant(-999).rename(['crop_class']),
        crop_data={9: {'crop_class': 10}},
        default_value=100))
    assert output['crop_class'] == 100


def test_crop_data_image_default_nodata():
    output = utils.constant_image_value(model.crop_data_image(
        param_name='crop_class',
        crop_type=ee.Image.constant(-999).rename(['crop_class']),
        crop_data={9: {'crop_class': 10}}))
    assert output['crop_class'] == None


def test_Model_init_default_parameters():
    m = default_model_obj()
    assert m.crop_type_source == f'USDA/NASS/CDL/{YEAR}'
    assert m.crop_type_remap == 'CDL'
    assert m.reflectance_type == 'SR'


@pytest.mark.parametrize(
    'parameter', ['m_l', 'h_max', 'fr_mid', 'fr_end', 'ls_start', 'ls_stop'])
def test_Model_init_crop_data_images(parameter):
    output = utils.getinfo(getattr(default_model_obj(), parameter))
    assert output['bands'][0]['id'] == parameter


@pytest.mark.parametrize(
    'year, expected',
    [
        [2007, 2008],
        [2008, 2008],
        [2016, 2016],
        [2019, 2019],
        [2020, 2020],
        [2021, 2021],
        [2022, 2022],
        [2023, 2023],
        [2024, 2023],
    ]
)
def test_Model_crop_type_source_cdl_collection(year, expected):
    """Test that the CDL collection is filtered to a single year and is limited
    to years with data (2008-2021 as of 3/25/2021)
    """
    output = utils.getinfo(default_model_obj(
        crop_type_source='USDA/NASS/CDL', year=ee.Number(year)).crop_type)
    assert output['properties']['id'] == f'USDA/NASS/CDL/{expected}'


def test_Model_crop_type_source_cdl_image():
    output = utils.getinfo(default_model_obj(
        crop_type_source='USDA/NASS/CDL/2008').crop_type)
    assert output['properties']['id'] == 'USDA/NASS/CDL/2008'


def test_Model_crop_type_source_cdl_image_exception():
    """Requesting a CDL image that doesn't exist should raise an EE exception"""
    with pytest.raises(Exception):
        utils.getinfo(default_model_obj(crop_type_source='USDA/NASS/CDL/2099'))
        # CGM - The exception is raised in the _crop_type() method which is
        #   in the init.  If crop_type is a lazy property then it is necessary
        #   to request the property in order to raise the exception.
        # utils.getinfo(default_model_obj(
        #     crop_type_source='USDA/NASS/CDL/2099').crop_type)


@pytest.mark.parametrize(
    'crop_type_source',
    [
        'projects/openet/crop_type/v2021a',
        'projects/earthengine-legacy/assets/projects/openet/crop_type/v2021a',
    ]
)
def test_Model_crop_type_source_openet_crop_type(crop_type_source):
    output = utils.getinfo(default_model_obj(
        crop_type_source=crop_type_source).crop_type)
    expected = crop_type_source.replace('projects/earthengine-legacy/assets/', '')
    assert output['properties']['id'] == expected


def test_Model_crop_type_source_exception():
    with pytest.raises(ValueError):
        utils.getinfo(default_model_obj(crop_type_source='FOO'))
        # utils.getinfo(default_model_obj(crop_type_source='FOO').crop_type)


def test_Model_crop_type_constant_value():
    output = utils.constant_image_value(default_model_obj(
        crop_type_source=10).crop_type)
    assert output['crop_type'] == 10


def test_Model_crop_data_dictionary():
    assert default_model_obj(crop_type_remap='CDL').crop_data


def test_Model_crop_data_remap_exception():
    with pytest.raises(ValueError):
        utils.getinfo(default_model_obj(crop_type_remap='FOO'))
        # utils.getinfo(default_model_obj(crop_type_remap='FOO').crop_data)


@pytest.mark.parametrize('crop_type, parameter', [[1, 'h_max'], [1, 'm_l']])
def test_Model_crop_data_image(crop_type, parameter):
    output = utils.constant_image_value(getattr(
        default_model_obj(crop_type_source=crop_type), parameter))
    assert output[parameter] == data.cdl[crop_type][parameter]


@pytest.mark.parametrize(
    'crop_type, expected',
    [
        [1, 1],
        [69, 2],
        [66, 3],
        [3, 5],    # Rice was switched to class 5 instead of 1
        [61, 6],   # Fallow was switched to class 6 instead of 1
        [176, 7],  # Grass/pasture was switched to class 7 instead of 1
    ]
)
def test_Model_crop_class_constant_value(crop_type, expected):
    output = utils.constant_image_value(default_model_obj(
        crop_type_source=crop_type,
        crop_type_remap='CDL').crop_class)
    assert output['crop_class'] == expected


@pytest.mark.parametrize(
    'ndvi, expected',
    [
        [-0.2, 0.0],  # Clamped
        [-0.1, 0.0],  # Clamped
        [0.0, 0.0],   # Clamped
        [0.1, 0.0],   # Clamped
        [0.2, 0.072],
        [0.5, 0.45],
        [0.7, 0.702],
        [0.8, 0.828],
        [0.95, 1.0],  # Clamped
    ]
)
def test_Model_fc_reflectance_type_sr(ndvi, expected, tol=0.0001):
    m = default_model_obj(reflectance_type='SR')
    output = utils.constant_image_value(m.fc(ndvi=ee.Image.constant(ndvi)))
    assert abs(output['fc'] - expected) <= tol


@pytest.mark.parametrize(
    'ndvi, expected',
    [
        [-0.2, 0.0],   # Clamped
        [-0.1, 0.0],   # Clamped
        [0.0, 0.0],    # Clamped
        [0.1, 0.0075],
        [0.14, 0.0661],   # Break value in rice Kc
        [0.2, 0.154],
        [0.35, 0.37375],  # Break value in fallow Kc
        [0.5, 0.5935],
        [0.7, 0.8865],
        [0.778, 1.0],  # Clamped
        [0.95, 1.0],   # Clamped
    ]
)
def test_Model_fc_reflectance_type_toa(ndvi, expected, tol=0.0001):
    m = default_model_obj(reflectance_type='TOA')
    output = utils.constant_image_value(m.fc(ndvi=ee.Image.constant(ndvi)))
    assert abs(output['fc'] - expected) <= tol


def test_Model_fc_reflectance_type_exception():
    with pytest.raises(Exception):
        utils.getinfo(default_model_obj(reflectance_type='FOO').fc(
            ndvi=ee.Image.constant(0.2)))


@pytest.mark.parametrize(
    'ndvi, expected',
    [
        [-0.2, 0.0],  # -0.05 without >= 0 clamping
        [-0.1, 0.075],
        [0.0, 0.2],
        [0.2, 0.45],
        [0.5, 0.825],
        [0.7, 1.075],
        [0.8, 1.2],
    ]
)
def test_Model_kc_generic_constant_value(ndvi, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=1, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc_generic(ndvi=ee.Image.constant(ndvi)))
    assert abs(output['kc'] - expected) <= tol


@pytest.mark.parametrize(
    'fc, expected',
    [
        [0.0, 0.15],
        [0.8, 0.9684],
    ]
)
def test_Model_kc_row_crop_constant_value(fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=1, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc_row_crop(fc=ee.Image.constant(fc)))
    assert abs(output['kc'] - expected) <= tol


def test_Model_kc_tree_constant_value(fc=0.8, expected=0.8*1.48+0.007,
                                      tol=0.0001):
    m = default_model_obj(crop_type_source=66, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc_tree(fc=ee.Image.constant(fc)))
    assert abs(output['kc'] - expected) <= tol


@pytest.mark.parametrize(
    'ndvi, fc, expected',
    [
        [-0.1, 0.0, 1.05],
        [0.14, 0.0661, 1.05],
        # An NDVI in the range [0.14, 0.142857] will be clamped to 0 in fc(),
        # but is above the 0.14 threshold in kc() so it is not set to 1.05.
        [0.142, 0, 0.15],
        [0.143, 0.00018, 0.1503],
        [0.5, 0.45, 0.6855],
        [0.8, 0.828, 0.9860],
    ]
)
def test_Model_kc_rice_constant_value(ndvi, fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=3, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc_rice(
        fc=ee.Image.constant(fc), ndvi=ee.Image.constant(ndvi)))
    assert abs(output['kc'] - expected) <= tol


@pytest.mark.parametrize(
    'ndvi, fc, expected',
    [
        [-0.1, 0.0, 0.01],
        [0.1, 0.0075, 0.01],
        [0.2, 0.154, 0.154],
        [0.35, 0.37375, 0.37375],
        [0.351, 0.37375, 0.6084],
        [0.5, 0.5935, 0.8156],
        [0.8, 1.0, 1.0776],
    ]
)
def test_Model_kc_fallow_constant_value(ndvi, fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=61, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc_fallow(
        fc=ee.Image.constant(fc), ndvi=ee.Image.constant(ndvi)))
    assert abs(output['kc'] - expected) <= tol


@pytest.mark.parametrize(
    'ndvi, fc, expected',
    [
        [-0.1, 0.0, 0.01],
        [0.1, 0.0075, 0.01],
        [0.2, 0.154, 0.154],
        [0.35, 0.37375, 0.37375],
        [0.351, 0.37375, 0.6084],
        [0.5, 0.5935, 0.8156],
        [0.8, 1.0, 1.0776],
    ]
)
def test_Model_kc_grass_pasture_constant_value(ndvi, fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=176, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc_grass_pasture(
        fc=ee.Image.constant(fc), ndvi=ee.Image.constant(ndvi)))
    assert abs(output['kc'] - expected) <= tol


@pytest.mark.parametrize(
    'fc, expected',
    [
        # [-0.1, 0.0],
        [0.0, 0.0],
        [0.1, 0.1668],
        [0.2, 0.3591],
        [0.3, 0.5229],
        [0.4, 0.6521],
        [0.45, 0.7051],  # NDVI == 0.5
        [0.5, 0.7517],
        [0.6, 0.8284],
        [0.7, 0.8879],
        [0.8, 0.9283],
        [0.9, 0.9655],
        [1.0, 1.0],
        [1.1, 1.0],  # Check clamping
    ]
)
def test_Model_kd_row_crop_constant_value(fc, expected, tol=0.0001):
    # m_l for crop_type 1 == 2.0
    m = default_model_obj(crop_type_source=1, crop_type_kc_flag=False)
    output = utils.constant_image_value(m._kd_row_crop(fc=ee.Image.constant(fc)))
    assert abs(output['kd'] - expected) <= tol


@pytest.mark.parametrize(
    'fc, expected',
    [
        # [-0.1, 0.0],
        [0.0, 0.0],
        [0.45, 0.675],
        [0.5, 0.75],
        [0.6, 0.8434],  # 0.6 ** (1/3)
        # [0.7, 0.8879],  # 0.7 ** (1/3)
        [0.8, 0.9283],  # 0.8 ** (1/3)
        # [0.9, 0.9655],  # 0.9 ** (1/3)
        [1.0, 1.0],  # 1.0 ** (1/3)
        [1.1, 1.0],  # 1.0 ** (1/3)
    ]
)
def test_Model_kd_vine_constant_value(fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=69, crop_type_kc_flag=False)
    output = utils.constant_image_value(m._kd_vine(fc=ee.Image.constant(fc)))
    assert abs(output['kd'] - expected) <= tol


@pytest.mark.parametrize(
    'fc, expected',
    [
        # [-0.1, 0.4096],
        [0.0, 0.0],
        [0.4, 0.7368],
        [0.45, 0.7663],
        [0.5, 0.7937],
        [0.6, 0.8801],
        [1.0, 1.0],
        [1.1, 1.0],
    ]
)
def test_Model_kd_tree_constant_value(fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=66, crop_type_kc_flag=False)
    output = utils.constant_image_value(m._kd_tree(fc=ee.Image.constant(fc)))
    assert abs(output['kd'] - expected) <= tol


@pytest.mark.parametrize(
    'kd, doy, h_max, expected',
    [
        [1, 250, 3, min(3 * 0.1 + 1, 1.2) * 0.95],  # 1.14
        [1, 270, 3, min(3 * 0.1 + 1, 1.2) * 0.95],  # 1.14
        [1, 285, 3, min(3 * 0.1 + 1, 1.2) * 0.85],  # 1.02
        [1, 320, 3, min(3 * 0.1 + 1, 1.2) * 0.75],  # 0.9
        [1, 285, 1, min(1 * 0.1 + 1, 1.2) * 0.85],  # 0.935
        [0.5, 285, 3, 0.5 * (1.2 * 0.85 - 0.15) + 0.15],  # 0.585
    ]
)
def test_Model_kcb_constant_value(kd, doy, h_max, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=66, doy=doy, crop_type_kc_flag=False)
    m.h_max = ee.Image.constant(h_max)
    m.fr_mid = ee.Image.constant(0.95)
    m.fr_end = ee.Image.constant(0.75)
    m.ls_start = ee.Image.constant(270)
    m.ls_stop = ee.Image.constant(300)
    output = utils.constant_image_value(m._kcb(kd=ee.Image.constant(kd)))
    assert abs(output['kcb'] - expected) <= tol


@pytest.mark.parametrize('crop_type', [0, 1, 69, 66, 3, 61])
def test_Model_kc_crop_class_constant_value(crop_type):
    # Check that a number is returned for all crop classes
    m = default_model_obj(crop_type_source=crop_type, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(0.5)))
    assert output['kc'] is not None


def test_Model_kc_crop_class_2_clamping():
    """Check that Kc for crop class 2 is clamped to 1.1"""
    m = default_model_obj(crop_type_source=78, crop_type_kc_flag=False)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(0.85)))
    assert output['kc'] == 1.1


@pytest.mark.parametrize(
    'mask_non_ag_flag, expected',
    [
        [False, 0.825],
        [True, None],
    ]
)
def test_Model_kc_mask_non_ag_flag(mask_non_ag_flag, expected):
    m = default_model_obj(crop_type_source=0, mask_non_ag_flag=mask_non_ag_flag)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(0.5)))
    assert output['kc'] == expected


@pytest.mark.parametrize(
    'crop_type_kc_flag, crop_type_annual_skip_flag',
    [
        [False, False],
        [True, False],
        [False, True],  # Use custom coefficients only for this condition
        [True, True],
    ]
)
def test_Model_kc_crop_type_kc_class_1(crop_type_kc_flag, crop_type_annual_skip_flag):
    """"Test that custom crop coefficients for annual crops are only used if
    the crop_type_kc_flag is True and the crop_type_annual_skip_flag is False.
    Otherwise, just use the generic row crop kc function.
    """
    m = default_model_obj(crop_type_source=1, crop_type_kc_flag=crop_type_kc_flag,
                          crop_type_annual_skip_flag=crop_type_annual_skip_flag)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(0.5)))
    if crop_type_kc_flag and not crop_type_annual_skip_flag:
        expected = utils.constant_image_value(
            m._kcb(m._kd_row_crop(fc=ee.Image.constant(0.45))))
        assert output['kc'] == expected['kcb']
    else:
        expected = utils.constant_image_value(
            m.kc_row_crop(fc=ee.Image.constant(0.45)))
        assert output['kc'] == expected['kc']


@pytest.mark.parametrize(
    'crop_type_kc_flag',
    [
        False,
        True,
    ]
)
def test_Model_kc_crop_type_kc_class_2(crop_type_kc_flag):
    """Check that vines are computed the same way """
    m = default_model_obj(crop_type_source=69, crop_type_kc_flag=crop_type_kc_flag)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(0.5)))
    expected = utils.constant_image_value(
        m._kcb(m._kd_vine(fc=ee.Image.constant(0.45))))
    assert output['kc'] == expected['kcb']


@pytest.mark.parametrize(
    'crop_type_kc_flag',
    [
        False,
        True,
    ]
)
def test_Model_kc_crop_type_kc_class_3(crop_type_kc_flag):
    m = default_model_obj(crop_type_source=66, crop_type_kc_flag=crop_type_kc_flag)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(0.5)))
    if crop_type_kc_flag:
        expected = utils.constant_image_value(
            m._kcb(m._kd_tree(fc=ee.Image.constant(0.45))))
        assert output['kc'] == expected['kcb']
    else:
        expected = utils.constant_image_value(m.kc_tree(fc=ee.Image.constant(0.45)))
        assert output['kc'] == expected['kc']


@pytest.mark.parametrize(
    'crop_type_source, expected',
    [
        # Wine grapes don't hit clamp value
        # [69, 1.1],
        [78, 1.1],
        # No tree crops hit clamp of 1.2 with an NDVI of 0.9
        # Peaches only hit with NDVI of 0.95
        [67, 1.2],
    ]
)
def test_Model_kc_crop_type_kc_clamping(crop_type_source, expected):
    m = default_model_obj(crop_type_source=crop_type_source, crop_type_kc_flag=True)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(0.95)))
    assert output['kc'] == expected


@pytest.mark.parametrize(
    'crop_type, ndvi, water_kc_flag, expected',
    [
        [0, -0.2, False, 0.0],
        [0, -0.2, True, 1.05],
        [1, -0.2, True, 0.15],  # Only set water Kc on crop_class 0
    ]
)
def test_Model_kc_water_kc_flag(crop_type, ndvi, water_kc_flag, expected):
    m = default_model_obj(crop_type_source=crop_type, crop_type_kc_flag=False,
                          water_kc_flag=water_kc_flag)
    output = utils.constant_image_value(m.kc(ndvi=ee.Image.constant(ndvi)))
    assert output['kc'] == expected


def ndvi_to_kc_point(ndvi, doy, crop_type):
    crop_profile = data.cdl[crop_type]

    fc = min(max((1.26 * ndvi) - 0.18, 0), 1)
    # print(crop_profile['crop_class'])
    if crop_profile['crop_class'] == 1:
        h = crop_profile['h_max'] * min((fc / 0.7), 1)
        fr = 1.0
    elif crop_profile['crop_class'] == 3 or crop_profile['crop_class'] == 2:
        # Set fr based on doy
        if doy < crop_profile['ls_start']:
            fr = crop_profile['fr_mid']
        elif crop_profile['ls_start'] <= doy and doy <= crop_profile['ls_stop']:
            fr = crop_profile['fr_mid'] - ((doy - crop_profile['ls_start'])\
                                           / (crop_profile['ls_stop'] - crop_profile['ls_start'])\
                                           * (crop_profile['fr_mid'] - crop_profile['fr_end']))
        elif doy > crop_profile['ls_stop']:
            fr = crop_profile['fr_end']

        # Set h based on crop class
        if crop_profile['crop_class'] == 3:
            if fc > 0.5:
                h = crop_profile['h_max']
            else:
                h = crop_profile['h_max'] - 1
        elif crop_profile['crop_class'] == 2:
            h = crop_profile['h_max']
    else:
        return -1

    kd = min(1, crop_profile['m_l'] * fc, fc ** (1 / (1 + h)))
    kcb_full = fr * min(1 + (0.1 * crop_profile['h_max']), 1.2)
    kc_min = 0.15
    kcb = kc_min + kd * (kcb_full - kc_min)

    # Crop class ceilings
    if crop_profile['crop_class'] == 2:
        kcb = min(kcb, 1.1)
    elif crop_profile['crop_class'] == 3:
        kcb = min(kcb, 1.2)

    return kcb


@pytest.mark.parametrize(
    'ndvi, doy, crop_type_num',
    [
        # 1.26 * 0.8 - 0.18 = 0.828
        # ((0.828 ** 2) * -0.4771) + (1.4047 * 0.828) + 0.15 = 0.9859994736
        [0.8, 174, 1],
        #[1.0, 200, 3],
        #[0.5, 200, 3],
        #[0.1, 200, 3],
        [1.0, 200, 1],
        [0.5, 200, 1],
        [0.1, 200, 1],
        [1.0, 200, 2],
        [0.5, 250, 2],
        [0.1, 300, 2],
        [1.0, 200, 69],
        [0.5, 200, 69],
        [0.1, 200, 69],
        [1.0, 250, 69],
        [0.5, 250, 69],
        [0.1, 250, 69],
        [1.0, 300, 69],
        [0.5, 300, 69],
        [0.1, 300, 69],
        [1.0, 200, 75],
        [0.5, 200, 75],
        [0.1, 200, 75],
        [1.0, 300, 75],
        [0.5, 300, 75],
        [0.1, 300, 75],
        [1.0, 301, 75],
        [0.5, 301, 75],
        [0.1, 301, 75],
    ]
)
def test_Image_kc_constant_value(ndvi, doy, crop_type_num, tol=0.0001):
    ndvi_img = ee.Image.constant(ndvi)
    m = default_model_obj(crop_type_source=crop_type_num, doy=doy,
                          crop_type_kc_flag=True)
    output = utils.constant_image_value(m.kc(ndvi_img))
    expected = ndvi_to_kc_point(ndvi, doy, crop_type_num)
    assert abs(output['kc'] - expected) <= tol


# Check the Kcb calculation for alfalfa
@pytest.mark.parametrize(
    'crop_type, fc, expected',
    [
        # [36, -0.1, 0.15],   # Check clamping
        [36, 0.0, 0.15],  # NDVI == 0.1429
        [36, 0.1, 0.2634],  # NDVI == 0.2222
        [36, 0.2, 0.3906],  # NDVI == 0.3016
        [36, 0.3, 0.5144],  # NDVI == 0.3809
        [36, 0.4, 0.6281],  # NDVI == 0.4603
        [36, 0.5, 0.7296],  # NDVI == 0.5397
        [36, 0.6, 0.8185],  # NDVI == 0.6190
        [36, 0.7, 0.8959],  # NDVI == 0.6984
        [36, 0.8, 0.9568],  # NDVI == 0.7778
        [36, 0.9, 1.0147],  # NDVI == 0.8571
        [36, 1.0, 1.07],
        [36, 1.1, 1.07],  # Check clamping
    ]
)
def test_Model_crop_type_kcb(crop_type, fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=crop_type, crop_type_kc_flag=True)
    output = utils.constant_image_value(m._kcb(m._kd_row_crop(
        fc=ee.Image.constant(fc))))
    assert abs(output['kcb'] - expected) <= tol


@pytest.mark.parametrize(
    'crop_type, fc, expected',
    [
        # [36, -0.1, 0.0],   # Check clamping
        [36, 0.0, 0.0],  # NDVI == 0.1429
        [36, 0.1, 0.1233],  # NDVI == 0.2222
        [36, 0.2, 0.2615],  # NDVI == 0.3016
        [36, 0.3, 0.3961],  # NDVI == 0.3809
        [36, 0.4, 0.5197],  # NDVI == 0.4603
        [36, 0.5, 0.6300],  # NDVI == 0.5397
        [36, 0.6, 0.7267],  # NDVI == 0.6190
        [36, 0.7, 0.8107],  # NDVI == 0.6984
        [36, 0.8, 0.8770],  # NDVI == 0.7778
        [36, 0.9, 0.9399],  # NDVI == 0.8571
        [36, 1.0, 1.0],
        [36, 1.1, 1.0],  # Check clamping
    ]
)
def test_Model_crop_type_kd(crop_type, fc, expected, tol=0.0001):
    m = default_model_obj(crop_type_source=crop_type, crop_type_kc_flag=True)
    output = utils.constant_image_value(m._kd_row_crop(fc=ee.Image.constant(fc)))
    assert abs(output['kd'] - expected) <= tol
