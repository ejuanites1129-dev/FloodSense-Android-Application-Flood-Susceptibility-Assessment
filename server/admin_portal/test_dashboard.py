"""Dashboard integration checks using isolated, neutral test records."""

from html.parser import HTMLParser

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import Client, RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape
from dss.models import GuidanceItem
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

    def test_active_staff_receives_zero_counts_and_meaningful_empty_states(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for name in ("geographic_areas", "data_sources", "guidance_items", "scenario_options"):
            with self.subTest(summary=name):
                self.assertEqual(response.context["dashboard"][name]["total"], 0)
        self.assertEqual(response.context["dashboard"]["review_attention"]["total"], 0)
        for message in self.approved_empty_messages:
            self.assertContains(response, message)
        self.assertContains(response, "No records currently need validation or content review.")
        self.assertContains(response, "No recorded maintenance activity is available.")
        self.assertContains(response, "current local database")
        self.assertNotContains(response, "Everything is approved")

    def test_demonstration_records_remain_unapproved_even_when_enabled(self):
        self.create_records()
        response = self.client.get(self.url)
        for name in ("geographic_areas", "data_sources", "guidance_items", "scenario_options"):
            with self.subTest(summary=name):
                summary = response.context["dashboard"][name]
                self.assertEqual(summary["total"], 1)
                self.assertEqual(summary["status_counts"][PublicationStatus.DEMONSTRATION], 1)
                self.assertEqual(summary["status_counts"][PublicationStatus.APPROVED], 0)
        for message in self.approved_empty_messages:
            self.assertContains(response, message)
        self.assertContains(response, PublicationStatus.DEMONSTRATION.label)
        self.assertContains(response, "No records currently need validation or content review.")
        self.assertContains(response, "No recorded maintenance activity is available.")
        self.assertEqual(response.context["dashboard"]["recent_activity"], [])

    def test_approved_data_removes_only_the_corresponding_empty_states(self):
        source, _, _, _ = self.create_records(status=PublicationStatus.APPROVED)
        source.is_publicly_releasable = False
        source.save(update_fields=["is_publicly_releasable"])
        response = self.client.get(self.url)
        self.assertContains(response, "No approved public data sources are available.")
        for message in self.approved_empty_messages:
            if "public data sources" not in message:
                self.assertNotContains(response, message)
        source.is_publicly_releasable = True
        source.save(update_fields=["is_publicly_releasable"])
        self.assertNotContains(
            self.client.get(self.url), "No approved public data sources are available."
        )

    def test_pending_records_populate_attention_without_counting_other_statuses(self):
        self.create_records(status=PublicationStatus.PENDING_VALIDATION)
        for status in (PublicationStatus.RESTRICTED, PublicationStatus.RETIRED):
            DataSource.objects.create(
                name=f"Synthetic {status} fixture",
                source_type=DataSource.SourceType.DEMONSTRATION,
                status=status,
            )
        response = self.client.get(self.url)
        self.assertEqual(response.context["dashboard"]["review_attention"]["total"], 4)
        self.assertNotContains(response, "No records currently need validation or content review.")
        self.assertContains(response, PublicationStatus.PENDING_VALIDATION.label)
        self.assertContains(response, PublicationStatus.RESTRICTED.label)
        self.assertContains(response, PublicationStatus.RETIRED.label)

    def test_guidance_in_review_populates_attention_without_pending_data_status(self):
        _, _, guidance, _ = self.create_records()
        guidance.workflow_status = GuidanceItem.WorkflowStatus.IN_REVIEW
        guidance.is_enabled = False
        guidance.save(update_fields=("workflow_status", "is_enabled"))

        response = self.client.get(self.url)

        self.assertEqual(response.context["dashboard"]["review_attention"]["total"], 1)
        self.assertContains(response, "Records needing review by module")

    def test_dashboard_get_is_read_only_and_does_not_query_raw_rule_tables(self):
        self.create_records()
        self.create_log(DataSource)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(queries.captured_queries)
        for query in queries.captured_queries:
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
            for query in queries.captured_queries:
                self.assertTrue(query["sql"].strip().upper().startswith("SELECT"))

    def test_source_details_guidance_body_and_derived_values_are_not_exposed(self):
        self.create_records(status=PublicationStatus.RESTRICTED)
        response = self.client.get(self.url)
        for private_value in (
            "private-note-sentinel",
            "private-permitted-use-sentinel",
            "private-guidance-body-sentinel",
            "91731",
        ):
            self.assertNotContains(response, private_value)

    def test_relevant_recorded_activity_uses_safe_labels_and_semantic_list(self):
        for model, action in (
            (DataSource, ADDITION),
            (GeographicArea, CHANGE),
            (GuidanceItem, DELETION),
            (ScenarioOption, CHANGE),
        ):
            self.create_log(model, action=action)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["dashboard"]["recent_activity"]), 4)
        self.assertContains(response, self.activity_limitation)
        self.assertContains(response, "Recent recorded maintenance activity")
        self.assertNotContains(response, "private-object-repr-sentinel")
        self.assertNotContains(response, "private-change-message-sentinel")
        self.assertNotContains(response, "No recorded maintenance activity is available.")
        for label in ("Added", "Changed", "Deleted"):
            self.assertContains(response, label)
        html = DashboardHTML(response)
        timestamps = html.select("time")
        self.assertEqual(len(timestamps), 4)
        for timestamp in timestamps:
            self.assertTrue(timestamp["attrs"].get("datetime"))
            self.assertIn("li", [ancestor["tag"] for ancestor in timestamp["ancestors"]])
            self.assertTrue(
                {"ul", "ol"}.intersection(ancestor["tag"] for ancestor in timestamp["ancestors"])
            )

    def test_raw_rule_and_condition_logs_do_not_create_dashboard_activity(self):
        for model in (ExpertRule, ExpertRuleCondition):
            self.create_log(model)
        response = self.client.get(self.url)
        self.assertEqual(response.context["dashboard"]["recent_activity"], [])
        self.assertContains(response, "No recorded maintenance activity is available.")
        self.assertContains(response, self.activity_limitation)

    def test_database_display_names_are_escaped_in_greeting_and_activity(self):
        self.staff.display_name = '<img src=x onerror="alert(1)">'
        self.staff.save(update_fields=["display_name"])
        self.create_log(DataSource)
        response = self.client.get(self.url)
        self.assertContains(response, escape(self.staff.display_name))
        self.assertNotContains(response, self.staff.display_name)
        self.assertFalse(DashboardHTML(response).select("img", onerror="alert(1)"))

    def test_quick_actions_are_descriptive_links_to_protected_modules(self):
        html = DashboardHTML(self.client.get(self.url))
        for label, slug in (
            ("Open map data", "map-data"),
            ("Review assessment parameters", "settings"),
        ):
            with self.subTest(link=label):
                url = reverse("admin_portal:section", kwargs={"section_slug": slug})
                link_url = f"{url}#parameters" if slug == "settings" else url
                self.assertTrue(
                    any(label in html.text(link) for link in html.select("a", href=link_url))
                )
                protected_response = self.client.get(url)
                self.assertContains(
                    protected_response,
                    {"map-data": "Map and geographic data", "settings": "Settings"}[slug],
                )
                self.assertRedirects(
                    Client().get(url),
                    f"{reverse('admin_portal:login')}?next={url}",
                    fetch_redirect_response=False,
                )
        self.assertFalse(
            any("Open DSS content" in html.text(link) for link in html.select("a"))
        )
        self.assertFalse(any("Manage sources" in html.text(link) for link in html.select("a")))

    def test_dashboard_retains_accessible_safety_and_removes_foundation_and_rule_controls(self):
        response = self.client.get(self.url)
        html = DashboardHTML(response)
        self.assertEqual(len(html.select("h1")), 1)
        self.assertTrue(html.select(**{"aria-label": "Data safety notice"}))
        self.assertTrue(html.select("nav", **{"aria-label": "Administration navigation"}))
        self.assertTrue(html.select("form", method="post", action=reverse("admin_portal:logout")))
        self.assertContains(response, "Development environment")
        for forbidden in (
            "Foundation · Day 1",
            "Day 1 checklist",
            "Continue the build",
            "Create rule draft",
            "Publish rule set",
            "Change inference method",
            "Publish center changes",
            "Approve all",
            "Bulk activate",
            "Expert Rule Set",
            "Published map version",
            "DSS version",
            "Verified centers",
            "API healthy",
        ):
            self.assertNotContains(response, forbidden)
        for link in html.select("a"):
            self.assertFalse(link["attrs"].get("href", "").startswith("/admin/"))
            self.assertNotIn("expert rules", html.text(link).lower())
        self.assertEqual(reverse("admin:index"), "/admin/")
        self.assertEqual(self.url, "/management/")
