import ee
import openet.core.common

from .model import Model
# from . import model
from . import utils
# import utils


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


class Image():
    """GEE based model for computing SIMS ETcb"""

    def __init__(
        self,
        image,
        crop_type_source='USDA/NASS/CDL',
        crop_type_remap='CDL',
        crop_type_kc_flag=False,
        crop_type_annual_skip_flag=False,
        et_reference_source=None,
        et_reference_band=None,
        et_reference_factor=None,
        et_reference_resample=None,
        mask_non_ag_flag=False,
        water_kc_flag=True,
        reflectance_type='SR',
    ):
        """Earth Engine based SIMS image object

        Parameters
        ----------
        image : ee.Image
            Required band: ndvi
            Required properties: system:time_start, system:index, system:id
        crop_type_source : str, optional
            Crop type source.  The default is the Cropland Data Layer (CDL) assets.
            Source should be an EE image or collection ID (or ee.Image).
            Currently only the OpenET crop type and CDL images are supported.
        crop_type_remap : {'CDL'}, optional
            Currently only CDL crop type values are supported.
        crop_type_kc_flag : bool, optional
            If True, compute Kc using crop type specific coefficients.
            If False, use generic crop class coefficients.
            The default is False.
        crop_type_annual_skip_flag : bool, optional
            If True, the crop type specific coefficients are NOT used for annual crops.
            If False, the crop type specific coefficients are used for annual crops.
            This flag is only applied/used if crop_type_kc_flag is also True.
            The default is False.
        et_reference_source : str, float, optional
            Reference ET source (the default is None).
            Parameter is required if computing 'et' or 'et_reference'.
        et_reference_band : str, optional
            Reference ET band name (the default is None).
            Parameter is required if computing 'et' or 'et_reference'.
        et_reference_factor : float, None, optional
            Reference ET scaling factor.  The default is None which is
            equivalent to 1.0 (or no scaling).
        et_reference_resample : {'nearest', 'bilinear', 'bicubic', None}, optional
            Reference ET resampling.  The default is None which is equivalent
            to nearest neighbor resampling.
        mask_non_ag_flag : bool, optional
            If True, mask all pixels that don't map to a crop_class.
            The default is False.
        water_kc_flag : bool, optional
            If True, set Kc for water pixels to 1.05.  The default is True.
        reflectance_type : {'SR', 'TOA'}, optional
            Used to select the fractional cover equation (the default is 'SR').

        Notes
        -----
        Fc = (NDVI * 1.26) - 0.18
        Kc = f(Fc) [based on crop type or crop class]
        ETcb = Kc * ETo

        References
        ----------
        .. [1] Johnson, L. and T. Trout, 2012. Satellite NDVI assisted
            monitoring of vegetable crop evapotranspiration in California's San
            Joaquin Valley. Remote Sensing 4:439-455. [EQN 1]

        """
        self.image = image

        # Get system properties from the input image
        self._id = self.image.get('system:id')
        self._index = self.image.get('system:index')
        self._time_start = self.image.get('system:time_start')
        self._properties = {
            'system:index': self._index,
            'system:time_start': self._time_start,
            'image_id': self._id,
        }

        # Build date properties from the system:time_start
        self._date = ee.Date(self._time_start)
        self._year = ee.Number(self._date.get('year'))
        self._start_date = ee.Date(utils.date_0utc(self._date).millis())
        self._end_date = self._start_date.advance(1, 'day')
        self._doy = self._date.getRelative('day', 'year').add(1).int()

        # Reference ET parameters
        self.et_reference_source = et_reference_source
        self.et_reference_band = et_reference_band
        self.et_reference_factor = et_reference_factor
        self.et_reference_resample = et_reference_resample

        # Check reference ET parameters
        if et_reference_factor and not utils.is_number(et_reference_factor):
            raise ValueError('et_reference_factor must be a number')
        if et_reference_factor and self.et_reference_factor < 0:
            raise ValueError('et_reference_factor must be greater than zero')
        et_reference_resample_methods = ['nearest', 'bilinear', 'bicubic']
        if (et_reference_resample and
                et_reference_resample.lower() not in et_reference_resample_methods):
            raise ValueError('unsupported et_reference_resample method')

        self.reflectance_type = reflectance_type

        # CGM - Model class could inherit these from Image instead of passing them
        #   Could pass time_start instead of separate year and doy
        self.model = Model(
            year=self._year,
            doy=self._doy,
            crop_type_source=crop_type_source,
            crop_type_remap=crop_type_remap,
            crop_type_kc_flag=crop_type_kc_flag,
            crop_type_annual_skip_flag=crop_type_annual_skip_flag,
            mask_non_ag_flag=mask_non_ag_flag,
            water_kc_flag=water_kc_flag,
            reflectance_type=reflectance_type,
        )

    def calculate(self, variables=['et']):
        """Return a multiband image of calculated variables

        Parameters
        ----------
        variables : list

        Returns
        -------
        ee.Image

        """
        output_images = []
        for v in variables:
            if v.lower() == 'et':
                output_images.append(self.et.float())
            elif v.lower() == 'et_reference':
                output_images.append(self.et_reference.float())
            elif v.lower() == 'et_fraction':
                output_images.append(self.et_fraction.float())
            # elif v.lower() == 'crop_class':
            #     output_images.append(self.crop_class)
            # elif v.lower() == 'crop_type':
            #     output_images.append(self.crop_type)
            elif v.lower() == 'fc':
                output_images.append(self.fc.float())
            elif v.lower() == 'kc':
                output_images.append(self.kc.float())
            elif v.lower() == 'mask':
                output_images.append(self.mask)
            elif v.lower() == 'ndvi':
                output_images.append(self.ndvi.float())
            elif v.lower() == 'time':
                output_images.append(self.time)
            else:
                raise ValueError(f'unsupported variable: {v}')

        return ee.Image(output_images).set(self._properties)

    @lazy_property
    def et_fraction(self):
        """Fraction of reference ET (equivalent to the Kc)

        This method is basically identical to the "kc" method and is only
        provided to simplify interaction with the interpolation tools in the
        Collection.

        Returns
        -------
        ee.Image

        """
        return self.kc.rename(['et_fraction']).set(self._properties)
        # ET fraction could also be calculated from ET and ET reference
        # return self.et.divide(self.et_reference)\
        #     .rename(['et_fraction']).set(self._properties)

    @lazy_property
    def et_reference(self):
        """Reference ET for the image date

        Returns
        -------
        ee.Image

        """
        if utils.is_number(self.et_reference_source):
            # Interpret numbers as constant images
            # CGM - Should we use the ee_types here instead?
            #   i.e. ee.ee_types.isNumber(self.et_reference_source)
            et_reference_img = ee.Image.constant(self.et_reference_source)
        elif type(self.et_reference_source) is str:
            # Assume a string source is an image collection ID (not an image ID)
            et_reference_coll = (
                ee.ImageCollection(self.et_reference_source)
                .filterDate(self._start_date, self._end_date)
                .select([self.et_reference_band])
            )
            et_reference_img = ee.Image(et_reference_coll.first())
            if self.et_reference_resample in ['bilinear', 'bicubic']:
                et_reference_img = et_reference_img.resample(self.et_reference_resample)
        else:
            raise ValueError(
                f'unsupported et_reference_source: {self.et_reference_source}'
            )

        if self.et_reference_factor:
            et_reference_img = et_reference_img.multiply(self.et_reference_factor)

        return (
            self.ndvi.multiply(0).add(et_reference_img)
            .rename(['et_reference']).set(self._properties)
        )

    @lazy_property
    def et(self):
        """Actual ET (ETcb)

        Returns
        -------
        ee.Image

        """
        return self.kc.multiply(self.et_reference).rename(['et']).set(self._properties)

    @lazy_property
    def crop_class(self):
        """Generic crop classes

        Returns
        -------
        ee.Image

        """
        # Map the crop class values to the NDVI image
        return (
            self.ndvi.multiply(0).add(self.model.crop_class)
            .rename('crop_class').set(self._properties)
        )

    @lazy_property
    def crop_type(self):
        """Crop type

        Returns
        -------
        ee.Image

        """
        # Map the crop class values to the NDVI image
        # Crop type image ID property is set in model function
        return self.ndvi.multiply(0).add(self.model.crop_type).rename(['crop_type'])

    @lazy_property
    def fc(self):
        """Fraction of cover (fc)

        Returns
        -------
        ee.Image

        """
        return self.model.fc(self.ndvi).rename(['fc']).set(self._properties)

    @lazy_property
    def kc(self):
        """Crop coefficient (Kc)

        Returns
        -------
        ee.Image

        """
        return self.model.kc(self.ndvi).rename(['kc']).set(self._properties)

    @lazy_property
    def mask(self):
        """Mask of all active pixels based on the final Kc

        Using Kc here to capture any masking that might be in the crop_type

        Returns
        -------
        ee.Image

        """
        return (
            self.kc.multiply(0).add(1).updateMask(1)
            .rename(['mask']).set(self._properties).uint8()
        )

    @lazy_property
    def ndvi(self):
        """Normalized difference vegetation index (NDVI)

        Returns
        -------
        ee.Image

        """
        return self.image.select(['ndvi']).set(self._properties)

    # @lazy_property
    # def quality(self):
    #     """Set quality to 1 for all active pixels (for now)"""
    #     return (
    #         self.mask
    #         .rename(['quality']).set(self._properties)
    #     )

    @lazy_property
    def time(self):
        """Image of the 0 UTC time (in milliseconds)

        Returns
        -------
        ee.Image

        """
        return (
            self.mask
            .double().multiply(0).add(utils.date_0utc(self._date).millis())
            .rename(['time']).set(self._properties)
        )

    @classmethod
    def from_image_id(cls, image_id, **kwargs):
        """Construct a SIMS Image instance from an image ID

        Parameters
        ----------
        image_id : str
            A full earth engine image ID.
            (i.e. 'LANDSAT/LC08/C02/T1_L2/LC08_044033_20170716')
        kwargs : dict
            Keyword arguments to pass through to model init.

        Returns
        -------
        new instance of Image class

        Raises
        ------
        ValueError for an unsupported collection ID.

        """
        collection_methods = {
            'LANDSAT/LC09/C02/T1_L2': 'from_landsat_c2_sr',
            'LANDSAT/LC08/C02/T1_L2': 'from_landsat_c2_sr',
            'LANDSAT/LE07/C02/T1_L2': 'from_landsat_c2_sr',
            'LANDSAT/LT05/C02/T1_L2': 'from_landsat_c2_sr',
            'LANDSAT/LT04/C02/T1_L2': 'from_landsat_c2_sr',
            'COPERNICUS/S2_SR_HARMONIZED': 'from_sentinel2_sr',
            # 'COPERNICUS/S2_SR': 'from_sentinel2_sr',
        }

        try:
            method_name = collection_methods[image_id.rsplit('/', 1)[0]]
        except KeyError:
            raise ValueError(f'unsupported collection ID: {image_id}')
        except Exception as e:
            raise Exception(f'unhandled exception: {e}')

        method = getattr(Image, method_name)

        return method(ee.Image(image_id), **kwargs)

    @classmethod
    def from_landsat_c2_sr(cls, sr_image, cloudmask_args={}, **kwargs):
        """Construct a SIMS Image instance from a Landsat C02 level 2 (SR) image

        Parameters
        ----------
        sr_image : ee.Image, str
            A raw Landsat Collection 2 level 2 (SR) image or image ID.
        cloudmask_args : dict
            keyword arguments to pass through to cloud mask function
        kwargs : dict
            Keyword arguments to pass through to model init.

        Returns
        -------
        new instance of Image class

        Notes
        -----
        https://www.usgs.gov/faqs/how-do-i-use-a-scale-factor-landsat-level-2-science-products?qt-news_science_products=0#qt-news_science_products
        https://www.usgs.gov/core-science-systems/nli/landsat/landsat-collection-2-level-2-science-products

        """
        sr_image = ee.Image(sr_image)

        # Use the SPACECRAFT_ID property identify each Landsat type
        spacecraft_id = ee.String(sr_image.get('SPACECRAFT_ID'))

        # Rename bands to generic names
        input_bands = ee.Dictionary({
            'LANDSAT_4': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7',
                          'ST_B6', 'QA_PIXEL', 'QA_RADSAT'],
            'LANDSAT_5': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7',
                          'ST_B6', 'QA_PIXEL', 'QA_RADSAT'],
            'LANDSAT_7': ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7',
                          'ST_B6', 'QA_PIXEL', 'QA_RADSAT'],
            'LANDSAT_8': ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7',
                          'ST_B10', 'QA_PIXEL', 'QA_RADSAT'],
            'LANDSAT_9': ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7',
                          'ST_B10', 'QA_PIXEL', 'QA_RADSAT'],
        })
        output_bands = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2',
                        'lst', 'QA_PIXEL', 'QA_RADSAT']
        prep_image = (
            sr_image
            .select(input_bands.get(spacecraft_id), output_bands)
            .multiply([0.0000275, 0.0000275, 0.0000275, 0.0000275, 0.0000275, 0.0000275, 0.00341802, 1, 1])
            .add([-0.2, -0.2, -0.2, -0.2, -0.2, -0.2, 149.0, 0, 0])
        )

        # Default the cloudmask flags to True if they were not
        # Eventually these will probably all default to True in openet.core
        if 'cirrus_flag' not in cloudmask_args.keys():
            cloudmask_args['cirrus_flag'] = True
        if 'dilate_flag' not in cloudmask_args.keys():
            cloudmask_args['dilate_flag'] = True
        if 'shadow_flag' not in cloudmask_args.keys():
            cloudmask_args['shadow_flag'] = True
        if 'snow_flag' not in cloudmask_args.keys():
            cloudmask_args['snow_flag'] = True
        if 'cloud_score_flag' not in cloudmask_args.keys():
            cloudmask_args['cloud_score_flag'] = False
        if 'cloud_score_pct' not in cloudmask_args.keys():
            cloudmask_args['cloud_score_pct'] = 100
        if 'filter_flag' not in cloudmask_args.keys():
            cloudmask_args['filter_flag'] = False
        if 'saturated_flag' not in cloudmask_args.keys():
            cloudmask_args['saturated_flag'] = False

        cloud_mask = openet.core.common.landsat_c2_sr_cloud_mask(sr_image, **cloudmask_args)

        # Build the input image
        # Eventually send the QA band or a cloud mask through also
        input_image = ee.Image([cls._ndvi(prep_image)])

        # Apply the cloud mask and add properties
        input_image = (
            input_image
            .updateMask(cloud_mask)
            .set({
                'system:index': sr_image.get('system:index'),
                'system:time_start': sr_image.get('system:time_start'),
                'system:id': sr_image.get('system:id'),
            })
        )

        return cls(input_image, reflectance_type='SR', **kwargs)

    @classmethod
    def from_sentinel2_sr(cls, sr_image, cloudmask_args={}, **kwargs):
        """Construct a SIMS Image instance from a Sentinel 2 Level 2 (SR) image

        Parameters
        ----------
        sr_image : ee.Image, str
            A raw Sentinel 2 Level 2 (SR) image or image ID.
        cloudmask_args : dict
            keyword arguments to pass through to cloud mask function
        kwargs : dict
            Keyword arguments to pass through to model init.

        Returns
        -------
        new instance of Image class

        """
        sr_image = ee.Image(sr_image)

        # Rename bands to generic names
        input_bands = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12']
        output_bands = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']
        prep_image = sr_image.select(input_bands, output_bands).divide(10000)

        # Read in Cloud Score+ Image Collection
        clear_threshold = 0.60
        cloud_mask = (
            ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
            .filterMetadata('system:index', 'equals', ee.String(sr_image.get('system:index')))
            .first()
            .select(['cs'])
            .gte(clear_threshold)
        )

        # Build the input image
        # Eventually send the QA band or a cloud mask through also
        input_image = ee.Image([cls._ndvi(prep_image)])

        # Apply the cloud mask and add properties
        input_image = (
            input_image
            .updateMask(cloud_mask)
            .set({
                'system:index': sr_image.get('system:index'),
                'system:time_start': sr_image.get('system:time_start'),
                'system:id': sr_image.get('system:id'),
            })
        )

        return cls(input_image, reflectance_type='SR', **kwargs)

    @staticmethod
    def _ndvi(landsat_image):
        """Normalized difference vegetation index

        Parameters
        ----------
        landsat_image : ee.Image
            "Prepped" Landsat image with standardized band names.

        Returns
        -------
        ee.Image

        """
        return landsat_image.normalizedDifference(['nir', 'red']).rename(['ndvi'])
