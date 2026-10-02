from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ReviewedImportMigrationTests(TransactionTestCase):
    def test_additive_batch_schema_preserves_existing_center_and_unknown_capacity(self):
        previous = [("evacuation", "0002_evacuationcenter_public_id")]
        current = [("evacuation", "0003_reviewed_center_import_batch")]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(previous)
            old = executor.loader.project_state(previous).apps
            source = old.get_model("provenance", "DataSource").objects.create(
                name="Synthetic migration source", source_type="OTHER", status="PENDING_VALIDATION"
            )
            center = old.get_model("evacuation", "EvacuationCenter").objects.create(
                name="Synthetic preserved draft",
                address="Test only",
                source=source,
                latitude="0.2",
                longitude="0.3",
            )
            before = (center.pk, center.public_id, center.updated_at)
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            new = executor.loader.project_state(current).apps
            preserved = new.get_model("evacuation", "EvacuationCenter").objects.get(pk=before[0])
            self.assertEqual((preserved.pk, preserved.public_id, preserved.updated_at), before)
            self.assertEqual(preserved.verification_status, "DRAFT")
            self.assertIsNone(preserved.capacity)
            self.assertEqual(new.get_model("evacuation", "CenterImportBatch").objects.count(), 0)
            self.assertTrue(
                new.get_model("evacuation", "CenterImportBatch")._meta.get_field("imported_by").null
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
