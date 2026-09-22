"""Top-level URL configuration for FloodSense."""

from accounts.urls import account_patterns, auth_patterns, legal_patterns
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("management/", include("admin_portal.urls")),
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("expert.urls")),
    path("api/v1/geography/", include("geography.urls")),
    path("api/v1/evacuation-centers/", include("evacuation.urls")),
    path("api/v1/dss/", include("dss.urls")),
    path("api/v1/auth/", include((auth_patterns, "resident_auth"))),
    path("api/v1/account/", include((account_patterns, "resident_account"))),
    path("api/v1/legal/", include((legal_patterns, "legal"))),
]

