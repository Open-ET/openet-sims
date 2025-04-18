# import pprint

import ee

from . import data
from . import utils


# def lazy_property(fn):
#     """Decorator that makes a property lazy-evaluated
#
#     https://stevenloria.com/lazy-properties/
#     """
#     attr_name = '_lazy_' + fn.__name__
#
#     @property
#     def _lazy_property(self):
#         if not hasattr(self, attr_name):
#             setattr(self, attr_name, fn(self))
#         return getattr(self, attr_name)
#     return _lazy_property


class Model():
    """GEE based model for computing SIMS ETcb"""

    def __init__(
        self,
        # CGM - Switch to ee.Date or time_start instead?
        year,
        doy,
        crop_type_source='USDA/NASS/CDL',
        crop_type_remap='CDL',
        crop_type_kc_flag=False,
        crop_type_annual_skip_flag=False,
        mask_non_ag_flag=True,
        water_kc_flag=True,
        reflectance_type='SR',
    ):
        """Earth Engine based SIMS model object

        Parameters
        ----------
        year : ee.Number
        doy : ee.Number
            Day of year
        crop_type_source : str, optional
            Crop type source.  The default is the Cropland Data Layer (CDL) assets.
            The source should be an Earth Engine Image ID (or ee.Image).
            Currently only the OpenET collection and CDL images are supported.
        crop_type_remap : {'CDL'}, optional
            Currently only CDL crop type values are supported.
        crop_type_kc_flag : bool, optional
            If True, compute Kc using crop type specific coefficients.
            If False, use generic crop class coefficients. The default is False.
        crop_type_annual_skip_flag : bool, optional
            If True, the crop type specific coefficients are NOT used for annual crops.
            If False, the crop type specific coefficients are used for annual crops.
            This flag is only applied/used if crop_type_kc_flag is also True.
            The default is False.
        mask_non_ag_flag : bool, optional
            If True, mask all pixels that don't map to a crop_class.
            The default is False.
        water_kc_flag : bool, optional
            If True, set Kc for water pixels to 1.05.  The default is True.
        reflectance_type : {'SR', 'TOA'}, optional
            Used to select the fractional cover equation (the default is 'SR').

        """

        # Model could inherit these values from Image instead of being passed in
        self.year = year
        self.doy = doy
        # self.date = ee.Date(self.time_start)
        # self.year = ee.Number(self.date.get('year'))
        # self.doy = self.date.getRelative('day', 'year').add(1).int()

        self.crop_type_source = crop_type_source
        self.crop_type_remap = crop_type_remap
        self.crop_type_kc_flag = crop_type_kc_flag
        self.crop_type_annual_skip_flag = crop_type_annual_skip_flag
        self.mask_non_ag_flag = mask_non_ag_flag
        self.water_kc_flag = water_kc_flag

        # CGM - Trying out setting these as properties in init
        #   instead of as lazy properties below
        self.crop_data = self._crop_data()
        self.crop_type = self._crop_type()
        self.crop_class = crop_data_image('crop_class', self.crop_type, self.crop_data, 0)

        # Manually set the crop data parameter images as class properties
        # Set default values for some properties to ensure fr == 1
        self.h_max = crop_data_image('h_max', self.crop_type, self.crop_data)
        self.m_l = crop_data_image('m_l', self.crop_type, self.crop_data)
        self.fr_mid = crop_data_image('fr_mid', self.crop_type, self.crop_data, 1)
        self.fr_end = crop_data_image('fr_end', self.crop_type, self.crop_data, 1)
        self.ls_start = crop_data_image('ls_start', self.crop_type, self.crop_data, 1)
        self.ls_stop = crop_data_image('ls_stop', self.crop_type, self.crop_data, 365)
        # setattr('h_max', crop_data_image(
        #     'h_max', self.crop_type, self.crop_data))

        self.reflectance_type = reflectance_type
        # TODO: Should type be checked (and exception raised) here or in fc()?
        #   Being raised in fc() for now since it is not a lazy property
        # if self.reflectance_type not in ['SR', 'TOA']:
        #     raise ValueError(f'unsupported reflectance type: {reflectance_type}')

    # CGM - It would be nice if kc and fc were lazy properties but then fc and
    #   ndvi would need to part of self (inherited from Image?).
    # @lazy_property
    def kc(self, ndvi):
        """Crop coefficient (kc) for all crop classes and types

        Parameters
        ----------
        ndvi : ee.Image
            Normalized difference vegetation index.

        Returns
        -------
        ee.Image

        Notes
        ----
        Generic Fc-Kcb conversion for:
        Annuals:
        Melton, F., L. Johnson, C. Lund, L. Pierce, A. Michaelis, S. Hiatt,
            A. Guzman, D. Adhikari, A. Purdy, C. Rosevelt, P. Votava, T. Trout,
            B. Temesgen, K. Frame, E. Sheffner, and R. Nemani (2012).
            Satellite Irrigation Management Support with the Terrestrial
            Observation and Prediction System: An Operational Framework for
            Integration of Satellite and Surface Observations to Support
            Improvements in Agricultural Water Resource Management.
            IEEE J. Selected Topics in Applied Earth Observations & Remote Sensing
            5:1709-1721.  [FIG 2b]

        Crop specific Fc-Kcb conversion:
        Allen, R., and L. Pereira (2009).  Estimating crop coefficients from
            fraction of ground cover and height.  Irrigation Science 28:17-34.
            DOI 10.1007/s00271-009-0182-z
            [EQNS 10 (Kd); 7a (Kcb_full) using tree/vine Fr vals from Table 2; 5a (Kcb)]

        """
        fc = self.fc(ndvi)

        # Start with the generic NDVI-Kc relationship to initialize Kc
        kc = self.kc_generic(ndvi)

        # Apply generic crop class Kc functions
        kc = kc.where(self.crop_class.eq(1), self.kc_row_crop(fc))
        kc = kc.where(self.crop_class.eq(2), self._kcb(self._kd_vine(fc)).clamp(0, 1.1))
        kc = kc.where(self.crop_class.eq(3), self.kc_tree(fc))
        kc = kc.where(self.crop_class.eq(5), self.kc_rice(fc, ndvi))
        kc = kc.where(self.crop_class.eq(6), self.kc_fallow(fc, ndvi))
        kc = kc.where(self.crop_class.eq(7), self.kc_grass_pasture(fc, ndvi))

        if self.crop_type_kc_flag:
            # Apply crop type specific Kc functions
            # h_max.gte(0) is needed to select pixels that have custom
            #   coefficient values in the crop_data dictionary
            # The h_max image was built with all non-remapped crop_types as nodata
            if not self.crop_type_annual_skip_flag:
                kc = kc.where(self.crop_class.eq(1).And(self.h_max.gte(0)),
                              self._kcb(self._kd_row_crop(fc)))

            kc = kc.where(self.crop_class.eq(3).And(self.h_max.gte(0)),
                          self._kcb(self._kd_tree(fc)).clamp(0, 1.2))

            # CGM - Commenting out for now
            # kc = kc.where(
            #     self.crop_class.eq(3).And(self.h_max.gte(0)).And(kc.gte(0.2)),
            #     self._kcb(self._kd_tree(fc), kc_min=0.5).clamp(0, 1.2))

        # CGM - Is it okay to apply this after all the other Kc functions?
        #   Should we only apply this to non-ag crop classes?
        if self.water_kc_flag:
            kc = kc.where(ndvi.lt(0).And(self.crop_class.eq(0)), 1.05)
            # kc = kc.where(ndvi.lt(0), 1.05)

        if self.mask_non_ag_flag:
            kc = kc.updateMask(self.crop_class.gt(0))

        return kc.rename(['kc'])

    # @lazy_property
    def fc(self, ndvi):
        """Fraction of cover (fc)

        Parameters
        ----------
        ndvi : ee.Image

        Returns
        -------
        ee.Image

        Raises
        ------
        ValueError if reflectance type is not supported

        References
        ----------


        """
        if self.reflectance_type == 'SR':
            fc = ndvi.multiply(1.26).subtract(0.18)
        elif self.reflectance_type == 'TOA':
            fc = ndvi.multiply(1.465).subtract(0.139)
        else:
            raise ValueError(f'Unsupported reflectance type: {self.reflectance_type}')

        return fc.clamp(0, 1).rename(['fc'])

    def _crop_type(self):
        """Crop type

        Parameters
        ----------
        crop_type_source : int, str
            CDL image collection ID: 'USDA/NASS/CDL'
                Collection will be filtered to a single year that is closest
                to the Image year.
            CDL image ID for a specific year: 'USDA/NASS/CDL/2018'
            OpenET crop type image collection ID:
                'projects/openet/assets/crop_type/v2023a'
                'projects/openet/assets/crop_type/v2024a'
                Collection will be mosaiced to a single image.
            Integer (will be converted to an EE constant image)
        year : ee.Number
            Year is needed if crop_type_source is the CDL collection.

        Returns
        -------
        ee.Image

        Raises
        ------
        ValueError for unsupported crop_type_sources

        """
        properties = ee.Dictionary()

        if utils.is_number(self.crop_type_source):
            # Interpret numbers as constant images
            # CGM - Should we use the ee_types here instead?
            #   i.e. ee.ee_types.isNumber(self.et_reference_source)
            crop_type_img = ee.Image.constant(self.crop_type_source)
            #     .rename('crop_type')
            # properties = properties.set('id', 'constant')
        elif (type(self.crop_type_source) is str and
              self.crop_type_source.upper() == 'USDA/NASS/CDL'):
            # Assume source is the CDL image collection ID
            # Use the CDL image closest to the image date
            # Don't use CDL images before 2008
            cdl_coll = ee.ImageCollection('USDA/NASS/CDL')
            cdl_year = (
                ee.Number(self.year)
                .max(2008)
                .min(ee.Date(cdl_coll.aggregate_max('system:time_start')).get('year'))
            )
            cdl_coll = (
                cdl_coll
                .filterDate(ee.Date.fromYMD(cdl_year, 1, 1),
                            ee.Date.fromYMD(cdl_year.add(1), 1, 1))
                .select(['cropland'])
            )
            crop_type_img = ee.Image(cdl_coll.first())
            properties = properties.set('id', crop_type_img.get('system:id'))
        elif (type(self.crop_type_source) is str and
                self.crop_type_source.upper().startswith('USDA/NASS/CDL')):
            # Assume source is a single CDL image ID
            crop_type_img = ee.Image(self.crop_type_source).select(['cropland'])
            properties = properties.set('id', crop_type_img.get('system:id'))
        elif (type(self.crop_type_source) is str and
              ('projects/openet/crop_type' in self.crop_type_source.lower() or
               'projects/openet/assets/crop_type' in self.crop_type_source.lower())):
            # Assume source is an OpenET crop type image collection ID
            # Use the crop type image closest to the image date
            crop_coll = ee.ImageCollection(self.crop_type_source)
            cdl_year = (
                ee.Number(self.year)
                .max(ee.Date(crop_coll.aggregate_min('system:time_start')).get('year'))
                .min(ee.Date(crop_coll.aggregate_max('system:time_start')).get('year'))
            )
            crop_type_coll = (
                ee.ImageCollection(self.crop_type_source)
                .filterDate(ee.Date.fromYMD(cdl_year, 1, 1),
                            ee.Date.fromYMD(cdl_year.add(1), 1, 1))
            )
            crop_type_img = crop_type_coll.mosaic()
            properties = properties.set('id', crop_type_coll.get('system:id'))
        # TODO: Support ee.Image and ee.ImageCollection sources
        # elif isinstance(self.crop_type_source, computedobject.ComputedObject):
        else:
            raise ValueError(f'unsupported crop_type_source: {self.crop_type_source}')

        # Should the image properties be set onto the image also?
        return crop_type_img.rename(['crop_type']).set(properties)

    def _crop_data(self):
        """Load the crop data dictionary

        Currently the data is in data.py but this method could also be used to
        read the data from a json or csv file.

        Parameters
        ----------
        crop_type : ee.Image
        crop_type_remap : str

        Returns
        -------
        dict

        Raises
        ------
        ValueError for unsupported crop_type_remap

        """
        if self.crop_type_remap.upper() == 'CDL':
            return data.cdl
        else:
            raise ValueError(f'unsupported crop_type_remap: "{self.crop_type_remap}"')

    def kc_generic(self, ndvi):
        """Generic crop coefficient based on linear function of NDVI

        Parameters
        ----------
        ndvi : ee.Image
            Normalized difference vegetation index.

        Returns
        -------
        ee.Image

        """
        return ndvi.multiply(1.25).add(0.2).max(0).rename(['kc'])

    def kc_row_crop(self, fc):
        """Generic crop coefficient for annual row crops (class 1)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover

        Returns
        -------
        ee.Image

        References
        ----------
        Melton, F., L. Johnson, C. Lund, L. Pierce, A. Michaelis, S. Hiatt,
            A. Guzman, D. Adhikari, A. Purdy, C. Rosevelt, P. Votava, T. Trout,
            B. Temesgen, K. Frame, E. Sheffner, and R. Nemani (2012).
            Satellite Irrigation Management Support with the Terrestrial
            Observation and Prediction System: An Operational Framework for
            Integration of Satellite and Surface Observations to Support
            Improvements in Agricultural Water Resource Management.
            IEEE J. Selected Topics in Applied Earth Observations & Remote Sensing
            5:1709-1721.  [FIG 2b]

        """
        return (
            fc.expression("((b(0) ** 2) * -0.4771) + (1.4047 * b(0)) + 0.15")
            .rename(['kc'])
        )

    def kc_tree(self, fc):
        """General crop coefficient for tree crops (class 3)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover

        Returns
        -------
        ee.Image

        References
        ----------
        Ayars, J., R. Johnson, C. Phene, T. Trout, D. Clark, and R. Mead, 2003.
            Water use by drip-irrigated late-season peaches.
            Irrigation Science 22:187-194.  DOI 10.1007/s00271-003-0084-4 [EQN 7]

        """
        return fc.multiply(1.48).add(0.007).rename(['kc'])

    def kc_rice(self, fc, ndvi):
        """Crop coefficient for rice crops (class 5)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover
        ndvi : ee.Image
            Normalized difference vegetation index

        Returns
        -------
        ee.Image

        Notes
        -----
        Kc is computed using the generic annual crop equation (class 1) but
        the Kc is adjusted to 1.05 for low NDVI pixels.

        """
        return self.kc_row_crop(fc).where(ndvi.lte(0.14), 1.05).rename(['kc'])

    def kc_fallow(self, fc, ndvi):
        """Crop coefficient for fallow crops (class 6)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover
        ndvi : ee.Image
            Normalized difference vegetation index

        Returns
        -------
        ee.Image

        Notes
        -----
        Kc is computed using the generic annual crop equation (class 1) but
        the Kc is set to the Fc for lower NDVI pixels.

        """
        return self.kc_row_crop(fc).where(ndvi.lte(0.35), fc).max(0.01).rename(['kc'])

    def kc_grass_pasture(self, fc, ndvi):
        """Crop coefficient for grass/pasture crops (class 7)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover
        ndvi : ee.Image
            Normalized difference vegetation index

        Returns
        -------
        ee.Image

        Notes
        -----
        Kc is computed using the generic annual crop equation (class 1) but
        the Kc is set to the Fc for lower NDVI pixels.

        """
        return self.kc_row_crop(fc).where(ndvi.lte(0.35), fc).max(0.01).rename(['kc'])

    def _kcb(self, kd, kc_min=0.15):
        """Basal crop coefficient (Kcb)

        Parameters
        ----------
        kd : ee.Image
            Crop density coefficient
        kc_min : float, optional

        Returns
        -------
        ee.Image

        Notes
        -----
        Compute fr along the line defined by:
            fr = (DOY - ls_start) * ((fr_end - fr_mid) / (ls_stop - ls_start))
                 + fr_mid
        Negated (DOY - ls_start) since DOY is a number and needs to be
        subtracted from an image (images can't be subtracted from numbers).
            fr = (ls_start - DOY) * ((fr_mid - fr_end) / (ls_stop - ls_start))
                 + fr_mid
        fr min/max calls may seem swapped since fr_mid is greater than fr_end

        References
        ----------
        Allen, R., and L. Pereira (2009).  Estimating crop coefficients from
            fraction of ground cover and height.  Irrigation Science 28:17-34.
            DOI 10.1007/s00271-009-0182-z [EQNS 5a, 7a]

        """
        # Reduction factor for adjusting Kcb of tree crops
        fr = (
            self.ls_start.subtract(self.doy)
            .multiply(self.fr_mid.subtract(self.fr_end))
            .divide(self.ls_stop.subtract(self.ls_start))
            .add(self.fr_mid)
            .max(self.fr_end)
            .min(self.fr_mid)
        )

        # Kcb during peak plant growth (near full cover)
        kcb_full = self.h_max.multiply(0.1).add(1).min(1.2).multiply(fr)

        return kd.multiply(kcb_full.subtract(kc_min)).add(kc_min).rename(['kcb'])

    def _kd_row_crop(self, fc):
        """Density coefficient for annual row crops (class 1)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover

        Returns
        -------
        ee.Image

        Notes
        -----
        TODO: Add a more readable version of the calculation

        References
        ----------
        Allen, R., and L. Pereira (2009).  Estimating crop coefficients from
            fraction of ground cover and height.  Irrigation Science 28:17-34.
            DOI 10.1007/s00271-009-0182-z
            [EQNS 10 (Kd); 7a (Kcb_full) using tree/vine Fr vals from Table 2]

        """
        # First calculation is the fc.divide(0.7).lte(1) case
        return (
            fc.multiply(self.m_l)
            .min(fc.pow(fc.divide(0.7).multiply(self.h_max).add(1).pow(-1)))
            .where(
                fc.divide(0.7).gt(1),
                fc.multiply(self.m_l).min(fc.pow(self.h_max.add(1).pow(-1))))
            .min(1)
            .rename(['kd'])
        )

    def _kd_vine(self, fc):
        """Crop coefficient for vine crops (class 2)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover

        Returns
        -------
        ee.Image

        References
        ----------
        CGM - I couldn't find this equation in FIG 10 of the reference
        Williams, L. and J. Ayars (2005).  Grapevine water use and the crop
            coefficient are linear functions of the shaded area measured beneath
            the canopy.  Ag. For. Meteor 132:201-211.  [FIG 10]

        """
        return fc.multiply(1.5).min(fc.pow(1 / (1 + 2))).min(1).rename(['kd'])

    def _kd_tree(self, fc):
        """Density coefficient for tree crops (class 3)

        Parameters
        ----------
        fc : ee.Image
            Fraction of cover

        Returns
        -------
        ee.Image

        References
        ----------
        Allen, R., and L. Pereira (2009).  Estimating crop coefficients from
            fraction of ground cover and height.  Irrigation Science 28:17-34.
            DOI 10.1007/s00271-009-0182-z
            [EQNS 10 (Kd); 7a (Kcb_full) using tree/vine Fr vals from Table 2; 5a (Kcb)]

        """
        # First calculation is the fc.gt(0.5) case
        return (
            fc.multiply(self.m_l).min(fc.pow(self.h_max.add(1).pow(-1)))
            .where(fc.lte(0.5), fc.multiply(self.m_l).min(fc.pow(self.h_max.pow(-1))))
            .min(1)
            .rename(['kd'])
        )


def crop_data_image(param_name, crop_type, crop_data, default_value=None):
    """Build a constant ee.Image of crop type data for one parameter

    Parameters
    ----------
    param_name : str
    crop_type : ee.Image
    crop_data : dict
        Imported from data.py
    default_value : float, optional
        The default value to replace values that weren't matched in the remap.
        If default_value is not set or is None, unmatched values are masked.

    Returns
    -------
    ee.Image

    Notes
    -----
    All values are multiplied by an factor (read from the data.py file),
    then divided after the remap in order to return floating point values.

    """
    data_dict = {
        c_type: round(c_data[param_name] * data.int_scalar)
        for c_type, c_data in crop_data.items()
        if param_name in c_data.keys()
    }
    from_list, to_list = zip(*sorted(data_dict.items()))

    # Scale the default value if it is set
    if default_value is not None:
        output = crop_type.remap(from_list, to_list, default_value * data.int_scalar)
    else:
        output = crop_type.remap(from_list, to_list)

    return output.double().divide(data.int_scalar).rename([param_name])
