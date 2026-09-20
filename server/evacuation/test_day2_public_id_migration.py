"""UUID upgrade/reversal and lifecycle evidence in the isolated test database."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from provenance.models import DataSource

from .models import EvacuationCenter
from .workflow import transition_center


class PublicIdMigrationTests(TransactionTestCase):
    old_target = [("evacuation", "0001_initial")]
    new_target = [("evacuation", "0002_evacuationcenter_public_id")]

    def setUp(self):
        super().setUp()
        self.addCleanup(self.restore_schema)
        executor = MigrationExecutor(connection)
        executor.migrate(self.old_target)
        old = executor.loader.project_state(self.old_target).apps
        source_model = old.get_model("provenance", "DataSource")
        self.source = source_model.objects.create(
            name="SYNTHETIC LEGACY SOURCE - TEST ONLY",
            organization="Synthetic custodian",
            source_type="AGENCY_DATASET",
            status="PENDING_VALIDATION",
        )
        center_model = old.get_model("evacuation", "EvacuationCenter")
        self.legacy = [
            center_model.objects.create(
                name=f"SYNTHETIC LEGACY CENTER {index}",
                address="Synthetic address",
                latitude="0.123456",
                longitude="0.654321",
                source_id=self.source.pk,
                notes="Legacy note must be preserved",
            )
            for index in range(3)
        ]
        self.before = list(center_model.objects.order_by("pk").values())

    def restore_schema(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def upgrade(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.new_target)
        return executor.loader.project_state(self.new_target).apps.get_model(
            "evacuation", "EvacuationCenter"
        )

    def test_upgrade_assigns_distinct_v4_ids_and_preserves_all_legacy_fields(self):
        model = self.upgrade()
        rows = list(model.objects.order_by("pk").values())
        identifiers = [row.pop("public_id") for row in rows]
        self.assertEqual(rows, self.before)
        self.assertEqual(len(set(identifiers)), 3)
        self.assertTrue(
            all(isinstance(value, UUID) and value.version == 4 for value in identifiers)
        )
        field = model._meta.get_field("public_id")
        self.assertFalse(field.null)
        self.assertFalse(field.editable)
        self.assertTrue(field.unique)
        self.assertIs(field.default, uuid4)
        new = model.objects.create(
            name="SYNTHETIC NEW CENTER",
            address="Synthetic address",
            latitude=0,
            longitude=0,
            source_id=self.source.pk,
        )
        self.assertNotIn(new.public_id, identifiers)

    def test_reversal_preserves_centers_source_and_unrelated_records(self):
        self.upgrade()
        executor = MigrationExecutor(connection)
        executor.migrate(self.old_target)
        old = executor.loader.project_state(self.old_target).apps
        center_model = old.get_model("evacuation", "EvacuationCenter")
        self.assertEqual(list(center_model.objects.order_by("pk").values()), self.before)
        source = old.get_model("provenance", "DataSource").objects.get(pk=self.source.pk)
        self.assertEqual(source.name, self.source.name)
        self.assertEqual(source.organization, self.source.organization)
        # Re-upgrade remains possible, but rollback drops the identifiers. It is
        # not an acceptable production rollback after clients consume UUIDs.
        self.assertEqual(self.upgrade().objects.count(), 3)


@pytest.mark.django_db
def test_uuid_default_uniqueness_non_null_and_ordinary_edit_stability():
    source = DataSource.objects.create(name="SYNTHETIC UUID SOURCE", source_type="OTHER")
    attrs = {
        "name": "SYNTHETIC UUID CENTER",
        "address": "Synthetic",
        "latitude": 0,
        "longitude": 0,
        "source": source,
    }
    center = EvacuationCenter.objects.create(**attrs)
    other = EvacuationCenter.objects.create(**attrs)
    assert center.public_id != other.public_id
    original = center.public_id
    center.name = "SYNTHETIC EDITED CENTER"
    center.save()
    center.refresh_from_db()
    assert center.public_id == original
    for bad_id in (None, original):
        with pytest.raises(IntegrityError), transaction.atomic():
            EvacuationCenter.objects.create(**attrs, public_id=bad_id)


@pytest.mark.django_db
def test_uuid_stability_through_every_verification_transition():
    actor = get_user_model().objects.create_superuser(
        email="synthetic-uuid@example.test", password=None
    )
    source = DataSource.objects.create(
        name="SYNTHETIC WORKFLOW SOURCE",
        organization="Synthetic",
        source_type="AGENCY_DATASET",
        status="APPROVED",
        is_publicly_releasable=False,
    )
    center = EvacuationCenter.objects.create(
        name="SYNTHETIC WORKFLOW CENTER",
        address="Synthetic",
        latitude=0,
        longitude=0,
        source=source,
    )
    original = center.public_id
    for action in (
        "submit",
        "return-draft",
        "submit",
        "verify",
        "deactivate",
        "reactivate-review",
        "verify",
    ):
        center = transition_center(
            center_id=center.pk,
            action=action,
            actor=actor,
            expected_status=center.verification_status,
            verified_on=date(2026, 9, 19),
        )
        assert center.public_id == original
    # Verification remains possible without public release or an area: Admin
    # workflow semantics must not silently become resident service eligibility.
    assert center.verification_status == "VERIFIED"
    assert not source.is_publicly_releasable
    assert center.geographic_area_id is None
