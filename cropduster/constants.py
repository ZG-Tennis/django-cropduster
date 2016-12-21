# -*- coding: utf-8 -*-
""" cropduster constants """


IMAGE_SAVE_PARAMS = {
    "quality": 95
}

MANUALLY_CROP = 0
AUTO_CROP = 1
AUTO_SIZE = 2

GENERATION_CHOICES = (
    (MANUALLY_CROP, "Manually Crop"),
    (AUTO_CROP, "Auto-Crop"),
    (AUTO_SIZE, "Auto-Size"),
)

RETINA_POSTFIX = "@2x"

BROWSER_WIDTH = 800
