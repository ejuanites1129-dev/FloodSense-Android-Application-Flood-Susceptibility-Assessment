
from django.contrib import admin
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
