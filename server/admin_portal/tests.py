from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminPortalAuthenticationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            email="maintainer@example.com",
            display_name="Test Maintainer",
            password="Strong-test-password-123",
            is_staff=True,
        )
        self.resident_user = user_model.objects.create_user(
            email="resident@example.com",
            display_name="Test Resident",
            password="Strong-test-password-123",
            is_staff=False,
        )

    def test_anonymous_dashboard_request_redirects_to_portal_login(self):
        response = self.client.get(reverse("admin_portal:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('admin_portal:login')}?next=/management/",
            fetch_redirect_response=False,
        )

    def test_staff_can_sign_in_with_email_and_open_dashboard(self):
        response = self.client.post(
            reverse("admin_portal:login"),
            {
                "username": self.staff_user.email,
                "password": "Strong-test-password-123",
            },
        )

        self.assertRedirects(response, reverse("admin_portal:dashboard"))
        dashboard_response = self.client.get(reverse("admin_portal:dashboard"))
        self.assertContains(dashboard_response, "Good day, Test Maintainer")

    def test_non_staff_account_cannot_sign_in_to_portal(self):
        response = self.client.post(
            reverse("admin_portal:login"),
            {
                "username": self.resident_user.email,
                "password": "Strong-test-password-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not authorized")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_non_staff_receives_forbidden_response(self):
        self.client.force_login(self.resident_user)

        response = self.client.get(reverse("admin_portal:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_every_planned_section_uses_protected_shared_shell(self):
        self.client.force_login(self.staff_user)
        section_slugs = (
            "assessment-parameters",
            "dss-content",
            "rainfall-references",
            "evacuation-centers",
            "sources-content",
            "audit-history",
            "settings",
        )

        for slug in section_slugs:
            with self.subTest(slug=slug):
                response = self.client.get(
                    reverse("admin_portal:section", kwargs={"section_slug": slug})
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Planned")

    def test_dashboard_uses_account_menu_instead_of_sidebar_footer(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin_portal:dashboard"))

        self.assertContains(response, ">Settings<")
        self.assertContains(response, ">Sign out<")
        self.assertNotContains(response, "Authorized maintainers only")
        self.assertNotContains(response, "Draft → Review → Approve")

    def test_logout_requires_post_and_ends_staff_session(self):
        self.client.force_login(self.staff_user)

        get_response = self.client.get(reverse("admin_portal:logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("admin_portal:logout"))
        self.assertRedirects(post_response, reverse("admin_portal:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_section_returns_not_found(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse(
                "admin_portal:section",
                kwargs={"section_slug": "not-a-real-module"},
            )
        )

        self.assertEqual(response.status_code, 404)


class AdminPortalPublicPageTests(TestCase):
    def test_login_and_password_help_are_public(self):
        self.assertEqual(self.client.get(reverse("admin_portal:login")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin_portal:password-help")).status_code,
            200,
        )
