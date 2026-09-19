from datetime import date

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from evacuation.models import EvacuationCenter
from expert.models import ScenarioOption
from provenance.models import DataSource, PublicationStatus


class DaysSixAndSevenPortalTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.manager = user_model.objects.create_user(
            email="operations-manager@example.com",
            display_name="Operations Manager",
            password="Strong-test-password-123",
            is_staff=True,
        )
        self.manager.user_permissions.set(
            Permission.objects.filter(
                codename__in=(
                    "view_scenariooption",
                    "view_evacuationcenter",
                    "add_evacuationcenter",
                    "change_evacuationcenter",
                    "verify_evacuationcenter",
                    "deactivate_evacuationcenter",
                    "view_datasource",
                    "add_datasource",
                    "change_datasource",
                    "approve_datasource",
                    "publish_datasource",
                    "restrict_datasource",
                    "view_logentry",
                )
            )
        )
        self.viewer = user_model.objects.create_user(
            email="operations-viewer@example.com",
            display_name="Operations Viewer",
            password="Strong-test-password-123",
            is_staff=True,
        )
        self.approved_source = DataSource.objects.create(
            name="Approved test fixture source",
            organization="Test Office",
            custodian="Test Data Custodian",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            coverage_description="Automated tests only.",
            permitted_use="Testing permitted.",
            limitations="Not real operational data.",
            status=PublicationStatus.APPROVED,
        )
        self.option = ScenarioOption.objects.create(
            category=ScenarioOption.Category.INTENSITY,
            code="test-intensity",
            label="Test intensity",
            minimum_value=1,
            maximum_value=2,
            derived_value=1,
            unit="test units",
            source=self.approved_source,
            status=PublicationStatus.APPROVED,
        )

    def _source_form_data(self, **overrides):
        data = {
            "name": "Candidate agency source",
            "organization": "Agency Test Office",
            "custodian": "Records Unit",
            "source_type": DataSource.SourceType.AGENCY_DATASET,
            "coverage_description": "Test coverage and time resolution.",
            "record_period_start": "2026-01-01",
            "record_period_end": "2026-06-30",
            "received_or_created_on": "2026-07-01",
            "version": "test-v1",
            "permitted_use": "Automated testing only.",
            "processing_notes": "Fixture validation.",
            "limitations": "Not operational data.",
            "citation_url": "https://example.com/source",
            "notes": "Test fixture.",
        }
        data.update(overrides)
        return data

    def _center_form_data(self, **overrides):
        data = {
            "name": "TEST CENTER - NOT OPERATIONAL",
            "address": "Automated test address",
            "geographic_area": "",
            "latitude": "14.462900",
            "longitude": "120.964700",
            "contact_information": "",
            "source": self.approved_source.pk,
            "publication_status": PublicationStatus.PENDING_VALIDATION,
            "notes": "Test fixture only.",
            "limitations": "Not a real evacuation center.",
        }
        data.update(overrides)
        return data

    def test_rainfall_references_are_permission_checked_and_read_only(self):
        url = reverse("admin_portal:rainfall-references")
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.manager.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="expert", codename="view_scenariooption"
            )
        )
        self.client.force_login(self.manager)
        response = self.client.get(url)
        self.assertContains(response, self.option.label)
        self.assertContains(response, "Scenario inputs—not live rainfall")
        self.assertNotContains(response, "Create rainfall")
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_source_create_approve_and_publish_are_separate_and_logged(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("admin_portal:data-source-create"), self._source_form_data()
        )
        source = DataSource.objects.get(name="Candidate agency source")
        self.assertRedirects(
            response,
            reverse("admin_portal:data-source-detail", args=(source.pk,)),
        )
        self.assertEqual(source.status, PublicationStatus.PENDING_VALIDATION)
        self.assertFalse(source.is_publicly_releasable)

        approve_url = reverse(
            "admin_portal:data-source-transition", args=(source.pk, "approve")
        )
        self.client.post(
            approve_url,
            {
                "expected_status": PublicationStatus.PENDING_VALIDATION,
                "confirm": "on",
            },
        )
        source.refresh_from_db()
        self.assertEqual(source.status, PublicationStatus.APPROVED)
        self.assertFalse(source.is_publicly_releasable)
        self.assertEqual(source.reviewed_by, self.manager)

        self.client.post(
            reverse(
                "admin_portal:data-source-transition", args=(source.pk, "publish")
            ),
            {
                "expected_status": PublicationStatus.APPROVED,
                "expected_public": "",
                "confirm": "on",
            },
        )
        source.refresh_from_db()
        self.assertTrue(source.is_publicly_releasable)
        self.assertGreaterEqual(LogEntry.objects.filter(object_id=str(source.pk)).count(), 3)

    def test_source_approval_rejects_incomplete_metadata(self):
        source = DataSource.objects.create(
            name="Incomplete source",
            source_type=DataSource.SourceType.OTHER,
            status=PublicationStatus.PENDING_VALIDATION,
        )
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse(
                "admin_portal:data-source-transition", args=(source.pk, "approve")
            ),
            {
                "expected_status": PublicationStatus.PENDING_VALIDATION,
                "confirm": "on",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "complete metadata", status_code=409)

    def test_center_draft_requires_review_before_verified_capacity(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("admin_portal:evacuation-center-create"), self._center_form_data()
        )
        center = EvacuationCenter.objects.get(name="TEST CENTER - NOT OPERATIONAL")
        self.assertRedirects(
            response,
            reverse("admin_portal:evacuation-center-detail", args=(center.pk,)),
        )
        self.assertEqual(center.verification_status, EvacuationCenter.VerificationStatus.DRAFT)
        self.assertIsNone(center.capacity)

        self.client.post(
            reverse(
                "admin_portal:evacuation-center-transition", args=(center.pk, "submit")
            ),
            {"expected_status": "DRAFT", "confirm": "on"},
        )
        self.client.post(
            reverse(
                "admin_portal:evacuation-center-transition", args=(center.pk, "verify")
            ),
            {
                "expected_status": "IN_REVIEW",
                "verified_on": "2026-09-19",
                "capacity": "125",
                "confirm": "on",
            },
        )
        center.refresh_from_db()
        self.assertEqual(
            center.verification_status, EvacuationCenter.VerificationStatus.VERIFIED
        )
        self.assertEqual(center.verified_on, date(2026, 9, 19))
        self.assertEqual(center.capacity, 125)
        self.assertEqual(center.publication_status, PublicationStatus.APPROVED)

    def test_center_form_rejects_out_of_range_coordinates(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("admin_portal:evacuation-center-create"),
            self._center_form_data(latitude="91.000000"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "less than or equal to 90")
        self.assertFalse(EvacuationCenter.objects.exists())

    def test_center_and_source_modules_deny_staff_without_view_permissions(self):
        self.client.force_login(self.viewer)

        for url_name in ("evacuation-centers", "sources-content"):
            with self.subTest(url_name=url_name):
                self.assertEqual(
                    self.client.get(reverse(f"admin_portal:{url_name}")).status_code,
                    403,
                )

    def test_audit_history_is_read_only_filtered_and_permission_checked(self):
        LogEntry.objects.log_actions(
            user_id=self.manager.pk,
            queryset=[self.option],
            action_flag=2,
            change_message="Safe test event.",
            single_object=True,
        )
        url = reverse("admin_portal:audit-history")
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.manager)
        response = self.client.get(
            url,
            {"actor": self.manager.pk, "module": "expert.scenariooption", "action": "2"},
        )
        self.assertContains(response, self.option.label)
        self.assertContains(response, "Rainfall references")
        self.assertEqual(self.client.post(url).status_code, 405)

        response = self.client.get(
            url, {"date_from": "2026-09-20", "date_to": "2026-09-19"}
        )
        self.assertContains(response, "end date cannot precede the start date")
