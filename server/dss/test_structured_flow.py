from copy import deepcopy

from accounts.models import User
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus
from rest_framework.test import APIClient

from .flow_workflow import publish_dss_flow
from .models import DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion, GuidanceItem
from .services import answer_dss_question, validate_dss_flow


class StructuredDSSFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.source = DataSource.objects.create(
            name="STRUCTURED DSS TEST DEMONSTRATION - NOT OFFICIAL",
            source_type=DataSource.SourceType.DEMONSTRATION,
            status=PublicationStatus.DEMONSTRATION,
        )
        self.level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.HIGH,
            label="High",
            display_order=3,
            map_color="#D14A3A",
            definition="Test only.",
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self.flow = DSSFlowVersion.objects.create(
            code="preparedness",
            title="Test preparedness flow",
            version="1",
            operating_mode=DSSFlowVersion.OperatingMode.DEMONSTRATION,
            workflow_status=DSSFlowVersion.WorkflowStatus.DRAFT,
            source=self.source,
            data_status=PublicationStatus.DEMONSTRATION,
            effective_date=timezone.localdate(),
        )
        self.flow.susceptibility_levels.add(self.level)
        self.start = DSSQuestion.objects.create(
            flow=self.flow,
            code="support",
            prompt="Do you need help preparing?",
            display_order=1,
            is_start=True,
        )
        self.second = DSSQuestion.objects.create(
            flow=self.flow,
            code="supplies",
            prompt="Are supplies ready?",
            display_order=2,
        )
        self.outcome = DSSOutcome.objects.create(
            flow=self.flow,
            code="prepare",
            title="Prepare safely",
            instruction="Review supplies and official information.",
            category=GuidanceItem.Category.PREPARE,
            source=self.source,
        )
        DSSOption.objects.create(
            question=self.start,
            code="yes",
            label="Yes",
            next_question=self.second,
        )
        DSSOption.objects.create(
            question=self.start,
            code="no",
            label="No",
            outcome=self.outcome,
        )
        DSSOption.objects.create(
            question=self.second,
            code="continue",
            label="Continue",
            outcome=self.outcome,
        )

    def test_valid_flow_and_deterministic_answer_do_not_mutate_assessment(self):
        validate_dss_flow(self.flow)
        assessment = {"susceptibility": {"code": "HIGH"}, "matched_rule": "R-1"}
        snapshot = deepcopy(assessment)
        response = answer_dss_question(
            flow=self.flow, question_code="support", option_code="yes"
        )
        self.assertEqual(response["kind"], "question")
        self.assertEqual(response["question"]["code"], "supplies")
        self.assertEqual(assessment, snapshot)

    def test_invalid_option_is_rejected(self):
        with self.assertRaises(ValidationError):
            answer_dss_question(
                flow=self.flow, question_code="support", option_code="unknown"
            )

    def test_dead_end_cycle_and_unreachable_question_are_detected(self):
        DSSOption.objects.filter(question=self.second).delete()
        with self.assertRaisesMessage(ValidationError, "has no options"):
            validate_dss_flow(self.flow)
        DSSOption.objects.create(
            question=self.second,
            code="loop",
            label="Loop",
            next_question=self.start,
        )
        with self.assertRaisesMessage(ValidationError, "cycle"):
            validate_dss_flow(self.flow)
        DSSOption.objects.filter(question=self.second).update(
            next_question=None, outcome=self.outcome
        )
        unreachable = DSSQuestion.objects.create(
            flow=self.flow,
            code="orphan",
            prompt="Unreachable?",
            display_order=3,
        )
        DSSOption.objects.create(
            question=unreachable,
            code="done",
            label="Done",
            outcome=self.outcome,
        )
        with self.assertRaisesMessage(ValidationError, "Unreachable"):
            validate_dss_flow(self.flow)

    def test_cross_version_branch_is_rejected(self):
        other = DSSFlowVersion.objects.create(
            code="other",
            title="Other",
            version="1",
            operating_mode=DSSFlowVersion.OperatingMode.DEMONSTRATION,
            source=self.source,
            data_status=PublicationStatus.DEMONSTRATION,
        )
        other_question = DSSQuestion.objects.create(
            flow=other, code="other", prompt="Other?", is_start=True
        )
        option = DSSOption(
            question=self.second,
            code="invalid-cross-version",
            label="Invalid",
            next_question=other_question,
        )
        with self.assertRaises(ValidationError):
            option.full_clean()

    def test_publication_requires_permission_review_state_and_audits(self):
        actor = User.objects.create_user(
            email="reviewer@example.com",
            password="Reviewer-Password-482!",
            display_name="Reviewer",
            is_staff=True,
        )
        self.flow.workflow_status = DSSFlowVersion.WorkflowStatus.IN_REVIEW
        self.flow.save(update_fields=("workflow_status",))
        with self.assertRaises(PermissionDenied):
            publish_dss_flow(flow_id=self.flow.pk, actor=actor)
        actor.user_permissions.add(
            Permission.objects.get(codename="publish_dssflowversion")
        )
        actor = User.objects.get(pk=actor.pk)
        published = publish_dss_flow(flow_id=self.flow.pk, actor=actor)
        self.assertEqual(
            published.workflow_status, DSSFlowVersion.WorkflowStatus.PUBLISHED
        )

    def test_mode_source_separation_is_enforced(self):
        self.flow.operating_mode = DSSFlowVersion.OperatingMode.OFFICIAL
        self.flow.data_status = PublicationStatus.APPROVED
        self.flow.workflow_status = DSSFlowVersion.WorkflowStatus.PUBLISHED
        self.flow.published_at = timezone.now()
        with self.assertRaises(ValidationError):
            self.flow.full_clean()

    def test_published_graph_nodes_are_append_only(self):
        self.flow.workflow_status = DSSFlowVersion.WorkflowStatus.PUBLISHED
        self.flow.published_at = timezone.now()
        self.flow.save(update_fields=("workflow_status", "published_at"))
        self.start.prompt = "Changed after publication?"
        with self.assertRaises(ValidationError):
            self.start.full_clean()
        option = self.start.options.first()
        option.label = "Changed"
        with self.assertRaises(ValidationError):
            option.full_clean()
        self.outcome.instruction = "Changed"
        with self.assertRaises(ValidationError):
            self.outcome.full_clean()

    def test_stateless_start_answer_back_and_restart_contract(self):
        self.flow.workflow_status = DSSFlowVersion.WorkflowStatus.PUBLISHED
        self.flow.published_at = timezone.now()
        self.flow.save(update_fields=("workflow_status", "published_at"))
        url = "/api/v1/dss/flows/start/?mode=demonstration&susceptibility_level=HIGH"
        started = self.client.get(url)
        answer = self.client.post(
            "/api/v1/dss/flows/preparedness/1/answer/",
            {
                "mode": "demonstration",
                "susceptibility_level": "HIGH",
                "question_code": "support",
                "option_code": "yes",
            },
            format="json",
        )
        restarted = self.client.get(url)
        self.assertEqual(started.status_code, 200)
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(restarted.data["question"]["code"], "support")
        self.assertFalse(answer.data["history_persisted"])
        self.assertEqual(started.data["assessment_context"]["susceptibility_level"], "HIGH")
