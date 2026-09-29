"""Reports use controlled records and the existing module permission boundaries."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from dss.models import GuidanceItem
from evacuation.models import EvacuationCenter
from expert.models import ScenarioOption, SusceptibilityLevel
from geography.constants import BACOOR_REFERENCE_SOURCE_NAME
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus

from .services.reports import get_report_summary
from .test_dashboard import DashboardHTML


class ReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(email="report@example.com", is_staff=True)
        cls.admin = get_user_model().objects.create_user(
            email="report-admin@example.com", is_staff=True, is_superuser=True
        )

    def setUp(self):
        self.url = reverse("admin_portal:reports")
        self.client.force_login(self.admin)

    def create_records(self, statuses):
        for status in statuses:
            source = DataSource.objects.create(
                name=f"Synthetic report {status}",
                source_type=DataSource.SourceType.OTHER,
                status=status,
                is_publicly_releasable=status == PublicationStatus.APPROVED,
                notes="PRIVATE_REPORT_SOURCE",
            )
            level, _ = SusceptibilityLevel.objects.get_or_create(
                code="LOW", defaults={"label": "Fixture", "source": source, "display_order": 1}
            )
            area = GeographicArea.objects.create(
                code=f"REPORT-{status}",
                name="Synthetic report area",
                source=source,
                area_type="DEMO_ZONE",
                geometry=MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326),
                status=status,
                is_enabled=True,
            )
            GuidanceItem.objects.create(
                title="Synthetic report guidance",
                instruction="PRIVATE_REPORT_GUIDANCE",
                category="PREPARE",
                susceptibility_level=level,
                source=source,
                status=status,
                workflow_status=(
                    "IN_REVIEW" if status == PublicationStatus.PENDING_VALIDATION else "PUBLISHED"
                ),
                is_enabled=status == PublicationStatus.APPROVED,
            )
            ScenarioOption.objects.create(
                code=f"REPORT-{status}",
                label="Synthetic report scenario",
                category="INTENSITY",
                source=source,
                status=status,
                is_enabled=False,
            )
            EvacuationCenter.objects.create(
                name="Synthetic report center",
                source=source,
                geographic_area=area,
                publication_status=status,
                verification_status="IN_REVIEW",
                latitude=0,
                longitude=0,
            )

    def test_staff_boundary_and_get_only(self):
        self.assertRedirects(
            Client().get(self.url),
            f"{reverse('admin_portal:login')}?next={self.url}",
            fetch_redirect_response=False,
        )
        resident = get_user_model().objects.create_user(email="report-resident@example.com")
        self.client.force_login(resident)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for method in ("post", "put", "patch", "delete", "head"):
            self.assertEqual(getattr(self.client, method)(self.url).status_code, 405)

    def test_empty_counts_unavailable_and_navigation(self):
        response = self.client.get(self.url)
        report = response.context["report"]
        self.assertEqual((report["total"], report["review_total"]), (0, 0))
        self.assertContains(response, "No records in this module.", count=5)
        self.assertContains(
            response, "Historical trends and time-to-review measures are unavailable"
        )
        self.assertContains(response, "not current flood conditions")
        html = DashboardHTML(response)
        self.assertTrue(html.select("a", href=self.url, **{"aria-current": "page"}))
        self.assertEqual(
            [row[0] for row in response.context["navigation"]][:2], ["dashboard", "reports"]
        )
        self.assertEqual(len(html.select("a", href=reverse("admin_portal:settings"))), 1)
        self.assertNotContains(response, "/management/settings/#parameters")
        self.assertEqual(reverse("admin_portal:dashboard"), "/management/")

    def test_demonstration_only_does_not_count_as_approved(self):
        self.create_records([PublicationStatus.DEMONSTRATION])
        response = self.client.get(self.url)
        report = response.context["report"]
        self.assertEqual(report["total"], 5)
        for module in report["modules"]:
            self.assertEqual(module["summary"]["status_counts"]["DEMONSTRATION"], 1)
            self.assertEqual(module["summary"]["status_counts"]["APPROVED"], 0)
        self.assertContains(response, "including demonstration")
        self.assertNotContains(response, "PRIVATE_REPORT_")

    def test_mixed_status_counts_and_independent_workflows(self):
        self.create_records(PublicationStatus.values)
        report = get_report_summary(user=self.admin)
        self.assertEqual(report["total"], 25)
        self.assertEqual(report["review_total"], 8)
        modules = {module["key"]: module for module in report["modules"]}
        for module in report["modules"]:
            self.assertEqual(
                module["summary"]["status_counts"], dict.fromkeys(PublicationStatus.values, 1)
            )
        self.assertEqual(modules["guidance_items"]["review"]["count"], 1)
        self.assertEqual(modules["guidance_items"]["summary"]["enabled"], 1)
        self.assertEqual(modules["guidance_items"]["summary"]["workflow_PUBLISHED"], 4)
        self.assertEqual(modules["scenario_options"]["summary"]["enabled"], 0)
        self.assertEqual(modules["data_sources"]["summary"]["approved_public"], 1)
        self.assertEqual(modules["evacuation_centers"]["review"]["count"], 5)

    def test_geographic_workload_matches_reviewable_map_population(self):
        self.create_records([PublicationStatus.PENDING_VALIDATION])
        source = DataSource.objects.create(
            name=BACOOR_REFERENCE_SOURCE_NAME,
            source_type="AGENCY_DATASET",
            status="PENDING_VALIDATION",
            is_publicly_releasable=True,
        )
        GeographicArea.objects.create(
            code="REPORT-ADMIN",
            name="Synthetic boundary",
            area_type="BARANGAY",
            geometry=MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)), srid=4326),
            source=source,
            status="PENDING_VALIDATION",
            is_enabled=False,
        )
        module = get_report_summary(user=self.admin)["modules"][0]
        self.assertEqual(module["summary"]["total"], 2)
        self.assertEqual(module["review"]["count"], 1)
        self.assertEqual(module["review"]["filter_query"], "status=PENDING_VALIDATION")

    def test_restricted_modules_are_withheld_including_totals_and_links(self):
        self.create_records([PublicationStatus.PENDING_VALIDATION])
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        report = response.context["report"]
        self.assertEqual(
            (report["total"], report["review_total"], report["restricted_modules"]), (1, 0, 4)
        )
        for module in report["modules"][1:]:
            self.assertNotIn("summary", module)
            self.assertNotIn("review", module)
            self.assertNotContains(response, f'href="/management/{module["slug"]}/')
        self.assertContains(response, "Access restricted — counts withheld", count=4)
        self.staff.user_permissions.add(Permission.objects.get(codename="view_datasource"))
        response = self.client.get(self.url)
        self.assertEqual(response.context["report"]["total"], 2)
        self.assertEqual(response.context["report"]["review_total"], 1)
        self.assertContains(response, 'href="/management/sources-content/')

    def test_read_only_aggregates_do_not_query_events_or_expert_rules(self):
        self.create_records([PublicationStatus.DEMONSTRATION])
        with self.assertNumQueries(5), CaptureQueriesContext(connection) as queries:
            get_report_summary(user=self.admin)
        for query in queries:
            sql = query["sql"].lower()
            self.assertTrue(sql.startswith("select"))
            for forbidden in ("django_admin_log", "expert_expertrule", '"instruction"', '"notes"'):
                self.assertNotIn(forbidden, sql)
