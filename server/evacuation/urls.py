from django.urls import path

from .views import LocalPreviewNearestCenterView, MapCenterView, NearestCenterView

app_name = "evacuation"

urlpatterns = [
    path("map/", MapCenterView.as_view(), name="map-centers"),
    path("nearest/", NearestCenterView.as_view(), name="nearest-centers"),
    path("local-preview/nearest/", LocalPreviewNearestCenterView.as_view(), name="local-preview"),
]
