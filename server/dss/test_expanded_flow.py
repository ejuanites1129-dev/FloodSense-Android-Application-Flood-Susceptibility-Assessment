"""Publication, provenance and append-only regression coverage for canonical Prepare."""

from datetime import timedelta

from accounts.models import User
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus
from rest_framework.test import APIClient

from .flow_workflow import (
    clone_dss_flow,
    publish_dss_flow,
    retire_dss_flow,
    return_dss_flow_to_draft,
    submit_dss_flow,
)
from .models import (
    DSSContentBlock,
    DSSFlowVersion,
    DSSOption,
    DSSOutcome,
    DSSQuestion,
    GuidanceItem,
)
from .services import (
    GuidanceSelectionError,
    answer_dss_question,
    select_dss_flow,
    select_guidance_for_level,
    serialize_dss_preview,
    serialize_dss_question,
    validate_dss_flow,
)


class ExpandedFlowTests(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="Synthetic test pack — NOT OFFICIAL",
            organization="Test project",
            source_type="DEMONSTRATION",
            status="DEMONSTRATION",
            version="test-1",
            notes="PRIVATE INTERVIEW",
            processing_notes="PRIVATE PROCESSING",
            permitted_use="PRIVATE RESTRICTION",
            limitations="Test material only.",
        )
        self.level = SusceptibilityLevel.objects.create(
            code="HIGH",
            label="High",
            display_order=3,
            map_color="#993333",
            definition="Synthetic test level.",
            source=self.source,
            status="DEMONSTRATION",
            is_enabled=True,
        )
        self.flow = DSSFlowVersion.objects.create(
            code="preparedness",
            title="Synthetic Prepare",
            version="test-1",
            operating_mode="DEMONSTRATION",
            source=self.source,
            data_status="DEMONSTRATION",
            effective_date=timezone.localdate(),
            limitations="Pending content validation; demonstration only.",
            attribution="Synthetic test author",
            source_locator="Test pack",
        )
        self.flow.susceptibility_levels.add(self.level)
        self.question = DSSQuestion.objects.create(
            flow=self.flow,
            code="support",
            prompt="Is a trusted helper assigned?",
            is_start=True,
        )
        self.outcome = DSSOutcome.objects.create(
            flow=self.flow,
            code="review",
            title="Review household preparations",
            instruction="Plan ahead with your household.",
            category="PREPARE",
            source=self.source,
        )
        self.option = DSSOption.objects.create(
            question=self.question,
            code="review",
            label="Review",
            outcome=self.outcome,
        )
        self.common = self.block(title="Common action", display_order=2)
        self.personal = self.block(title="Support priority", outcome=self.outcome, display_order=1)
        self.actor = User.objects.create_user(
            email="dss-publisher@example.com",
            password="Synthetic-Test-483!",
            display_name="Test publisher",
            is_staff=True,
        )

    def block(self, **fields):
        values = {
            "flow": self.flow,
            "source": self.source,
            "title": "Action",
            "body": "Synthetic preparedness action, pending validation.",
            "content_type": DSSContentBlock.ContentType.HOUSEHOLD_ACTION,
            "data_status": PublicationStatus.DEMONSTRATION,
        }
        values.update(fields)
        return DSSContentBlock.objects.create(**values)

    def permit(self, *codenames):
        self.actor.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        self.actor = User.objects.get(pk=self.actor.pk)

    def publish(self):
        self.permit("review_dssflowversion", "publish_dssflowversion")
        submit_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        self.flow = publish_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        return self.flow

    def test_common_and_outcome_blocks_are_ordered_without_changing_legacy_keys(self):
        self.publish()
        question = serialize_dss_question(self.flow, self.question)
        outcome = answer_dss_question(flow=self.flow, question_code="support", option_code="review")
        self.assertEqual(question["contract_version"], 2)
        self.assertEqual([item["title"] for item in question["content_blocks"]], ["Common action"])
        self.assertEqual(
            [item["title"] for item in outcome["content_blocks"]],
            ["Support priority", "Common action"],
        )
        self.assertEqual(outcome["outcome"]["instruction"], self.outcome.instruction)
        self.assertEqual(question["flow"]["limitations"], self.flow.limitations)
        self.assertEqual(question["question"]["options"][0]["code"], "review")

    def test_linked_guidance_public_provenance_is_expanded_only_in_versioned_contract(self):
        item = GuidanceItem.objects.create(
            susceptibility_level=self.level,
            title="Linked synthetic action",
            instruction="Existing synthetic library action.",
            category="PREPARE",
            source=self.source,
            status="DEMONSTRATION",
            workflow_status="PUBLISHED",
            is_enabled=True,
        )
        self.outcome.guidance_item = item
        self.outcome.save()
        self.publish()
        result = answer_dss_question(
            flow=self.flow, question_code="support", option_code="review"
        )
        linked = result["outcome"]["guidance"][0]
        self.assertEqual(linked["source"]["version"], "test-1")
        self.assertEqual(linked["source"]["limitations"], "Test material only.")
        self.assertEqual(linked["source"]["data_status"], "DEMONSTRATION")
        self.assertIsNone(linked["source"]["citation_url"])
        self.assertNotIn("PRIVATE INTERVIEW", str(linked))
        self.assertNotIn("PRIVATE PROCESSING", str(linked))
        self.assertNotIn("PRIVATE RESTRICTION", str(linked))
        preview = serialize_dss_preview(self.flow)
        self.assertEqual(preview["outcomes"][0]["guidance"][0], linked)
        legacy = select_guidance_for_level(susceptibility_code="HIGH", mode="DEMONSTRATION")
        self.assertEqual(set(legacy[0]["source"]), {"id", "name", "organization"})

    def test_staff_pending_board_references_never_enter_public_or_resident_preview(self):
        candidate = DataSource.objects.create(
            name="Board candidate pending BDRRMO review",
            source_type="OTHER",
            status="PENDING_VALIDATION",
            notes="PRIVATE INTERVIEW CONTENT",
        )
        self.block(
            title="Pending board stage",
            body="Pending BDRRMO validation — not public guidance",
            source=candidate,
            audience="STAFF_ONLY",
            data_status="PENDING_VALIDATION",
            reference_stage="YELLOW",
            content_type="RISK_REFERENCE",
        )
        self.publish()
        payload = serialize_dss_question(self.flow, self.question)
        self.assertNotIn("Pending board stage", str(payload))
        self.assertNotIn("Pending board stage", str(serialize_dss_preview(self.flow)))
        preview = serialize_dss_preview(self.flow, include_staff_only=True)
        self.assertTrue(preview["preview"])
        self.assertFalse(preview["history_persisted"])
        self.assertIn("Pending board stage", str(preview))
        self.assertNotIn("PRIVATE INTERVIEW", str(preview))

    def test_public_provenance_excludes_private_notes_processing_and_permissions(self):
        self.publish()
        payload = serialize_dss_question(self.flow, self.question)
        self.assertNotIn("PRIVATE", str(payload))
        self.assertNotIn("reviewed_by", str(payload))
        self.assertEqual(payload["flow"]["source"]["version"], "test-1")
        self.assertEqual(payload["flow"]["source"]["limitations"], "Test material only.")

    def test_draft_preview_uses_exact_graph_and_presentation_contract(self):
        self.common.data_status = "PENDING_VALIDATION"
        self.common.save()
        preview = serialize_dss_preview(self.flow)
        self.assertTrue(preview["preview"])
        self.assertEqual(preview["questions"][0]["options"][0]["outcome_code"], "review")
        self.assertIsNone(preview["questions"][0]["options"][0]["next_question_code"])
        self.assertEqual(preview["outcomes"][0]["instruction"], self.outcome.instruction)
        self.assertEqual(len(preview["content_blocks"]), 2)
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION")

    def test_pending_or_restricted_public_block_prevents_submission(self):
        self.permit("review_dssflowversion")
        for status in ("PENDING_VALIDATION", "RESTRICTED"):
            self.common.data_status = status
            self.common.save()
            with self.assertRaisesMessage(ValidationError, "not eligible"):
                submit_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.workflow_status, "DRAFT")
        self.assertEqual(LogEntry.objects.count(), 0)

    def test_every_intended_outcome_must_be_reachable(self):
        DSSOutcome.objects.create(
            flow=self.flow,
            code="orphan",
            title="Unused",
            instruction="Unused outcome",
            category="PREPARE",
            source=self.source,
        )
        with self.assertRaisesMessage(ValidationError, "Unreachable outcomes"):
            validate_dss_flow(self.flow)

    def test_selection_is_explicit_by_purpose_and_rechecks_source_revocation(self):
        self.publish()
        other = DSSFlowVersion.objects.create(
            code="other-purpose",
            title="Unrelated flow",
            version="1",
            operating_mode="DEMONSTRATION",
            source=self.source,
            data_status="DEMONSTRATION",
            effective_date=timezone.localdate(),
        )
        self.assertEqual(
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION"), self.flow
        )
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION", code=other.code)
        self.source.status = "RESTRICTED"
        self.source.save()
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION")

    def test_mode_and_level_revocation_fail_closed(self):
        self.publish()
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="OFFICIAL")
        self.level.is_enabled = False
        self.level.save()
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION")

    def test_future_and_expired_flow_do_not_select_and_expired_blocks_are_omitted(self):
        self.common.expires_on = timezone.localdate() - timedelta(days=1)
        self.common.save()
        self.flow.effective_date = timezone.localdate() + timedelta(days=1)
        self.flow.save()
        self.publish()
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION")
        self.assertEqual(serialize_dss_question(self.flow, self.question)["content_blocks"], [])

    def test_published_graph_cannot_be_saved_added_moved_bulk_updated_or_deleted(self):
        self.publish()
        self.question.prompt = "Changed"
        self.common.body = "Changed"
        for obj in (self.question, self.option, self.outcome, self.common):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
        with self.assertRaises(ValidationError):
            self.block(title="Appended after publication")
        with self.assertRaises(ValidationError):
            DSSQuestion.objects.filter(pk=self.question.pk).update(prompt="Bulk bypass")
        draft = DSSFlowVersion.objects.create(
            code="other",
            title="Editable",
            version="1",
            operating_mode="DEMONSTRATION",
            source=self.source,
        )
        self.question.flow = draft
        with self.assertRaises(ValidationError):
            self.question.save()
        with self.assertRaises(ValidationError):
            self.flow.delete()

    def test_published_forward_reverse_and_direct_m2m_operations_are_protected(self):
        self.publish()
        for operation in (
            lambda: self.flow.susceptibility_levels.clear(),
            lambda: self.flow.susceptibility_levels.remove(self.level),
            lambda: self.level.dss_flows.remove(self.flow),
            lambda: self.level.dss_flows.clear(),
        ):
            with self.assertRaises(ValidationError):
                with transaction.atomic():
                    operation()
        second = SusceptibilityLevel.objects.create(
            code="LOW",
            label="Low",
            display_order=1,
            map_color="#339933",
            definition="Test",
            source=self.source,
            status="DEMONSTRATION",
            is_enabled=True,
        )
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.flow.susceptibility_levels.add(second)
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                second.dss_flows.add(self.flow)
        with self.assertRaises(ValidationError):
            DSSFlowVersion.susceptibility_levels.through.objects.create(
                dssflowversion=self.flow,
                susceptibilitylevel=second,
            )
        self.assertEqual(self.flow.susceptibility_levels.count(), 1)

    def test_review_freezes_graph_metadata_and_associations_until_returned(self):
        self.permit("review_dssflowversion")
        self.flow = submit_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        with self.assertRaises(ValidationError):
            self.common.save()
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.flow.susceptibility_levels.clear()
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.level.dss_flows.remove(self.flow)
        self.flow.title = "Changed under review"
        with self.assertRaises(ValidationError):
            self.flow.save()
        self.flow = return_dss_flow_to_draft(flow_id=self.flow.pk, actor=self.actor)
        self.common.body = "Updated draft"
        self.common.save()
        self.assertEqual(DSSContentBlock.objects.get(pk=self.common.pk).body, "Updated draft")

    def test_direct_association_apis_cannot_modify_or_reparent_published_history(self):
        through = DSSFlowVersion.susceptibility_levels.through
        link = through.objects.get(dssflowversion=self.flow, susceptibilitylevel=self.level)
        draft = clone_dss_flow(
            flow_id=self.flow.pk,
            version="next-draft",
            actor=User.objects.create_superuser(email="clone@example.com", password="Test-483!"),
        )
        self.publish()
        link.dssflowversion = draft
        for operation in (
            lambda: link.save(),
            lambda: through.objects.filter(pk=link.pk).update(dssflowversion=draft),
            lambda: through.objects.bulk_update([link], ["dssflowversion"]),
            lambda: through.objects.filter(pk=link.pk).delete(),
            lambda: link.delete(),
            lambda: through.objects.bulk_create(
                [through(dssflowversion=self.flow, susceptibilitylevel=self.level)],
                ignore_conflicts=True,
            ),
            lambda: through._default_manager.filter(pk=link.pk).update(dssflowversion=draft),
            lambda: through._base_manager.filter(pk=link.pk).update(dssflowversion=draft),
            lambda: through.objects.bulk_create(
                [through(pk=link.pk, dssflowversion=draft, susceptibilitylevel=self.level)],
                update_conflicts=True,
                update_fields=["dssflowversion"],
                unique_fields=["pk"],
            ),
            lambda: self.level.delete(),
        ):
            with self.assertRaises(ValidationError):
                with transaction.atomic():
                    operation()
        self.assertEqual(through.objects.get(pk=link.pk).dssflowversion_id, self.flow.pk)
        self.assertTrue(SusceptibilityLevel.objects.filter(pk=self.level.pk).exists())

    def test_direct_association_writes_advance_draft_revision_tokens(self):
        through = DSSFlowVersion.susceptibility_levels.through
        self.flow.susceptibility_levels.clear()
        self.flow.refresh_from_db()
        previous = self.flow.updated_at
        link = through.objects.create(dssflowversion=self.flow, susceptibilitylevel=self.level)
        self.flow.refresh_from_db()
        self.assertGreater(self.flow.updated_at, previous)
        previous = self.flow.updated_at
        link.delete()
        self.flow.refresh_from_db()
        self.assertGreater(self.flow.updated_at, previous)
        previous = self.flow.updated_at
        through.objects.bulk_create(
            [through(dssflowversion=self.flow, susceptibilitylevel=self.level)]
        )
        self.flow.refresh_from_db()
        self.assertGreater(self.flow.updated_at, previous)

    def test_draft_graph_relationship_writes_cannot_cross_flow_versions(self):
        draft = DSSFlowVersion.objects.create(
            code="other-purpose",
            title="Other draft",
            version="1",
            operating_mode="DEMONSTRATION",
            source=self.source,
        )
        other_outcome = DSSOutcome.objects.create(
            flow=draft,
            code="other",
            title="Other",
            instruction="Synthetic test.",
            category="PREPARE",
            source=self.source,
        )
        for operation in (
            lambda: DSSOption.objects.filter(pk=self.option.pk).update(outcome=other_outcome),
            lambda: DSSContentBlock.objects.filter(pk=self.personal.pk).update(
                outcome=other_outcome
            ),
            lambda: DSSQuestion.objects.filter(pk=self.question.pk).update(flow=draft),
            lambda: DSSOutcome.objects.filter(pk=self.outcome.pk).update(flow=draft),
        ):
            with self.assertRaises(ValidationError):
                operation()
        self.question.flow = draft
        with self.assertRaises(ValidationError):
            self.question.save()
        self.outcome.flow = draft
        with self.assertRaises(ValidationError):
            self.outcome.save()
        self.assertEqual(DSSQuestion.objects.get(pk=self.question.pk).flow_id, self.flow.pk)
        self.assertEqual(DSSOutcome.objects.get(pk=self.outcome.pk).flow_id, self.flow.pk)

    def test_linked_guidance_is_frozen_with_reviewed_graph_but_can_be_withdrawn(self):
        item = GuidanceItem.objects.create(
            susceptibility_level=self.level,
            title="Synthetic library action",
            instruction="Original synthetic action.",
            category="PREPARE",
            source=self.source,
            status="DEMONSTRATION",
            workflow_status="PUBLISHED",
            is_enabled=True,
        )
        self.outcome.guidance_item = item
        self.outcome.save()
        self.flow.refresh_from_db()
        previous_revision = self.flow.updated_at
        item.instruction = "Revised synthetic action before review."
        item.save()
        self.flow.refresh_from_db()
        self.assertGreater(self.flow.updated_at, previous_revision)
        self.permit("review_dssflowversion", "publish_dssflowversion")
        self.flow = submit_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        item.instruction = "Unreviewed silent replacement."
        for operation in (
            lambda: item.save(),
            lambda: GuidanceItem.objects.filter(pk=item.pk).update(instruction=item.instruction),
            lambda: GuidanceItem.objects.bulk_update([item], ["instruction"]),
            lambda: GuidanceItem.objects.bulk_create(
                [GuidanceItem(pk=item.pk, title="Replacement")],
                update_conflicts=True,
                update_fields=["title"],
                unique_fields=["pk"],
            ),
        ):
            with self.assertRaises(ValidationError):
                with transaction.atomic():
                    operation()
        item.refresh_from_db()
        self.flow = publish_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        item.title = "Unreviewed new title"
        with self.assertRaises(ValidationError):
            item.save()
        item.refresh_from_db()
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        readonly = admin.site._registry[GuidanceItem].get_readonly_fields(request, item)
        self.assertIn("instruction", readonly)
        self.assertIn("source", readonly)
        item.workflow_status = "APPROVED"
        item.is_enabled = False
        item.save(update_fields=("workflow_status", "is_enabled", "updated_at"))
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION")

    def test_clone_does_not_copy_or_allow_erasing_publication_history(self):
        self.publish()
        self.permit("add_dssflowversion", "change_dssflowversion")
        clone = clone_dss_flow(flow_id=self.flow.pk, version="next", actor=self.actor)
        self.assertIsNone(clone.published_at)
        self.assertIsNone(clone.reviewed_on)
        published_at = self.flow.published_at
        self.flow.published_at = None
        with self.assertRaises(ValidationError):
            self.flow.save()
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.published_at, published_at)

    def test_conflict_upserts_cannot_replace_versioned_graph_records(self):
        self.publish()
        for model, fields, conflict in (
            (
                DSSFlowVersion,
                {"code": self.flow.code, "version": self.flow.version},
                ["code", "version"],
            ),
            (DSSQuestion, {"flow": self.flow, "code": self.question.code}, ["flow", "code"]),
        ):
            with self.assertRaises(ValidationError):
                model.objects.bulk_create(
                    [model(**fields)],
                    update_conflicts=True,
                    update_fields=["title" if model is DSSFlowVersion else "prompt"],
                    unique_fields=conflict,
                )
        self.assertEqual(DSSFlowVersion.objects.get(pk=self.flow.pk).title, self.flow.title)

    def test_retirement_preserves_frozen_history_and_removes_public_selection(self):
        self.publish()
        published_at = self.flow.published_at
        retired = retire_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        self.assertEqual(retired.published_at, published_at)
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION")
        for operation in (lambda: retired.delete(), lambda: self.common.save()):
            with self.assertRaises(ValidationError):
                operation()
        retired.workflow_status = "DRAFT"
        with self.assertRaises(ValidationError):
            retired.save()

    def test_permissions_stale_transitions_and_logs_record_only_successful_actions(self):
        with self.assertRaises(PermissionDenied):
            submit_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        self.permit("review_dssflowversion")
        stale = self.flow.updated_at
        self.flow.title = "Revised draft title"
        self.flow.save()
        with self.assertRaisesMessage(ValidationError, "changed after"):
            submit_dss_flow(flow_id=self.flow.pk, actor=self.actor, expected_updated_at=stale)
        reviewed = submit_dss_flow(
            flow_id=self.flow.pk,
            actor=self.actor,
            expected_updated_at=self.flow.updated_at.isoformat(),
        )
        with self.assertRaises(PermissionDenied):
            publish_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        self.permit("publish_dssflowversion")
        publish_dss_flow(
            flow_id=self.flow.pk,
            actor=self.actor,
            expected_updated_at=reviewed.updated_at,
        )
        self.assertEqual(LogEntry.objects.filter(user=self.actor).count(), 2)
        self.assertNotIn(
            self.common.body, str(list(LogEntry.objects.values_list("change_message")))
        )

    def test_child_and_association_edits_advance_parent_revision_token(self):
        self.flow.refresh_from_db()
        before = self.flow.updated_at
        self.common.body = "Draft edited through another authorized surface"
        self.common.save()
        self.flow.refresh_from_db()
        self.assertGreater(self.flow.updated_at, before)
        after_child = self.flow.updated_at
        DSSContentBlock.objects.filter(pk=self.common.pk).update(body="Draft bulk edit")
        self.flow.refresh_from_db()
        self.assertGreater(self.flow.updated_at, after_child)
        before_levels = self.flow.updated_at
        self.flow.susceptibility_levels.clear()
        self.flow.refresh_from_db()
        self.assertGreater(self.flow.updated_at, before_levels)
        self.flow.susceptibility_levels.add(self.level)
        self.permit("review_dssflowversion")
        with self.assertRaisesMessage(ValidationError, "changed after"):
            submit_dss_flow(flow_id=self.flow.pk, actor=self.actor, expected_updated_at=before)

    def test_clone_is_complete_new_draft_and_original_stays_append_only(self):
        self.publish()
        self.permit("add_dssflowversion", "change_dssflowversion")
        clone = clone_dss_flow(
            flow_id=self.flow.pk,
            version="test-2",
            actor=self.actor,
            expected_updated_at=self.flow.updated_at,
        )
        self.assertEqual(clone.workflow_status, "DRAFT")
        self.assertIsNone(clone.published_at)
        self.assertEqual(clone.source, self.flow.source)
        self.assertEqual(clone.susceptibility_levels.get(), self.level)
        self.assertEqual(clone.content_blocks.count(), 2)
        self.assertNotEqual(clone.questions.get().pk, self.question.pk)
        option = clone.questions.get().options.get()
        self.assertEqual(option.outcome.flow, clone)
        self.assertEqual(clone.content_blocks.get(outcome__isnull=False).outcome, option.outcome)
        validate_dss_flow(clone)
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.workflow_status, "PUBLISHED")
        self.assertEqual(LogEntry.objects.filter(action_flag=1).count(), 1)

    def test_linked_guidance_must_be_published_eligible_and_keeps_history(self):
        guidance = GuidanceItem.objects.create(
            susceptibility_level=self.level,
            source=self.source,
            title="Reusable draft",
            instruction="Synthetic library instruction",
            category="PREPARE",
        )
        self.outcome.guidance_item = guidance
        self.outcome.save()
        with self.assertRaisesMessage(ValidationError, "ineligible assessment guidance"):
            validate_dss_flow(self.flow)
        guidance.workflow_status = "PUBLISHED"
        guidance.is_enabled = True
        guidance.save()
        self.publish()
        guidance.is_enabled = False
        guidance.workflow_status = "APPROVED"
        guidance.save()
        with self.assertRaises(GuidanceSelectionError):
            select_dss_flow(susceptibility_code="HIGH", mode="DEMONSTRATION")
        with self.assertRaises(ProtectedError):
            guidance.delete()

    def test_board_reference_cannot_be_presented_as_susceptibility(self):
        with self.assertRaisesMessage(ValidationError, "staff-only"):
            self.block(reference_stage="YELLOW", audience="RESIDENT")

    def test_channel_urls_require_https_verified_reviewed_public_source(self):
        for url in ("http://example.gov.ph", "https://example.gov.ph"):
            with self.assertRaises(ValidationError):
                self.block(content_type="OFFICIAL_CHANNEL", public_url=url)
        approved = DataSource.objects.create(
            name="Test public source",
            source_type="PUBLICATION",
            status="APPROVED",
            is_publicly_releasable=True,
            reviewed_on=timezone.localdate(),
        )
        block = self.block(
            content_type="OFFICIAL_CHANNEL",
            public_url="https://example.gov.ph/channel",
            url_verified_on=timezone.localdate(),
            source=approved,
            data_status="APPROVED",
        )
        preview = serialize_dss_preview(self.flow)
        self.assertIn(block.public_url, str(preview))
        approved.is_publicly_releasable = False
        approved.save()
        self.assertNotIn(block.public_url, str(serialize_dss_preview(self.flow)))

    def test_api_is_stateless_and_retirement_returns_truthful_unavailable_response(self):
        self.publish()
        client = APIClient()
        start_url = "/api/v1/dss/flows/start/?mode=demonstration&susceptibility_level=HIGH"
        initial = client.get(start_url)
        answer = client.post(
            f"/api/v1/dss/flows/preparedness/{self.flow.version}/answer/",
            {
                "mode": "demonstration",
                "susceptibility_level": "HIGH",
                "question_code": "support",
                "option_code": "review",
            },
            format="json",
        )
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(answer.status_code, 200)
        self.assertFalse(answer.data["history_persisted"])
        self.assertEqual(client.get(start_url).data["question"]["code"], "support")
        retire_dss_flow(flow_id=self.flow.pk, actor=self.actor)
        unavailable = client.get(start_url)
        self.assertEqual(unavailable.status_code, 400)
        self.assertIn("No published", str(unavailable.data))

    def test_technical_admin_published_records_allow_view_but_not_change_or_delete(self):
        self.publish()
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            email="technical@example.com",
            password="Technical-Test-483!",
        )
        for obj in (self.flow, self.question, self.option, self.outcome, self.common):
            registered = admin.site._registry[type(obj)]
            self.assertTrue(registered.has_view_permission(request, obj))
            self.assertFalse(registered.has_change_permission(request, obj))
            self.assertFalse(registered.has_delete_permission(request, obj))
