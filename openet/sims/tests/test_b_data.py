import ee
import pytest

import openet.sims.data as data
import openet.sims.utils as utils


def test_int_scalar():
    assert data.int_scalar == 100
    # assert data.int_scalar
    # assert data.int_scalar % 10 == 0


def test_cdl_dict():
    assert type(data.cdl) is dict


@pytest.mark.parametrize('year', [2019])
def test_cdl_crop_types(year):
    # Check that the codes in the data dictionary are valid CDL codes
    output = utils.getinfo(ee.Image(f'USDA/NASS/CDL/{year}').get('cropland_class_values'))
    output = [round(float(item)) for item in output.split(',')]
    for crop_type, crop_data in data.cdl.items():
        # Crop type 78 is non-standard CDL code being used for Grapes (table/raisin)
        if crop_type == 78:
            continue
        assert crop_type in output


@pytest.mark.parametrize('param', ['crop_class', 'h_max', 'm_l', 'fr_mid'])
def test_cdl_parameters(param):
    # Check that all default parameter keys have a value
    # Crops without a key will use general Kc equation
    # CGM - This test isn't very informative about which crop is the problem
    assert all(crop_data[param] for crop_data in data.cdl.values()
               if param in crop_data.keys())


@pytest.mark.parametrize('param', ['fr_end', 'ls_start', 'ls_stop'])
def test_cdl_class3_parameters(param):
    assert all(crop_data[param] for crop_data in data.cdl.values()
               if crop_data['crop_class'] == 3 and param in crop_data.keys())


@pytest.mark.parametrize(
    'crop_type, crop_class',
    [
        [1, 1],
        [69, 2],
        [66, 3],
        [3, 5],    # Rice was switched to class 5 instead of 1
        [61, 6],   # Fallow was switched to class 6 instead of 1
        [176, 7],  # Grass/pasture was switched to class 7 instead of 1
    ]
)
def test_cdl_crop_classes(crop_type, crop_class):
    assert data.cdl[crop_type]['crop_class'] == crop_class


# CGM - How would I do this?
# def test_cdl_int_scalar_digits():
#     # Check if any values have more digits than can be handled by int_scalar
#     assert False
