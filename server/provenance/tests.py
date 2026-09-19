from datetime import date

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .models import DataSource, PublicationStatus


class DataSourceDefinitionTests(SimpleTestCase):
    def test_new_source_defaults_to_safe_demonstration_status(self):
        source = DataSource(
            name="Demonstration Source",
            source_type=DataSource.SourceType.DEMONSTRATION,
        )

        self.assertEqual(source.status, PublicationStatus.DEMONSTRATION)
        self.assertFalse(source.is_publicly_releasable)
        self.assertEqual(str(source), "Demonstration Source")

    def test_data_source_is_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(DataSource))

    def test_coverage_period_must_be_chronological(self):
        source = DataSource(
            name="Invalid period",
            source_type=DataSource.SourceType.PUBLICATION,
            record_period_start=date(2026, 2, 1),
            record_period_end=date(2026, 1, 1),
        )

        with self.assertRaisesMessage(ValidationError, "cannot precede"):
            source.full_clean()
