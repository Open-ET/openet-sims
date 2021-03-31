import datetime
import logging

import ee
from dateutil.relativedelta import *

from . import utils

import openet.core.interpolate
# TODO: import utils from openet.core
# import openet.core.utils as utils


def from_scene_et_fraction(scene_coll, start_date, end_date, variables,
                           interp_args, model_args, t_interval='custom',
                           use_joins=False,
                           _interp_vars=['et_fraction', 'ndvi']):
    """Interpolate from a precomputed collection of Landast ET fraction scenes

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
        water_balance: bool
            Compute daily Ke values by simulating water balance in evaporable
            zone. Default is False.
    model_args : dict
        Parameters from the MODEL section of the INI file.  The reference
        source and parameters will need to be set here if computing
        reference ET or actual ET.
    t_interval : {'daily', 'monthly', 'annual', 'custom'}, optional
        Time interval over which to interpolate and aggregate values
        The default is 'custom' which means the aggregation time period
        will be controlled by the start and end date parameters.
    use_joins : bool, optional
        If True, use joins to link the target and source collections.
        If False, the source collection will be filtered for each target image.
        This parameter is passed through to interpolate.daily().
    _interp_vars : list, optional
        The variables that can be interpolated to daily timesteps.
        The default is to interpolate the 'et_fraction' and 'ndvi' bands.

    Returns
    -------
    ee.ImageCollection

    Raises
    ------
    ValueError

    """
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

    # Check whether to compute daily Ke
    if 'water_balance' in interp_args.keys():
        water_balance = interp_args['water_balance']
    else:
        water_balance = False

    # Check that the input parameters are valid
    if t_interval.lower() not in ['daily', 'monthly', 'annual', 'custom']:
        raise ValueError('unsupported t_interval: {}'.format(t_interval))
    elif interp_method.lower() not in ['linear']:
        raise ValueError('unsupported interp_method: {}'.format(
            interp_method))

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
    interp_start_dt = start_dt - datetime.timedelta(days=interp_days)
    interp_end_dt = end_dt + datetime.timedelta(days=interp_days)
    interp_start_date = interp_start_dt.date().isoformat()
    interp_end_date = interp_end_dt.date().isoformat()

    # Get reference ET source
    if 'et_reference_source' in model_args.keys():
        et_reference_source = model_args['et_reference_source']
    else:
        raise ValueError('et_reference_source was not set')

    # Get reference ET band name
    if 'et_reference_band' in model_args.keys():
        et_reference_band = model_args['et_reference_band']
    else:
        raise ValueError('et_reference_band was not set')

    # Get reference ET factor
    if 'et_reference_factor' in model_args.keys():
        et_reference_factor = model_args['et_reference_factor']
    else:
        et_reference_factor = 1.0
        logging.debug('et_reference_factor was not set, default to 1.0')
        # raise ValueError('et_reference_factor was not set')

    # CGM - Resampling is not working correctly so commenting out for now
    # # Get reference ET resample
    # if 'et_reference_resample' in model_args.keys():
    #     et_reference_resample = model_args['et_reference_resample']
    # else:
    #     et_reference_resample = 'nearest'
    #     logging.debug('et_reference_resample was not set, default to nearest')
    #     # raise ValueError('et_reference_resample was not set')

    if type(et_reference_source) is str:
        # Assume a string source is an single image collection ID
        #   not an list of collection IDs or ee.ImageCollection
        daily_et_ref_coll = ee.ImageCollection(et_reference_source) \
            .filterDate(start_date, end_date) \
            .select([et_reference_band], ['et_reference'])
    # elif isinstance(et_reference_source, computedobject.ComputedObject):
    #     # Interpret computed objects as image collections
    #     daily_et_ref_coll = ee.ImageCollection(et_reference_source) \
    #         .filterDate(self.start_date, self.end_date) \
    #         .select([et_reference_band])
    else:
        raise ValueError('unsupported et_reference_source: {}'.format(
            et_reference_source))

    # Scale reference ET images (if necessary)
    # CGM - Resampling is not working correctly so not including for now
    if (et_reference_factor and et_reference_factor != 1):
        def et_reference_adjust(input_img):
            return input_img.multiply(et_reference_factor) \
                .copyProperties(input_img) \
                .set({'system:time_start': input_img.get('system:time_start')})

        daily_et_ref_coll = daily_et_ref_coll.map(et_reference_adjust)

    # Initialize variable list to only variables that can be interpolated
    interp_vars = list(set(_interp_vars) & set(variables))

    # To return ET, the ETf must be interpolated
    if 'et' in variables and 'et_fraction' not in interp_vars:
        interp_vars.append('et_fraction')

    # With the current interpolate.daily() function,
    #   something has to be interpolated in order to return et_reference
    if 'et_reference' in variables and 'et_fraction' not in interp_vars:
        interp_vars.append('et_fraction')

    # The time band is always needed for interpolation
    interp_vars.append('time')

    # Filter scene collection to the interpolation range
    # This probably isn't needed since scene_coll was built to this range
    scene_coll = scene_coll.filterDate(interp_start_date, interp_end_date)

    # For count, compute the composite/mosaic image for the mask band only
    if 'count' in variables:
        aggregate_coll = openet.core.interpolate.aggregate_to_daily(
            image_coll = scene_coll.select(['mask']),
            start_date=start_date, end_date=end_date)
        # The following is needed because the aggregate collection can be
        #   empty if there are no scenes in the target date range but there
        #   are scenes in the interpolation date range.
        # Without this the count image will not be built but the other
        #   bands will be which causes a non-homogeneous image collection.
        aggregate_coll = aggregate_coll.merge(
            ee.Image.constant(0).rename(['mask'])
                .set({'system:time_start': ee.Date(start_date).millis()}))

    # Interpolate to a daily time step
    # NOTE: the daily function is not computing ET (ETf x ETo)
    #   but is returning the target (ETo) band
    daily_coll = openet.core.interpolate.daily(
        target_coll=daily_et_ref_coll,
        source_coll=scene_coll.select(interp_vars),
        interp_method=interp_method, interp_days=interp_days,
        use_joins=use_joins,
        compute_product=False,
    )

    if water_balance:
        daily_coll = daily_ke(daily_coll, start_date, end_date,
                                        model_args, **interp_args)

    # The interpolate.daily() function can/will return the product of
    # the source and target image named as "{source_band}_1".
    # The problem with this approach is that is will drop any other bands
    # that are being interpolated (such as the ndvi).
    # daily_coll = daily_coll.select(['et_fraction_1'], ['et'])

    # Compute ET from ETf and ETo (if necessary)
    # This isn't needed if compute_product=True in daily() and band is renamed
    # The check for et_fraction is needed since it is back computed from ET and ETo
    # if 'et' in variables or 'et_fraction' in variables:
    if 'et' in variables or 'et_fraction' in variables:
        def compute_et(img):
            """This function assumes ETr and ETf are present"""
            if water_balance:
                et_frac = img.select(['et_fraction'])
                et_frac = et_frac.where(et_frac.lte(1.15),
                                        et_frac.add(img.select(['ke'])).clamp(0, 1.15))
            else:
                et_frac = img.select(['et_fraction'])
            et_img = et_frac.multiply(img.select(['et_reference']))
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
        if 'et' in variables or 'et_fraction' in variables:
            et_img = daily_coll.filterDate(agg_start_date, agg_end_date) \
                .select(['et']).sum()
        if 'et_reference' in variables or 'et_fraction' in variables:
            # et_reference_img = daily_et_ref_coll \
            et_reference_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .select(['et_reference']).sum()

        image_list = []
        if 'et' in variables:
            image_list.append(et_img.float())
        if 'et_reference' in variables:
            image_list.append(et_reference_img.float())
        if 'et_fraction' in variables:
            # Compute average et fraction over the aggregation period
            image_list.append(
                et_img.divide(et_reference_img).rename(
                    ['et_fraction']).float())
        if 'ndvi' in variables:
            # Compute average ndvi over the aggregation period
            ndvi_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['ndvi']).float()
            image_list.append(ndvi_img)
        if 'ke' in variables:
            ke_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['ke']).float()
            image_list.append(ke_img)
        if 'kr' in variables:
            kr_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['kr']).float()
            image_list.append(kr_img)
        if 'ft' in variables:
            ft_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['ft']).float()
            image_list.append(ft_img)
        if 'de_rew' in variables:
            de_rew_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['de_rew']).float()
            image_list.append(de_rew_img)
        if 'precip' in variables:
            precip_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['precip']).float()
            image_list.append(precip_img)
        if 'de' in variables:
            de_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['de']).float()
            image_list.append(de_img)
        if 'de_prev' in variables:
            de_prev_img = daily_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .mean().select(['de_prev']).float()
            image_list.append(de_prev_img)
        if 'count' in variables:
            count_img = aggregate_coll \
                .filterDate(agg_start_date, agg_end_date) \
                .select(['mask']).sum().rename('count').uint8()
            image_list.append(count_img)

        return ee.Image(image_list) \
            .set({
            'system:index': ee.Date(agg_start_date).format(date_format),
            'system:time_start': ee.Date(agg_start_date).millis()})
        #     .set(interp_properties)\

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
                date_format='YYYYMMdd')

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
                date_format='YYYYMM')

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
                date_format='YYYY')

        return ee.ImageCollection(year_list.map(agg_annual))

    elif t_interval.lower() == 'custom':
        # Returning an ImageCollection to be consistent
        return ee.ImageCollection(aggregate_image(
            agg_start_date=start_date, agg_end_date=end_date,
            date_format='YYYYMMdd'))

def daily_ke(daily_coll, start_date, end_date, model_args,
                       precip_source='IDAHO_EPSCOR/GRIDMET', precip_band='pr',
                       fc_source='projects/eeflux/soils/gsmsoil_mu_a_fc_10cm_albers_100',
                       fc_band='b1',
                       wp_source='projects/eeflux/soils/gsmsoil_mu_a_wp_10cm_albers_100',
                       wp_band='b1', **kwargs):
    """Compute daily Ke values by simulating evaporable zone water balance 
    Parameters
    ----------
    daily_coll : ee.Image
        Collection of daily Kcb images
    start_date : str
        ISO format start date.
    end_date : str
        ISO format end date (exclusive, passed directly to .filterDate()).
    model_args : dict
        Parameters from the MODEL section of the INI file.  The reference
        source and parameters will need to be set here if computing
        reference ET or actual ET.
    precip_source : str, optional
        GEE data source for gridded precipitation data, default is gridMET.
    precip_band : str, option
        GEE Image band that contains gridded precipitaiton data, default is
        'pr', which is the band for gridMET.
    fc_source : ee.Image
        GEE Image of soil field capacity values
    fc_band : str 
        Name of the band in `fc_source` that contains field capacity values
    wp_source : ee.Image
        GEE Image of soil permanent wilting point values
    wp_band : str 
        Name of the band in `wp_source` that contains wilting point values

    Returns
    -------
    ee.ImageCollectionl

    """

    start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    spinup_start_date = start_dt - datetime.timedelta(days=30)
    field_capacity = ee.Image(fc_source).select(fc_band)
    wilting_point = ee.Image(wp_source).select(wp_band)

    # Available water content (mm)
    awc = field_capacity.subtract(wilting_point)

    # Fraction of wetting
    # Setting to 1 for now (precip), but could be lower for irrigation
    frac_wet = ee.Image(1)

    # Depth of evaporable zone
    # Set to 10 cm
    z_e = .1

    # Total evaporable water (mm)
    # Allen et al. 1998 eqn 73
    tew = field_capacity.expression(
        '10*(b()-0.5*wp)*z_e',
        {'wp': wilting_point, 'z_e': z_e}
    )

    # Readily evaporable water (mm)
    rew = awc.expression('0.8+54.4*b()/100')
    rew = rew.where(rew.gt(tew), tew)

    # Coefficients for skin layer retention, Allen (2011)
    c0 = ee.Image(0.8)
    c1 = c0.expression('2*(1-b())')

    # 1.2 is max for grass reference (ETo)
    ke_max = ee.Image(1.2)

    # Fraction of precip that evaps today vs tomorrow
    # .5 is arbitrary
    frac_day_evap = ee.Image(0.5)

    # Get precip collection
    daily_pr_coll = ee.ImageCollection(precip_source) \
        .select(precip_band)

    # Assume soil is at field capacity to start
    # i.e. depletion = 0
    #init_de = ee.Image(ee.Image(0.0).select([0], ['de']))
    #init_de_rew = ee.Image(ee.Image(0.0).select([0], ['de_rew']))
    init_de = tew.select([0], ['de'])
    init_de_rew = rew.select([0], ['de_rew'])
    init_c_eff = ee.Image(init_de \
        .expression(
            "C0+C1*(1-b()/TEW)",
            {'C0': c0, 'C1': c1, 'TEW': tew}) \
        .min(1) \
        .select([0], ['c_eff']))

    # Create list to hold water balance rasters when iterating over collection
    # Doesn't seem like you can create an empty list in ee?
    init_img = ee.Image([init_de, init_de_rew, init_c_eff])
    init_img_list = ee.ImageCollection([init_img]).toList(1)

    # Convert interp collection to list
    interp_list = daily_coll.toList(daily_coll.size())
    # Is list guaranteed to have right order?
    # (Seems to be fine in initial testing.)
    #interp_list = interp_list.sort(ee.List(['system:index']))

    # Perform daily water balance update
    def water_balance_step(img, wb_coll):
        # Explicit cast ee.Image
        prev_img = ee.Image(ee.List(wb_coll).get(-1))
        curr_img = ee.Image(img)

        # Make precip image with bands for today and tomorrow
        curr_date = curr_img.date()
        curr_precip = ee.Image(daily_pr_coll
            .filterDate(curr_date, curr_date.advance(1, 'day')).first()).rename('precip')
        next_precip = ee.Image(daily_pr_coll
            .filterDate(curr_date.advance(1, 'day'), curr_date.advance(2, 'day')).first())
        precip_img = ee.Image([curr_precip, next_precip]) \
            .rename(['current', 'next'])

        # Fraction of day stage 1 evap
        # Allen 2011, eq 12
        ft = rew.expression(
            '(b()-de_rew_prev)/(ke_max*eto)',
            {
                'de_rew_prev': prev_img.select('de_rew'),
                'rew': rew,
                'ke_max': ke_max,
                'eto': curr_img.select('et_reference')}).clamp(0.0, 1.0).rename('ft')

        # Soil evap reduction coeff, FAO 56
        kr = tew.expression(
            "(b()-de_prev)/(b()-rew)",
            {
                'de_prev': prev_img.select('de'),
                'rew': rew}).clamp(0.0, 1.0).rename('kr')
        
        de_prev = prev_img.select('de').rename('de_prev')

        # precip only for now
        # irrigation might have lower f_w
        fw = prev_img.select('de').multiply(0).add(1).rename('fw')
        low_few = fw.multiply(0).add(0.01).rename('low_few')
        fc = curr_img.select('ndvi').multiply(1.26).subtract(0.18).rename('fc')
        few = fw.min(fc.multiply(-1).add(1)).max(low_few).rename('few')

        # Soil evap coeff, FAO 56
        ke = ft.expression(
            "(b() + (1 - b()) * kr) * ke_max",
            {
                'kr': kr,
                'ke_max': ke_max}).rename('ke')
        ke = ke.min(few.multiply(ke_max))

        # Dual crop coefficient: Kc = Kcb + Ke
        #kc = ke.add(curr_img.select('et_fraction')).rename('kc')

        # Crop ET (note that Kc in other parts of code refers to *basal*
        # crop coeff (Kcb))
        #etc = kc.multiply(curr_img.select('et_reference')).rename('etc')

        # ETe - bare soil evaporation
        ete = ke.multiply(curr_img.select('et_reference')).rename('ete')

        # Depletion, FAO 56
        de = prev_img.select('de') \
            .subtract(
                frac_day_evap
                    .multiply(ee.Image(precip_img.select('next')))
                    .add(
                        ee.Image(1)
                            .subtract(frac_day_evap)
                            .multiply(precip_img.select('current')))) \
            .add(ete.divide(few.select('few'))) \
            .select([0], ['de']).rename('de')

        # Can't have negative depletion
        de = de.min(tew).max(0)

        # Stage 1 depletion (REW)
        # Allen 2011
        de_rew = prev_img.select('de_rew')\
            .subtract(
                frac_day_evap
                    .multiply(precip_img.select('next'))
                    .add(
                        ee.Image(1)
                        .subtract(frac_day_evap)
                        .multiply(precip_img.select('current'))
                    )
                    .multiply(prev_img.select('c_eff'))
            ) \
        .add(ete.divide(few.select('few'))) \
        .select([0], ['de_rew']).rename('de_rew')

        # Can't have negative depletion
        de_rew = de_rew.min(rew).max(0)

        # Efficiency of skin layer
        # Allen 2011, eq 15
        c_eff = de \
            .expression(
                "c0+c1*(1-b()/tew)",
                {'c0': c0, 'c1': c1, 'tew': tew}
            ) \
            .min(1) \
            .select([0], ['c_eff'])

        # Make image to add to list
        new_day_img = ee.Image(
            curr_img.addBands(
                ee.Image([de, de_rew, c_eff, ke, kr, ft, de, de_rew, de_prev, ete, curr_precip, ft])
            )
        )

        return ee.List(wb_coll).add(new_day_img)

    daily_coll = interp_list.iterate(water_balance_step, init_img_list)
    # remove dummy first element
    daily_coll = ee.List(daily_coll).slice(1, ee.List(daily_coll).size())
    daily_coll = ee.ImageCollection.fromImages(daily_coll)

    return daily_coll
