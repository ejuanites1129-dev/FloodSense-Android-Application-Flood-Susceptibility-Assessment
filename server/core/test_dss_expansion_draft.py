"""The optional expansion prepares one local draft without changing public history."""

from io import StringIO
from itertools import product

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from dss.management.commands.prepare_dss_expansion import (
    CONTENT,
    FLOW_CODE,
    FLOW_VERSION,
    QUESTIONS,
    SOURCE_NAME,
    SOURCE_VALUES,
)
from dss.models import DSSContentBlock, DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion
from dss.services import validate_dss_flow
from expert.models import (
    ExpertRule,
    ExpertRuleCondition,
    RuleSet,
    ScenarioOption,
    SusceptibilityLevel,
)
from expert.services import evaluate_assessment
from geography.models import GeographicArea
from provenance.models import DataSource, PublicationStatus


class PrepareDSSExpansionDraftTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Commands execute only inside Django's isolated test database here.
        call_command("seed_demo", stdout=StringIO())

    def _prepare(self):
        output = StringIO()
        call_command("prepare_dss_expansion", confirm_local_development=True, stdout=output)
        return output.getvalue()

    def _flow(self):
        return DSSFlowVersion.objects.get(code=FLOW_CODE, version=FLOW_VERSION)

    def _start(self):
        return self.client.get(
            "/api/v1/dss/flows/start/",
            {"mode": "demonstration", "susceptibility_level": "HIGH"},
        )

    def test_confirmation_is_required_before_any_record_is_created(self):
        with self.assertRaisesMessage(CommandError, "--confirm-local-development"):
            call_command("prepare_dss_expansion", stdout=StringIO())
        self.assertFalse(DataSource.objects.filter(name=SOURCE_NAME).exists())
        self.assertFalse(DSSFlowVersion.objects.filter(version=FLOW_VERSION).exists())

    def test_prepares_complete_nonpublic_synthetic_draft_and_preserves_current_flow(self):
        public_before = self._start().json()
        existing = DSSFlowVersion.objects.get(version="presentation-1")
        old_flow_snapshot = dict(DSSFlowVersion.objects.filter(pk=existing.pk).values().get())
        old_questions = list(existing.questions.values())
        old_outcomes = list(existing.outcomes.values())
        old_options = list(DSSOption.objects.filter(question__flow=existing).values())

        output = self._prepare()

        flow = self._flow()
        self.assertEqual(flow.workflow_status, DSSFlowVersion.WorkflowStatus.DRAFT)
        self.assertIsNone(flow.published_at)
        self.assertEqual(flow.data_status, PublicationStatus.DEMONSTRATION)
        self.assertEqual(flow.operating_mode, DSSFlowVersion.OperatingMode.DEMONSTRATION)
        self.assertFalse(flow.source.is_publicly_releasable)
        self.assertIn("not BDRRMO-authored", flow.source.limitations)
        self.assertIn("pending expert validation", flow.limitations)
        self.assertIn("unpublished demonstration draft", output)
        self.assertEqual(flow.questions.count(), 6)
        self.assertEqual(DSSOption.objects.filter(question__flow=flow).count(), 12)
        self.assertEqual(flow.outcomes.count(), 2)
        self.assertEqual(flow.content_blocks.count(), len(CONTENT))
        validate_dss_flow(flow)
        self.assertEqual(
            old_flow_snapshot, dict(DSSFlowVersion.objects.filter(pk=existing.pk).values().get())
        )
        self.assertEqual(old_questions, list(existing.questions.values()))
        self.assertEqual(old_outcomes, list(existing.outcomes.values()))
        self.assertEqual(
            old_options, list(DSSOption.objects.filter(question__flow=existing).values())
        )
        self.assertEqual(public_before, self._start().json())
        draft_answer = self.client.post(
            f"/api/v1/dss/flows/{FLOW_CODE}/{FLOW_VERSION}/answer/",
            {
                "mode": "demonstration",
                "susceptibility_level": "HIGH",
                "question_code": "support-needs",
                "option_code": "yes",
            },
            content_type="application/json",
        )
        self.assertEqual(draft_answer.status_code, 400)
        self.assertIn("not current", draft_answer.json()["flow"][0])

    def test_every_answer_combination_visits_all_six_checks_and_reaches_one_outcome(self):
        self._prepare()
        flow = self._flow()
        all_outcomes = set()
        for answers in product(("yes", "no"), repeat=6):
            question = flow.questions.get(is_start=True)
            visited = []
            for answer in answers:
                visited.append(question.code)
                option = question.options.select_related("next_question", "outcome").get(
                    code=answer
                )
                self.assertTrue(option.supporting_text)
                if option.next_question_id:
                    question = option.next_question
                else:
                    self.assertEqual(len(visited), 6)
                    all_outcomes.add(option.outcome.code)
            self.assertEqual(visited, [values[0] for values in QUESTIONS])
        self.assertEqual(all_outcomes, {"review-household-plan", "identify-official-channels"})

    def test_content_has_all_phases_and_provenance_without_operational_thresholds_or_links(self):
        self._prepare()
        flow = self._flow()
        blocks = list(flow.content_blocks.all())
        self.assertEqual({block.phase for block in blocks}, {"ALWAYS", "BEFORE", "DURING", "AFTER"})
        for block in blocks:
            self.assertEqual(block.source_id, flow.source_id)
            self.assertEqual(block.data_status, PublicationStatus.DEMONSTRATION)
            self.assertTrue(block.source_locator)
            self.assertTrue(block.attribution)
            self.assertTrue(block.limitations)
            self.assertFalse(block.reference_stage)
            self.assertFalse(block.public_url)
            self.assertIsNone(block.url_verified_on)
        text = " ".join(block.body for block in blocks)
        self.assertIn("FloodSense does not monitor these sources live.", text)
        for withheld_marker in ("1.0–2.0", "2.1–5.0", "5.1", "C.O. 250-2022", "30 cm"):
            self.assertNotIn(withheld_marker, text)
        self.assertTrue(flow.content_blocks.filter(content_type="AUTHORITY_ACTIVITY").exists())
        self.assertTrue(flow.content_blocks.filter(content_type="OFFICIAL_CHANNEL").exists())

    def test_identical_rerun_is_a_noop_including_record_timestamps(self):
        self._prepare()
        snapshots = {
            model: list(model.objects.values())
            for model in (
                DataSource,
                DSSFlowVersion,
                DSSQuestion,
                DSSOption,
                DSSOutcome,
                DSSContentBlock,
            )
        }
        output = self._prepare()
        self.assertIn("Existing matching presentation-2 draft preserved", output)
        for model, before in snapshots.items():
            self.assertEqual(list(model.objects.values()), before)

    def test_local_edits_are_preserved_and_refuse_silent_reseeding(self):
        self._prepare()
        flow = self._flow()
        block = flow.content_blocks.first()
        block.body = "Locally revised draft awaiting review."
        block.save()
        with self.assertRaisesMessage(CommandError, "Existing draft content differs"):
            self._prepare()
        block.refresh_from_db()
        self.assertEqual(block.body, "Locally revised draft awaiting review.")
        self.assertEqual(self._start().json()["flow"]["version"], "presentation-1")

    def test_foreign_flow_identity_rolls_back_the_new_source_atomically(self):
        foreign_source = DataSource.objects.create(
            name="Other local content source",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
        )
        foreign_flow = DSSFlowVersion.objects.create(
            code=FLOW_CODE,
            version=FLOW_VERSION,
            title="Other local draft",
            source=foreign_source,
            operating_mode=DSSFlowVersion.OperatingMode.DEMONSTRATION,
        )
        with self.assertRaisesMessage(CommandError, "Existing presentation-2 is different"):
            self._prepare()
        self.assertFalse(DataSource.objects.filter(name=SOURCE_NAME).exists())
        foreign_flow.refresh_from_db()
        self.assertEqual(foreign_flow.title, "Other local draft")
        self.assertEqual(foreign_flow.questions.count(), 0)

    def test_reserved_source_conflict_is_preserved_and_aborts_without_a_flow(self):
        source = DataSource.objects.create(
            name=SOURCE_NAME,
            source_type=DataSource.SourceType.PUBLICATION,
            status=PublicationStatus.PENDING_VALIDATION,
        )
        with self.assertRaisesMessage(CommandError, "reserved expansion source differs"):
            self._prepare()
        source.refresh_from_db()
        self.assertEqual(source.source_type, DataSource.SourceType.PUBLICATION)
        self.assertFalse(DSSFlowVersion.objects.filter(version=FLOW_VERSION).exists())

    def test_duplicate_source_identity_aborts_without_choosing_an_arbitrary_source(self):
        for _ in range(2):
            DataSource.objects.create(name=SOURCE_NAME, **SOURCE_VALUES)
        with self.assertRaisesMessage(CommandError, "Multiple sources"):
            self._prepare()
        self.assertFalse(DSSFlowVersion.objects.filter(version=FLOW_VERSION).exists())

    def test_missing_or_ineligible_classification_never_creates_assessment_data(self):
        level = SusceptibilityLevel.objects.get(code="HIGH")
        level.is_enabled = False
        level.save(update_fields=("is_enabled",))
        with self.assertRaisesMessage(CommandError, "four existing enabled demonstration"):
            self._prepare()
        level.refresh_from_db()
        self.assertFalse(level.is_enabled)
        self.assertFalse(DataSource.objects.filter(name=SOURCE_NAME).exists())

    def test_draft_expansion_leaves_expert_system_output_and_all_knowledge_unchanged(self):
        inputs = {
            "area_identifier": GeographicArea.objects.get(code="DEMO_ZONE_C").pk,
            "intensity_code": "DEMO_HEAVY",
            "duration_code": "DEMO_3_HOURS",
            "mode": "DEMONSTRATION",
        }
        result_before = evaluate_assessment(**inputs)
        knowledge_before = {
            model: list(model.objects.values())
            for model in (
                SusceptibilityLevel,
                ScenarioOption,
                RuleSet,
                ExpertRule,
                ExpertRuleCondition,
            )
        }
        self._prepare()
        self.assertEqual(evaluate_assessment(**inputs), result_before)
        for model, before in knowledge_before.items():
            self.assertEqual(list(model.objects.values()), before)
