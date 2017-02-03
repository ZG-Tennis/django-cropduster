# -*- coding: utf-8 -*-
""" cropduster utils """

import cStringIO
import os
import urllib2

from PIL import Image
from decimal import Decimal
from uuid import uuid4

from django.utils.timezone import datetime
from django.utils.deconstruct import deconstructible


def aspect_ratio(width, height):
    """ Defines aspect ratio from two sizes with consistent rounding method """
    if not height or not width:
        return 1
    else:
        return Decimal(str(round(float(width)/float(height), 2)))


def rescale(img, width=0, height=0, auto_crop=True, **kwargs):
    """
    Rescale the given image.  If one size is not given, image is scaled down at
    current aspect ratio
    img -- a PIL image object

    Auto-crop option does a dumb crop that chops the image to the needed size
    """
    if width <= 0:
        width = float(img.size[0]*height)/float(img.size[1])

    if height <= 0:
        height = float(img.size[1]*width)/float(img.size[0])

    max_width = width
    max_height = height
    src_width, src_height = img.size
    src_ratio = float(src_width)/float(src_height)
    dst_width, dst_height = max_width, max_height
    dst_ratio = float(dst_width)/float(dst_height)

    if auto_crop:
        if dst_ratio < src_ratio:
            crop_height = src_height
            crop_width = crop_height*dst_ratio
            x_offset = float(src_width-crop_width)/2
            y_offset = 0
        else:
            crop_width = src_width
            crop_height = crop_width/dst_ratio
            x_offset = 0
            y_offset = float(src_height-crop_height)/3

        img = img.crop((
            int(x_offset),
            int(y_offset),
            int(x_offset + crop_width),
            int(y_offset + crop_height)
        ))
        img = img.resize((int(dst_width), int(dst_height)), Image.ANTIALIAS)

    # if not cropping, don't squish, use w/h as max values to resize on
    else:
        if (width / src_ratio) > height:
            # height larger than intended
            dst_width = width
            dst_height = width / src_ratio
        else:
            # width larger than intended
            dst_width = src_ratio * height
            dst_height = height

        img = img.resize((int(dst_width), int(dst_height)), Image.ANTIALIAS)
        img = img.crop([0, 0, int(width), int(height)])

    return img


def create_cropped_image(path=None, x=0, y=0, width=0, height=0):
    """
    Crop image given a starting (x, y) position and a width and height
    of the cropped area
    """

    if path is None:
        raise ValueError("A path must be specified")
    try:
        img = Image.open(path)
    except IOError:
        img_file = cStringIO.StringIO(urllib2.urlopen(path).read())
        img = Image.open(img_file)
    finally:
        img.copy()
        img.load()
        img = img.crop((x, y, x + width, y + height))
        img.load()

        return img


def path_exists(path):
    """ Returns True if the path/url exists """
    try:
        urllib2.urlopen(path)
    except urllib2.HTTPError:
        return False
    except ValueError:
        return os.path.exists(path)
    else:
        return True


def is_url(path):
    """ Returns True if the path is an url """
    try:
        urllib2.urlopen(path)
    except urllib2.HTTPError:
        return True
    except ValueError:
        return False
    else:
        return True


def url_exists(path):
    """ returns True just if the url exits """
    try:
        urllib2.urlopen(path)
    except urllib2.HTTPError:
        return False
    except ValueError:
        return False
    else:
        return True


@deconstructible
class UploadToPathAndRename(object):
    """
    Resolves the file upload path and replaces the filename with a
    nandom one, if set to do that replacement.
    Usage:
        models.ImageField(
            upload_to=UploadToPathAndRename(
                'some_path/%Y/%m/%d',
                 rename=False
            )
        )
    """

    def __init__(self, sub_path, rename=True):
        """ initializes the object instance """
        self.sub_path = sub_path
        self.rename = rename

    def resolve_sub_path(self):
        """ resolves and returns the sub_path """
        now = datetime.now()
        return now.strftime(self.sub_path)

    def __call__(self, instance, filename):
        """ returns the file path """
        ext = filename.split('.')[-1]
        if self.rename:
            filename = '{}.{}'.format(uuid4().hex, ext)
        return os.path.join(self.resolve_sub_path(), filename)
