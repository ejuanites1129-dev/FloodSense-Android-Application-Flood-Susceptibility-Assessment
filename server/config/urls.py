"""Top-level URL configuration for FloodSense."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("expert.urls")),
    path("api/v1/geography/", include("geography.urls")),
    path("api/v1/dss/", include("dss.urls")),
]

