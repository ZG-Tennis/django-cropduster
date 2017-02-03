# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import cropduster.utils


class Migration(migrations.Migration):

    dependencies = [
        ('cropduster', '0002_auto_20151023_1424'),
    ]

    operations = [
        migrations.AlterField(
            model_name='image',
            name='image',
            field=models.ImageField(max_length=255, upload_to=cropduster.utils.UploadToPathAndRename(b'img/%Y/%m/%d', True), db_index=True),
        ),
    ]
