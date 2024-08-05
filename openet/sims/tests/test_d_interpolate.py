import datetime
# import pprint

import ee
import pandas as pd
import pytest

import openet.sims.interpolate as interpolate
import openet.sims.utils as utils
import openet.sims as sims


def scene_coll(variables, etf=[0.4, 0.4, 0.4], et=[5, 5, 5], ndvi=[0.6, 0.6, 0.6]):
    """Return a generic scene collection to test scene interpolation functions

    Parameters
    ----------
    variables : list
        The variables to return in the collection
    et_fraction : list
    et : list
    ndvi : list

    Returns
    -------
    ee.ImageCollection

    """
    img = (
        ee.Image('LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716')
        .select(['SR_B3']).double().multiply(0)
    )
    mask = img.add(1).updateMask(1).uint8()

    # # The "date" is used for the time band since it needs to be the 0 UTC time
    # date1 = ee.Number(ee.Date.fromYMD(2017, 7, 8).millis())
    # date2 = ee.Number(ee.Date.fromYMD(2017, 7, 16).millis())
    # date3 = ee.Number(ee.Date.fromYMD(2017, 7, 24).millis())

    # The "time" is advanced to match the typical Landsat overpass time
    time1 = ee.Number(ee.Date.fromYMD(2017, 7, 8).advance(18, 'hours').millis())
    time2 = ee.Number(ee.Date.fromYMD(2017, 7, 16).advance(18, 'hours').millis())
    time3 = ee.Number(ee.Date.fromYMD(2017, 7, 24).advance(18, 'hours').millis())

    # TODO: Add code to convert et, et_fraction, and ndvi to lists if they
    #   are set as a single value

    # Don't add mask or time band to scene collection
    # since they are now added in the interpolation calls
    scene_coll = ee.ImageCollection.fromImages([
        ee.Image([img.add(etf[0]), img.add(et[0]), img.add(ndvi[0])])
        .rename(['et_fraction', 'et', 'ndvi'])
        .set({'system:index': 'LE07_044033_20170708', 'system:time_start': time1}),
        ee.Image([img.add(etf[1]), img.add(et[1]), img.add(ndvi[1])])
        .rename(['et_fraction', 'et', 'ndvi'])
        .set({'system:index': 'LC08_044033_20170716', 'system:time_start': time2}),
        ee.Image([img.add(etf[2]), img.add(et[2]), img.add(ndvi[2])])
        .rename(['et_fraction', 'et', 'ndvi'])
        .set({'system:index': 'LE07_044033_20170724', 'system:time_start': time3}),
    ])

    # # Mask and time bands currently get added on to the scene collection
    # #   and images are unscaled just before interpolating in the export tool
    # scene_coll = ee.ImageCollection([
    #     ee.Image([img.add(etf[0]), img.add(et[0]), img.add(ndvi[0]), img.add(date1), mask])
    #     .rename(['et_fraction', 'et', 'ndvi', 'time', 'mask'])
    #     .set({'system:index': 'LE07_044033_20170708', 'system:time_start': time1}),
    #     ee.Image([img.add(etf[1]), img.add(et[1]), img.add(ndvi[1]), img.add(date2), mask])
    #     .rename(['et_fraction', 'et', 'ndvi', 'time', 'mask'])
    #     .set({'system:index': 'LC08_044033_20170716', 'system:time_start': time2}),
    #     ee.Image([img.add(etf[2]), img.add(et[2]), img.add(ndvi[2]), img.add(date3), mask])
    #     .rename(['et_fraction', 'et', 'ndvi', 'time', 'mask'])
    #     .set({'system:index': 'LE07_044033_20170724', 'system:time_start': time3}),
    # ])

    return scene_coll.select(variables)


def test_from_scene_et_fraction_t_interval_daily_values(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi'], ndvi=[0.2, 0.4, 0.6]),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily',
    )

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=30)
    assert abs(output['ndvi']['2017-07-01'] - 0.2) <= tol
    assert abs(output['ndvi']['2017-07-08'] - 0.2) <= tol
    assert abs(output['ndvi']['2017-07-10'] - 0.25) <= tol
    assert abs(output['ndvi']['2017-07-12'] - 0.3) <= tol
    assert abs(output['ndvi']['2017-07-16'] - 0.4) <= tol
    assert abs(output['ndvi']['2017-07-24'] - 0.6) <= tol
    assert abs(output['ndvi']['2017-07-31'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-10'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-10'] - 8.0) <= tol
    assert abs(output['et']['2017-07-10'] - (8.0 * 0.4)) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_fraction']['2017-07-31'] - 0.4) <= tol
    assert '2017-08-01' not in output['et_fraction'].keys()
    # assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_t_interval_monthly_values(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='monthly',
    )

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=30)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 236.5) <= tol
    assert abs(output['et']['2017-07-01'] - (236.5 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_t_interval_custom_values(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='custom',
    )

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=30)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 236.5) <= tol
    assert abs(output['et']['2017-07-01'] - (236.5 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_t_interval_monthly_et_reference_factor(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 0.5,
                    'et_reference_resample': 'nearest'},
        t_interval='monthly',
    )

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=30)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 236.5 * 0.5) <= tol
    assert abs(output['et']['2017-07-01'] - (236.5 * 0.5 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_t_interval_monthly_et_reference_resample(tol=0.0001):
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'bilinear'},
        t_interval='monthly',
    )

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=30)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    # CGM - ETo (and ET) test values are slightly different with bilinear resampling
    #   but ET fraction should be the same
    assert abs(output['et_reference']['2017-07-01'] - 236.05609) <= tol
    assert abs(output['et']['2017-07-01'] - (236.05609 * 0.4)) <= tol
    # assert abs(output['et_reference']['2017-07-01'] - 236.5) <= tol
    # assert abs(output['et']['2017-07-01'] - (236.5 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_t_interval_monthly_interp_args_et_reference(tol=0.0001):
    # Check that the et_reference parameters can be set through the interp_args
    output_coll = interpolate.from_scene_et_fraction(
        scene_coll(['et_fraction', 'ndvi']),
        start_date='2017-07-01', end_date='2017-08-01',
        variables=['et', 'et_reference', 'et_fraction', 'ndvi', 'count'],
        interp_args={'interp_method': 'linear', 'interp_days': 32,
                     'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                     'et_reference_band': 'eto',
                     'et_reference_factor': 1.0,
                     'et_reference_resample': 'nearest'},
        model_args={},
        t_interval='monthly',
    )

    TEST_POINT = (-121.5265, 38.7399)
    output = utils.point_coll_value(output_coll, TEST_POINT, scale=30)
    assert abs(output['ndvi']['2017-07-01'] - 0.6) <= tol
    assert abs(output['et_fraction']['2017-07-01'] - 0.4) <= tol
    assert abs(output['et_reference']['2017-07-01'] - 236.5) <= tol
    assert abs(output['et']['2017-07-01'] - (236.5 * 0.4)) <= tol
    assert output['count']['2017-07-01'] == 3


def test_from_scene_et_fraction_t_interval_bad_value():
    # Function should raise a ValueError if t_interval is not supported
    with pytest.raises(ValueError):
        interpolate.from_scene_et_fraction(
            scene_coll(['et']),
            start_date='2017-07-01', end_date='2017-08-01', variables=['et'],
            interp_args={'interp_method': 'linear', 'interp_days': 32},
            model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                        'et_reference_band': 'etr',
                        'et_reference_factor': 0.5,
                        'et_reference_resample': 'nearest'},
            t_interval='deadbeef',
        )


def test_from_scene_et_fraction_t_interval_no_value():
    # Function should raise an Exception if t_interval is not set
    with pytest.raises(TypeError):
        interpolate.from_scene_et_fraction(
            scene_coll(['et']),
            start_date='2017-07-01', end_date='2017-08-01',
            variables=['et', 'et_reference', 'et_fraction', 'count'],
            interp_args={'interp_method': 'linear', 'interp_days': 32},
            model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                        'et_reference_band': 'etr',
                        'et_reference_factor': 0.5,
                        'et_reference_resample': 'nearest'},
        )


def test_soil_evaporation_landsat(tol=0.001):
    TEST_POINT = (-120.201, 36.1696)
    et_reference_source = 'IDAHO_EPSCOR/GRIDMET'
    et_reference_band = 'eto'
    start_date = '2018-02-16'
    end_date = '2018-03-08'

    # Goal is to have the following two images in the test collection
    # ['LC08_043035_20180218', 'LC08_043035_20180306']
    landsat_coll = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start_date, end_date)
        .filterMetadata('WRS_PATH', 'equals', 43)
        .filterMetadata('WRS_ROW', 'equals', 35)
        # .filterBounds(ee.Geometry.Point(TEST_POINT))
    )

    def make_et_frac(img):
        # if 'C02' in landsat_coll_id:
        mask_img = img.select(['SR_B3']).double().multiply(0).rename(['mask'])
        time_img = mask_img.add(ee.Number(img.get('system:time_start'))).rename(['time'])
        et_img = sims.Image.from_landsat_c2_sr(
            img,
            et_reference_source=et_reference_source,
            et_reference_band=et_reference_band,
            cloudmask_args={'cloud_score_flag': False, 'filter_flag': False},
        ).calculate(['ndvi', 'et_reference', 'et_fraction', 'et'])
        return et_img.addBands([time_img])

    test_coll = landsat_coll.map(make_et_frac)

    # # Build the collection manually
    # img_a = ee.Image('LANDSAT/LC08/C02/T1_L2/LC08_043035_20180218')
    # img_b = ee.Image('LANDSAT/LC08/C02/T1_L2/LC08_043035_20180306')
    # time_a = (
    #     img_a.select(['SR_B3'], ['time'])
    #     .double().multiply(0).add(ee.Number(img_a.get('system:time_start')))
    # )
    # time_b = (
    #     img_b.select(['SR_B3'], ['time'])
    #     .double().multiply(0).add(ee.Number(img_b.get('system:time_start')))
    # )
    # img_a = sims.Image.from_landsat_c2_sr(
    #         img_a,
    #         et_reference_source=et_reference_source,
    #         et_reference_band=et_reference_band,
    #         cloudmask_args={'cloud_score_flag': False, 'filter_flag': False},
    #     ).calculate(['ndvi', 'et_reference', 'et_fraction', 'et'])
    # img_b = sims.Image.from_landsat_c2_sr(
    #         img_b,
    #         et_reference_source=et_reference_source,
    #         et_reference_band=et_reference_band,
    #         cloudmask_args={'cloud_score_flag': False, 'filter_flag': False},
    #     ).calculate(['ndvi', 'et_reference', 'et_fraction', 'et'])
    # test_coll = ee.ImageCollection([img_a.addBands([time_a]), img_b.addBands([time_b])])

    normal_coll = interpolate.from_scene_et_fraction(
        test_coll,
        start_date=start_date,
        end_date=end_date,
        variables=['et_reference', 'et_fraction', 'et'],
        interp_args={'interp_method': 'linear', 'interp_days': 32, 'use_joins': True},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily',
    )
    normal = utils.point_coll_value(normal_coll, TEST_POINT, scale=30)

    wb_coll = interpolate.from_scene_et_fraction(
        test_coll,
        start_date=start_date,
        end_date=end_date,
        variables=['et_reference', 'et_fraction', 'ke', 'et', 'ndvi'],
        interp_args={'interp_method': 'linear', 'interp_days': 32,
                     'estimate_soil_evaporation': True, 'use_joins': True},
        model_args={'et_reference_source': 'IDAHO_EPSCOR/GRIDMET',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily',
    )
    wb = utils.point_coll_value(wb_coll, TEST_POINT, scale=30)

    for date in normal['et'].keys():
        # check that ET with soil evap >= ET without soil evap
        assert wb['et'][date] >= normal['et'][date]


# Global constants for soil evap tests
TEST_POINT = (-120.201, 36.1696)
start_date = '2018-02-10'
end_date = '2018-03-14'
comp_df = pd.read_csv('openet/sims/tests/ee_wb_valid.csv')
comp_df['et_fraction'] = comp_df['etc'] / comp_df['eto']


@pytest.fixture
def synth_test_imgs():
    landsat_coll = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start_date, end_date)
        .filterBounds(ee.Geometry.Point(TEST_POINT))
    )
    mask = landsat_coll.first().select(['SR_B3']).double().multiply(0)

    test_imgs = []
    for index, row in comp_df.iterrows():
        # The time band needs to be 0 UTC for the interpolation to work correctly
        date = ee.Date.fromYMD(2018, 1, 1).advance(row.doy-1, 'days')
        time = date.advance(16, 'hours')
        test_img = (
            ee.Image([mask.add(ee.Number(date.millis())),
                      mask.add(row.ndvi_interp),
                      mask.add(row.kc), mask.add(row.eto)])
            .rename(['time', 'ndvi', 'et_fraction', 'et_reference'])
            .set({'system:time_start': ee.Number(time.millis()),
                  'system:index': date.format('yyyyMMdd')})
        )
        test_imgs.append(test_img)

    return ee.ImageCollection(test_imgs)


@pytest.fixture
def synth_precip_imgs():
    mask = (
        ee.ImageCollection('IDAHO_EPSCOR/GRIDMET')
        .filterDate(start_date, end_date)
        .first().select(['pr']).multiply(0)
    )

    precip_imgs = []
    for index, row in comp_df.iterrows():
        # Add 6 hours to mimic GRIDMET start time
        date = ee.Date.fromYMD(2018, 1, 1).advance(row.doy-1, 'days').advance(6, 'hours')
        precip_img = (
            mask.add(row.pr).rename(['pr'])
            .set({'system:time_start': ee.Number(date.millis()),
                  'system:index': date.format('yyyyMMdd')})
        )
        precip_imgs.append(precip_img)

    # Precipitation collection needs extra images at the end since the
    #   daily_ke builds a "next_precip" image in the iterate block
    date = ee.Date.fromYMD(2018, 1, 1).advance(comp_df.iloc[-1].doy, 'days')\
        .advance(6, 'hours')
    precip_imgs.append(mask.add(0).rename(['pr']).set({
        'system:time_start': ee.Number(date.millis()),
        'system:index': date.format('yyyyMMdd')}))

    return ee.ImageCollection(precip_imgs)


def test_daily_ke(synth_test_imgs, synth_precip_imgs):
    """"""
    evap_imgs = interpolate.daily_ke(
        synth_test_imgs,
        # CGM - model_args isn't used by daily_ke function and could be removed
        model_args={},
        precip_source=synth_precip_imgs,
        precip_band='pr',
        # precip_source='IDAHO_EPSCOR/GRIDMET',
        # precip_band='pr',
        fc_source='projects/eeflux/soils/gsmsoil_mu_a_fc_10cm_albers_100',
        fc_band='b1',
        wp_source='projects/eeflux/soils/gsmsoil_mu_a_wp_10cm_albers_100',
        wp_band='b1',
        # fc_source='projects/openet/assets/soils/ancillary/gsmsoil_mu_a_fc_10cm_albers_100',
        # wp_source='projects/openet/assets/soils/ancillary/gsmsoil_mu_a_wp_10cm_albers_100',
        # fc_band='fc',
        # wp_band='wp',
    )

    base_ts = utils.point_coll_value(synth_test_imgs, TEST_POINT, scale=30)
    base_df = pd.DataFrame(base_ts).reset_index()
    base_df['et'] = base_df['et_fraction'] * base_df['et_reference']

    evap_ts = utils.point_coll_value(evap_imgs, TEST_POINT, scale=30)
    evap_df = pd.DataFrame(evap_ts).reset_index()
    evap_df['et'] = evap_df['et_fraction'] * evap_df['et_reference']

    # Iterate through time series, stop one before end to avoid out of bounds
    # in "check next day state variable" tests
    for i in range(evap_df.shape[0]-1):
        # Check that soil evap only increase et fraction
        assert base_df.loc[i, 'et_fraction'] <= evap_df.loc[i, 'et_fraction']

        # Check that etc strictly greater than etcb if it rained and
        # kcb isn't maxed out
        if evap_df.loc[i, 'precip'] > 0 and base_df.loc[i, 'et_fraction'] < 1.15:
            assert base_df.loc[i+1, 'et_fraction'] < evap_df.loc[i+1, 'et_fraction']

        # Check evaporation reduction coefficients
        # Should be nonzero next day when depletion > REW
        if evap_df.loc[i, 'de'] > evap_df.de_rew.max():
            assert evap_df.loc[i+1, 'kr'] < 1

        # should be one next day when depletion is less than REW
        if evap_df.loc[i, 'de'] < evap_df.de_rew.max():
            assert evap_df.loc[i+1, 'kr'] == 1

        # should be zero next day when fully depleted
        if evap_df.loc[i, 'de'] == evap_df.de.max():
            assert evap_df.loc[i+1, 'kr'] == 0


def test_soil_evap_fails_without_ndvi(synth_test_imgs):
    """Test that daily_ke raises exception if `ndvi` band not present"""
    try:
        interpolate.from_scene_et_fraction(
            synth_test_imgs,
            start_date=start_date,
            end_date=end_date,
            variables=['et_reference', 'et_fraction', 'ke', 'et', 'precip'],
            interp_args={'interp_method': 'linear', 'interp_days': 10,
                         'estimate_soil_evaporation': True},
            model_args={'et_reference_source': 'provided',
                        'et_reference_band': 'eto',
                        'et_reference_factor': 1.0,
                        'et_reference_resample': 'nearest'},
            t_interval='daily',
        )
        # if from_scene_et_fraction doesn't raise, assert False
        assert False
    except Exception:
        pass


def test_soil_evaporation_synthetic(synth_test_imgs, synth_precip_imgs, tol=0.001):
    """Test that setting 'estimate_soil_evaporation' flag runs SWB"""
    normal_coll = interpolate.from_scene_et_fraction(
        scene_coll=synth_test_imgs,
        start_date=start_date,
        end_date=end_date,
        variables=['et_reference', 'et_fraction', 'et', 'ndvi'],
        interp_args={'interp_method': 'linear', 'interp_days': 10,
                     'estimate_soil_evaporation': False},
        model_args={'et_reference_source': 'provided',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily',
    )

    wb_coll = interpolate.from_scene_et_fraction(
        scene_coll=synth_test_imgs,
        start_date=start_date,
        end_date=end_date,
        variables=['et_reference', 'et_fraction', 'ke', 'et', 'ndvi', 'precip'],
        interp_args={'interp_method': 'linear', 'interp_days': 10,
                     'estimate_soil_evaporation': True,
                     'precip_source': synth_precip_imgs,
                     'precip_band': 'pr'},
        model_args={'et_reference_source': 'provided',
                    'et_reference_band': 'eto',
                    'et_reference_factor': 1.0,
                    'et_reference_resample': 'nearest'},
        t_interval='daily',
    )

    # synth = utils.point_coll_value(synth_test_imgs, TEST_POINT, scale=30)
    normal = utils.point_coll_value(normal_coll, TEST_POINT, scale=30)
    wb = utils.point_coll_value(wb_coll, TEST_POINT, scale=30)

    # check that wb ET >= regular SIMS ET
    for date in normal['et'].keys():
        assert wb['et'][date] >= normal['et'][date]

    def get_doy(dt_str):
        return datetime.datetime.strptime(dt_str, '%Y-%m-%d').timetuple().tm_yday

    wb_df = pd.DataFrame(wb)
    wb_df = wb_df.reset_index()
    wb_df['doy'] = wb_df['index'].apply(get_doy)

    for i in range(46, 52):
        assert abs(wb_df[wb_df.doy==i]['et'].iloc[0] -
                   comp_df[comp_df.doy==i]['etc'].iloc[0]) < tol
