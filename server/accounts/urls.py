from django.urls import path

from . import views

app_name = "accounts"

auth_patterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),
    path("google/", views.google_auth, name="google"),
    path("token/refresh/", views.ResidentTokenRefreshView.as_view(), name="refresh"),
    path("logout/", views.logout, name="logout"),
    path("password-reset/request/", views.password_reset_request, name="reset-request"),
    path("password-reset/confirm/", views.password_reset_confirm, name="reset-confirm"),
    path("email/verify/", views.verify_email, name="email-verify"),
    path("email/resend/", views.resend_verification, name="email-resend"),
    path("setup-status/", views.setup_status, name="setup-status"),
    path("legal/required/", views.required_legal_documents, name="legal-required"),
    path("legal/accept/", views.accept_legal_documents, name="legal-accept"),
    path("onboarding/current/", views.current_onboarding, name="onboarding-current"),
    path("onboarding/acknowledge/", views.acknowledge_onboarding, name="onboarding-ack"),
]

account_patterns = [
    path("me/", views.account_me, name="me"),
    path("preferences/", views.account_preferences, name="preferences"),
    path("change-password/", views.change_password, name="change-password"),
    path("request-deletion/", views.request_deletion, name="request-deletion"),
    path("google/link/", views.link_google, name="google-link"),
    path("google/unlink/", views.unlink_google, name="google-unlink"),
]

legal_patterns = [
    path(
        "terms/current/",
        views.legal_document,
        {"document_type": "TERMS"},
        name="terms",
    ),
    path(
        "privacy/current/",
        views.legal_document,
        {"document_type": "PRIVACY"},
        name="privacy",
    ),
]
