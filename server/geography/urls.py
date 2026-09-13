from django.urls import path

from .views import area_collection, resolve_point

app_name = "geography"

urlpatterns = [
    path("areas/", area_collection, name="area-collection"),
    path("resolve-point/", resolve_point, name="resolve-point"),
]
