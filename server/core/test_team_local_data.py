import copy
import json
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from evacuation.local_preview import eligible_local_center_candidates
from evacuation.models import EvacuationCenter
from evacuation.services import eligible_center_candidates, ready_reference_barangays
from geography.constants import BACOOR_CITY_CODE
from geography.models import AreaFact, GeographicArea
from provenance.models import DataSource, PublicationStatus

from core.management.commands.import_team_local_data import PACKAGE_PATH, Command


@override_settings(DEBUG=True, ENABLE_LOCAL_TESTING=True)
class TeamLocalDataTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            email="team-import-test@example.test",
            password="test-only-password",
        )

    def run_import(self, *, apply=True, actor=None):
        output = StringIO()
        call_command(
            "import_team_local_data", actor=actor or self.actor.email, apply=apply, stdout=output
        )
        return output.getvalue()

    def package(self):
        return json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))

    def test_fresh_setup_copies_only_selected_normal_table_rows(self):
        output = self.run_import()
        self.assertIn("created=48", output)
        self.assertEqual(DataSource.objects.count(), 2)
        self.assertEqual(GeographicArea.objects.count(), 48)
        self.assertEqual(EvacuationCenter.objects.count(), 2)
        self.assertEqual(AreaFact.objects.count(), 0)
        self.assertEqual(get_user_model().objects.count(), 1)
        city = GeographicArea.objects.get(code=BACOOR_CITY_CODE)
        self.assertEqual(city.source.status, PublicationStatus.APPROVED)
        self.assertIsNone(city.source.reviewed_by_id)
        self.assertTrue(city.source.is_publicly_releasable)
        self.assertEqual(
            set(GeographicArea.objects.values_list("status", flat=True)),
            {PublicationStatus.PENDING_VALIDATION},
        )
        self.assertEqual(len(ready_reference_barangays()), 47)
        for center in EvacuationCenter.objects.select_related("source"):
            self.assertTrue(center.is_temporary)
            self.assertTrue(center.source.test_approved)
            self.assertEqual(center.source.reviewed_by_id, self.actor.pk)
            self.assertEqual(center.verification_status, "VERIFIED")
            self.assertIsNone(center.verified_on)
            self.assertIsNone(center.capacity)
            self.assertEqual(center.contact_information, "")
            self.assertFalse(center.source.is_publicly_releasable)
        self.assertGreater(LogEntry.objects.count(), 0)
        self.assertEqual(set(LogEntry.objects.values_list("user_id", flat=True)), {self.actor.pk})

    def test_preview_rolls_back_all_rows_and_audit_entries(self):
        self.assertIn("PREVIEW ONLY", self.run_import(apply=False))
        self.assertEqual(DataSource.objects.count(), 0)
        self.assertEqual(GeographicArea.objects.count(), 0)
        self.assertEqual(EvacuationCenter.objects.count(), 0)
        self.assertEqual(LogEntry.objects.count(), 0)

    def test_idempotent_preserves_ids_dates_and_audit_count(self):
        self.run_import()
        ids = list(EvacuationCenter.objects.values_list("pk", "public_id", "updated_at"))
        sources = list(
            DataSource.objects.values_list("pk", "reviewed_by_id", "reviewed_on", "updated_at")
        )
        audits = LogEntry.objects.count()
        self.assertIn("centers: created=0, changed=0, unchanged=2", self.run_import())
        self.assertEqual(
            ids, list(EvacuationCenter.objects.values_list("pk", "public_id", "updated_at"))
        )
        self.assertEqual(
            sources,
            list(
                DataSource.objects.values_list("pk", "reviewed_by_id", "reviewed_on", "updated_at")
            ),
        )
        self.assertEqual(LogEntry.objects.count(), audits)

    def test_reuses_fresh_imported_boundary_rows_without_duplicate_source(self):
        call_command("import_bacoor_boundaries", stdout=StringIO())
        ids = list(GeographicArea.objects.values_list("pk", "code"))
        source_id = GeographicArea.objects.get(code=BACOOR_CITY_CODE).source_id
        self.run_import()
        self.assertEqual(GeographicArea.objects.get(code=BACOOR_CITY_CODE).source_id, source_id)
        self.assertEqual(list(GeographicArea.objects.values_list("pk", "code")), ids)
        self.assertEqual(DataSource.objects.count(), 2)

    def test_different_local_primary_keys_are_not_shared(self):
        unrelated = DataSource.objects.create(name="Unrelated local source", source_type="OTHER")
        self.run_import()
        self.assertTrue(DataSource.objects.filter(pk=unrelated.pk).exists())
        self.assertNotEqual(
            GeographicArea.objects.get(code=BACOOR_CITY_CODE).source_id, unrelated.pk
        )
        self.assertEqual(
            {str(c.public_id) for c in EvacuationCenter.objects.all()},
            {c["public_id"] for c in self.package()["temporary_centers"]},
        )

    def test_existing_contacts_are_preserved_but_not_in_package(self):
        self.run_import()
        center = EvacuationCenter.objects.first()
        center.contact_information = "LOCAL ONLY - do not export"
        center.save()
        self.run_import()
        center.refresh_from_db()
        self.assertEqual(center.contact_information, "LOCAL ONLY - do not export")
        self.assertNotIn("contact_information", PACKAGE_PATH.read_text(encoding="utf-8"))

    def test_source_edits_are_not_overwritten(self):
        self.run_import()
        source = GeographicArea.objects.get(code=BACOOR_CITY_CODE).source
        source.notes = "Teammate's reviewed edits"
        source.save()
        with self.assertRaisesMessage(CommandError, "Source conflicts"):
            self.run_import()
        source.refresh_from_db()
        self.assertEqual(source.notes, "Teammate's reviewed edits")

    def test_area_approval_or_disabled_state_is_not_downgraded(self):
        for update in ({"status": PublicationStatus.APPROVED}, {"is_enabled": False}):
            with self.subTest(update=update):
                self.run_import()
                area = GeographicArea.objects.filter(area_type="BARANGAY").first()
                GeographicArea.objects.filter(pk=area.pk).update(**update)
                with self.assertRaisesMessage(CommandError, "conflicts with local edits"):
                    self.run_import()
                GeographicArea.objects.filter(pk=area.pk).update(
                    status=PublicationStatus.PENDING_VALIDATION,
                    is_enabled=True,
                )

    def test_geometry_or_source_ownership_conflicts_are_atomic(self):
        self.run_import()
        other = DataSource.objects.create(name="Another source", source_type="OTHER")
        area = GeographicArea.objects.filter(area_type="BARANGAY").first()
        GeographicArea.objects.filter(pk=area.pk).update(source=other)
        audits = LogEntry.objects.count()
        with self.assertRaisesMessage(CommandError, "conflicts with local edits"):
            self.run_import()
        self.assertEqual(LogEntry.objects.count(), audits)

    def test_late_center_conflict_rolls_back_earlier_source_updates(self):
        call_command("import_bacoor_boundaries", stdout=StringIO())
        city = GeographicArea.objects.get(code=BACOOR_CITY_CODE)
        row = self.package()["temporary_centers"][0]
        EvacuationCenter.objects.create(
            public_id=row["public_id"],
            name="Teammate's different center",
            address="Local only",
            source=city.source,
            geographic_area=city,
            latitude=row["latitude"],
            longitude=row["longitude"],
        )
        with self.assertRaisesMessage(CommandError, "Test center conflicts"):
            self.run_import()
        city.source.refresh_from_db()
        self.assertEqual(city.source.status, PublicationStatus.PENDING_VALIDATION)
        self.assertEqual(DataSource.objects.count(), 1)
        self.assertEqual(EvacuationCenter.objects.count(), 1)
        self.assertEqual(LogEntry.objects.count(), 0)

    def test_same_name_with_different_uuid_refuses_duplicate(self):
        self.run_import()
        center = EvacuationCenter.objects.first()
        from uuid import uuid4

        center.public_id = uuid4()
        center.save()
        with self.assertRaisesMessage(CommandError, "refusing a duplicate"):
            self.run_import()
        self.assertEqual(EvacuationCenter.objects.count(), 2)

    def test_revoked_test_approval_is_not_automatically_restored(self):
        self.run_import()
        source = EvacuationCenter.objects.first().source
        source.reviewed_by = None
        source.reviewed_on = None
        source.save()
        with self.assertRaisesMessage(CommandError, "unapproved"):
            self.run_import()
        source.refresh_from_db()
        self.assertFalse(source.test_approved)

    def test_inactive_center_is_not_reactivated(self):
        self.run_import()
        center = EvacuationCenter.objects.first()
        center.verification_status = "INACTIVE"
        center.save()
        with self.assertRaisesMessage(CommandError, "Test center conflicts"):
            self.run_import()
        center.refresh_from_db()
        self.assertEqual(center.verification_status, "INACTIVE")

    def test_test_centers_cannot_enter_ordinary_facility_candidates(self):
        self.run_import()
        identities = ready_reference_barangays()
        self.assertEqual(eligible_center_candidates(identities).count(), 0)
        self.assertEqual(
            eligible_local_center_candidates(identities, approved_testing=True).count(), 2
        )
        with override_settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, "Requires DEBUG"):
                self.run_import()

    def test_requires_existing_active_superuser(self):
        get_user_model().objects.create_user(email="resident@example.test", password="test-only")
        for email in ("missing@example.test", "resident@example.test"):
            with self.subTest(email=email), self.assertRaisesMessage(CommandError, "superuser"):
                self.run_import(actor=email)
        self.assertEqual(DataSource.objects.count(), 0)

    def test_opt_in_and_local_database_guards(self):
        with override_settings(ENABLE_LOCAL_TESTING=False):
            with self.assertRaisesMessage(CommandError, "Requires DEBUG"):
                self.run_import()
        with patch.dict(settings.DATABASES["default"], {"HOST": "shared.example.test"}):
            with self.assertRaisesMessage(CommandError, "loopback PostGIS"):
                self.run_import()
        self.assertEqual(DataSource.objects.count(), 0)

    def test_rejects_unknown_fields_and_missing_or_duplicate_identities(self):
        original = self.package()
        variants = []
        payload = copy.deepcopy(original)
        payload["temporary_source"]["reviewed_by"] = 1
        variants.append(payload)
        payload = copy.deepcopy(original)
        payload["temporary_centers"][0]["contact_information"] = "private"
        variants.append(payload)
        payload = copy.deepcopy(original)
        payload["areas"].pop()
        variants.append(payload)
        payload = copy.deepcopy(original)
        payload["temporary_centers"][1]["public_id"] = payload["temporary_centers"][0]["public_id"]
        variants.append(payload)
        for payload in variants:
            with (
                self.subTest(payload=payload.keys()),
                patch.object(Command, "_read_package", return_value=payload),
            ):
                with self.assertRaises(CommandError):
                    self.run_import()
        self.assertEqual(DataSource.objects.count(), 0)

    def test_rejects_changed_checksums_public_tests_and_outside_coordinates(self):
        original = self.package()
        variants = []
        payload = copy.deepcopy(original)
        payload["boundary_files"]["bacoor_city_boundary.geojson"] = "0" * 64
        variants.append(payload)
        payload = copy.deepcopy(original)
        payload["temporary_source"]["is_publicly_releasable"] = True
        variants.append(payload)
        payload = copy.deepcopy(original)
        payload["temporary_centers"][0]["latitude"] = "0"
        variants.append(payload)
        for payload in variants:
            with (
                self.subTest(payload=payload.keys()),
                patch.object(Command, "_read_package", return_value=payload),
            ):
                with self.assertRaises(CommandError):
                    self.run_import()
        self.assertEqual(DataSource.objects.count(), 0)
