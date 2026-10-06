"""Dashboard integration checks using isolated, neutral test records."""

from html.parser import HTMLParser

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape
from dss.models import GuidanceItem
from evacuation.models import EvacuationCenter
from expert.models import ExpertRule, ExpertRuleCondition, ScenarioOption, SusceptibilityLevel
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus

from .views import dashboard


class DashboardHTML(HTMLParser):
    """Collect semantic elements without tying tests to presentation classes."""

    void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}

    def __init__(self, response):
        super().__init__()
        self.elements = []
        self.stack = []
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        element = {"tag": tag, "attrs": dict(attrs), "text": [], "ancestors": self.stack[:]}
        self.elements.append(element)
        if tag not in self.void_tags:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for element in self.stack:
            element["text"].append(data)

    @staticmethod
    def text(element):
        return " ".join("".join(element["text"]).split())

    def select(self, tag=None, **attrs):
        return [
            element
            for element in self.elements
            if (tag is None or element["tag"] == tag)
            and all(element["attrs"].get(key) == value for key, value in attrs.items())
        ]


class OperationalDashboardTests(TestCase):
    approved_empty_messages = (
        "No geographic records are currently approved.",
        "No approved public data sources are available.",
        "No approved preparedness guidance is available.",
        "No approved scenario options are available.",
        "No evacuation-center records are currently verified.",
    )
    activity_limitation = (
        "This is a limited view of recorded Django maintenance actions, "
        "not the complete FloodSense audit history."
    )

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            email="dashboard-maintainer@example.com",
            display_name="Dashboard Maintainer",
            is_staff=True,
        )

    def setUp(self):
        self.url = reverse("admin_portal:dashboard")
        self.client.force_login(self.staff)

    def create_records(self, status=PublicationStatus.DEMONSTRATION):
        source = DataSource.objects.create(
            name="Synthetic dashboard fixture source",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=status,
            is_publicly_releasable=True,
            notes="private-note-sentinel",
            permitted_use="private-permitted-use-sentinel",
        )
        area = GeographicArea.objects.create(
            code="dashboard-fixture-area",
            name="Synthetic dashboard fixture area",
            area_type=GeographicArea.AreaType.DEMO_ZONE,
            geometry=MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326),
            source=source,
            status=status,
            is_enabled=True,
        )
        level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.LOW,
            label="Synthetic test vocabulary",
            display_order=1,
            map_color="#112233",
            definition="Isolated fixture, not a geographic classification.",
            source=source,
            is_enabled=True,
        )
        guidance = GuidanceItem.objects.create(
            title="Synthetic dashboard fixture content",
            instruction="private-guidance-body-sentinel",
            category=GuidanceItem.Category.PREPARE,
            susceptibility_level=level,
            source=source,
            status=status,
            workflow_status=GuidanceItem.WorkflowStatus.PUBLISHED,
            is_enabled=True,
        )
        option = ScenarioOption.objects.create(
            code="dashboard-fixture-option",
            label="Synthetic dashboard fixture option",
            category=ScenarioOption.Category.INTENSITY,
            derived_value="91731.0000",
            source=source,
            status=status,
            is_enabled=True,
        )
        EvacuationCenter.objects.create(
            name="Synthetic dashboard fixture center",
            address="Synthetic test address",
            geographic_area=area,
            latitude=0,
            longitude=0,
            source=source,
            publication_status=status,
            verification_status=(
                EvacuationCenter.VerificationStatus.IN_REVIEW
                if status == PublicationStatus.PENDING_VALIDATION
                else EvacuationCenter.VerificationStatus.DRAFT
            ),
        )
        return source, area, guidance, option

    def create_log(self, model, *, action=CHANGE, user=None):
        return LogEntry.objects.create(
            user=user or self.staff,
            content_type=ContentType.objects.get_for_model(model),
            object_id="123456",
            object_repr="private-object-repr-sentinel",
            action_flag=action,
            change_message='[{"changed":{"fields":["private-change-message-sentinel"]}}]',
        )

    def test_anonymous_and_nonstaff_cannot_read_summaries(self):
        anonymous = Client()
        self.assertRedirects(
            anonymous.get(self.url),
            f"{reverse('admin_portal:login')}?next={self.url}",
            fetch_redirect_response=False,
        )
        resident = get_user_model().objects.create_user(email="dashboard-resident@example.com")
        anonymous.force_login(resident)
        response = anonymous.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "No approved scenario options", status_code=403)

    def test_inactive_staff_is_rejected_before_dashboard_queries(self):
        inactive = get_user_model().objects.create_user(
            email="dashboard-inactive@example.com", is_staff=True, is_active=False
        )
        request = RequestFactory().get(self.url)
        request.user = inactive
        with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            dashboard(request)

    def grant(self, *, activity=False, create=False):
        permissions = [
            "view_datasource",
            "view_guidanceitem",
            "view_dssflowversion",
            "view_scenariooption",
            "view_ruleset",
            "view_evacuationcenter",
        ]
        if activity:
            permissions.append("view_logentry")
        if create:
            permissions += ["add_guidanceitem", "add_evacuationcenter"]
        self.staff.user_permissions.set(Permission.objects.filter(codename__in=permissions))

    def cards(self, response):
        return {card["key"]: card for card in response.context["dashboard"]["cards"]}

    def test_inaccessible_module_information_is_restricted_not_zero(self):
        self.create_records()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)
        cards = self.cards(response)
        self.assertEqual(len(cards), 5)
        self.assertTrue(cards["map-data"]["allowed"])
        for key in ("sources-content", "dss-content", "rainfall-references", "evacuation-centers"):
            self.assertFalse(cards[key]["allowed"])
            self.assertNotIn("metric", cards[key])
        self.assertContains(response, "Access restricted", count=4)
        self.assertEqual(response.context["dashboard"]["attention"], [])
        self.assertIsNone(response.context["dashboard"]["recent_activity"])
        for query in queries:
            for table in (
                "dss_guidanceitem",
                "dss_dssflowversion",
                "expert_scenariooption",
                "evacuation_evacuationcenter",
                "django_admin_log",
            ):
                self.assertNotIn(table, query["sql"].lower())

    def test_permitted_empty_modules_show_measured_zero_and_unavailable_states(self):
        self.grant()
        response = self.client.get(self.url)
        cards = self.cards(response)
        self.assertEqual(cards["map-data"]["metric"], "0 / 47")
        for key in ("sources-content", "dss-content", "rainfall-references", "evacuation-centers"):
            self.assertEqual(cards[key]["metric"], 0)
        self.assertContains(response, "Prepare flow unavailable")
        self.assertContains(response, "Reference layer unavailable")
        self.assertContains(response, "Resident setup content incomplete")
        self.assertContains(response, "Assessment configuration incomplete")
        self.assertNotContains(response, "System healthy")
        self.assertContains(response, "current local database")

    def test_demonstration_is_an_explicit_mode_and_never_normal_public_availability(self):
        self.grant()
        self.create_records()
        official = self.cards(self.client.get(self.url))
        demo_response = self.client.get(self.url, {"mode": "DEMONSTRATION"})
        demo = self.cards(demo_response)
        self.assertEqual(official["rainfall-references"]["metric"], 0)
        self.assertEqual(official["dss-content"]["metric"], 0)
        self.assertEqual(demo["rainfall-references"]["metric"], 1)
        self.assertEqual(demo["dss-content"]["metric"], 1)
        self.assertEqual(demo["sources-content"]["metric"], 0)
        self.assertEqual(demo["evacuation-centers"]["metric"], 0)
        self.assertContains(demo_response, "Demonstration data—not official")

    def test_approved_sources_require_public_permission_and_non_demo_provenance(self):
        self.grant()
        source, _, _, _ = self.create_records(status=PublicationStatus.APPROVED)
        self.assertEqual(self.cards(self.client.get(self.url))["sources-content"]["metric"], 0)
        source.source_type = DataSource.SourceType.AGENCY_DATASET
        source.is_publicly_releasable = False
        source.save(update_fields=["source_type", "is_publicly_releasable"])
        self.assertEqual(self.cards(self.client.get(self.url))["sources-content"]["metric"], 0)
        source.is_publicly_releasable = True
        source.save(update_fields=["is_publicly_releasable"])
        self.assertEqual(self.cards(self.client.get(self.url))["sources-content"]["metric"], 1)

    def test_attention_counts_explicit_review_states_and_excludes_restrictions(self):
        self.grant()
        _, _, guidance, _ = self.create_records(status=PublicationStatus.PENDING_VALIDATION)
        guidance.workflow_status = GuidanceItem.WorkflowStatus.IN_REVIEW
        guidance.is_enabled = False
        guidance.save(update_fields=["workflow_status", "is_enabled"])
        DataSource.objects.create(
            name="Synthetic restricted source", source_type="OTHER", status="RESTRICTED"
        )
        response = self.client.get(self.url)
        items = response.context["dashboard"]["attention"]
        self.assertEqual(
            {row["label"]: row["count"] for row in items},
            {
                "Centers awaiting verification review": 1,
                "Assessment guidance awaiting review": 1,
                "Source metadata awaiting review": 1,
            },
        )
        self.assertTrue(all(row["kind"] == "Workflow queue" for row in items))
        self.assertTrue(all("?state=" in row["url"] for row in items))
        self.assertNotContains(response, "Synthetic restricted source")

    def test_pending_guidance_draft_is_not_an_error_or_review_queue(self):
        self.grant()
        _, _, guidance, _ = self.create_records(status=PublicationStatus.PENDING_VALIDATION)
        guidance.workflow_status = "DRAFT"
        guidance.is_enabled = False
        guidance.save(update_fields=["workflow_status", "is_enabled"])
        items = self.client.get(self.url).context["dashboard"]["attention"]
        self.assertFalse(any("Assessment guidance" in row["label"] for row in items))

    def test_dashboard_get_is_read_only_and_does_not_query_raw_rule_tables(self):
        self.grant(activity=True)
        self.create_records()
        self.create_log(DataSource)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for query in queries:
            sql = query["sql"].strip().upper()
            self.assertTrue(sql.startswith("SELECT"), msg=sql)
            self.assertNotIn('"EXPERT_EXPERTRULE"', sql)
            self.assertNotIn('"EXPERT_EXPERTRULECONDITION"', sql)

    def test_every_non_get_method_is_rejected_without_writes(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"):
            with self.subTest(method=method), CaptureQueriesContext(connection) as queries:
                response = self.client.generic(method, self.url)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "GET")
            for query in queries:
                self.assertTrue(query["sql"].strip().upper().startswith("SELECT"))

    def test_source_details_guidance_body_and_derived_values_are_not_exposed(self):
        self.grant(activity=True)
        self.create_records(status=PublicationStatus.RESTRICTED)
        self.create_log(DataSource)
        response = self.client.get(self.url)
        for value in (
            "private-note-sentinel",
            "private-permitted-use-sentinel",
            "private-guidance-body-sentinel",
            "91731",
            "private-object-repr-sentinel",
            "private-change-message-sentinel",
        ):
            self.assertNotContains(response, value)

    def test_activity_requires_audit_and_individual_module_view_permission(self):
        self.create_log(DataSource)
        self.create_log(GuidanceItem)
        self.staff.user_permissions.set(Permission.objects.filter(codename="view_logentry"))
        response = self.client.get(self.url)
        self.assertEqual(response.context["dashboard"]["recent_activity"], [])
        self.assertContains(response, "No recorded changes are available")
        self.staff.user_permissions.clear()
        response = self.client.get(self.url)
        self.assertNotContains(response, "Recent administrative changes")

    def test_recent_changes_are_three_real_events_and_include_prepare_versions(self):
        from dss.models import DSSFlowVersion

        self.grant(activity=True)
        for model in (DataSource, GeographicArea, GuidanceItem, DSSFlowVersion):
            self.create_log(model)
        response = self.client.get(self.url)
        events = response.context["dashboard"]["recent_activity"]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["module"], "Prepare flows")
        self.assertContains(response, "View audit history")
        for model in (ExpertRule, ExpertRuleCondition):
            self.create_log(model)
        self.assertEqual(self.client.get(self.url).context["dashboard"]["recent_activity"], events)

    def test_database_display_names_are_escaped_in_greeting_and_activity(self):
        self.grant(activity=True)
        self.staff.display_name = '<img src=x onerror="alert(1)">'
        self.staff.save(update_fields=["display_name"])
        self.create_log(GeographicArea)
        response = self.client.get(self.url)
        self.assertContains(response, escape(self.staff.display_name))
        self.assertNotContains(response, self.staff.display_name)
        self.assertFalse(DashboardHTML(response).select("img", onerror="alert(1)"))

    def test_compact_snapshot_has_no_status_breakdown_or_rule_controls(self):
        self.grant(create=True)
        response = self.client.get(self.url)
        html = DashboardHTML(response)
        self.assertEqual(len(html.select("h1")), 1)
        self.assertTrue(html.select(**{"aria-label": "Data safety notice"}))
        self.assertTrue(html.select("label", **{"for": "snapshot-mode"}))
        self.assertTrue(html.select("time"))
        self.assertContains(response, "Needs attention")
        self.assertContains(response, "Create center draft")
        self.assertContains(response, "Create guidance draft")
        self.assertNotContains(response, "Verification states")
        self.assertNotContains(response, "Area types")
        self.assertNotContains(response, "dashboard-statuses")
        for forbidden in (
            "API healthy",
            "System healthy",
            "Create rule draft",
            "Publish rule set",
            "Approve all",
            "Bulk activate",
        ):
            self.assertNotContains(response, forbidden)
        for link in html.select("a"):
            self.assertFalse(link["attrs"].get("href", "").startswith("/admin/"))

    def test_invalid_mode_falls_back_to_approved_source_snapshot(self):
        response = self.client.get(self.url, {"mode": "invented"})
        self.assertEqual(response.context["dashboard"]["mode"], "OFFICIAL")
