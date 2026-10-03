from django.urls import path

from .views import LocalPreviewNearestCenterView, NearestCenterView

app_name = "evacuation"

urlpatterns = [
    path("nearest/", NearestCenterView.as_view(), name="nearest-centers"),
    path("local-preview/nearest/", LocalPreviewNearestCenterView.as_view(), name="local-preview"),
]
