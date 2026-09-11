from django.urls import path

from .views import area_collection

app_name = "geography"

urlpatterns = [
    path("areas/", area_collection, name="area-collection"),
]
