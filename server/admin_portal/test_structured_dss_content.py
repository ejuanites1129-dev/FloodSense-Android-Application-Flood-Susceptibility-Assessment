from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from dss.models import DSSContentBlock, DSSFlowVersion, DSSOutcome, GuidanceItem
from dss.services import serialize_dss_preview
from expert.models import SusceptibilityLevel
from provenance.models import DataSource


class StructuredPreparePortalTests(TestCase):
    def setUp(self):
        self.manager = self._staff(
            "manager", Permission.objects.filter(content_type__app_label="dss")
        )
        self.viewer = self._staff(
            "viewer", Permission.objects.filter(codename="view_dssflowversion")
        )
        self.editor = self._staff(
            "editor",
            Permission.objects.filter(
                content_type__app_label="dss",
                codename__startswith="change_",
            )
            | Permission.objects.filter(content_type__app_label="dss", codename__startswith="add_")
            | Permission.objects.filter(codename="view_dssflowversion"),
        )
        self.source = DataSource.objects.create(
            name="Synthetic source " + "Long reference name " * 6,
            organization="Synthetic QA custodian",
            source_type="DEMONSTRATION",
            status="DEMONSTRATION",
            notes="PRIVATE_NOTES_SHOULD_NOT_LEAK",
            permitted_use="PRIVATE_RESTRICTIONS",
        )
        self.level = SusceptibilityLevel.objects.create(
            code="HIGH",
            label="High",
            display_order=3,
            definition="Synthetic",
            map_color="#C00000",
            source=self.source,
            status="DEMONSTRATION",
            is_enabled=True,
        )
        self.client.force_login(self.manager)

    def _staff(self, name, permissions):
        user = get_user_model().objects.create_user(
            email=f"{name}-dss@example.com", is_staff=True, password="test-long-password"
        )
        user.user_permissions.set(permissions)
        return user

    def _create_flow(self):
        response = self.client.post(
            reverse("admin_portal:dss-flow-create"),
            {
                "code": "preparedness",
                "version": "portal-test-1",
                "title": "Portal canonical draft",
                "operating_mode": "DEMONSTRATION",
                "data_status": "DEMONSTRATION",
                "source": self.source.pk,
                "susceptibility_levels": [self.level.pk],
                "effective_date": timezone.localdate().isoformat(),
                "limitations": "Synthetic; pending validation.",
            },
        )
        self.assertEqual(response.status_code, 302)
        flow = DSSFlowVersion.objects.get(version="portal-test-1")
        # Build the graph through staff forms, as an ordinary editor would.
        self._node(
            flow,
            "outcome",
            {
                "code": "plan",
                "title": "Plan together",
                "instruction": "Synthetic checklist.",
                "category": "PREPARE",
                "source": self.source.pk,
                "warning": "Demonstration only.",
            },
        )
        self._node(
            flow,
            "question",
            {
                "code": "support",
                "prompt": "Do you have a support plan?",
                "display_order": 1,
                "is_start": "on",
            },
        )
        question = flow.questions.get()
        self._node(
            flow,
            "option",
            {"code": "yes", "label": "Yes", "display_order": 1, "outcome": flow.outcomes.get().pk},
            query=f"?question={question.pk}",
        )
        self._node(
            flow,
            "block",
            {
                "title": "Household plan",
                "body": "Synthetic household action " * 40,
                "phase": "BEFORE",
                "content_type": "HOUSEHOLD_ACTION",
                "audience": "RESIDENT",
                "display_order": 1,
                "source": self.source.pk,
                "data_status": "DEMONSTRATION",
                "limitations": "Not official advice.",
            },
        )
        flow.refresh_from_db()
        return flow

    def _node(self, flow, kind, data, query=""):
        flow.refresh_from_db()
        data["expected_updated_at"] = flow.updated_at.isoformat()
        response = self.client.post(
            reverse("admin_portal:dss-node-create", args=(flow.pk, kind)) + query, data
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))

    def _transition(self, flow, action, **extra):
        flow.refresh_from_db()
        return self.client.post(
            reverse("admin_portal:dss-flow-transition", args=(flow.pk, action)),
            {
                "expected_updated_at": flow.updated_at.isoformat(),
                "confirm": "on",
                **extra,
            },
        )

    def test_option_creation_requires_a_question_from_the_selected_flow(self):
        flow = self._create_flow()
        url = reverse("admin_portal:dss-node-create", args=(flow.pk, "option"))
        for query in ("", "?question=not-a-number", "?question=999999"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(url + query).status_code, 404)

    def test_reused_guidance_is_counted_once_in_both_inventories(self):
        flow = self._create_flow()
        item = GuidanceItem.objects.create(
            title="Reusable test action",
            instruction="Synthetic test action.",
            source=self.source,
            susceptibility_level=self.level,
            category="PREPARE",
        )
        outcome = flow.outcomes.get()
        outcome.guidance_item = item
        outcome.save()
        DSSOutcome.objects.create(
            flow=flow,
            code="second",
            title="Second test outcome",
            instruction="Synthetic second path.",
            category="PREPARE",
            source=self.source,
            guidance_item=item,
        )
        inventory = self.client.get(reverse("admin_portal:dss-flow-list"))
        detail = self.client.get(reverse("admin_portal:dss-flow-detail", args=(flow.pk,)))
        self.assertEqual(inventory.context["flows"][0].linked_guidance_count, 1)
        self.assertEqual(detail.context["linked_guidance_count"], 1)
        self.assertContains(detail, "Item review: Not recorded")

    def test_portal_draft_is_same_admin_record_and_only_public_after_publication(self):
        flow = self._create_flow()
        self.manager.is_superuser = True
        self.manager.save(update_fields=("is_superuser",))
        self.assertContains(
            self.client.get(reverse("admin:dss_dssflowversion_change", args=(flow.pk,))),
            "Portal canonical draft",
        )
        public_url = "/api/v1/dss/flows/start/?mode=demonstration&susceptibility_level=HIGH"
        self.assertEqual(self.client.get(public_url).status_code, 400)
        self.assertEqual(self._transition(flow, "submit").status_code, 302)
        self.assertEqual(self._transition(flow, "publish").status_code, 302)
        response = self.client.get(public_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["flow"]["version"], flow.version)
        self.assertEqual(response.json()["content_blocks"][0]["title"], "Household plan")
        self.assertNotContains(response, "PRIVATE_NOTES_SHOULD_NOT_LEAK")
        self.assertNotContains(response, "PRIVATE_RESTRICTIONS")
        self.assertGreaterEqual(LogEntry.objects.filter(user=self.manager).count(), 7)

    def test_viewer_editor_reviewer_and_publisher_have_distinct_authority(self):
        flow = self._create_flow()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("admin_portal:dss-flow-list")).status_code, 200)
        self.assertContains(
            self.client.get(reverse("admin_portal:dss-flow-detail", args=(flow.pk,))),
            "Resident-width preview",
        )
        self.assertEqual(
            self.client.get(reverse("admin_portal:dss-flow-edit", args=(flow.pk,))).status_code, 403
        )
        self.assertEqual(self._transition(flow, "submit").status_code, 403)
        self.client.force_login(self.editor)
        self.assertEqual(self._transition(flow, "publish").status_code, 403)
        self.assertEqual(self._transition(flow, "submit").status_code, 403)
        reviewer = self._staff(
            "reviewer",
            Permission.objects.filter(
                codename__in=("view_dssflowversion", "review_dssflowversion")
            ),
        )
        self.client.force_login(reviewer)
        self.assertEqual(self._transition(flow, "submit").status_code, 302)
        self.assertEqual(self._transition(flow, "publish").status_code, 403)
        publisher = self._staff(
            "publisher",
            Permission.objects.filter(
                codename__in=("view_dssflowversion", "publish_dssflowversion")
            ),
        )
        self.client.force_login(publisher)
        self.assertEqual(self._transition(flow, "publish").status_code, 302)

    def test_admin_edit_updates_same_portal_record_and_invalidates_old_transition(self):
        flow = self._create_flow()
        stale_stamp = flow.updated_at.isoformat()
        self.manager.is_superuser = True
        self.manager.save(update_fields=("is_superuser",))
        block = flow.content_blocks.get()
        response = self.client.post(
            reverse("admin:dss_dsscontentblock_change", args=(block.pk,)),
            {
                "flow": flow.pk,
                "title": "Admin revised household plan",
                "body": block.body,
                "phase": block.phase,
                "content_type": block.content_type,
                "audience": block.audience,
                "display_order": block.display_order,
                "source": self.source.pk,
                "data_status": block.data_status,
                "limitations": block.limitations,
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertContains(
            self.client.get(reverse("admin_portal:dss-flow-detail", args=(flow.pk,))),
            "Admin revised household plan",
        )
        flow.refresh_from_db()
        self.assertNotEqual(flow.updated_at.isoformat(), stale_stamp)
        response = self.client.post(
            reverse("admin_portal:dss-flow-transition", args=(flow.pk, "submit")),
            {"expected_updated_at": stale_stamp, "confirm": "on"},
        )
        self.assertEqual(response.status_code, 409)

    def test_flow_inventory_navigation_available_without_flat_guidance_permission(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("admin_portal:dss-content"))
        self.assertRedirects(response, reverse("admin_portal:dss-flow-list"))
        response = self.client.get(reverse("admin_portal:dashboard"))
        self.assertContains(response, "DSS content")

    def test_preview_uses_shared_serializer_and_keeps_staff_only_blocks_out(self):
        flow = self._create_flow()
        DSSContentBlock.objects.create(
            flow=flow,
            title="Internal board thresholds",
            body="Do not release",
            phase="ALWAYS",
            content_type="RISK_REFERENCE",
            audience="STAFF_ONLY",
            reference_stage="YELLOW",
            source=self.source,
            data_status="PENDING_VALIDATION",
        )
        response = self.client.get(reverse("admin_portal:dss-flow-preview", args=(flow.pk,)))
        self.assertEqual(response.context["structure"], serialize_dss_preview(flow))
        self.assertContains(response, "Preview only")
        self.assertNotContains(response, "Internal board thresholds")
        self.assertNotContains(response, "PRIVATE_NOTES_SHOULD_NOT_LEAK")
        self.assertEqual(
            self.client.get(reverse("admin_portal:dss-flow-detail", args=(flow.pk,))).status_code,
            200,
        )

    def test_stale_draft_and_transition_do_not_change_records(self):
        flow = self._create_flow()
        stale_stamp = flow.updated_at.isoformat()
        flow.title = "Newer title"
        flow.save()
        response = self.client.post(
            reverse("admin_portal:dss-flow-transition", args=(flow.pk, "submit")),
            {
                "expected_updated_at": stale_stamp,
                "confirm": "on",
            },
        )
        self.assertEqual(response.status_code, 409)
        flow.refresh_from_db()
        self.assertEqual(flow.workflow_status, "DRAFT")
        question = flow.questions.get()
        response = self.client.post(
            reverse("admin_portal:dss-node-edit", args=(flow.pk, "question", question.pk)),
            {
                "code": question.code,
                "prompt": "Stale replacement",
                "display_order": 1,
                "is_start": "on",
                "expected_updated_at": stale_stamp,
            },
        )
        self.assertEqual(response.status_code, 409)
        question.refresh_from_db()
        self.assertEqual(question.prompt, "Do you have a support plan?")

    def test_published_graph_requires_new_version_and_retirement_is_safe(self):
        flow = self._create_flow()
        self._transition(flow, "submit")
        self._transition(flow, "publish")
        self.assertEqual(
            self.client.get(reverse("admin_portal:dss-flow-edit", args=(flow.pk,))).status_code, 403
        )
        self.assertEqual(self._transition(flow, "clone", version="portal-test-2").status_code, 302)
        clone = DSSFlowVersion.objects.get(version="portal-test-2")
        self.assertEqual(clone.workflow_status, "DRAFT")
        self.assertEqual(clone.questions.count(), flow.questions.count())
        self.assertEqual(clone.content_blocks.count(), flow.content_blocks.count())
        self.assertEqual(self._transition(flow, "retire").status_code, 302)
        flow.refresh_from_db()
        self.assertEqual(flow.workflow_status, "RETIRED")
        self.assertTrue(flow.questions.exists())
        self.assertEqual(
            self.client.get(
                "/api/v1/dss/flows/start/?mode=demonstration&susceptibility_level=HIGH"
            ).status_code,
            400,
        )

    def test_workflow_confirmation_get_and_missing_confirmation_are_non_mutating(self):
        flow = self._create_flow()
        url = reverse("admin_portal:dss-flow-transition", args=(flow.pk, "submit"))
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"expected_updated_at": flow.updated_at.isoformat()})
        self.assertEqual(response.status_code, 200)
        flow.refresh_from_db()
        self.assertEqual(flow.workflow_status, "DRAFT")

    def test_anonymous_nonstaff_and_csrf_boundaries(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.manager)
        self.assertEqual(
            csrf_client.post(reverse("admin_portal:dss-flow-create"), {}).status_code, 403
        )
        self.client.logout()
        self.assertEqual(self.client.get(reverse("admin_portal:dss-flow-list")).status_code, 302)
        self.manager.is_staff = False
        self.manager.save(update_fields=("is_staff",))
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("admin_portal:dss-flow-list")).status_code, 403)
