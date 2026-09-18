"""Settings governance boundary tests; all fixtures are isolated synthetic data."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape
from expert.models import RuleSet, ScenarioOption
from provenance.models import DataSource, PublicationStatus

from .services.settings_data import _active_version_states, get_settings_data
from .test_dashboard import DashboardHTML
from .views import settings_view


class SettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="settings-staff@example.com",
            display_name="Settings maintainer",
            is_staff=True,
            home_barangay="PRIVATE_HOME_SENTINEL",
            disclaimer_version_accepted="PRIVATE_DISCLAIMER_SENTINEL",
        )

    def setUp(self):
        self.url = reverse("admin_portal:settings")
        self.alias = reverse("admin_portal:assessment-parameters")
        self.client.force_login(self.staff)

    def source(self, status=PublicationStatus.DEMONSTRATION, **overrides):
        data = {
            "name": "Synthetic Settings source",
            "organization": "Synthetic organization",
            "source_type": (
                DataSource.SourceType.DEMONSTRATION
                if status == PublicationStatus.DEMONSTRATION
                else DataSource.SourceType.AGENCY_DATASET
            ),
            "status": status,
            "is_publicly_releasable": status != PublicationStatus.DEMONSTRATION,
            "notes": "PRIVATE_SOURCE_NOTES",
            "permitted_use": "PRIVATE_SOURCE_USAGE",
        }
        return DataSource.objects.create(**(data | overrides))

    def option(self, source=None, **overrides):
        source = source or self.source()
        data = {
            "label": "Synthetic intensity",
            "code": "SYNTHETIC_OPTION",
            "category": ScenarioOption.Category.INTENSITY,
            "derived_value": Decimal("2.5"),
            "unit": "fixture unit",
            "status": source.status,
            "source": source,
            "is_enabled": True,
            "display_order": 7,
        }
        return ScenarioOption.objects.create(**(data | overrides))

    def ruleset(self, source=None, **overrides):
        source = source or self.source()
        data = {
            "name": "Synthetic knowledge set",
            "version": "fixture-2.3",
            "mode": (
                RuleSet.Mode.DEMONSTRATION
                if source.status == PublicationStatus.DEMONSTRATION
                else RuleSet.Mode.OFFICIAL
            ),
            "source": source,
            "status": source.status,
            "effective_on": date(2026, 9, 1),
            "is_active": True,
            "change_summary": "PRIVATE_RULE_CHANGE_SUMMARY",
        }
        return RuleSet.objects.create(**(data | overrides))

    def test_anonymous_and_nonstaff_are_denied_for_both_routes(self):
        client = Client()
        for url in (self.url, self.alias):
            self.assertRedirects(
                client.get(url),
                f"{reverse('admin_portal:login')}?next={url}",
                fetch_redirect_response=False,
            )
        client.force_login(
            get_user_model().objects.create_user(email="settings-resident@example.com")
        )
        for url in (self.url, self.alias):
            self.assertEqual(client.get(url).status_code, 403)

    def test_inactive_staff_denied_before_any_queries(self):
        self.staff.is_active = False
        request = RequestFactory().get(self.url)
        request.user = self.staff
        with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            settings_view(request)

    def test_empty_settings_has_truthful_states_and_own_profile(self):
        response = self.client.get(self.url)
        self.assertContains(response, "No reviewable scenario references")
        self.assertContains(response, "0 matching of 0 reviewable references")
        self.assertContains(response, "No active rule set is recorded for this mode.", count=2)
        self.assertContains(response, "Awaiting confirmed requirements")
        self.assertContains(response, self.staff.email)
        self.assertContains(response, "Parameter changes await governance approval")
        for hidden in (
            "PRIVATE_HOME_SENTINEL",
            "PRIVATE_DISCLAIMER_SENTINEL",
            "is_superuser",
            "is_staff",
            "password",
            "groups",
            "user_permissions",
        ):
            self.assertNotContains(response, hidden)

    def test_existing_named_routes_still_resolve_and_alias_redirects(self):
        self.assertEqual(
            self.url, reverse("admin_portal:section", kwargs={"section_slug": "settings"})
        )
        self.assertEqual(
            self.alias,
            reverse("admin_portal:section", kwargs={"section_slug": "assessment-parameters"}),
        )
        self.assertRedirects(self.client.get(self.alias), f"{self.url}#parameters")

    def test_every_non_get_method_is_rejected_and_no_writes_occur(self):
        for url in (self.url, self.alias):
            for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"):
                with (
                    self.subTest(url=url, method=method),
                    CaptureQueriesContext(connection) as queries,
                ):
                    response = self.client.generic(method, url)
                    self.assertEqual(response.status_code, 405)
                    self.assertEqual(response.headers["Allow"], "GET")
                self.assertTrue(
                    all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries)
                )

    def test_demo_and_approved_records_are_separate_even_with_similar_names(self):
        self.option()
        self.option(self.source(PublicationStatus.APPROVED), code="APPROVED_FIXTURE")
        self.option(self.source(PublicationStatus.PENDING_VALIDATION), code="PENDING_FIXTURE")
        groups = get_settings_data()["groups"]
        self.assertEqual([g["total"] for g in groups], [1, 1, 1])
        self.assertEqual(groups[0]["records"][0]["code"], "SYNTHETIC_OPTION")
        self.assertEqual(groups[1]["records"][0]["code"], "APPROVED_FIXTURE")
        self.assertEqual(groups[2]["records"][0]["code"], "PENDING_FIXTURE")
        self.assertContains(self.client.get(self.url), "Demonstration only")

    def test_mismatched_demo_marker_never_becomes_an_official_reference(self):
        source = self.source(
            PublicationStatus.APPROVED, source_type=DataSource.SourceType.DEMONSTRATION
        )
        self.option(source)
        groups = get_settings_data()["groups"]
        self.assertEqual([g["total"] for g in groups], [1, 0, 0])
        self.assertIn("Not eligible", groups[0]["records"][0]["eligible_mode"])

    def test_restricted_retired_and_nonpublic_sources_and_records_are_withheld(self):
        public_source = self.source(PublicationStatus.APPROVED)
        for index, status in enumerate((PublicationStatus.RESTRICTED, PublicationStatus.RETIRED)):
            self.option(public_source, code=f"PRIVATE_RECORD_{index}", status=status)
            source = self.source(status, name=f"PRIVATE_SOURCE_{index}")
            self.option(
                source, code=f"PRIVATE_SOURCE_OPTION_{index}", status=PublicationStatus.APPROVED
            )
        private = self.source(
            PublicationStatus.APPROVED,
            is_publicly_releasable=False,
            name="PRIVATE_UNRELEASED_SOURCE",
        )
        self.option(private, code="PRIVATE_UNRELEASED_OPTION")
        self.ruleset(private, name="PRIVATE_ACTIVE_RULESET")
        response = self.client.get(self.url)
        self.assertEqual(response.context["settings_data"]["total"], 0)
        self.assertContains(response, "Active version unavailable")
        self.assertNotContains(response, "PRIVATE_")

    def test_active_metadata_is_database_backed_for_each_mode(self):
        self.ruleset()
        self.ruleset(
            self.source(PublicationStatus.APPROVED),
            name="Approved synthetic set",
            version="official-fixture-4",
        )
        response = self.client.get(self.url)
        states = response.context["settings_data"]["active_versions"]
        self.assertEqual([s["state"] for s in states], ["available", "available"])
        self.assertEqual(
            [s["record"]["version"] for s in states], ["fixture-2.3", "official-fixture-4"]
        )
        self.assertEqual(states[0]["record"]["effective_on"], date(2026, 9, 1))
        self.assertContains(response, "Synthetic organization")
        self.assertNotContains(response, "Active version unavailable")

    def test_inactive_metadata_is_not_present(self):
        self.ruleset(name="INACTIVE_NAME_SENTINEL", is_active=False)
        response = self.client.get(self.url)
        self.assertNotContains(response, "INACTIVE_NAME_SENTINEL")
        self.assertContains(response, "No active rule set is recorded", count=2)

    def test_pending_or_mode_mismatched_active_ruleset_is_withheld(self):
        ruleset = self.ruleset(mode=RuleSet.Mode.OFFICIAL, name="MISMATCH_SENTINEL")
        response = self.client.get(self.url)
        self.assertContains(response, "Active version unavailable")
        self.assertNotContains(response, "MISMATCH_SENTINEL")
        ruleset.mode = RuleSet.Mode.DEMONSTRATION
        ruleset.status = PublicationStatus.PENDING_VALIDATION
        ruleset.save()
        response = self.client.get(self.url)
        self.assertContains(response, "Active version unavailable")
        self.assertNotContains(response, "MISMATCH_SENTINEL")

    def test_blank_version_is_not_fabricated(self):
        self.ruleset(version=" ", name="MISSING_VERSION_SENTINEL")
        response = self.client.get(self.url)
        self.assertContains(response, "Active version unavailable")
        self.assertNotContains(response, "MISSING_VERSION_SENTINEL")

    def test_unknown_mode_has_safe_warning(self):
        self.ruleset(mode="UNSUPPORTED", name="UNKNOWN_MODE_SENTINEL")
        response = self.client.get(self.url)
        self.assertContains(response, "unsupported operating mode")
        self.assertNotContains(response, "UNKNOWN_MODE_SENTINEL")

    def test_multiple_active_defense_withholds_metadata_without_removing_constraints(self):
        # The checked-in DB constraint prevents duplicates. Exercise the defensive
        # state builder with legacy/corrupt inputs without weakening that constraint.
        candidate = {"mode": "DEMONSTRATION", "name": "Duplicate private name", "version": "1"}
        for candidates in ([candidate], [candidate, candidate]):
            states = _active_version_states({"DEMONSTRATION": 2}, candidates)
            self.assertEqual(states[0]["state"], "unavailable")
            self.assertIsNone(states[0]["record"])
        context = get_settings_data()
        context["active_versions"] = states
        with patch("admin_portal.views.get_settings_data", return_value=context):
            response = self.client.get(self.url)
        self.assertContains(response, "Active version unavailable")
        self.assertNotContains(response, "Duplicate private name")

    def test_missing_effective_date_and_revision_information_are_truthful(self):
        self.ruleset(effective_on=None)
        self.option(derived_value=None, unit="")
        response = self.client.get(self.url)
        self.assertContains(response, "Not recorded")
        self.assertContains(response, "not recorded in the current data model")
        self.assertIsNone(
            response.context["settings_data"]["groups"][0]["records"][0]["derived_value"]
        )

    def test_zero_values_and_disabled_state_are_preserved(self):
        self.option(
            minimum_value=0, maximum_value=0, derived_value=0, is_enabled=False, display_order=0
        )
        record = get_settings_data()["groups"][0]["records"][0]
        self.assertEqual(record["derived_value"], Decimal("0"))
        self.assertEqual(record["minimum"], Decimal("0"))
        self.assertEqual(record["maximum"], Decimal("0"))
        self.assertFalse(record["enabled"])
        self.assertEqual(record["display_order"], 0)

    def test_search_label_code_category_and_no_results_without_javascript(self):
        self.option()
        self.option(code="DURATION_FIXTURE", label="Synthetic duration", category="DURATION")
        for filters in ({"q": "InTEnsITY"}, {"q": "synthetic_option"}, {"category": "DURATION"}):
            response = self.client.get(self.url, filters)
            self.assertEqual(response.context["settings_data"]["matching"], 1)
            self.assertEqual(response.context["settings_data"]["total"], 2)
        self.assertContains(
            self.client.get(self.url, {"q": "NO_SUCH_REFERENCE"}),
            "No references match these filters",
        )

    def test_invalid_filter_has_accessible_summary_and_does_not_hide_records(self):
        self.option()
        for filters in ({"category": "not-a-category"}, {"q": "x" * 121}):
            response = self.client.get(self.url, filters)
            self.assertContains(response, "Filters were not applied")
            self.assertEqual(response.context["settings_data"]["matching"], 1)
            self.assertTrue(DashboardHTML(response).select(role="alert"))
            error_id = "id_category_error" if "category" in filters else "id_q_error"
            self.assertTrue(DashboardHTML(response).select(id=error_id))

    def test_user_controlled_text_is_escaped(self):
        unsafe = '<img src=x onerror="alert(1)">'
        source = self.source(name=unsafe, organization=unsafe)
        self.option(source, label=unsafe, code=unsafe, unit=unsafe)
        self.ruleset(source, name=unsafe, version=unsafe)
        self.staff.display_name = unsafe
        self.staff.save(update_fields=["display_name"])
        response = self.client.get(self.url, {"q": "<script>"})
        self.assertContains(response, escape(unsafe))
        self.assertNotContains(response, unsafe)
        response = self.client.get(self.url)
        self.assertContains(response, escape(unsafe))
        self.assertFalse(DashboardHTML(response).select("img", onerror="alert(1)"))

    def test_queries_are_read_only_allowlisted_and_constant_with_more_records(self):
        self.ruleset()
        source = self.source()
        for count in (1, 20):
            for number in range(count):
                self.option(source, code=f"fixture-{count}-{number}")
            with self.assertNumQueries(3), CaptureQueriesContext(connection) as queries:
                get_settings_data()
            for query in queries:
                sql = query["sql"].lower()
                self.assertTrue(sql.lstrip().startswith("select"))
                for forbidden in (
                    "expert_expertrule",
                    "expert_expertrulecondition",
                    '"notes"',
                    '"permitted_use"',
                    '"change_summary"',
                ):
                    self.assertNotIn(forbidden, sql)
        response = self.client.get(self.url)
        self.assertNotContains(response, "PRIVATE_")
        for link in DashboardHTML(response).select("a"):
            self.assertFalse(link["attrs"].get("href", "").startswith("/admin/"))

    def test_settings_get_cannot_change_api_options_or_create_audit_events(self):
        self.option()
        from django.contrib.admin.models import LogEntry

        api_url = reverse("expert:assessment-options")
        before = self.client.get(api_url).json()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url, {"derived_value": "999", "is_enabled": "False"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(api_url).json(), before)
        self.assertEqual(LogEntry.objects.count(), 0)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))

    def test_settings_group_navigation_and_regression_links(self):
        response = self.client.get(self.url)
        html = DashboardHTML(response)
        self.assertTrue(html.select("nav", **{"aria-label": "Settings sections"}))
        self.assertTrue(html.select("a", href=self.url, **{"aria-current": "page"}))
        self.assertTrue(
            html.select("form", method="get", **{"aria-label": "Filter scenario references"})
        )
        self.assertEqual(len(html.select("h1")), 1)
        for anchor in (
            "settings-overview",
            "account",
            "methodology",
            "parameters",
            "data-exchange",
        ):
            self.assertTrue(html.select("a", href=f"#{anchor}"))
            self.assertTrue(html.select(id=anchor))
        self.assertContains(
            self.client.get(reverse("admin_portal:dashboard")), f"{self.url}#parameters"
        )
        self.assertContains(
            self.client.get(reverse("admin_portal:map-data")), "Map and geographic data"
        )
