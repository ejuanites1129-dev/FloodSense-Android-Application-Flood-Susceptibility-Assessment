"""The additive schema preserves existing published records and creates no guidance."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import PROTECT
from django.test import TransactionTestCase
from django.utils import timezone


class ExpandedDSSMigrationTests(TransactionTestCase):
    migrate_from = [("dss", "0003_dssflowversion_dssoutcome_dssquestion_dssoption_and_more")]
    migrate_to = [("dss", "0004_expanded_structured_content")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        previous_apps = executor.loader.project_state(self.migrate_from).apps
        Source = previous_apps.get_model("provenance", "DataSource")
        Flow = previous_apps.get_model("dss", "DSSFlowVersion")
        Level = previous_apps.get_model("expert", "SusceptibilityLevel")
        Guidance = previous_apps.get_model("dss", "GuidanceItem")
        Question = previous_apps.get_model("dss", "DSSQuestion")
        Outcome = previous_apps.get_model("dss", "DSSOutcome")
        Option = previous_apps.get_model("dss", "DSSOption")
        source = Source.objects.create(
            name="Synthetic migration fixture",
            source_type="DEMONSTRATION",
            status="DEMONSTRATION",
        )
        level = Level.objects.create(
            code="LOW",
            label="Low",
            display_order=1,
            map_color="#123456",
            definition="Synthetic migration fixture.",
            source=source,
            status="DEMONSTRATION",
            is_enabled=True,
        )
        guidance = Guidance.objects.create(
            title="Existing library guidance",
            instruction="Existing synthetic instruction.",
            category="PREPARE",
            source=source,
            susceptibility_level=level,
            status="DEMONSTRATION",
            workflow_status="PUBLISHED",
            is_enabled=True,
        )
        flow = Flow.objects.create(
            code="preparedness",
            title="Existing published version",
            version="presentation-1",
            operating_mode="DEMONSTRATION",
            workflow_status="PUBLISHED",
            source=source,
            data_status="DEMONSTRATION",
            effective_date=timezone.localdate(),
            published_at=timezone.now(),
        )
        flow.susceptibility_levels.add(level)
        question = Question.objects.create(
            flow=flow, code="support", prompt="Existing support question?", is_start=True
        )
        outcome = Outcome.objects.create(
            flow=flow,
            code="plan",
            title="Existing outcome",
            instruction="Existing outcome instruction.",
            category="PREPARE",
            source=source,
            guidance_item=guidance,
        )
        option = Option.objects.create(
            question=question, code="yes", label="Existing choice", outcome=outcome
        )
        self.legacy_id = flow.pk
        self.published_at = flow.published_at
        self.updated_at = flow.updated_at
        self.graph_ids = (question.pk, option.pk, outcome.pk, guidance.pk, level.pk)
        self.source_count = Source.objects.count()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_published_legacy_version_is_preserved_and_no_content_or_source_is_inserted(self):
        Flow = self.apps.get_model("dss", "DSSFlowVersion")
        Block = self.apps.get_model("dss", "DSSContentBlock")
        Source = self.apps.get_model("provenance", "DataSource")
        existing = Flow.objects.get(pk=self.legacy_id)
        self.assertEqual(existing.title, "Existing published version")
        self.assertEqual(existing.workflow_status, "PUBLISHED")
        self.assertEqual(existing.version, "presentation-1")
        self.assertEqual(existing.attribution, "")
        self.assertEqual(existing.limitations, "")
        self.assertEqual(existing.source_locator, "")
        self.assertEqual(existing.published_at, self.published_at)
        self.assertEqual(existing.updated_at, self.updated_at)
        self.assertIsNone(existing.reviewed_on)
        self.assertIsNone(existing.expires_on)
        self.assertEqual(Block.objects.count(), 0)
        self.assertEqual(Source.objects.count(), self.source_count)
        Question = self.apps.get_model("dss", "DSSQuestion")
        Option = self.apps.get_model("dss", "DSSOption")
        Outcome = self.apps.get_model("dss", "DSSOutcome")
        Guidance = self.apps.get_model("dss", "GuidanceItem")
        question_id, option_id, outcome_id, guidance_id, level_id = self.graph_ids
        self.assertEqual(existing.susceptibility_levels.get().pk, level_id)
        self.assertEqual(Question.objects.get(pk=question_id).flow_id, existing.pk)
        option = Option.objects.get(pk=option_id)
        self.assertEqual(option.question_id, question_id)
        self.assertEqual(option.outcome_id, outcome_id)
        outcome = Outcome.objects.get(pk=outcome_id)
        self.assertEqual(outcome.flow_id, existing.pk)
        self.assertEqual(outcome.guidance_item_id, guidance_id)
        self.assertEqual(
            Guidance.objects.get(pk=guidance_id).instruction, "Existing synthetic instruction."
        )
        self.assertIs(Outcome._meta.get_field("guidance_item").remote_field.on_delete, PROTECT)
