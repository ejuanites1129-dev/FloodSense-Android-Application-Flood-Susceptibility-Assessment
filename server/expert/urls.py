from django.urls import path

from .views import assessment_options, evaluate, evaluate_map

app_name = "expert"

urlpatterns = [
    path("assessment-options/", assessment_options, name="assessment-options"),
    path("assessments/evaluate/", evaluate, name="evaluate"),
    path("assessments/evaluate-map/", evaluate_map, name="evaluate-map"),
]
