from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from .models import (
    EmailVerificationChallenge,
    ExternalIdentity,
    LegalAcceptance,
    LegalDocumentVersion,
    OnboardingAcknowledgement,
    OnboardingVersion,
    User,
)
from .throttles import LoginThrottle

FAST_TEST_RATES = {
    "nearest_centers": "1000/min",
    "resident_login": "1000/min",
    "resident_registration": "1000/min",
    "resident_password_reset": "1000/min",
    "resident_verification": "1000/min",
    "resident_google_auth": "1000/min",
    "resident_token_refresh": "1000/min",
}


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.IsAuthenticated",
        ),
        "DEFAULT_THROTTLE_RATES": FAST_TEST_RATES,
    },
)
class ResidentAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _user(self, **overrides):
        values = {
            "email": "resident@example.com",
            "resident_username": "resident",
            "display_name": "resident",
            "password": "Strong-Test-Password-482!",
            "email_verified_at": timezone.now(),
        }
        values.update(overrides)
        return User.objects.create_user(**values)

    def _login(self, identifier="resident", password="Strong-Test-Password-482!"):
        return self.client.post(
            "/api/v1/auth/login/",
            {"identifier": identifier, "password": password, "remember_me": True},
            format="json",
        )

    def test_registration_normalizes_identifiers_and_sends_one_time_verification(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "Resident.One",
                "email": "Resident@Example.COM",
                "password": "Strong-Test-Password-482!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get()
        self.assertEqual(user.resident_username, "resident.one")
        self.assertEqual(user.email, "resident@example.com")
        self.assertIsNone(user.email_verified_at)
        self.assertNotIn("access", response.data)
        self.assertEqual(len(mail.outbox), 1)
        link = next(line for line in mail.outbox[0].body.splitlines() if "?" in line)
        token = parse_qs(urlparse(link).query)["token"][0]

        verified = self.client.post(
            "/api/v1/auth/email/verify/", {"token": token}, format="json"
        )
        reused = self.client.post(
            "/api/v1/auth/email/verify/", {"token": token}, format="json"
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(reused.status_code, 400)

    def test_registration_rejects_duplicate_case_invalid_values_and_weak_password(self):
        self._user()
        duplicate = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "RESIDENT",
                "email": "other@example.com",
                "password": "Strong-Test-Password-482!",
            },
            format="json",
        )
        invalid = self.client.post(
            "/api/v1/auth/register/",
            {"username": "bad user", "email": "not-email", "password": "123"},
            format="json",
        )
        duplicate_email = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "someone",
                "email": "RESIDENT@EXAMPLE.COM",
                "password": "Strong-Test-Password-482!",
            },
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate_email.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("username", invalid.data)
        self.assertIn("email", invalid.data)

    def test_legacy_staff_account_remains_valid_without_resident_username(self):
        staff = User.objects.create_superuser(
            email="staff@example.com", password="Admin-Test-Password-482!", display_name="Staff"
        )
        staff.full_clean()
        self.assertIsNone(staff.resident_username)
        self.assertTrue(staff.check_password("Admin-Test-Password-482!"))

    def test_login_by_username_or_email_is_case_insensitive_and_generic_on_failure(self):
        self._user()
        by_username = self._login("RESIDENT")
        by_email = self._login("Resident@Example.COM")
        bad_password = self._login(password="wrong")
        unknown = self._login("nobody")
        self.assertEqual(by_username.status_code, 200)
        self.assertEqual(by_email.status_code, 200)
        self.assertNotIn("password", by_username.data["user"])
        self.assertEqual(bad_password.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(bad_password.data, unknown.data)

    def test_inactive_and_unverified_users_receive_no_tokens(self):
        unverified = self._user(email_verified_at=None)
        response = self._login()
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("access", response.data)
        unverified.is_active = False
        unverified.save(update_fields=("is_active",))
        inactive = self._login()
        self.assertEqual(inactive.status_code, 401)

    def test_refresh_and_logout_blacklist_refresh_token(self):
        self._user()
        login = self._login()
        refresh = login.data["refresh"]
        refreshed = self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json"
        )
        self.assertEqual(refreshed.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        rotated_refresh = refreshed.data["refresh"]
        logout = self.client.post(
            "/api/v1/auth/logout/", {"refresh": rotated_refresh}, format="json"
        )
        self.assertEqual(logout.status_code, 204)
        revoked = self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json"
        )
        self.assertEqual(revoked.status_code, 401)

    def test_password_reset_is_non_enumerating_validated_and_one_use(self):
        user = self._user()
        known = self.client.post(
            "/api/v1/auth/password-reset/request/",
            {"email": user.email},
            format="json",
        )
        unknown = self.client.post(
            "/api/v1/auth/password-reset/request/",
            {"email": "unknown@example.com"},
            format="json",
        )
        self.assertEqual(known.data, unknown.data)
        link = next(line for line in mail.outbox[0].body.splitlines() if "?" in line)
        query = parse_qs(urlparse(link).query)
        weak = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": query["uid"][0], "token": query["token"][0], "new_password": "123"},
            format="json",
        )
        self.assertEqual(weak.status_code, 400)
        valid = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": "Replacement-Password-938!",
            },
            format="json",
        )
        reused = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": query["uid"][0],
                "token": query["token"][0],
                "new_password": "Another-Password-938!",
            },
            format="json",
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(reused.status_code, 400)

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_expired_password_reset_token_is_rejected(self):
        user = self._user()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        with patch("django.contrib.auth.tokens.PasswordResetTokenGenerator._now") as now:
            now.return_value = datetime.now() + timedelta(seconds=2)
            response = self.client.post(
                "/api/v1/auth/password-reset/confirm/",
                {"uid": uid, "token": token, "new_password": "Replacement-Password-938!"},
                format="json",
            )
        self.assertEqual(response.status_code, 400)

    @override_settings(GOOGLE_OAUTH_WEB_CLIENT_ID="")
    def test_google_missing_configuration_is_graceful(self):
        response = self.client.post(
            "/api/v1/auth/google/", {"id_token": "opaque"}, format="json"
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "google_not_configured")

    @override_settings(GOOGLE_OAUTH_WEB_CLIENT_ID="server-client-id")
    @patch("accounts.views.google_id_token.verify_oauth2_token")
    def test_google_invalid_signature_wrong_audience_and_expiry_are_generic(
        self, verify
    ):
        for reason in ("invalid signature", "wrong audience", "expired"):
            with self.subTest(reason=reason):
                verify.side_effect = ValueError(reason)
                response = self.client.post(
                    "/api/v1/auth/google/", {"id_token": "opaque"}, format="json"
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.data["detail"],
                    "Google authentication could not be verified.",
                )
        self.assertTrue(
            all(
                call.kwargs["audience"] == "server-client-id"
                for call in verify.call_args_list
            )
        )

    @override_settings(GOOGLE_OAUTH_WEB_CLIENT_ID="server-client-id")
    @patch("accounts.views.google_id_token.verify_oauth2_token")
    def test_google_requires_subject_verified_email_and_email_claim(self, verify):
        for claims in (
            {"email": "google@example.com", "email_verified": True},
            {"sub": "subject", "email": "google@example.com", "email_verified": False},
            {"sub": "subject", "email_verified": True},
        ):
            with self.subTest(claims=claims):
                verify.side_effect = None
                verify.return_value = claims
                response = self.client.post(
                    "/api/v1/auth/google/", {"id_token": "opaque"}, format="json"
                )
                self.assertEqual(response.status_code, 401)

    @patch("accounts.views._verified_google_claims")
    def test_google_new_linked_and_unsafe_email_match_flows(self, verify):
        verify.return_value = {
            "sub": "google-subject-1",
            "email": "google@example.com",
            "email_verified": True,
        }
        created = self.client.post(
            "/api/v1/auth/google/",
            {"id_token": "opaque", "username": "google.user"},
            format="json",
        )
        linked = self.client.post(
            "/api/v1/auth/google/", {"id_token": "opaque"}, format="json"
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(linked.status_code, 200)
        verify.return_value = {
            "sub": "different-subject",
            "email": "google@example.com",
            "email_verified": True,
        }
        unsafe = self.client.post(
            "/api/v1/auth/google/", {"id_token": "opaque"}, format="json"
        )
        self.assertEqual(unsafe.status_code, 409)
        self.assertEqual(ExternalIdentity.objects.count(), 1)

    def test_expired_email_verification_token_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "expiring.user",
                "email": "expiring@example.com",
                "password": "Strong-Test-Password-482!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        EmailVerificationChallenge.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        link = next(line for line in mail.outbox[0].body.splitlines() if "?" in line)
        token = parse_qs(urlparse(link).query)["token"][0]
        expired = self.client.post(
            "/api/v1/auth/email/verify/", {"token": token}, format="json"
        )
        self.assertEqual(expired.status_code, 400)
        self.assertIsNone(User.objects.get(email="expiring@example.com").email_verified_at)


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": (
            "rest_framework.permissions.IsAuthenticated",
        ),
        "DEFAULT_THROTTLE_RATES": FAST_TEST_RATES,
    }
)
class ResidentSetupAndAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="resident@example.com",
            resident_username="resident",
            display_name="resident",
            password="Strong-Test-Password-482!",
            email_verified_at=timezone.now(),
        )
        self.client.force_authenticate(self.user)

    def _published_legal(self, kind, version="1"):
        return LegalDocumentVersion.objects.create(
            document_type=kind,
            version=version,
            title=f"Test {kind}",
            summary="Test only.",
            effective_date=timezone.localdate(),
            status=LegalDocumentVersion.Status.PUBLISHED,
            requires_acceptance=True,
            published_at=timezone.now(),
        )

    def test_drafts_are_publicly_labeled_but_do_not_gate_accounts(self):
        LegalDocumentVersion.objects.create(
            document_type=LegalDocumentVersion.DocumentType.TERMS,
            version="test-draft",
            title="Prototype draft",
            summary="Test only.",
            status=LegalDocumentVersion.Status.DRAFT,
        )
        terms = self.client.get("/api/v1/legal/terms/current/")
        setup = self.client.get("/api/v1/auth/setup-status/")
        self.assertEqual(terms.status_code, 200)
        self.assertTrue(terms.data["prototype_draft"])
        self.assertFalse(terms.data["requires_acceptance"])
        self.assertEqual(setup.data["stage"], "configuration_required")

    def test_public_legal_endpoints_return_published_current_versions(self):
        terms = self._published_legal(LegalDocumentVersion.DocumentType.TERMS)
        privacy = self._published_legal(LegalDocumentVersion.DocumentType.PRIVACY)
        for path, expected in (
            ("/api/v1/legal/terms/current/", terms),
            ("/api/v1/legal/privacy/current/", privacy),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["id"], expected.pk)
                self.assertFalse(response.data["prototype_draft"])

    def test_acceptance_and_onboarding_are_version_specific_gates(self):
        terms = self._published_legal(LegalDocumentVersion.DocumentType.TERMS)
        privacy = self._published_legal(LegalDocumentVersion.DocumentType.PRIVACY)
        onboarding = OnboardingVersion.objects.create(
            version="1",
            status=OnboardingVersion.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        setup = self.client.get("/api/v1/auth/setup-status/")
        self.assertEqual(setup.data["stage"], "awaiting_legal_acceptance")
        accepted = self.client.post(
            "/api/v1/auth/legal/accept/",
            {"document_version_ids": [terms.pk, privacy.pk], "application_version": "test"},
            format="json",
        )
        self.assertEqual(accepted.data["stage"], "awaiting_onboarding")
        duplicate = self.client.post(
            "/api/v1/auth/legal/accept/",
            {"document_version_ids": [terms.pk, privacy.pk]},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(LegalAcceptance.objects.count(), 2)
        completed = self.client.post(
            "/api/v1/auth/onboarding/acknowledge/",
            {"version": onboarding.version},
            format="json",
        )
        self.assertEqual(completed.data["stage"], "authenticated_ready")
        self.assertEqual(OnboardingAcknowledgement.objects.count(), 1)

    def test_account_update_preferences_and_deletion_require_authentication(self):
        updated = self.client.patch(
            "/api/v1/account/me/", {"username": "new.name"}, format="json"
        )
        preferences = self.client.patch(
            "/api/v1/account/preferences/",
            {"high_contrast": True, "reduce_motion": True},
            format="json",
        )
        deletion = self.client.post("/api/v1/account/request-deletion/", {}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["username"], "new.name")
        self.assertTrue(preferences.data["high_contrast"])
        self.assertFalse(preferences.data["stores_precise_coordinates"])
        self.assertEqual(deletion.status_code, 201)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/v1/account/me/").status_code, 401)

    def test_preferences_reject_unknown_or_wrong_default_records(self):
        response = self.client.patch(
            "/api/v1/account/preferences/",
            {
                "home_barangay_id": 999999,
                "default_rainfall_intensity_id": 999998,
                "default_rainfall_duration_id": 999997,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.data),
            {
                "home_barangay_id",
                "default_rainfall_intensity_id",
                "default_rainfall_duration_id",
            },
        )

    @patch("accounts.views._verified_google_claims")
    def test_change_password_and_google_linking_require_reauthentication(self, verify):
        weak = self.client.post(
            "/api/v1/account/change-password/",
            {"current_password": "wrong", "new_password": "123"},
            format="json",
        )
        self.assertEqual(weak.status_code, 400)
        changed = self.client.post(
            "/api/v1/account/change-password/",
            {
                "current_password": "Strong-Test-Password-482!",
                "new_password": "Replacement-Password-938!",
            },
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Replacement-Password-938!"))

        verify.return_value = {
            "sub": "linked-google-subject",
            "email": "verified-google@example.com",
            "email_verified": True,
        }
        denied_link = self.client.post(
            "/api/v1/account/google/link/",
            {"password": "wrong", "id_token": "opaque"},
            format="json",
        )
        linked = self.client.post(
            "/api/v1/account/google/link/",
            {"password": "Replacement-Password-938!", "id_token": "opaque"},
            format="json",
        )
        denied_unlink = self.client.post(
            "/api/v1/account/google/unlink/",
            {"password": "wrong"},
            format="json",
        )
        unlinked = self.client.post(
            "/api/v1/account/google/unlink/",
            {"password": "Replacement-Password-938!"},
            format="json",
        )
        self.assertEqual(denied_link.status_code, 401)
        self.assertEqual(linked.status_code, 200)
        self.assertEqual(denied_unlink.status_code, 401)
        self.assertEqual(unlinked.status_code, 204)
        self.assertFalse(ExternalIdentity.objects.filter(user=self.user).exists())

    def test_new_required_legal_version_triggers_reconsent(self):
        OnboardingVersion.objects.create(
            version="current",
            status=OnboardingVersion.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        terms = self._published_legal(LegalDocumentVersion.DocumentType.TERMS)
        privacy = self._published_legal(LegalDocumentVersion.DocumentType.PRIVACY)
        LegalAcceptance.objects.create(
            user=self.user,
            document_version=terms,
            acceptance_source=LegalAcceptance.Source.ANDROID,
        )
        LegalAcceptance.objects.create(
            user=self.user,
            document_version=privacy,
            acceptance_source=LegalAcceptance.Source.ANDROID,
        )
        terms.status = LegalDocumentVersion.Status.RETIRED
        terms.save(update_fields=("status",))
        self._published_legal(LegalDocumentVersion.DocumentType.TERMS, version="2")
        setup = self.client.get("/api/v1/auth/setup-status/")
        self.assertEqual(setup.data["stage"], "awaiting_legal_acceptance")


class ResidentThrottleTests(TestCase):
    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": (
                "rest_framework_simplejwt.authentication.JWTAuthentication",
            ),
            "DEFAULT_PERMISSION_CLASSES": (
                "rest_framework.permissions.IsAuthenticated",
            ),
            "DEFAULT_THROTTLE_RATES": {**FAST_TEST_RATES, "resident_login": "2/min"},
        }
    )
    @patch.object(LoginThrottle, "rate", "2/min", create=True)
    def test_login_endpoint_is_throttled(self):
        cache.clear()
        client = APIClient()
        statuses = [
            client.post(
                "/api/v1/auth/login/",
                {"identifier": "unknown", "password": "wrong"},
                format="json",
            ).status_code
            for _ in range(3)
        ]
        self.assertEqual(statuses, [401, 401, 429])
