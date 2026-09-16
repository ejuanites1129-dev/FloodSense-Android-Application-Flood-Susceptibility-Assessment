from django.urls import path

from .views import (
    AdminLoginView,
    AdminLogoutView,
    dashboard,
    password_help,
    section,
)

app_name = "admin_portal"

urlpatterns = [
    path("login/", AdminLoginView.as_view(), name="login"),
    path("logout/", AdminLogoutView.as_view(), name="logout"),
    path("password-help/", password_help, name="password-help"),
    path("", dashboard, name="dashboard"),
    path("<slug:section_slug>/", section, name="section"),
]
