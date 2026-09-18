from django.urls import path

from .views import (
    AdminLoginView,
    AdminLogoutView,
    assessment_parameters,
    dashboard,
    map_data,
    password_help,
    section,
    settings_view,
)

app_name = "admin_portal"

urlpatterns = [
    path("login/", AdminLoginView.as_view(), name="login"),
    path("logout/", AdminLogoutView.as_view(), name="logout"),
    path("password-help/", password_help, name="password-help"),
    path("", dashboard, name="dashboard"),
    path("map-data/", map_data, name="map-data"),
    path("settings/", settings_view, name="settings"),
    path("assessment-parameters/", assessment_parameters, name="assessment-parameters"),
    path("<slug:section_slug>/", section, name="section"),
]
