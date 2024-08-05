import datetime
import logging

from dateutil.relativedelta import relativedelta
import ee
import openet.core.interpolate
# TODO: import utils from openet.core
# import openet.core.utils as utils

from . import utils

RESAMPLE_METHODS = ['nearest', 'bilinear', 'bicubic']

def from_scene_et_fraction(
    scene_coll,
    start_date,
    end_date,
    variables,
    interp_args,
    model_args,
    t_interval,
    _interp_vars=['et_fraction', 'ndvi'],
):
    """Interpolate from a precomputed collection of Landsat ET fraction scenes

    Parameters
    ----------
    scene_coll : ee.ImageCollection
        Non-daily 'et_fraction' images that will be interpolated.
    start_date : str
        ISO format start date.
    end_date : str
        ISO format end date (exclusive, passed directly to .filterDate()).
    variables : list
        List of variables that will be returned in the Image Collection.
    interp_args : dict
        Parameters from the INTERPOLATE section of the INI file.
        # TODO: Look into a better format for showing the options
        interp_method : {'linear}, optional
            Interpolation method.  The default is 'linear'.
        interp_days : int, str, optional
            Number of extra days before the start date and after the end date
            to include in the interpolation calculation. The default is 32.
        use_joins : bool, optional
            If True, use joins to link the target and source collections.
            If False, the source collection will be filtered for each target image.
            This parameter is passed through to interpolate.daily().
        et_reference_source : str
            Reference ET collection ID.
        et_reference_band : str
            Reference ET band name.
        et_reference_factor : float, None, optional
            Reference ET scaling factor.  The default is 1.0 which is
            equivalent to no scaling.
        et_reference_resample : {'nearest', 'bilinear', 'bicubic', None}, optional
            Reference ET resampling.  The default is 'nearest'.
        estimate_soil_evaporation: bool
            Compute daily Ke values by simulating water balance in evaporable
            zone. Default is False.
        spinup_days: int
            Number of extra days prior to start_date to simulate for starting
            soil water state.  This value will be added to the interp_days when
            setting the interpolation start date.  Default is 0 days.
    model_args : dict
        Parameters from the MODEL section of the INI file.
    t_interval : {'daily', 'monthly', 'annual', 'custom'}
        Time interval over which to interpolate and aggregate values
        The 'custom' interval will aggregate all days within the start and end
        dates into an image collection with a single image.
    _interp_vars : list, optional
        The variables that can be interpolated to daily timesteps.
        The default is to interpolate the 'et_fraction' and 'ndvi' bands.

    Returns
    -------
    ee.ImageCollection

    Raises
    ------
    ValueError

    Notes
    -----
    This function assumes that "mask" and "time" bands are not in the scene collection.

    """
    # Check whether to compute daily Ke
    if 'estimate_soil_evaporation' in interp_args.keys():
        estimate_soil_evaporation = interp_args['estimate_soil_evaporation']
    else:
        estimate_soil_evaporation = False

    if estimate_soil_evaporation:
        # Add spinup days, will remove after water balance calculations
        if 'spinup_days' in interp_args.keys():
            spinup_days = interp_args['spinup_days']
        else:
            spinup_days = 0

    # Get interp_method
    if 'interp_method' in interp_args.keys():
        interp_method = interp_args['interp_method']
    else:
        interp_method = 'linear'
        logging.debug('interp_method was not set, default to "linear"')

    # Get interp_days
    if 'interp_days' in interp_args.keys():
        interp_days = interp_args['interp_days']
    else:
        interp_days = 32
        logging.debug('interp_days was not set, default to 32')

    # Get use_joins
    if 'use_joins' in interp_args.keys():
        use_joins = interp_args['use_joins']
    else:
        use_joins = True
        logging.debug('use_joins was not set in interp_args, default to True')

    # Check that the input parameters are valid
    if t_interval.lower() not in ['daily', 'monthly', 'annual', 'custom']:
        raise ValueError(f'unsupported t_interval: {t_interval}')
    elif interp_method.lower() not in ['linear']:
        raise ValueError(f'unsupported interp_method: {interp_method}')

    if ((type(interp_days) is str or type(interp_days) is float) and
            utils.is_number(interp_days)):
        interp_days = int(interp_days)
    elif not type(interp_days) is int:
        raise TypeError('interp_days must be an integer')
    elif interp_days <= 0:
        raise ValueError('interp_days must be a positive integer')

    if not variables:
        raise ValueError('variables parameter must be set')

    # Adjust start/end dates based on t_interval
    # Increase the date range to fully include the time interval
    start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d')
    if t_interval.lower() == 'annual':
        start_dt = datetime.datetime(start_dt.year, 1, 1)
        # Covert end date to inclusive, flatten to beginning of year,
        # then add a year which will make it exclusive
        end_dt -= relativedelta(days=+1)
        end_dt = datetime.datetime(end_dt.year, 1, 1)
        end_dt += relativedelta(years=+1)
    elif t_interval.lower() == 'monthly':
        start_dt = datetime.datetime(start_dt.year, start_dt.month, 1)
        end_dt -= relativedelta(days=+1)
        end_dt = datetime.datetime(end_dt.year, end_dt.month, 1)
        end_dt += relativedelta(months=+1)
    start_date = start_dt.strftime('%Y-%m-%d')
    end_date = end_dt.strftime('%Y-%m-%d')

    # The start/end date for the interpolation include more days
    # (+/- interp_days) than are included in the ETr collection
    if estimate_soil_evaporation:
        interp_start_dt = start_dt - datetime.timedelta(days=interp_days+spinup_days)
    else:
        interp_start_dt = start_dt - datetime.timedelta(days=interp_days)
    interp_end_dt = end_dt + datetime.timedelta(days=interp_days)
    interp_start_date = interp_start_dt.date().isoformat()
    interp_end_date = interp_end_dt.date().isoformat()

    # Get reference ET parameters
    # Supporting reading the parameters from both the interp_args and model_args dictionaries
    # Check interp_args then model_args, but eventually drop support for reading from model_args
    # Assume that if source and band are both set, the parameters in that section should be used
    if ('et_reference_source' in interp_args.keys()) and ('et_reference_band' in interp_args.keys()):
        et_reference_source = interp_args['et_reference_source']
        et_reference_band = interp_args['et_reference_band']
        if not et_reference_source or not et_reference_band:
            raise ValueError('et_reference_source or et_reference_band were not set')

        if 'et_reference_factor' in interp_args.keys():
            et_reference_factor = interp_args['et_reference_factor']
        else:
            et_reference_factor = 1.0
            logging.debug('et_reference_factor was not set, default to 1.0')

        if 'et_reference_resample' in interp_args.keys():
            et_reference_resample = interp_args['et_reference_resample'].lower()
            if not et_reference_resample:
                et_reference_resample = 'nearest'
                logging.debug('et_reference_resample was not set, default to nearest')
            elif et_reference_resample not in ['nearest', 'bilinear', 'bicubic']:
                raise ValueError(f'unsupported et_reference_resample method: '
                                 f'{et_reference_resample}')
        else:
            et_reference_resample = 'nearest'
            logging.debug('et_reference_resample was not set, default to nearest')

    elif ('et_reference_source' in model_args.keys()) and ('et_reference_band' in model_args.keys()):
        et_reference_source = model_args['et_reference_source']
        et_reference_band = model_args['et_reference_band']
        if not et_reference_source or not et_reference_band:
            raise ValueError('et_reference_source or et_reference_band were not set')

        if 'et_reference_factor' in model_args.keys():
            et_reference_factor = model_args['et_reference_factor']
        else:
            et_reference_factor = 1.0
            logging.debug('et_reference_factor was not set, default to 1.0')

        if 'et_reference_resample' in model_args.keys():
            et_reference_resample = model_args['et_reference_resample'].lower()
            if not et_reference_resample:
                et_reference_resample = 'nearest'
                logging.debug('et_reference_resample was not set, default to nearest')
            elif et_reference_resample not in ['nearest', 'bilinear', 'bicubic']:
                raise ValueError(f'unsupported et_reference_resample method: '
                                 f'{et_reference_resample}')
        else:
            et_reference_resample = 'nearest'
            logging.debug('et_reference_resample was not set, default to nearest')

    else:
        raise ValueError('et_reference_source or et_reference_band were not set')

    # Check if collection already has et_reference provided
    #   if not, get it from the collection
    if (type(et_reference_source) is str) and (et_reference_source.lower() == 'provided'):
        daily_et_ref_coll = scene_coll.map(lambda x: x.select('et_reference'))
    elif type(et_reference_source) is str:
        # Assume a string source is a single image collection ID
        #   not a list of collection IDs or ee.ImageCollection
        daily_et_ref_coll = (
            ee.ImageCollection(et_reference_source)
            .filterDate(start_date, end_date)
            .select([et_reference_band], ['et_reference'])
        )
    # elif isinstance(et_reference_source, computedobject.ComputedObject):
    #     # Interpret computed objects as image collections
    #     daily_et_ref_coll = (
    #         ee.ImageCollection(et_reference_source)
    #         .filterDate(self.start_date, self.end_date)
    #         .select([et_reference_band])
    #     )
    else:
        raise ValueError(f'unsupported et_reference_source: {et_reference_source}')

    # Scale reference ET images (if necessary)
    # CGM - Resampling is not working correctly so not including for now
    if et_reference_factor and (et_reference_factor != 1):
        def et_reference_adjust(input_img):
            return (
                input_img.multiply(et_reference_factor)
                .copyProperties(input_img)
                .set({'system:time_start': input_img.get('system:time_start')})
            )
        daily_et_ref_coll = daily_et_ref_coll.map(et_reference_adjust)

    # Initialize variable list to only variables that can be interpolated
    interp_vars = list(set(_interp_vars) & set(variables))

    # To return ET, the ETf must be interpolated
    if ('et' in variables) and ('et_fraction' not in interp_vars):
        interp_vars = interp_vars + ['et_fraction']

    # With the current interpolate.daily() function,
    #   something has to be interpolated in order to return et_reference
    if ('et_reference' in variables) and ('et_fraction' not in interp_vars):
        interp_vars = interp_vars + ['et_fraction']

    # The NDVI band is always needed for the soil water balance
    if estimate_soil_evaporation and ('ndvi' not in interp_vars):
        interp_vars = interp_vars + ['ndvi']

    # TODO: Look into implementing et_fraction clamping here
    #   (similar to et_actual below)

    def interpolate_prep(img):
        """Prep WRS2 scene images for interpolation

        "Unscale" the images using the "scale_factor" property and convert to double.
        Add a mask and time band to each image in the scene_coll since
            interpolator is assuming time and mask bands exist.
        The interpolation could be modified to get the mask from the
            time band instead of setting it here.
        The time image must be the 0 UTC time

        """
        mask_img = (
            img.select(['et_fraction']).multiply(0).add(1).updateMask(1).uint8()
            .rename(['mask'])
        )
        time_img = (
            img.select(['et_fraction']).double().multiply(0)
            .add(utils.date_0utc(ee.Date(img.get('system:time_start'))).millis())
            .rename(['time'])
        )

        # Set the default scale factor to 1 if the image does not have the property
        scale_factor = (
            ee.Dictionary({'scale_factor': img.get('scale_factor')})
            .combine({'scale_factor': 1.0}, overwrite=False)
        )

        return (
            img.select(interp_vars)
            .double().multiply(ee.Number(scale_factor.get('scale_factor')))
            .addBands([mask_img, time_img])
            .set({
                'system:time_start': ee.Number(img.get('system:time_start')),
                'system:index': ee.String(img.get('system:index')),
            })
        )

    # Filter scene collection to the interpolation range
    #   This probably isn't needed since scene_coll was built to this range
    # Then add the time and mask bands needed for interpolation
    scene_coll = ee.ImageCollection(
        scene_coll.filterDate(interp_start_date, interp_end_date)
        .map(interpolate_prep)
    )

    # For count, compute the composite/mosaic image for the mask band only
    if 'count' in variables:
        aggregate_coll = openet.core.interpolate.aggregate_to_daily(
            image_coll=scene_coll.select(['mask']),
            start_date=start_date,
            end_date=end_date,
        )

        # The following is needed because the aggregate collection can be
        #   empty if there are no scenes in the target date range but there
        #   are scenes in the interpolation date range.
        # Without this the count image will not be built but the other
        #   bands will be which causes a non-homogeneous image collection.
        aggregate_coll = aggregate_coll.merge(
            ee.Image.constant(0).rename(['mask'])
            .set({'system:time_start': ee.Date(start_date).millis()})
        )

    # Interpolate to a daily time step
    # NOTE: the daily function is not computing ET (ETf x ETo)
    #   but is returning the target (ETo) band
    daily_coll = openet.core.interpolate.daily(
        target_coll=daily_et_ref_coll,
        source_coll=scene_coll.select(interp_vars + ['time']),
        interp_method=interp_method,
        interp_days=interp_days,
        use_joins=use_joins,
        compute_product=False,
        # resample_method=et_reference_resample,
    )

    if estimate_soil_evaporation:
        daily_coll = daily_ke(daily_coll, model_args, **interp_args)

    # The interpolate.daily() function can/will return the product of
    # the source and target image named as "{source_band}_1".
    # The problem with this approach is that is will drop any other bands
    # that are being interpolated (such as the ndvi).
    # daily_coll = daily_coll.select(['et_fraction_1'], ['et'])

    # Compute ET from ETf and ETo (if necessary)
    # This isn't needed if compute_product=True in daily() and band is renamed
    # The check for et_fraction is needed since it is back computed from ET and ETo
    if ('et' in variables) or ('et_fraction' in variables):
        def compute_et(img):
            """This function assumes ETr and ETf are present"""
            # Apply any resampling to the reference ET image before computing ET
            et_reference_img = img.select(['et_reference'])
            if et_reference_resample and (et_reference_resample in ['bilinear', 'bicubic']):
                et_reference_img = et_reference_img.resample(et_reference_resample)

            et_img = img.select(['et_fraction']).multiply(et_reference_img)

            return img.addBands(et_img.double().rename('et'))

        daily_coll = daily_coll.map(compute_et)

    def aggregate_image(agg_start_date, agg_end_date, date_format):
        """Aggregate the daily images within the target date range

        Parameters
        ----------
        agg_start_date: str
            Start date (inclusive).
        agg_end_date : str
            End date (exclusive).
        date_format : str
            Date format for system:index (uses EE JODA format).

        Returns
        -------
        ee.Image

        Notes
        -----
        Since this function takes multiple inputs it is being called
        for each time interval by separate mappable functions

        """
        if ('et' in variables) or ('et_fraction' in variables):
            et_img = daily_coll.filterDate(agg_start_date, agg_end_date).select(['et']).sum()

        if ('et_reference' in variables) or ('et_fraction' in variables):
            et_reference_img = (
                daily_et_ref_coll
                .filterDate(agg_start_date, agg_end_date)
                .select(['et_reference'])
                .sum()
            )
            if et_reference_resample and (et_reference_resample in ['bilinear', 'bicubic']):
                et_reference_img = (
                    et_reference_img
                    .setDefaultProjection(daily_et_ref_coll.first().projection())
                    .resample(et_reference_resample)
                )

        image_list = []
        if 'et' in variables:
            image_list.append(et_img.float())
        if 'et_reference' in variables:
            image_list.append(et_reference_img.float())
        if 'et_fraction' in variables:
            # Compute average et fraction over the aggregation period
            image_list.append(et_img.divide(et_reference_img).rename(['et_fraction']).float())
        if 'ndvi' in variables:
            # Compute average ndvi over the aggregation period
            ndvi_img = (
                daily_coll.filterDate(agg_start_date, agg_end_date)
                .mean().select(['ndvi']).float()
            )
            image_list.append(ndvi_img)
        if 'count' in variables:
            count_img = (
                aggregate_coll.filterDate(agg_start_date, agg_end_date)
                .select(['mask']).sum().rename('count').uint8()
            )
            image_list.append(count_img)

        # Return other SWB variables
        for var_name in ['ke', 'kr', 'ft', 'de_rew', 'de', 'de_prev', 'precip']:
            if var_name in variables:
                var_img = (
                    daily_coll.filterDate(agg_start_date, agg_end_date)
                    .mean().select([var_name]).float()
                )
                image_list.append(var_img)

        return (
            ee.Image(image_list)
            .set({
                'system:index': ee.Date(agg_start_date).format(date_format),
                'system:time_start': ee.Date(agg_start_date).millis(),
            })
            # .set(interp_properties)
        )

    # Combine input, interpolated, and derived values
    if t_interval.lower() == 'daily':
        def agg_daily(daily_img):
            # CGM - Double check that this time_start is a 0 UTC time.
            # It should be since it is coming from the interpolate source
            #   collection, but what if source is GRIDMET (+6 UTC)?
            agg_start_date = ee.Date(daily_img.get('system:time_start'))
            # CGM - This calls .sum() on collections with only one image
            return aggregate_image(
                agg_start_date=agg_start_date,
                agg_end_date=ee.Date(agg_start_date).advance(1, 'day'),
                date_format='YYYYMMdd',
            )

        return ee.ImageCollection(daily_coll.map(agg_daily))

    elif t_interval.lower() == 'monthly':
        def month_gen(iter_start_dt, iter_end_dt):
            iter_dt = iter_start_dt
            # Conditional is "less than" because end date is exclusive
            while iter_dt < iter_end_dt:
                yield iter_dt.strftime('%Y-%m-%d')
                iter_dt += relativedelta(months=+1)

        month_list = ee.List(list(month_gen(start_dt, end_dt)))

        def agg_monthly(agg_start_date):
            return aggregate_image(
                agg_start_date=agg_start_date,
                agg_end_date=ee.Date(agg_start_date).advance(1, 'month'),
                date_format='YYYYMM',
            )

        return ee.ImageCollection(month_list.map(agg_monthly))

    elif t_interval.lower() == 'annual':
        def year_gen(iter_start_dt, iter_end_dt):
            iter_dt = iter_start_dt
            while iter_dt < iter_end_dt:
                yield iter_dt.strftime('%Y-%m-%d')
                iter_dt += relativedelta(years=+1)

        year_list = ee.List(list(year_gen(start_dt, end_dt)))

        def agg_annual(agg_start_date):
            return aggregate_image(
                agg_start_date=agg_start_date,
                agg_end_date=ee.Date(agg_start_date).advance(1, 'year'),
                date_format='YYYY',
            )

        return ee.ImageCollection(year_list.map(agg_annual))

    elif t_interval.lower() == 'custom':
        # Returning an ImageCollection to be consistent
        return ee.ImageCollection(aggregate_image(
            agg_start_date=start_date,
            agg_end_date=end_date,
            date_format='YYYYMMdd',
        ))


def daily_ke(
        daily_coll,
        model_args,  # CGM - This parameter isn't used
        precip_source='IDAHO_EPSCOR/GRIDMET',
        precip_band='pr',
        fc_source='projects/eeflux/soils/gsmsoil_mu_a_fc_10cm_albers_100',
        fc_band='b1',
        wp_source='projects/eeflux/soils/gsmsoil_mu_a_wp_10cm_albers_100',
        wp_band='b1',
        # fc_source='projects/openet/assets/soils/ancillary/gsmsoil_mu_a_fc_10cm_albers_100',
        # fc_band='fc',
        # wp_source='projects/openet/assets/soils/ancillary/gsmsoil_mu_a_wp_10cm_albers_100',
        # wp_band='wp',
        **kwargs
        ):
    """Compute daily Ke values by simulating evaporable zone water balance

    Parameters
    ----------
    daily_coll : ee.Image
        Collection of daily Kcb images
    model_args : dict
        Parameters from the MODEL section of the INI file.  The reference
        source and parameters will need to be set here if computing
        reference ET or actual ET.
    precip_source : str, optional
        GEE data source for gridded precipitation data, default is gridMET.
    precip_band : str, option
        GEE Image band that contains gridded precipitaiton data, default is
        'pr', which is the band for gridMET.
    fc_source : str, ee.Image
        GEE Image of soil field capacity values
    fc_band : str
        Name of the band in `fc_source` that contains field capacity values
    wp_source : str, ee.Image
        GEE Image of soil permanent wilting point values
    wp_band : str
        Name of the band in `wp_source` that contains wilting point values

    Returns
    -------
    ee.ImageCollection

    """
    # First check that ndvi band is present in daily_coll
    if daily_coll.first().bandNames().indexOf('ndvi').eq(-1).getInfo():
        raise Exception('Daily collection must have NDVI band to compute soil evaporation')

    field_capacity = ee.Image(fc_source).select(fc_band)
    wilting_point = ee.Image(wp_source).select(wp_band)

    # Available water content (mm)
    awc = field_capacity.subtract(wilting_point)

    # Fraction of wetting
    # Setting to 1 for now (precip), but could be lower for irrigation
    # CGM - Not used below, commenting out for now
    # frac_wet = ee.Image(1)

    # Depth of evaporable zone
    # Set to 10 cm
    z_e = 0.1

    # Total evaporable water (mm)
    # Allen et al. 1998 eqn 73
    tew = field_capacity.expression(
        '10 * (b() - 0.5 * wp) * z_e', {'wp': wilting_point, 'z_e': z_e}
    )

    # Readily evaporable water (mm)
    rew = awc.expression('0.8 + 54.4 * b() / 100')
    rew = rew.where(rew.gt(tew), tew)

    # Coefficients for skin layer retention, Allen (2011)
    c0 = ee.Image(0.8)
    c1 = c0.expression('2 * (1 - b())')

    # 1.2 is max for grass reference (ETo)
    ke_max = ee.Image(1.2)

    # Fraction of precip that evaps today vs tomorrow
    # .5 is arbitrary
    frac_day_evap = ee.Image(0.5)

    # Get precip collection
    daily_pr_coll = ee.ImageCollection(precip_source).select(precip_band)

    # Assume soil is at field capacity to start
    # i.e. depletion = 0
    # init_de = ee.Image(ee.Image(0.0).select([0], ['de']))
    # init_de_rew = ee.Image(ee.Image(0.0).select([0], ['de_rew']))
    init_de = tew.select([0], ['de'])
    init_de_rew = rew.select([0], ['de_rew'])
    init_c_eff = (
        init_de.expression("C0 + C1 * (1 - b() / TEW)", {'C0': c0, 'C1': c1, 'TEW': tew})
        .min(1)
        .select([0], ['c_eff'])
    )

    # Create list to hold water balance rasters when iterating over collection
    # Doesn't seem like you can create an empty list in ee?
    init_img = ee.Image([init_de, init_de_rew, init_c_eff])
    init_img_list = ee.ImageCollection([init_img]).toList(1)

    # Convert interp collection to list
    interp_list = daily_coll.toList(daily_coll.size())
    # Is list guaranteed to have right order?
    # (Seems to be fine in initial testing.)
    # interp_list = interp_list.sort(ee.List(['system:index']))

    # Perform daily water balance update
    def water_balance_step(img, wb_coll):
        # Explicit cast ee.Image
        prev_img = ee.Image(ee.List(wb_coll).get(-1))
        curr_img = ee.Image(img)

        # Make precip image with bands for today and tomorrow
        # CGM - The current image is selected by filtering to the previous day
        #   since the Landsat image time is ~18 UTC but the precip start time
        #   is likely 0 UTC or 6 UTC (for GRIDMET)
        # CGM the
        curr_date = curr_img.date()
        curr_precip = ee.Image(
            daily_pr_coll.filterDate(curr_date.advance(-1, 'day'), curr_date).first()
        )
        next_precip = ee.Image(
            daily_pr_coll.filterDate(curr_date, curr_date.advance(1, 'day')).first()
        )
        # curr_precip = ee.Image(
        #     daily_pr_coll.filterDate(curr_date, curr_date.advance(1, 'day')).first()
        # )
        # next_precip = ee.Image(
        #     daily_pr_coll.filterDate(curr_date.advance(1, 'day'), curr_date.advance(2, 'day'))
        #     .first()
        # )
        precip_img = ee.Image([curr_precip, next_precip]).rename(['current', 'next'])

        # Fraction of day stage 1 evap
        # Allen 2011, eq 12
        ft = (
            rew.expression(
                '(b() - de_rew_prev) / (ke_max * eto)',
                {
                    'de_rew_prev': prev_img.select('de_rew'),
                    'rew': rew,
                    'ke_max': ke_max,
                    'eto': curr_img.select('et_reference')
                }
            )
            .clamp(0.0, 1.0)
            .rename('ft')
        )

        # Soil evap reduction coeff, FAO 56
        kr = (
            tew.expression(
                "(b() - de_prev) / (b() - rew)",
                {'de_prev': prev_img.select('de'), 'rew': rew}
            )
            .clamp(0.0, 1.0)
            .rename('kr')
        )

        de_prev = prev_img.select('de').rename('de_prev')

        # precip only for now
        # irrigation might have lower f_w
        fw = prev_img.select('de').multiply(0).add(1).rename('fw')
        low_few = fw.multiply(0).add(0.01).rename('low_few')
        fc = curr_img.select('ndvi').multiply(1.26).subtract(0.18).rename('fc')
        few = fw.min(fc.multiply(-1).add(1)).max(low_few).rename('few')

        # Soil evap coeff, FAO 56
        ke = (
            ft.expression("(b() + (1 - b()) * kr) * ke_max", {'kr': kr, 'ke_max': ke_max})
            .min(few.multiply(ke_max))
            .rename('ke')
        )

        # Dual crop coefficient: Kc = Kcb + Ke
        # kc = ke.add(curr_img.select('et_fraction')).rename('kc')

        # Crop ET (note that Kc in other parts of code refers to *basal*
        # crop coeff (Kcb))
        # etc = kc.multiply(curr_img.select('et_reference')).rename('etc')

        # ETe - soil evaporation
        ete = ke.multiply(curr_img.select('et_reference')).rename('ete')

        # CGM - Why not just add ke to et_frac and clamp the result?
        #   What does the extra .where call do?
        et_frac = ee.Image(img).select(['et_fraction'])
        etof = (
            et_frac.where(et_frac.lte(1.15), et_frac.add(ke).clamp(0, 1.15))
            .rename('et_fraction')
        )

        # Depletion, FAO 56
        de = (
            prev_img.select('de')
            .subtract(
                frac_day_evap
                .multiply(ee.Image(precip_img.select('next')))
                .add(
                    ee.Image(1)
                    .subtract(frac_day_evap)
                    .multiply(precip_img.select('current')))
            )
            .add(ete.divide(few.select('few')))
            .select([0], ['de'])
        )

        # Can't have negative depletion
        de = de.min(tew).max(0)

        # Stage 1 depletion (REW)
        # Allen 2011
        de_rew = (
            prev_img.select('de_rew')
            .subtract(
                frac_day_evap
                .multiply(precip_img.select('next'))
                .add(
                    ee.Image(1)
                    .subtract(frac_day_evap)
                    .multiply(precip_img.select('current'))
                )
                .multiply(prev_img.select('c_eff'))
            )
            .add(ete.divide(few.select('few')))
            .select([0], ['de_rew'])
        )

        # Can't have negative depletion
        de_rew = de_rew.min(rew).max(0)

        # Efficiency of skin layer
        # Allen 2011, eq 15
        c_eff = (
            de.expression("c0 + c1 * (1 - b() / tew)", {'c0': c0, 'c1': c1, 'tew': tew})
            .min(1)
            .select([0], ['c_eff'])
        )

        # Make image to add to list
        # CGM - I removed the duplicate de, de_rew, and ft bands
        #   Are they needed?
        new_day_img = ee.Image(
            curr_img.addBands(
                ee.Image([de, de_rew, c_eff, ke, kr, ft, de_prev, ete,
                          precip_img.select(['current'], ['precip']), etof]),
                overwrite=True
            )
        )

        return ee.List(wb_coll).add(new_day_img)

    # Run the water balance calculations
    daily_coll = interp_list.iterate(water_balance_step, init_img_list)

    # remove empty first day
    daily_coll = ee.List(daily_coll).slice(1, ee.List(daily_coll).size())
    daily_coll = ee.ImageCollection.fromImages(daily_coll)

    return daily_coll
