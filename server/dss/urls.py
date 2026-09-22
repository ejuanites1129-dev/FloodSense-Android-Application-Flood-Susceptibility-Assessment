from django.urls import path

from .views import flow_answer, flow_start, guidance_collection

app_name = "dss"

urlpatterns = [
    path("guidance/", guidance_collection, name="guidance-collection"),
    path("flows/start/", flow_start, name="flow-start"),
    path("flows/<slug:code>/<str:version>/answer/", flow_answer, name="flow-answer"),
]
