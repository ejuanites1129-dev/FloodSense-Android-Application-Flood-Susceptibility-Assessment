from django.urls import path

from .views import guidance_collection

app_name = "dss"

urlpatterns = [
    path("guidance/", guidance_collection, name="guidance-collection"),
]
