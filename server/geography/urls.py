from django.urls import path

from .views import (
    area_collection,
    reference_boundary_collection,
    resolve_barangay,
    resolve_point,
)

app_name = "geography"

urlpatterns = [
    path("areas/", area_collection, name="area-collection"),
    path(
        "reference-boundaries/",
        reference_boundary_collection,
        name="reference-boundary-collection",
    ),
    path("resolve-barangay/", resolve_barangay, name="resolve-barangay"),
    path("resolve-point/", resolve_point, name="resolve-point"),
]
