from django.urls import path

from .views import NearestCenterView

app_name = "evacuation"

urlpatterns = [
    path("nearest/", NearestCenterView.as_view(), name="nearest-centers"),
]
