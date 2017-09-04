# -*- coding: utf-8 -*-
""" cropduster urls """

import os

from django.conf.urls import url
from django.views.static import serve

from cropduster import views

urlpatterns = [
    url(
        r'^_static/(?P<path>.*)$', serve,
        {"document_root": os.path.dirname(__file__) + "/media"},
        name='cropduster-static'
    ),
    url(r'^upload/$', views.upload, name='cropduster-upload'),
    url(r'^ratio/$', views.get_ratio, name='cropduster-ratio'),
]
