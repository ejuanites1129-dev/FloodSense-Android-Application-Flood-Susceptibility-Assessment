from django.urls import path

from .views import assessment_options, evaluate

app_name = "expert"

urlpatterns = [
    path("assessment-options/", assessment_options, name="assessment-options"),
    path("assessments/evaluate/", evaluate, name="evaluate"),
]
