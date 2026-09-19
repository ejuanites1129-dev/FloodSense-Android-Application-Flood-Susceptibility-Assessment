from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class GuidanceWorkflowMigrationTests(TransactionTestCase):
    migrate_from = [
        ("dss", "0001_initial"),
        ("provenance", "0001_initial"),
    ]
    migrate_to = [
        ("dss", "0002_guidance_workflow"),
        ("provenance", "0002_datasource_metadata_and_permissions"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        DataSource = old_apps.get_model("provenance", "DataSource")
        SusceptibilityLevel = old_apps.get_model("expert", "SusceptibilityLevel")
        GuidanceItem = old_apps.get_model("dss", "GuidanceItem")
        source = DataSource.objects.create(
            name="TEST LEGACY DEMONSTRATION SOURCE - NOT OFFICIAL",
            source_type="DEMONSTRATION",
            status="DEMONSTRATION",
        )
        level = SusceptibilityLevel.objects.create(
            code="LOW",
            label="Low",
            display_order=1,
            map_color="#2E9E5B",
            definition="Test-only migration classification.",
            source=source,
            status="DEMONSTRATION",
            is_enabled=True,
        )
        self.eligible_id = GuidanceItem.objects.create(
            susceptibility_level=level,
            title="Legacy eligible item",
            instruction="Test-only legacy guidance.",
            category="PREPARE",
            source=source,
            status="DEMONSTRATION",
            is_enabled=True,
        ).pk
        self.ineligible_id = GuidanceItem.objects.create(
            susceptibility_level=level,
            title="Legacy pending item",
            instruction="Test-only pending legacy guidance.",
            category="PREPARE",
            source=source,
            status="PENDING_VALIDATION",
            is_enabled=True,
        ).pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_only_previously_publicly_eligible_items_remain_published(self):
        GuidanceItem = self.apps.get_model("dss", "GuidanceItem")
        eligible = GuidanceItem.objects.get(pk=self.eligible_id)
        ineligible = GuidanceItem.objects.get(pk=self.ineligible_id)

        self.assertEqual(eligible.workflow_status, "PUBLISHED")
        self.assertTrue(eligible.is_enabled)
        self.assertEqual(ineligible.workflow_status, "DRAFT")
        self.assertFalse(ineligible.is_enabled)
