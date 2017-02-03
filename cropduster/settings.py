# -*- coding: utf-8 -*-
""" cropduster settings """

from django.conf import settings


CROPDUSTER_UPLOAD_PATH = getattr(
    settings, "CROPDUSTER_UPLOAD_PATH", settings.MEDIA_ROOT)

CROPDUSTER_CROP_ONLOAD = getattr(settings, "CROPDUSTER_CROP_ONLOAD", True)

CROPDUSTER_PLACEHOLDER_MODE = getattr(
    settings, "CROPDUSTER_PLACEHOLDER_MODE", False)

CROPDUSTER_EXIF_DATA = getattr(settings, "CROPDUSTER_EXIF_DATA", True)

CROPDUSTER_RENAME_IMAGES = getattr(
    settings, "CROPDUSTER_RENAME_IMAGES", False)
