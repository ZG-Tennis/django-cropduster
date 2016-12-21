# -*- coding: utf-8 -*-
""" cropduster templatetags images """

from django import template
from django.template.loader import get_template

from cropduster.constants import AUTO_SIZE
from cropduster.models import Size
from cropduster.settings import CROPDUSTER_CROP_ONLOAD, \
    CROPDUSTER_PLACEHOLDER_MODE
from cropduster.utils import path_exists


register = template.Library()

# preload a map of image sizes so it doesn"t make a DB call for
# each templatetag use
IMAGE_SIZE_MAP = {}
for size in Size.objects.all():
    IMAGE_SIZE_MAP[(size.size_set_id, size.slug)] = size


@register.filter
def get_image(
    image, size_name=None, template_name="image.html",
    retina=False, **kwargs
):
    """
    Templatetag to get the HTML for an image from a cropduster image object
    """
    if image:
        if CROPDUSTER_CROP_ONLOAD:
            # If set, will check for thumbnail existence
            # if not there, will create the thumb based on predefiend
            # crop/size settings
            thumb_path = image.thumbnail_path(size_name)
            if not path_exists(thumb_path) and path_exists(image.path):
                try:
                    size = image.size_set.size_set.get(slug=size_name)
                except Size.DoesNotExist:
                    return ""

                try:
                    image.create_thumbnail(size, force_crop=True)
                except:
                    return ""

        if retina:
            image_url = image.retina_thumbnail_url(size_name)
        else:
            image_url = image.thumbnail_url(size_name)

        if not image_url:
            return ""

        try:
            image_size = IMAGE_SIZE_MAP[(image.size_set_id, size_name)]
        except KeyError:
            return ""

        # Set all the args that get passed to the template
        kwargs["image_url"] = image_url

        if hasattr(image_size, "auto_size") and \
                image_size.auto_size != AUTO_SIZE:
            kwargs["width"] = image_size.width \
                if hasattr(image_size, "width") else ""
            kwargs["height"] = image_size.height \
                if hasattr(image_size, "height") else ""

        if CROPDUSTER_PLACEHOLDER_MODE:
            kwargs["image_url"] = "http://placehold.it/%sx%s" % (
                kwargs["width"], kwargs["height"])

        kwargs["size_name"] = size_name
        kwargs["attribution"] = image.attribution

        if hasattr(image, "caption"):
            kwargs["alt"] = image.caption

        if "title" not in kwargs:
            kwargs["title"] = kwargs["alt"]

        tmpl = get_template("templatetags/" + template_name)
        context = template.Context(kwargs)
        return tmpl.render(context)
    else:
        return ""


@register.filter
def thumbnail_url(image, size):
        return image.thumbnail_url(size.slug)


@register.filter
def pdb(variable):
    import pdb
    pdb.set_trace()
