from datetime import date

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import TestCase
from provenance.models import DataSource, PublicationStatus

from .models import EvacuationCenter


class EvacuationCenterValidationTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="Approved test source",
            organization="Test organization",
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.APPROVED,
        )

    def test_capacity_is_rejected_until_center_is_verified(self):
        center = EvacuationCenter(
            name="Test center",
            address="Test address",
            latitude="14.46",
            longitude="120.96",
            capacity=50,
            source=self.source,
        )

        with self.assertRaisesMessage(
            ValidationError, "Capacity may be recorded only after verification"
        ):
            center.full_clean()

    def test_verified_center_requires_date_and_approved_source(self):
        self.source.status = PublicationStatus.PENDING_VALIDATION
        self.source.save(update_fields=("status",))
        center = EvacuationCenter(
            name="Test center",
            address="Test address",
            latitude="14.46",
            longitude="120.96",
            source=self.source,
            verification_status=EvacuationCenter.VerificationStatus.VERIFIED,
        )

        with self.assertRaises(ValidationError) as raised:
            center.full_clean()

        self.assertIn("verified_on", raised.exception.message_dict)
        self.assertIn("source", raised.exception.message_dict)

    def test_valid_verified_center_has_audit_friendly_string(self):
        center = EvacuationCenter(
            name="Test center",
            address="Test address",
            latitude="14.46",
            longitude="120.96",
            source=self.source,
            verification_status=EvacuationCenter.VerificationStatus.VERIFIED,
            verified_on=date(2026, 9, 19),
        )

        center.full_clean()

        self.assertEqual(str(center), "Test center")
        self.assertTrue(admin.site.is_registered(EvacuationCenter))
