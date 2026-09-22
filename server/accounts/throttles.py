from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginThrottle(AnonRateThrottle):
    scope = "resident_login"


class RegistrationThrottle(AnonRateThrottle):
    scope = "resident_registration"


class PasswordResetThrottle(AnonRateThrottle):
    scope = "resident_password_reset"


class VerificationThrottle(AnonRateThrottle):
    scope = "resident_verification"


class GoogleAuthThrottle(AnonRateThrottle):
    scope = "resident_google_auth"


class GoogleLinkThrottle(UserRateThrottle):
    scope = "resident_google_auth"


class TokenRefreshThrottle(AnonRateThrottle):
    scope = "resident_token_refresh"
