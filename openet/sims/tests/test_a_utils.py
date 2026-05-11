import datetime
# import pprint

import ee
import pytest

import openet.sims.utils as utils


def test_ee_init():
    assert utils.getinfo(ee.Number(1)) == 1


def test_constant_image_value(expected=10.123456789, tol=0.000001):
    output = utils.constant_image_value(ee.Image.constant(expected))
    assert abs(output['constant'] - expected) <= tol


def test_constant_image_value_band_name(expected=10.123456789, tol=0.000001):
    """Test that a custom band name is carried through"""
    input_img = ee.Image.constant(expected).rename('foo')
    output = utils.constant_image_value(input_img)
    assert abs(output['foo'] - expected) <= tol


def test_constant_image_value_multiband(expected=10.123456789, tol=0.000001):
    """Test that a multiband image returns multiple values"""
    input_img = ee.Image.constant([expected, expected + 1])
    output = utils.constant_image_value(input_img)
    assert abs(output['constant_0'] - expected) <= tol
    assert abs(output['constant_1'] - (expected + 1)) <= tol


def test_constant_image_value_multiband_bands(expected=10.123456789, tol=0.000001):
    """Test that the band names are carried through on a multiband image"""
    input_img = ee.Image.constant([expected, expected + 1]).rename(['foo', 'bar'])
    output = utils.constant_image_value(input_img)
    assert abs(output['foo'] - expected) <= tol
    assert abs(output['bar'] - (expected + 1)) <= tol


@pytest.mark.parametrize(
    'image_id, xy, scale, expected, tol',
    [
        ['USGS/SRTMGL1_003', [-106.03249, 37.17777], 30, 2362, 0.001],
        ['NASA/NASADEM_HGT/001', [-106.03249, 37.17777], 30, 2361, 0.001],
    ]
)
def test_point_image_value(image_id, xy, scale, expected, tol):
    output = utils.point_image_value(
        ee.Image(image_id).select(['elevation'], ['output']), xy, scale
    )
    assert abs(output['output'] - expected) <= tol


@pytest.mark.parametrize(
    'image_id, image_date, xy, scale, expected, tol',
    [
        ['USGS/SRTMGL1_003', '2012-04-04', [-106.03249, 37.17777], 30, 2362, 0.001],
        ['NASA/NASADEM_HGT/001', '2012-04-04', [-106.03249, 37.17777], 30, 2361, 0.001],
    ]
)
def test_point_coll_value(image_id, image_date, xy, scale, expected, tol):
    # The image must have a system:time_start for this function to work correctly
    input_img = (
        ee.Image(image_id).select(['elevation'], ['output'])
        .set({'system:time_start': ee.Date(image_date).millis()})
    )
    output = utils.point_coll_value(ee.ImageCollection([input_img]), xy, scale)
    assert abs(output['output'][image_date] - expected) <= tol


@pytest.mark.parametrize(
    'input, expected',
    [
        ['2015-07-13T18:33:39', 1436745600000],
        ['2015-07-13T00:00:00', 1436745600000],

    ]
)
def test_date_0utc(input, expected):
    assert utils.getinfo(utils.date_0utc(ee.Date(input)).millis()) == expected


@pytest.mark.parametrize(
    # Note: These are made up values
    'input, expected',
    [
        [300, True],
        ['300', True],
        [300.25, True],
        ['300.25', True],
        ['a', False],
    ]
)
def test_is_number(input, expected):
    assert utils.is_number(input) == expected


def test_millis():
    assert utils.millis(datetime.datetime(2015, 7, 13)) == 1436745600000


def test_valid_date():
    assert utils.valid_date('2015-07-13') is True
    assert utils.valid_date('2015-02-30') is False
    assert utils.valid_date('20150713') is False
    assert utils.valid_date('07/13/2015') is False
    assert utils.valid_date('07-13-2015', '%m-%d-%Y') is True
