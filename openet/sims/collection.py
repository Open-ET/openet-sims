# title           : collection.py
# description     : Script used to run the Earth Engine version of SIMS for an image collection.
#                   This is based on the Charles Morton's openET model
#                   template(https://github.com/Open-ET/openet-ndvi-beta).
#                   This is an early version that comes without support and
#                   might change at anytime without notice
# author          : Alberto Guzman
# date            : 03-01-2017
# version         : 0.1
# usage           :
# notes           :
# python_version  : 3.2

import datetime
import pprint

from dateutil.relativedelta import *
import ee

from . import utils
from .image import Image
# Importing to get version number, is there a better way?
import openet.sims
import openet.core.interp as interp
# TODO: import utils from openet.core
# import openet.core.utils as utils


def lazy_property(fn):
    """Decorator that makes a property lazy-evaluated

    https://stevenloria.com/lazy-properties/
    """
    attr_name = '_lazy_' + fn.__name__

    @property
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazy_property


class Collection():
    """"""

    def __init__(
            self,
            collections,
            start_date,
            end_date,
            geometry,
            variables=None,
            cloud_cover_max=70,
            # CGM - Should should probably not be separate parameters and should
            #   only be set through model_args or kwargs
            etr_source=None,
            etr_band=None,
            etr_factor=None,
            filter_args=None,
            # CGM: Should model_args be split up into image_args, model_args?
            model_args=None,
            # model_args={'etr_source': 'IDAHO_EPSCOR/GRIDMET',
            #             'etr_band': 'etr',
            #             'etr_factor': 1.0},
            # **kwargs
        ):
        """Earth Engine based SIMS ETcb Image Collection object

        Parameters
        ----------
        collections : list, str
            GEE satellite image collection IDs.
        start_date : str
            ISO format inclusive start date (i.e. YYYY-MM-DD).
        end_date : str
            ISO format exclusive end date (i.e. YYYY-MM-DD).
            This date needs to be exclusive since it will be passed directly
            to the .filterDate() calls.
        geometry : ee.Geometry
            The geometry object will be used to filter the input collections
            using the ee.ImageCollection.filterBounds() method.
        variables : list, optional
            Output variables can also be specified in the method calls.
        cloud_cover_max : float
            Maximum cloud cover percentage (the default is 70%).
                - Landsat SR: CLOUD_COVER_LAND
                - Sentinel2: CLOUDY_PIXEL_PERCENTAGE
        etr_source : str, float, optional
            Reference ET source (the default is None).  Parameter must
            be set here (in class init) or model args to compute ET or ETr.
        etr_band : str, optional
            Reference ET band name (the default is None).  Parameter must
            be set here (in class init) or model args to compute ET or ETr.
        etr_factor : float, optional
            Reference ET scaling factor (the default is None).  Parameter must
            be set here (in class init) or model args to compute ET or ETr.
        filter_args : dict
            Image collection filter keyword arguments (the default is None).
            Organize filter arguments as a nested dictionary with the primary
            key being the collection ID.
        model_args : dict
            Model Image initialization keyword arguments (the default is None).
            Dictionary will be passed through to model Image init.

        """
        self.collections = collections
        self.variables = variables
        self.start_date = start_date
        self.end_date = end_date
        self.geometry = geometry
        self.cloud_cover_max = cloud_cover_max

        # CGM - Should we check that model_args and filter_args are dict?
        if model_args is not None:
            self.model_args = model_args
        else:
            self.model_args = {}
        if filter_args is not None:
            self.filter_args = filter_args
        else:
            self.filter_args = {}

        # Pass the ETr parameters through as model keyword arguments
        self.etr_source = etr_source
        self.etr_band = etr_band
        self.etr_factor = etr_factor
        if etr_source is not None:
            self.model_args['etr_source'] = etr_source
        if etr_band is not None:
            self.model_args['etr_band'] = etr_band
        if etr_factor is not None:
            self.model_args['etr_factor'] = etr_factor

        # Model specific variables that can be interpolated to a daily timestep
        # Should this be specified in the interpolation method instead?
        self._interp_vars = ['ndvi', 'etf']

        self._landsat_c1_sr_collections = [
            'LANDSAT/LC08/C01/T1_SR',
            'LANDSAT/LE07/C01/T1_SR',
            'LANDSAT/LT05/C01/T1_SR',
            'LANDSAT/LT04/C01/T1_SR',
        ]

        # If collections is a string, place in a list
        if type(self.collections) is str:
            self.collections = [self.collections]

        # Check that collection IDs are supported
        for coll_id in self.collections:
            if (coll_id not in self._landsat_c1_sr_collections):
                raise ValueError('unsupported collection: {}'.format(coll_id))

        # Check that collections don't have "duplicates"
        #   (i.e TOA and SR or TOA and TOA_RT for same Landsat)
        def duplicates(x):
            return len(x) != len(set(x))
        if duplicates([c.split('/')[1] for c in self.collections]):
            raise ValueError('duplicate landsat types in collection list')

        # Check start/end date
        if not utils.valid_date(self.start_date):
            raise ValueError('start_date is not a valid')
        elif not utils.valid_date(self.end_date):
            raise ValueError('end_date is not valid')
        elif not self.start_date < self.end_date:
            raise ValueError('end_date must be after start_date')

        # Check cloud_cover_max
        if (not type(self.cloud_cover_max) is int and
                not type(self.cloud_cover_max) is float and
                not utils.is_number(self.cloud_cover_max)):
            raise TypeError('cloud_cover_max must be a number')
        if (type(self.cloud_cover_max) is str and
                utils.is_number(self.cloud_cover_max)):
            self.cloud_cover_max = float(self.cloud_cover_max)
        if self.cloud_cover_max < 0 or self.cloud_cover_max > 100:
            raise ValueError('cloud_cover_max must be in the range 0 to 100')

        # Check geometry?
        # if not isinstance(self.geometry, computedobject.ComputedObject):
        #     raise ValueError()

        # Filter collection list based on start/end dates
        if self.end_date <= '1982-01-01':
            self.collections = [c for c in self.collections if 'LT04' not in c]
        if self.start_date >= '1994-01-01':
            self.collections = [c for c in self.collections if 'LT04' not in c]
        if self.end_date <= '1984-01-01':
            self.collections = [c for c in self.collections if 'LT05' not in c]
        if self.start_date >= '2012-01-01':
            self.collections = [c for c in self.collections if 'LT05' not in c]
        if self.end_date <= '1999-01-01':
            self.collections = [c for c in self.collections if 'LE07' not in c]
        if self.end_date <= '2013-01-01':
            self.collections = [c for c in self.collections if 'LC08' not in c]
        # if self.end_date <= '2015-01-01':
        #     self.collections = [c for c in self.collections if 'COPERNICUS' not in c]

    def _build(self, variables=None, start_date=None, end_date=None):
        """Build a merged model variable image collection

        Parameters
        ----------
        variables : list
            Set a variable list that is different than the class variable list.
        start_date : str, optional
            Set a start_date that is different than the class start_date.
            This is needed when defining the scene collection to have extra
            images for interpolation.
        end_date : str, optional
            Set a end_date that is different than the class end_date.

        Returns
        -------
        ee.ImageCollection

        Raises
        ------
        ValueError if collection IDs are invalid.

        """

        # Override the class parameters if necessary
        if variables is None:
            if self.variables:
                variables = self.variables
            else:
                raise ValueError('variables parameter must be set')
        if start_date is None or not start_date:
            start_date = self.start_date
        if end_date is None :
            end_date = self.end_date

        # Build the variable image collection
        variable_coll = ee.ImageCollection([])
        for coll_id in self.collections:
            if coll_id in self._landsat_c1_sr_collections:
                input_coll = ee.ImageCollection(coll_id)\
                    .filterDate(start_date, end_date)\
                    .filterBounds(self.geometry)\
                    .filterMetadata('CLOUD_COVER_LAND', 'less_than',
                                    self.cloud_cover_max)

                # TODO: Need to come up with a system for applying
                #   generic filter arguments to the collections
                if coll_id in self.filter_args.keys():
                    for f in self.filter_args[coll_id]:
                        try:
                            filter_type = f.pop('type')
                        except KeyError:
                            continue
                        if filter_type.lower() == 'equals':
                            input_coll = input_coll.filter(ee.Filter.equals(**f))

                def compute_lsr(image):
                    model_obj = Image.from_landsat_c1_sr(
                        sr_image=ee.Image(image), **self.model_args)
                    return model_obj.calculate(variables)

                variable_coll = variable_coll.merge(
                    ee.ImageCollection(input_coll.map(compute_lsr)))

            else:
                raise ValueError('unsupported collection: {}'.format(coll_id))

        return variable_coll

    def overpass(self, variables=None):
        """Return a collection of computed values for the overpass images

        Parameters
        ----------
        variables : list, optional
            List of variables that will be returned in the Image Collection.
            If variables is not set here it must be specified in the class
            instantiation call.

        Returns
        -------
        ee.ImageCollection

        Raises
        ------
        ValueError

        """
        # Does it make sense to use the class variable list if not set?
        if not variables:
            if self.variables:
                variables = self.variables
            else:
                raise ValueError('variables parameter must be set')

        return self._build(variables=variables)

    def interpolate(self, variables=None, t_interval='custom',
                    interp_method='linear', interp_days=32,
                    # CGM - The etr params should probably not be inputs
                    etr_source=None, etr_band=None, etr_factor=None,
                    output_type='float'):
        """

        Parameters
        ----------
        variables : list, optional
            List of variables that will be returned in the Image Collection.
            If variables is not set here it must be specified in the class
            instantiation call.
        t_interval : {'daily', 'monthly', 'annual', 'custom'}, optional
            Time interval over which to interpolate and aggregate values
            (the default is 'monthly').
        interp_method : {'linear}, optional
            Interpolation method (the default is 'linear').
        interp_days : int, str, optional
            Number of extra days before the start date and after the end date
            to include in the interpolation calculation. (the default is 32).
        etr_source : str, float, optional
            Reference ET source (the default is None).  Parameter must be
            set here, in class init, or in model_args (searched in that order).
        etr_band : str, optional
            Reference ET band name (the default is None).  Parameter must be
            set here, in class init, or in model_args (searched in that order).
        etr_factor : float, optional
            Reference ET scaling factor (the default is 1.0).
        output_type : {'int8', 'uint8', 'int16', 'float', 'double'}, optional
            Output data type for the ET and ETr bands (the default is 'float').
            NDVI and ETf bands will always be written as float type.
            Count band will always be written as uint8 type.

        Returns
        -------
        ee.ImageCollection

        Raises
        ------
        ValueError for unsupported input parameters
        ValueError for negative interp_days values
        TypeError for non-integer interp_days

        Notes
        -----
        Not all variables can be interpolated to new time steps.
        Variables like ETr are simply summed whereas ETf is computed from the
        interpolated/aggregated values.

        """
        # Check that the input parameters are valid
        if t_interval.lower() not in ['daily', 'monthly', 'annual', 'custom']:
            raise ValueError('unsupported t_interval: {}'.format(t_interval))
        elif interp_method.lower() not in ['linear']:
            raise ValueError('unsupported interp_method: {}'.format(
                interp_method))

        if type(interp_days) is str and utils.is_number(interp_days):
            interp_days = int(interp_days)
        elif not type(interp_days) is int:
            raise TypeError('interp_days must be an integer')
        elif interp_days <= 0:
            raise ValueError('interp_days must be a positive integer')

        # Does it make sense to use the class variable list if not set?
        if not variables:
            if self.variables:
                variables = self.variables
            else:
                raise ValueError('variables parameter must be set')

        output_types = ['int8', 'uint8', 'int16', 'uint16', 'float', 'double']
        if output_type.lower() not in output_types:
            raise ValueError('unsupported output_type: {}'.format(output_type))

        # Adjust start/end dates based on t_interval
        # Increase the date range to fully include the time interval
        start_dt = datetime.datetime.strptime(self.start_date, '%Y-%m-%d')
        end_dt = datetime.datetime.strptime(self.end_date, '%Y-%m-%d')
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

        # TODO: model_args needs to be updated if the etr parameters were set on the interpolate call directly

        # Get ETr source
        if etr_source is not None:
            self.model_args['etr_source'] = etr_source
        elif self.etr_source is not None:
            self.model_args['etr_source']  = self.etr_source
        elif ('etr_source' in self.model_args.keys() and
                self.model_args['etr_source']):
            pass
        else:
            raise ValueError('etr_source was not set')

        # Get ETr band name
        if etr_band is not None:
            self.model_args['etr_band'] = etr_band
        elif self.etr_band is not None:
            self.model_args['etr_band']  = self.etr_band
        elif ('etr_band' in self.model_args.keys() and
                self.model_args['etr_band']):
            pass
        else:
            raise ValueError('etr_band was not set')

        # Get ETr factor
        if etr_factor is not None:
            self.model_args['etr_factor'] = etr_factor
        elif self.etr_factor is not None:
            self.model_args['etr_factor']  = self.etr_factor
        elif 'etr_factor' in self.model_args.keys():
            pass
        else:
            raise ValueError('etr_factor was not set')

        if type(self.model_args['etr_source']) is str:
            # Assume a string source is an single image collection ID
            #   not an list of collection IDs or ee.ImageCollection
            daily_etr_coll = ee.ImageCollection(self.model_args['etr_source'])\
                .filterDate(start_date, end_date)\
                .select([self.model_args['etr_band']], ['etr'])
        # elif type(self.model_args['etr_source']) is list:
        #     # Interpret as list of image collection IDs to composite/mosaic
        #     #   i.e. Spatial CIMIS and GRIDMET
        #     # CGM - The following from the Image class probably won't work
        #     #   I think the two collections will need to be joined together,
        #     #   probably in some sort of mapped function
        #     daily_etr_coll = ee.ImageCollection([])
        #     for coll_id in self.model_args['etr_source']:
        #         coll = ee.ImageCollection(coll_id)\
        #             .select([self.model_args['etr_band']])\
        #             .filterDate(self.start_date, self.end_date)
        #         daily_etr_coll = daily_etr_coll.merge(coll)
        # elif isinstance(self.model_args['etr_source'], computedobject.ComputedObject):
        #     # Interpret computed objects as image collections
        #     daily_etr_coll = ee.ImageCollection(self.model_args['etr_source'])\
        #         .select([self.model_args['etr_band']])\
        #         .filterDate(self.start_date, self.end_date)
        else:
            raise ValueError('unsupported etr_source: {}'.format(etr_source))

        # Initialize variable list to only variables that can be interpolated
        interp_vars = list(set(self._interp_vars) & set(variables))

        # To return ET, the ETf must be interpolated
        if 'et' in variables and 'etf' not in interp_vars:
            interp_vars.append('etf')

        # With the current interp.daily() function,
        #   something has to be interpolated in order to return etr
        if 'etr' in variables and 'etf' not in interp_vars:
            interp_vars.append('etf')

        # The time band is always needed for interpolation
        interp_vars.append('time')

        # Count will be determined using the aggregate_coll image masks
        if 'count' in variables:
            interp_vars.append('mask')
            # interp_vars.remove('count')

        # Build initial scene image collection
        scene_coll = self._build(
            variables=interp_vars, start_date=interp_start_date,
            end_date=interp_end_date)

        # For count, compute the composite/mosaic image for the mask band only
        if 'count' in variables:
            aggregate_coll = interp.aggregate_daily(
                image_coll=scene_coll.select(['mask']),
                start_date=start_date, end_date=end_date,
            )

        # Including count/mask causes problems in interp.daily() function.
        # Issues with mask being an int but the values need to be double.
        # Casting the mask band to a double would fix this problem also.
        if 'mask' in interp_vars:
            interp_vars.remove('mask')

        # Interpolate to a daily time step
        # NOTE: the daily function is not computing ET (ETf x ETr)
        #   but is returning the target (ETr) band
        daily_coll = interp.daily(
            target_coll=daily_etr_coll,
            source_coll=scene_coll.select(interp_vars),
            interp_method=interp_method, interp_days=interp_days,
        )

        # DEADBEEF - Originally all variables were being aggregated
        # It may be sufficient to only aggregate the mask/count variable,
        #   since all other variables will be interpolated using the 0 UTC time
        #
        # # Compute composite/mosaic images for each image date
        # aggregate_coll = interp.aggregate_daily(
        #     image_coll=scene_coll,
        #     start_date=interp_start_date,
        #     end_date=interp_end_date)
        #
        # # Including count/mask causes problems in interp.daily() function.
        # # Issues with mask being an int but the values need to be double.
        # # Casting the mask band to a double would fix this problem also.
        # if 'mask' in interp_vars:
        #     interp_vars.remove('mask')
        #
        # # Interpolate to a daily time step
        # # NOTE: the daily function is not computing ET (ETf x ETr)
        # #   but is returning the target (ETr) band
        # daily_coll = interp.daily(
        #     target_coll=daily_etr_coll,
        #     source_coll=aggregate_coll.select(interp_vars),
        #     interp_method=interp_method,  interp_days=interp_days)

        # Compute ET from ETf and ETr (if necessary)
        if 'et' in variables or 'etf' in variables:
            def compute_et(img):
                """This function assumes ETr and ETf are present"""
                et_img = img.select(['etf']).multiply(img.select(['etr']))
                return img.addBands(et_img.rename('et'))
                # img_dt = ee.Date(img.get('system:time_start'))
                # etr_coll = daily_etr_coll\
                #     .filterDate(img_dt, img_dt.advance(1, 'day'))
                # Set ETr to Landsat resolution/projection?
                # etr_img = img.select(['etf']).multiply(0)\
                #     .add(ee.Image(etr_coll.first())).rename('etr')
                # et_img = img.select(['etf']).multiply(etr_img).rename('et')
                # return img.addBands(et_img)
            daily_coll = daily_coll.map(compute_et)

        # DEADBEEF - Some of the following functionality could be moved to core
        #   since the functionality is basically identical for all t_interval
        interp_properties = {
            'cloud_cover_max': self.cloud_cover_max,
            'collections': ', '.join(self.collections),
            'interp_days': interp_days,
            'interp_method': interp_method,
            'model_name': openet.sims.MODEL_NAME,
            'model_version': openet.sims.__version__,
        }
        interp_properties.update(self.model_args)

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
            # if 'et' in variables or 'etf' in variables:
            et_img = daily_coll.filterDate(agg_start_date, agg_end_date)\
                .select(['et']).sum().multiply(self.model_args['etr_factor'])
            # if 'etr' in variables or 'etf' in variables:
            etr_img = daily_coll.filterDate(agg_start_date, agg_end_date)\
                .select(['etr']).sum().multiply(self.model_args['etr_factor'])

            # Round and save ET and ETr as integer values to save space
            # Ensure that ETr > 0 after rounding to avoid divide by zero
            # Compute ETf from the rounded values
            if output_type.lower() == 'int16':
                etf_img = et_img.round().divide(etr_img.round().max(1)).float()
                et_img = et_img.round().int16()
                etr_img = etr_img.round().int16()
            elif output_type.lower() == 'uint16':
                etf_img = et_img.round().divide(etr_img.round().max(1)).float()
                et_img = et_img.round().uint16()
                etr_img = etr_img.round().uint16()
            elif output_type.lower() == 'int8':
                etf_img = et_img.round().divide(etr_img.round().max(1)).float()
                et_img = et_img.round().int8()
                etr_img = etr_img.round().int8()
            elif output_type.lower() == 'uint8':
                etf_img = et_img.round().divide(etr_img.round().max(1)).float()
                et_img = et_img.round().uint8()
                etr_img = etr_img.round().uint8()
            elif output_type.lower() == 'float':
                etf_img = et_img.divide(etr_img).float()
                et_img = et_img.float()
                etr_img = etr_img.float()
            elif output_type.lower() == 'double':
                # Casting to double may be redundant since these values should
                #   all be doubles be default
                etf_img = et_img.divide(etr_img).double()
                et_img = et_img.double()
                etr_img = etr_img.double()

            image_list = []
            if 'et' in variables:
                image_list.append(et_img)
            if 'etr' in variables:
                image_list.append(etr_img)
            if 'etf' in variables:
                image_list.append(etf_img.rename(['etf']))
            if 'ndvi' in variables:
                ndvi_img = daily_coll\
                    .filterDate(agg_start_date, agg_end_date)\
                    .mean().select(['ndvi']).float()
                image_list.append(ndvi_img)
            if 'count' in variables:
                count_img = aggregate_coll\
                    .filterDate(agg_start_date, agg_end_date)\
                    .select(['mask']).count().rename('count').uint8()
                image_list.append(count_img)

            return ee.Image(image_list)\
                .set(interp_properties)\
                .set({
                    'system:index': ee.Date(agg_start_date).format(date_format),
                    'system:time_start': ee.Date(agg_start_date).millis(),
                })

        # Combine input, interpolated, and derived values
        if t_interval.lower() == 'daily':
            def aggregate_daily(daily_img):
                # CGM - Double check that this time_start is a 0 UTC time.
                # It should be since it is coming from the interpolate source
                #   collection, but what if source is GRIDMET (+6 UTC)?
                agg_start_date = ee.Date(daily_img.get('system:time_start'))
                # CGM - This calls .sum() on collections with only one image
                return aggregate_image(
                    agg_start_date=agg_start_date,
                    agg_end_date=ee.Date(agg_start_date).advance(1, 'day'),
                    date_format='YYYYMMdd')

            return ee.ImageCollection(daily_coll.map(aggregate_daily))

        elif t_interval.lower() == 'monthly':
            def month_gen(iter_start_dt, iter_end_dt):
                iter_dt = iter_start_dt
                # Conditional is "less than" because end date is exclusive
                while iter_dt < iter_end_dt:
                    yield iter_dt.strftime('%Y-%m-%d')
                    iter_dt += relativedelta(months=+1)
            month_list = ee.List(list(month_gen(start_dt, end_dt)))

            def aggregate_monthly(agg_start_date):
                return aggregate_image(
                    agg_start_date=agg_start_date,
                    agg_end_date=ee.Date(agg_start_date).advance(1, 'month'),
                    date_format='YYYYMM')

            return ee.ImageCollection(month_list.map(aggregate_monthly))

        elif t_interval.lower() == 'annual':
            def year_gen(iter_start_dt, iter_end_dt):
                iter_dt = iter_start_dt
                while iter_dt < iter_end_dt:
                    yield iter_dt.strftime('%Y-%m-%d')
                    iter_dt += relativedelta(years=+1)
            year_list = ee.List(list(year_gen(start_dt, end_dt)))

            def aggregate_annual(agg_start_date):
                return aggregate_image(
                    agg_start_date=agg_start_date,
                    agg_end_date=ee.Date(agg_start_date).advance(1, 'year'),
                    date_format='YYYY')

            return ee.ImageCollection(year_list.map(aggregate_annual))

        elif t_interval.lower() == 'custom':
            # Returning an ImageCollection to be consistent
            return ee.ImageCollection(aggregate_image(
                agg_start_date=start_date, agg_end_date=end_date,
                date_format='YYYYMMdd'))

    def get_image_ids(self):
        """Return image IDs of the input images

        Returns
        -------
        list

        """
        # DEADBEEF - This doesn't return the extra images used for interpolation
        #   and may not be that useful of a method
        # CGM - Could the build function and Image class support returning
        #   the system:index?
        output = list(self._build(variables=['ndvi'])\
            .aggregate_histogram('image_id').getInfo().keys())
        return sorted(output)
        # Strip merge indices (this works for Landsat and Sentinel image IDs
        # return sorted(['_'.join(x.split('_')[-3:]) for x in output])
