# -*- coding: utf-8 -*-
""" cropduster models"""

import copy
import os
import urllib2
import cStringIO

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image as pil
from s3utils import S3utils

from cropduster import utils
from cropduster.constants import IMAGE_SAVE_PARAMS, MANUALLY_CROP, AUTO_CROP, \
    AUTO_SIZE, GENERATION_CHOICES, RETINA_POSTFIX
from cropduster.settings import CROPDUSTER_UPLOAD_PATH, \
    CROPDUSTER_RENAME_IMAGES


class CachingMixin(object):
    pass
CachingManager = models.Manager


class SizeSet(CachingMixin, models.Model):
    objects = CachingManager()

    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=50, null=False,)

    def __unicode__(self):
        return u"%s" % self.name

    def get_unique_ratios(self, created=True):
        """
        Shorthand to get all the unique ratios rather than show
        every possible thumbnail
        """
        create_on_request = not created

        size_query = Size.objects.all().filter(
            size_set__id=self.id, create_on_request=create_on_request)

        size_query.query.group_by = ["aspect_ratio"]
        try:
            return size_query
        except ValueError:
            return None


class SizeManager(CachingManager):

    def get_size_by_ratio(self, size_set, aspect_ratio_id):
        """ Gets the largest image of a certain ratio in this size set """

        try:
            aspect_ratio = self.get_queryset()\
                .filter(size_set=size_set, auto_size=MANUALLY_CROP)\
                .values_list('aspect_ratio', flat=True)\
                .distinct()\
                .order_by('-aspect_ratio')[aspect_ratio_id]

            # get the largest size with this aspect ratio
            return self.get_queryset()\
                .filter(size_set=size_set, aspect_ratio=aspect_ratio, auto_size=MANUALLY_CROP)\
                .order_by("-width")[0]
        except IndexError:
            return None


class Size(CachingMixin, models.Model):

    objects = SizeManager()

    name = models.CharField(max_length=255, db_index=True)

    slug = models.SlugField(max_length=50, null=False,)

    height = models.PositiveIntegerField(blank=True, null=True)

    width = models.PositiveIntegerField(blank=True, null=True)

    auto_size = models.PositiveIntegerField(
        "Thumbnail Generation", default=0, choices=GENERATION_CHOICES)

    size_set = models.ForeignKey(SizeSet)

    aspect_ratio = models.FloatField(default=1)

    create_on_request = models.BooleanField("Crop on request", default=False)

    retina = models.BooleanField("Auto-create retina thumb", default=False,)

    def clean(self):
        if not (self.width or self.height):
            raise ValidationError(
                "Size requires either a width, a height, or both")

        elif self.auto_size != AUTO_SIZE and not (self.width and self.height):
            # Raise a validation error if one of the sizes is not set for
            # cropping.
            # Auto-crop is the only one that can take a missing size.
            raise ValidationError("Auto-crop requires both sizes be specified")

    def save(self, *args, **kwargs):
        self.aspect_ratio = utils.aspect_ratio(self.width, self.height)
        super(Size, self).save(*args, **kwargs)

    class Meta:
        db_table = "cropduster_size"

    def __unicode__(self):
        return u"%s: %sx%s" % (self.name, self.width, self.height)

    @property
    def retina_size(self):
        """
        Returns a Size object based on the current object but for the
        retina size
        """
        retina_size = copy.copy(self)
        retina_size.width = retina_size.width * 2
        retina_size.height = retina_size.height * 2
        retina_size.slug = u"%s%s" % (retina_size.slug, RETINA_POSTFIX)

        return retina_size


class Crop(CachingMixin, models.Model):
    class Meta:
        db_table = "cropduster_crop"
        unique_together = (("size", "image"),)

    objects = CachingManager()

    crop_x = models.PositiveIntegerField(default=0, blank=True, null=True)
    crop_y = models.PositiveIntegerField(default=0, blank=True, null=True)
    crop_w = models.PositiveIntegerField(default=0, blank=True, null=True)
    crop_h = models.PositiveIntegerField(default=0, blank=True, null=True)

    size = models.ForeignKey(
        "cropduster.Size",
        related_name="size",
        verbose_name="sizes",
    )
    image = models.ForeignKey(
        "cropduster.Image",
        related_name="images",
        verbose_name="images",
    )

    def __unicode__(self):
        return u"%s: %sx%s" % (
            self.image.image, self.size.width, self.size.height)

    def save(self, *args, **kwargs):
        """
        Save the Crop object, and create the thumbnails by creating
        one rescaled version for each ratio and then resizing for each
        thumbnail within that ratio
        """
        super(Crop, self).save(*args, **kwargs)

        if self.size:
            # get all the manually cropped sizes with the same aspect
            # ratio as this crop/size
            sizes = Size.objects.all().filter(
                aspect_ratio=self.size.aspect_ratio,
                size_set=self.size.size_set,
                auto_size=0,
            ).order_by("-width")

            if sizes:
                # create the cropped image
                cropped_image = utils.create_cropped_image(
                    self.image.path,
                    self.crop_x,
                    self.crop_y,
                    self.crop_w,
                    self.crop_h
                )

                # loop through the other sizes of the same aspect ratio,
                # and create those crops
                for size in sizes:
                    self.image.rescale(cropped_image, size=size)

    def clean(self):

        if not hasattr(self, "crop_x") or not hasattr(self, "crop_y"):
            raise ValidationError("Missing crop values")

        if self.crop_x < 0 or self.crop_y < 0:
            raise ValidationError("Crop positions must be non-negative")

        if self.crop_w <= 0 or self.crop_h <= 0:
            raise ValidationError(
                "Crop measurements must be greater than zero")


class Image(CachingMixin, models.Model):

    objects = CachingManager()

    validate_image_size = True

    image = models.ImageField(
        upload_to=utils.UploadToPathAndRename(
            CROPDUSTER_UPLOAD_PATH + "%Y/%m/%d",
            CROPDUSTER_RENAME_IMAGES
        ),
        max_length=255,
        db_index=True
    )

    size_set = models.ForeignKey(
        SizeSet,
    )

    attribution = models.CharField(max_length=255, blank=True, null=True)

    caption = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "cropduster_image"
        verbose_name = "Image"
        verbose_name_plural = "Image"

    def __init__(self, *args, **kwargs):
        if "validate_image_size" in kwargs:
            self.validate_image_size = kwargs["validate_image_size"]
        super(Image, self).__init__(*args, **kwargs)

    def __unicode__(self):
        if self.image:
            return u"%s" % self.image.url
        else:
            return ""

    @property
    def path(self):
        """ Path to the original image file """
        try:
            return self.image.path
        except NotImplementedError:
            return self.image.url

    @property
    def extension(self):
        if hasattr(self.image, "url"):
            file_root, extension = os.path.splitext(self.path)
            return extension
        else:
            return ""

    @property
    def folder_path(self):
        """ System path to the folder containing the thumbnails """
        file_path, file_name = os.path.split(self.path)
        file_root, extension = os.path.splitext(file_name)
        return u"%s" % os.path.join(file_path, file_root)

    def thumbnail_path(self, size_slug, retina=False):
        """ System path to the image file for a thumbnail based on the slug """
        format = u"%s%s"
        if retina:
            format = u"%s" + RETINA_POSTFIX + "%s"

        return format % (
            os.path.join(self.folder_path, size_slug), self.extension)

    def retina_thumbnail_path(self, size_slug):
        """
        System path to the image file for a retina thumbnail based on the slug
        """
        return self.thumbnail_path(size_slug, retina=True)

    @property
    def folder_url(self):
        """ Web URL for the folder containing the thumbs """
        if hasattr(self.image, "url"):
            file_path, file_name = os.path.split(self.image.url)
            file_root, extension = os.path.splitext(file_name)
            return u"%s" % os.path.join(file_path, file_root)
        else:
            return ""

    def thumbnail_url(self, size_slug, retina=False):
        """ Web URL for a thumbnail based on the size slug """
        format = u"%s%s"
        if retina:
            format = u"%s" + RETINA_POSTFIX + "%s"
        return format % (
            os.path.join(self.folder_url, size_slug), self.extension)

    def retina_thumbnail_url(self, size_slug):
        """ Web URL for a thumbnail based on the size slug """
        return self.thumbnail_url(size_slug, retina=True)

    def has_size(self, size_slug):
        return self.size_set.size_set.filter(slug=size_slug).exists()

    def has_crop_for_size(self, size_slug):
        return Crop.objects\
            .filter(size__size_set=self.size_set, size__slug=size_slug, image=self)\
            .exists()

    def get_absolute_url(self):
        return settings.STATIC_URL + self.image

    def get_crop(self, size):
        """
        Gets the crop for this image and size based on size set and
        aspect ratio
        """
        return Crop.objects\
            .filter(
                size__size_set=size.size_set,
                size__aspect_ratio=size.aspect_ratio,
                image=self
            )\
            .order_by("-crop_w")[0]

    def save(self, *args, **kwargs):
        """
        Save the image object and create any auto-sized thumbnails
        that don't need crops
        Also, delete any old thumbs that aren't being written over
        """
        super(Image, self).save(*args, **kwargs)

        # get all the auto sized thumbnails and create them
        sizes = self.size_set.size_set.all().filter(
            auto_size__in=[AUTO_CROP, AUTO_SIZE],
            create_on_request=False
        )
        for size in sizes:
            self.create_thumbnail(size)

        # get all of the create on request sizes and delete the thumbnails
        # in anticipation of them being rewritten
        create_on_request_sizes = self.size_set.size_set.all().filter(
            auto_size__in=[AUTO_CROP, AUTO_SIZE],
            create_on_request=True
        )
        for size in create_on_request_sizes:
            # TODO: maybe a tweak to do this on s3 should be implemented...
            if os.path.exists(self.thumbnail_path(size.slug)):
                os.remove(self.thumbnail_path(size.slug))

    def clean(self):
        """ Additional file validation for saving """

        if self.image:
            # Check for valid file extension
            if os.path.splitext(self.image.name)[1] == '':
                raise ValidationError(
                    "Please make sure images have file extensions "
                    "before uploading"
                )

            # Check for valid file
            try:
                pil_image = pil.open(self.image)
            except:
                raise ValidationError("Unable to open image file")

            # Check for minimum size requirement
            if self.validate_image_size:
                for size in self.size_set.size_set.all().order_by("-width"):
                    if size.width > pil_image.size[0] or \
                            size.height > pil_image.size[1]:
                        raise ValidationError(
                            "Uploaded image (%s x %s) is smaller than a "
                            "required thumbnail size: %s"
                            % (pil_image.size[0], pil_image.size[1], size)
                        )

        return super(Image, self).clean()

    def get_width_height(self):
        """ Returns a tuple with the image with and height """
        try:
            pil_image = pil.open(self.image)
        except:
            return 0, 0
        return pil_image.size

    def create_thumbnail(self, size, force_crop=False):
        """ Creates a thumbnail for an image at the specified size """

        if not size.auto_size:
            try:
                crop = self.get_crop(size)

                cropped_image = utils.create_cropped_image(
                    self.path,
                    crop.crop_x,
                    crop.crop_y,
                    crop.crop_w,
                    crop.crop_h
                )
            except (Crop.DoesNotExist, IndexError):
                # auto-crop if no crop is defined
                try:
                    cropped_image = pil.open(self.path)
                except IOError:
                    img_file = cStringIO.StringIO(
                        urllib2.urlopen(self.path).read())
                    cropped_image = pil.open(img_file)
        else:
            try:
                cropped_image = pil.open(self.path)
            except IOError:
                img_file = cStringIO.StringIO(
                    urllib2.urlopen(self.path).read())
                cropped_image = pil.open(img_file)

        self.rescale(
            cropped_image=cropped_image, size=size, force_crop=force_crop)

    def thumb_to_s3(self, thumbnail, size):
        """
        Uploads an unsaved thumbnail, product of using
        cropduster.utils.rescale, into s3.
        """
        go_s3 = S3utils()
        img_string = cStringIO.StringIO()
        thumbnail_path = self.thumbnail_path(size.slug)
        output_path, crop_name = os.path.split(thumbnail_path)
        folder = output_path.replace(settings.MEDIA_URL, '')
        output_path = os.path.join(
            settings.MEDIAFILES_LOCATION, folder)
        thumbnail.save(img_string, "JPEG", **IMAGE_SAVE_PARAMS)
        # setting the content type manually, otherwise it will be saved
        # as content-type: application/octet-stream
        go_s3.AWS_HEADERS['Content-Type'] = 'image/jpeg'
        result = go_s3.cp_from_string(
            img_string, crop_name, output_path)
        if result:
            print "Image could not be loaded into s3 bucket. Error: {}"\
                .format(result)

    def rescale(self, cropped_image, size, force_crop=False):
        """
        Resizes and saves the image to other sizes of the same aspect
        ratio from a given cropped image
        """
        if force_crop or not size.create_on_request:
            auto_crop = (size.auto_size == AUTO_CROP)
            thumbnail = utils.rescale(
                cropped_image, size.width, size.height, auto_crop=auto_crop)

            path_is_url = utils.is_url(self.folder_path)

            if path_is_url:
                self.thumb_to_s3(thumbnail, size)
            else:
                # In case the thumbnail path hasn't been created yet
                if not os.path.exists(self.folder_path):
                    try:
                        os.makedirs(self.folder_path)
                    except OSError:
                        # Handles weird race conditions if the path wasn't
                        # created just yet
                        if os.path.exists(self.folder_path):
                            pass
                        else:
                            os.makedirs(self.folder_path)

                thumbnail.save(
                    self.thumbnail_path(size.slug), **IMAGE_SAVE_PARAMS)

            # Create retina image
            if size.retina:
                retina_size = size.retina_size

                # Only create retina image if cropped image is large enough
                # If retina size is required, make a separate size
                if retina_size.width <= cropped_image.size[0] and \
                        retina_size.height <= cropped_image.size[1]:
                    retina_thumbnail = utils.rescale(
                        cropped_image, retina_size.width, retina_size.height,
                        crop=retina_size.auto_size
                    )
                    if path_is_url:
                        self.thumb_to_s3(retina_thumbnail, retina_size)
                    else:
                        retina_thumbnail.save(
                            self.thumbnail_path(retina_size.slug),
                            **IMAGE_SAVE_PARAMS
                        )

    def tag(self, **kwargs):
        from cropduster.templatetags.images import get_image
        return get_image(self, **kwargs)


class CropDusterField(models.ForeignKey):
    pass
