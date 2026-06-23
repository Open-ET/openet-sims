"""
References
----------
    Allen, R. and L. Pereira (2009).  Estimating crop coefficients from
    fraction of ground cover and height. Irrigation Science 28:17-34.
    DOI 10.1007/s00271-009-0182-z
"""

# Scaling factor to use in EE remap function since it only work with integers
int_scalar = 100

cdl = {
    # Field crops
    49: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Onions'},
    206: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Carrots'},
    208: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Garlic'},
    214: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Broccoli'},
    227: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Lettuce'},
    243: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Cabbage'},
    244: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Cauliflower'},
    245: {'crop_class': 1, 'h_max': 0.6, 'm_l': 2, 'fr_mid': 1, 'name': 'Celery'},
    246: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Radishes'},

    # Vegetables, solanum family
    54: {'crop_class': 1, 'h_max': 0.6, 'm_l': 2, 'fr_mid': 1, 'name': 'Tomatoes'},
    248: {'crop_class': 1, 'h_max': 0.8, 'm_l': 2, 'fr_mid': 1, 'name': 'Eggplants'},

    # Vegetables, cucurb family
    48: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Watermelons'},
    209: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Cantaloupes'},
    213: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Honeydew Melons'},
    222: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Squash'},
    228: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Dbl Crop Triticale/Corn'},
    229: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Pumpkins'},

    # Vegetables, other
    47: {'crop_class': 1, 'h_max': 0.37, 'm_l': 2, 'fr_mid': 1, 'name': 'Misc Vegs & Fruits'},

    # Roots & tubers
    41: {'crop_class': 1, 'h_max': 0.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Sugarbeets'},
    43: {'crop_class': 1, 'h_max': 0.6, 'm_l': 2, 'fr_mid': 1, 'name': 'Potatoes'},
    46: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Sweet Potatoes'},
    247: {'crop_class': 1, 'h_max': 0.6, 'm_l': 2, 'fr_mid': 1, 'name': 'Turnips'},

    # Legumes
    5: {'crop_class': 1, 'h_max': 0.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Soybeans'},
    10: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Peanuts'},
    30: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Speltz'},
    42: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Dry Beans'},
    51: {'crop_class': 1, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1, 'name': 'Chick Peas'},
    52: {'crop_class': 1, 'h_max': 0.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Lentils'},
    53: {'crop_class': 1, 'h_max': 0.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Peas'},
    224: {'crop_class': 1, 'h_max': 0.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Vetch'},

    # Perennial vegetables or fruit
    14: {'crop_class': 1, 'h_max': 0.7, 'm_l': 2, 'fr_mid': 1, 'name': 'Mint'},
    50: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Cucumbers'},
    207: {'crop_class': 1, 'h_max': 0.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Asparagus'},
    216: {'crop_class': 1, 'h_max': 0.7, 'm_l': 2, 'fr_mid': 1, 'name': 'Peppers'},
    221: {'crop_class': 1, 'h_max': 0.2, 'm_l': 2, 'fr_mid': 1, 'name': 'Strawberries'},

    # Fiber
    2: {'crop_class': 1, 'h_max': 1.35, 'm_l': 2, 'fr_mid': 1, 'name': 'Cotton'},
    6: {'crop_class': 1, 'h_max': 2.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Sunflower'},
    31: {'crop_class': 1, 'h_max': 0.6, 'm_l': 2, 'fr_mid': 1, 'name': 'Canola'},
    32: {'crop_class': 1, 'h_max': 1.2, 'm_l': 2, 'fr_mid': 1, 'name': 'Flaxseed'},
    33: {'crop_class': 1, 'h_max': 0.8, 'm_l': 2, 'fr_mid': 1, 'name': 'Safflower'},
    45: {'crop_class': 1, 'h_max': 3.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Sugarcane'},

    # Cereal
    1: {'crop_class': 1, 'h_max': 2.0, 'm_l': 2, 'fr_mid': 1,  'name': 'Corn'},
    4: {'crop_class': 1, 'h_max': 1.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Sorghum'},
    12: {'crop_class': 1, 'h_max': 1.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Sweet Corn'},
    21: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Barley'},
    22: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Durum Wheat'},
    23: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Spring Wheat'},
    24: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Winter Wheat'},
    25: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Other Small Grains'},
    26: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Dbl Crop WinWht/Soybeans'},
    28: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Oats'},
    29: {'crop_class': 1, 'h_max': 1.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Millet'},
    # CGM - Repeat of crop 32 in fiber section
    #   Same values so commenting out for now
    # 32: {'crop_class': 1, 'h_max': 1.2, 'm_l': 2, 'fr_mid': 1, 'name': 'Flaxseed'},
    34: {'crop_class': 1, 'h_max': 0.6, 'm_l': 2, 'fr_mid': 1, 'name': 'Rape Seed'},
    35: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Mustard'},
    39: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Buckwheat'},
    56: {'crop_class': 1, 'h_max': 5.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Hops'},

    # Rice
    3: {'crop_class': 5, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Rice'},

    # Forage
    27: {'crop_class': 1, 'h_max': 0.3, 'm_l': 2, 'fr_mid': 1, 'name': 'Rye'},
    36: {'crop_class': 1, 'h_max': 0.7, 'm_l': 2, 'fr_mid': 1, 'name': 'Alfalfa'},
    58: {'crop_class': 1, 'h_max': 0.6, 'm_l': 2, 'fr_mid': 1, 'name': 'Clover/Wildflowers'},
    37: {'crop_class': 1, 'h_max': 0.5, 'm_l': 2, 'fr_mid': 1, 'name': 'Other Hay/Non Alfalfa'},
    38: {'crop_class': 1, 'h_max': 1.0, 'm_l': 2, 'fr_mid': 1, 'name': 'Camelina'},
    205: {'crop_class': 1, 'h_max': 0.65, 'm_l': 2, 'fr_mid': 1, 'name': 'Triticale'},

    # Crops without custom coefficients
    11: {'crop_class': 1, 'name': 'Tobacco'},
    13: {'crop_class': 1, 'name': 'Pop or Orn Corn'},
    44: {'crop_class': 1, 'name': 'Other Crops'},
    55: {'crop_class': 1, 'name': 'Caneberries'},
    57: {'crop_class': 1, 'name': 'Herbs'},
    59: {'crop_class': 1, 'name': 'Sod/Grass Seed'},
    60: {'crop_class': 1, 'name': 'Switchgrass'},
    219: {'crop_class': 1, 'name': 'Greens'},
    225: {'crop_class': 1, 'name': 'Dbl Crop WinWht/Corn'},
    226: {'crop_class': 1, 'name': 'Dbl Crop Oats/Corn'},
    230: {'crop_class': 1, 'name': 'Dbl Crop Lettuce/Durum Wht'},
    231: {'crop_class': 1, 'name': 'Dbl Crop Lettuce/Cantaloupe'},
    232: {'crop_class': 1, 'name': 'Dbl Crop Lettuce/Cotton'},
    233: {'crop_class': 1, 'name': 'Dbl Crop Lettuce/Barley'},
    234: {'crop_class': 1, 'name': 'Dbl Crop Durum Wht/Sorghum'},
    235: {'crop_class': 1, 'name': 'Dbl Crop Barley/Sorghum'},
    236: {'crop_class': 1, 'name': 'Dbl Crop WinWht/Sorghum'},
    237: {'crop_class': 1, 'name': 'Dbl Crop Barley/Corn'},
    238: {'crop_class': 1, 'name': 'Dbl Crop WinWht/Cotton'},
    239: {'crop_class': 1, 'name': 'Dbl Crop Soybeans/Cotton'},
    240: {'crop_class': 1, 'name': 'Dbl Crop Soybeans/Oats'},
    241: {'crop_class': 1, 'name': 'Dbl Crop Corn/Soybeans'},
    242: {'crop_class': 1, 'name': 'Blueberries'},
    249: {'crop_class': 1, 'name': 'Gourds'},
    250: {'crop_class': 1, 'name': 'Cranberries'},
    254: {'crop_class': 1, 'name': 'Dbl Crop Barley/Soybeans'},

    # Vines
    69: {
        'crop_class': 2, 'h_max': 2, 'm_l': 1.5, 'fr_mid': 0.65, 'fr_end': 0.43,
        'ls_start': 205, 'ls_stop': 265, 'name': 'Wine Grapes'
    },
    78: {
        'crop_class': 2, 'h_max': 2, 'm_l': 1.5, 'fr_mid': 0.95, 'fr_end': 0.51,
        'ls_start': 205, 'ls_stop': 265, 'name': 'Grapes (table/raisin)'
    },

    # Trees
    66: {
        'crop_class': 3, 'h_max': 3, 'm_l': 2, 'fr_mid': 0.95, 'fr_end': 0.75,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Cherries',
    },
    67: {
        'crop_class': 3, 'h_max': 3, 'm_l': 1.5, 'fr_mid': 1.0, 'fr_end': 0.71,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Peaches',
    },
    68: {
        'crop_class': 3, 'h_max': 3, 'm_l': 2, 'fr_mid': 0.95, 'fr_end': 0.75,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Apples',
    },
    71: {
        'crop_class': 3, 'h_max': 4, 'm_l': 1.5, 'fr_mid': 0.89, 'fr_end': 0.63,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Other Tree Crops'
    },
    72: {
        'crop_class': 3, 'h_max': 2.5, 'm_l': 1.5, 'fr_mid': 0.71, 'fr_end': 0.94,
        'ls_start': 270, 'ls_stop': 365, 'name': 'Citrus',
    },
    74: {
        'crop_class': 3, 'h_max': 4, 'm_l': 1.5, 'fr_mid': 0.89, 'fr_end': 0.80,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Pecans',
    },
    75: {
        'crop_class': 3, 'h_max': 4, 'm_l': 1.5, 'fr_mid': 0.81, 'fr_end': 0.59,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Almonds',
    },
    76: {
        'crop_class': 3, 'h_max': 5, 'm_l': 1.5, 'fr_mid': 0.9, 'fr_end': 0.52,
        'ls_start': 250, 'ls_stop': 280, 'name': 'Walnuts',
    },
    77: {
        'crop_class': 3, 'h_max': 3, 'm_l': 2, 'fr_mid': 0.95, 'fr_end': 0.75,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Pears',
    },
    204: {
        'crop_class': 3, 'h_max': 3, 'm_l': 1.5, 'fr_mid': 0.81, 'fr_end': 0.57,
        'ls_start': 200, 'ls_stop': 240, 'name': 'Pistachios',
    },
    210: {
        'crop_class': 3, 'h_max': 3, 'm_l': 1.5, 'fr_mid': 0.95, 'fr_end': 0.71,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Prunes',
    },
    211: {
        'crop_class': 3, 'h_max': 4, 'm_l': 1.5, 'fr_mid': 0.48, 'fr_end': 0.46,
        'ls_start': 240, 'ls_stop': 330, 'name': 'Olives',
    },
    212: {
        'crop_class': 3, 'h_max': 2.5, 'm_l': 1.5, 'fr_mid': 0.71, 'fr_end': 0.94,
        'ls_start': 270, 'ls_stop': 365, 'name': 'Oranges',
    },
    215: {
        'crop_class': 3, 'h_max': 3, 'm_l': 2, 'fr_mid': 0.81, 'fr_end': 0.73,
        'ls_start': 270, 'ls_stop': 365, 'name': 'Avocados',
    },
    218: {
        'crop_class': 3, 'h_max': 3, 'm_l': 1.5, 'fr_mid': 0.95, 'fr_end': 0.75,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Nectarines',
    },
    220: {
        'crop_class': 3, 'h_max': 3, 'm_l': 1.5, 'fr_mid': 0.95, 'fr_end': 0.71,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Plums',
    },
    223: {
        'crop_class': 3, 'h_max': 3, 'm_l': 1.5, 'fr_mid': 0.95, 'fr_end': 0.71,
        'ls_start': 270, 'ls_stop': 300, 'name': 'Apricots',
    },

    # Tree crops without custom coefficients
    70: {'crop_class': 3, 'name': 'Christmas Trees'},
    217: {'crop_class': 3, 'name': 'Pomegranates'},

    # Fallow
    61: {'crop_class': 6, 'name': 'Fallow/Idle Cropland'},

    # Grass pasture
    176: {'crop_class': 7, 'name': 'Grassland/pasture'},
}

# TODO: Check crop_class values, some of them are guesses
# https://agriwatch.projects.earthengine.app/view/hcdl-viewer

hcdl = {
    5: {'crop_class': 1, 'name': 'Other Crops', 'cdl': 106},
    11: {'crop_class': 7, 'name': 'Grassland/pasture', 'cdl': 176},
    14: {'crop_class': 3, 'name': 'Banana', 'cdl': 93},
    17: {'crop_class': 3, 'name': 'Other Exotic Fruits', 'cdl': 94},
    21: {'crop_class': 3, 'name': 'Coffee', 'cdl': 95},
    19: {
        'crop_class': 3, 'name': 'Citrus', 'cdl': 72,
        'h_max': 2.5, 'm_l': 1.5, 'fr_mid': 0.71, 'fr_end': 0.94, 'ls_start': 270, 'ls_stop': 365,
    },
    34: {'crop_class': 3, 'name': 'Macadamia', 'cdl': 96},
    40: {'crop_class': 3, 'name': 'Papaya', 'cdl': 97},
    42: {'crop_class': 1, 'name': 'Pineapple', 'cdl': 98},
    48: {'crop_class': 1, 'name': 'Sugarcane', 'cdl': 45, 'h_max': 3.0, 'm_l': 2, 'fr_mid': 1},
    52: {'crop_class': 1, 'name': 'Taro', 'cdl': 100},
    56: {'crop_class': 1, 'name': 'Misc Vegs & Fruits', 'cdl': 47, 'h_max': 0.37, 'm_l': 2, 'fr_mid': 1},
    57: {'crop_class': 1, 'name': 'Sweet Basil', 'cdl': 101},
    58: {'crop_class': 1, 'name': 'Sunflower', 'cdl': 6, 'h_max': 2.0, 'm_l': 2, 'fr_mid': 1},
    59: {'crop_class': 1, 'name': 'Corn', 'cdl': 1, 'h_max': 2.0, 'm_l': 2, 'fr_mid': 1},
    60: {
        'crop_class': 3, 'name': 'Avocados', 'cdl': 215,
        'h_max': 3, 'm_l': 2, 'fr_mid': 0.81, 'fr_end': 0.73, 'ls_start': 270, 'ls_stop': 365
    },
    62: {'crop_class': 3, 'name': 'Coconut', 'cdl': 102},
    64: {'crop_class': 1, 'name': 'Plumeria', 'cdl': 103},
    65: {'crop_class': 3, 'name': 'Noni Fruit', 'cdl': 104},
    66: {'crop_class': 3, 'name': 'Dracaena', 'cdl': 105},
    67: {'crop_class': 1, 'name': 'Sweet Potatoes', 'cdl': 46, 'h_max': 0.4, 'm_l': 2, 'fr_mid': 1},
    # Other non-crop codes
    # HCDL  CDL  Name
    #    1  111  Open Water
    #    2   63  Forest
    #    7   82  Developed
    #    8  131  Barren
    #   12  152  Shrubland
    #   22   99  Commercial Forest*
}
