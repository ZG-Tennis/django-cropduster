# -*- coding: utf-8 -*-
""" cropduster's views """

import io

from django.http import HttpResponse
from django.shortcuts import render
from django.forms import TextInput
from django.views.decorators.csrf import csrf_exempt
from django.forms import ModelForm
from django.conf import settings
import json

from cropduster.constants import BROWSER_WIDTH
from cropduster.exif import process_file
from cropduster.models import Image as CropDusterImage, Crop, Size, SizeSet
from cropduster.settings import CROPDUSTER_EXIF_DATA
from cropduster.utils import aspect_ratio, path_exists


def get_ratio(request):
    return HttpResponse(json.dumps(
        [u"%s" % aspect_ratio(request.GET["width"], request.GET["height"])]
    ))


# Create the form class.
class ImageForm(ModelForm):
    class Meta:
        model = CropDusterImage
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """
        * Initializes the form
        * Deactivates the image size validation
        """
        super(self.__class__, self).__init__(*args, **kwargs)
        if self.instance and self.instance.id:
            self.instance.validate_image_size = False


class CropForm(ModelForm):
    class Meta:
        model = Crop
        widgets = {
            "image": TextInput(),
        }
        fields = '__all__'


@csrf_exempt
def upload(request):
    size_set = SizeSet.objects.get(id=request.GET["size_set"])

    # Get the current aspect ratio
    if "aspect_ratio_id" in request.POST:
        aspect_ratio_id = int(request.POST["aspect_ratio_id"])
    else:
        aspect_ratio_id = 0

    image_id = None

    if "image_id" in request.GET:
        image_id = request.GET["image_id"]
    elif "image_id" in request.POST:
        image_id = request.POST["image_id"]

    try:
        image_id = int(image_id)
        image = CropDusterImage.objects.get(id=image_id)
    except:
        image = CropDusterImage(size_set=size_set)

    size = Size.objects.get_size_by_ratio(
        size_set.id, aspect_ratio_id) or Size()

    # Get the current crop
    try:
        crop = Crop.objects.get(image=image.id, size=size.id)
    except Crop.DoesNotExist:
        crop = Crop()
        crop.crop_w = size.width
        crop.crop_h = size.height
        crop.crop_x = 0
        crop.crop_y = 0
        crop.image = image
        crop.size = size

    if request.method == "POST":
        if request.FILES:
            # Process uploaded image form
            formset = ImageForm(request.POST, request.FILES, instance=image)

            if formset.is_valid():
                if CROPDUSTER_EXIF_DATA:
                    # Check for exif data and use it to populate
                    # caption/attribution
                    try:
                        exif_data = process_file(io.BytesIO(
                            b"%s" % formset.cleaned_data["image"]
                            .file.getvalue()
                        ))
                    except AttributeError:
                        exif_data = {}

                    if not formset.cleaned_data["caption"] and \
                            "Image ImageDescription" in exif_data:
                        formset.data["caption"] = exif_data[
                            "Image ImageDescription"].__str__()
                    if not formset.cleaned_data["attribution"] and \
                            "EXIF UserComment" in exif_data:
                        formset.data["attribution"] = \
                            exif_data["EXIF UserComment"].__str__()

                image = formset.save()
                crop.image = image
                crop_formset = CropForm(instance=crop)
            else:
                # Invalid upload return form
                errors = formset.errors.values()[0]
                return render(request, "admin/upload.html", {
                    "aspect_ratio_id": 0,
                    "errors": errors,
                    "formset": formset,
                    "image_element_id": request.GET["image_element_id"],
                    "static_url": settings.STATIC_URL,
                })

        else:
            # If its the first frame, get the image formset and
            # save it (for attribution)

            if not aspect_ratio_id:
                formset = ImageForm(request.POST, instance=image)
                if formset.is_valid():
                    formset.save()
            else:
                formset = ImageForm(instance=image)

            # If there's no cropping to be done, then just complete the process
            if size.id:
                # Lets save the crop
                request.POST['size'] = size.id
                request.POST['image'] = image.id
                crop_formset = CropForm(request.POST, instance=crop)

                if crop_formset.is_valid():
                    crop = crop_formset.save()
                    # Now get the next crop if it exists
                    aspect_ratio_id = aspect_ratio_id + 1
                    size = Size.objects.get_size_by_ratio(
                        size_set, aspect_ratio_id)
                    # If there's another crop
                    if size:
                        try:
                            crop = Crop.objects.get(
                                image=image.id, size=size.id)
                            crop_formset = CropForm(instance=crop)
                        except Crop.DoesNotExist:
                            crop = Crop()
                            crop.crop_w = size.width
                            crop.crop_h = size.height
                            crop.crop_x = 0
                            crop.crop_y = 0
                            crop.size = size
                            crop_formset = CropForm()

    # Nothing being posted, get the image and form if they exist
    else:
        formset = ImageForm(instance=image)
        crop_formset = CropForm(instance=crop)

    # If theres more cropping to be done or its the first frame,
    # show the upload/crop form
    if (size and size.id) or request.method != "POST":
        sizes_modified = False
        crop_w = crop.crop_w or size.width
        crop_h = crop.crop_h or size.height
        min_w = size.width
        min_h = size.height
        image_width, image_height = image.get_width_height()
        if image_width > 0 and image_height > 0:
            if image_width <= size.width or image_height <= size.height:
                # calculating new values holding width/height ratio
                dimentions_fixed = False
                height_buffer = image_height - 1
                while (not dimentions_fixed):
                    crop_h = int(round(height_buffer))
                    crop_w = int(round(size.aspect_ratio * crop_h))
                    if crop_w < image_width - 1:
                        dimentions_fixed = True
                    else:
                        height_buffer *= 0.9
                # calulating new min width and height values
                min_h = int(round(crop_h/10))
                min_w = int(round(size.aspect_ratio * min_h))
                sizes_modified = True

        # Combine errors from both forms, eliminate duplicates
        errors = dict(crop_formset.errors)
        errors.update(formset.errors)
        all_errors = []
        for error in errors.items():
            if error[0] != '__all__':
                string = u"%s: %s" % (
                    error[0].capitalize(), error[1].as_text())
            else:
                string = error[1].as_text()
            all_errors.append(string)

        if image.image:
            image_exists = path_exists(image.path)
        else:
            image_exists = False

        return render(request, "admin/upload.html", {
            "aspect_ratio": size.aspect_ratio,
            "aspect_ratio_id": aspect_ratio_id,
            "browser_width": BROWSER_WIDTH,
            "crop_formset": crop_formset,
            "crop_w": crop_w,
            "crop_h": crop_h,
            "crop_x": crop.crop_x or 0,
            "crop_y": crop.crop_y or 0,
            "errors": all_errors,
            "formset": formset,
            "image": image,
            "image_element_id": request.GET["image_element_id"],
            "image_exists": image_exists,
            "min_w": min_w,
            "min_h": min_h,
            "size_width": size.width,
            "size_height": size.height,
            "size_name": size.name,
            "static_url": settings.STATIC_URL,
            "sizes_modified": sizes_modified,
        })

    # No more cropping to be done, close out
    else:
        image_thumbs = [
            image.thumbnail_url(size_obj.slug) for size_obj in
            image.size_set.get_unique_ratios()
        ]

        return render(request, "admin/complete.html", {
            "image": image,
            "image_thumbs": image_thumbs,
            "image_element_id": request.GET["image_element_id"],
            "static_url": settings.STATIC_URL,
        })
