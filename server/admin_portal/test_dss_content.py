from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from dss.models import GuidanceItem
from expert.models import SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus


class GuidanceManagementTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.manager = user_model.objects.create_user(
            email="guidance-manager@example.com",
            display_name="Guidance Manager",
            password="Strong-test-password-123",
            is_staff=True,
        )
        permissions = Permission.objects.filter(
            content_type__app_label="dss",
            codename__in=(
                "view_guidanceitem",
                "add_guidanceitem",
                "change_guidanceitem",
                "approve_guidanceitem",
                "publish_guidanceitem",
            ),
        )
        self.manager.user_permissions.set(permissions)
        self.viewer = user_model.objects.create_user(
            email="guidance-viewer@example.com",
            display_name="Guidance Viewer",
            password="Strong-test-password-123",
            is_staff=True,
        )
        self.viewer.user_permissions.add(
            Permission.objects.get(content_type__app_label="dss", codename="view_guidanceitem")
        )
        self.staff_without_permission = user_model.objects.create_user(
            email="staff-no-guidance@example.com",
            display_name="Other Staff",
            password="Strong-test-password-123",
            is_staff=True,
        )
        self.source = DataSource.objects.create(
            name="TEST DEMONSTRATION SOURCE - NOT OFFICIAL",
            source_type=DataSource.SourceType.DEMONSTRATION,
            permitted_use="Isolated automated testing only.",
            status=PublicationStatus.DEMONSTRATION,
        )
        self.level = SusceptibilityLevel.objects.create(
            code=SusceptibilityLevel.Code.LOW,
            label="Low",
            display_order=1,
            map_color="#2E9E5B",
            definition="Test-only demonstration classification.",
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            is_enabled=True,
        )
        self.item = GuidanceItem.objects.create(
            susceptibility_level=self.level,
            title="Review test supplies",
            instruction="Review fictional test supplies for this isolated fixture.",
            category=GuidanceItem.Category.PREPARE,
            display_order=10,
            source=self.source,
            attribution="Automated test fixture",
            status=PublicationStatus.DEMONSTRATION,
        )

    def _form_data(self, **overrides):
        values = {
            "susceptibility_level": self.level.pk,
            "title": "New test preparedness content",
            "instruction": "Review this fictional instruction during an automated test.",
            "category": GuidanceItem.Category.MONITOR,
            "source": self.source.pk,
            "attribution": "Automated test fixture",
            "status": PublicationStatus.DEMONSTRATION,
            "display_order": 20,
        }
        values.update(overrides)
        return values

    def test_list_requires_staff_and_explicit_view_permission(self):
        url = reverse("admin_portal:dss-content")
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('admin_portal:login')}?next={url}",
            fetch_redirect_response=False,
        )

        self.client.force_login(self.staff_without_permission)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.viewer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.title)
        self.assertNotContains(response, "Create guidance")

    def test_search_and_filters_use_existing_fields_and_truthful_empty_state(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse("admin_portal:dss-content"),
            {
                "q": "supplies",
                "category": GuidanceItem.Category.PREPARE,
                "workflow_status": GuidanceItem.WorkflowStatus.DRAFT,
                "susceptibility_level": self.level.pk,
            },
        )
        self.assertContains(response, self.item.title)

        response = self.client.get(
            reverse("admin_portal:dss-content"), {"q": "no matching content"}
        )
        self.assertContains(response, "No guidance items match this view")
        self.assertEqual(GuidanceItem.objects.count(), 1)

    def test_review_attention_filter_matches_dashboard_union_without_duplicates(self):
        self.client.force_login(self.manager)
        self.item.status = PublicationStatus.PENDING_VALIDATION
        self.item.workflow_status = GuidanceItem.WorkflowStatus.IN_REVIEW
        self.item.save(update_fields=("status", "workflow_status"))
        GuidanceItem.objects.create(
            susceptibility_level=self.level,
            title="Not under review",
            instruction="Synthetic non-review fixture.",
            category=GuidanceItem.Category.PREPARE,
            source=self.source,
            status=PublicationStatus.DEMONSTRATION,
            workflow_status=GuidanceItem.WorkflowStatus.DRAFT,
        )

        response = self.client.get(
            reverse("admin_portal:dss-content"),
            {"review_attention": "needs_review"},
        )

        self.assertEqual(response.context["guidance_page"].paginator.count, 1)
        self.assertContains(response, self.item.title)
        self.assertNotContains(response, "Not under review")

    def test_create_uses_server_validation_preserves_input_and_logs_addition(self):
        self.client.force_login(self.manager)
        url = reverse("admin_portal:guidance-create")
        response = self.client.post(url, self._form_data(instruction=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New test preparedness content")
        self.assertContains(response, "This field is required")
        self.assertEqual(GuidanceItem.objects.count(), 1)

        response = self.client.post(url, self._form_data())
        self.assertRedirects(response, reverse("admin_portal:dss-content"))
        created = GuidanceItem.objects.get(title="New test preparedness content")
        self.assertEqual(created.workflow_status, GuidanceItem.WorkflowStatus.DRAFT)
        self.assertFalse(created.is_enabled)
        log = LogEntry.objects.get(object_id=str(created.pk))
        self.assertEqual(log.action_flag, ADDITION)
        self.assertNotIn(created.instruction, log.change_message)

    def test_only_drafts_can_be_edited(self):
        self.client.force_login(self.manager)
        edit_url = reverse("admin_portal:guidance-edit", args=(self.item.pk,))
        response = self.client.post(
            edit_url,
            self._form_data(title="Edited draft", display_order=5),
        )
        self.assertRedirects(response, reverse("admin_portal:dss-content"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Edited draft")

        self.item.workflow_status = GuidanceItem.WorkflowStatus.IN_REVIEW
        self.item.save(update_fields=("workflow_status",))
        response = self.client.post(edit_url, self._form_data(title="Bypass attempt"))
        self.assertRedirects(response, reverse("admin_portal:dss-content"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Edited draft")

    def test_workflow_needs_confirmation_and_separate_publish_permission(self):
        self.client.force_login(self.manager)
        submit_url = reverse("admin_portal:guidance-transition", args=(self.item.pk, "submit"))
        response = self.client.get(submit_url)
        self.assertContains(response, "Submit for review")
        self.item.refresh_from_db()
        self.assertEqual(self.item.workflow_status, GuidanceItem.WorkflowStatus.DRAFT)

        response = self.client.post(
            submit_url,
            {"expected_status": "DRAFT"},
        )
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.workflow_status, GuidanceItem.WorkflowStatus.DRAFT)

        self.client.post(
            submit_url,
            {"expected_status": "DRAFT", "confirm": "on"},
        )
        self.client.post(
            reverse("admin_portal:guidance-transition", args=(self.item.pk, "approve")),
            {"expected_status": "IN_REVIEW", "confirm": "on"},
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.workflow_status, GuidanceItem.WorkflowStatus.APPROVED)
        self.assertFalse(self.item.is_enabled)

        self.client.force_login(self.viewer)
        publish_url = reverse("admin_portal:guidance-transition", args=(self.item.pk, "publish"))
        self.assertEqual(self.client.get(publish_url).status_code, 403)

        self.client.force_login(self.manager)
        response = self.client.post(
            publish_url,
            {"expected_status": "APPROVED", "confirm": "on"},
        )
        self.assertRedirects(response, reverse("admin_portal:dss-content"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.workflow_status, GuidanceItem.WorkflowStatus.PUBLISHED)
        self.assertTrue(self.item.is_enabled)
        self.assertEqual(
            LogEntry.objects.filter(object_id=str(self.item.pk), action_flag=CHANGE).count(),
            3,
        )

    def test_publish_revalidates_source_eligibility(self):
        self.item.workflow_status = GuidanceItem.WorkflowStatus.APPROVED
        self.item.save(update_fields=("workflow_status",))
        self.source.status = PublicationStatus.RESTRICTED
        self.source.save(update_fields=("status",))
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("admin_portal:guidance-transition", args=(self.item.pk, "publish")),
            {"expected_status": "APPROVED", "confirm": "on"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "requires a demonstration source", status_code=409)
        self.item.refresh_from_db()
        self.assertEqual(self.item.workflow_status, GuidanceItem.WorkflowStatus.APPROVED)
        self.assertFalse(self.item.is_enabled)

    def test_mobile_preview_is_staff_only_and_clearly_labeled(self):
        url = reverse("admin_portal:guidance-create")
        self.client.force_login(self.manager)
        response = self.client.get(url)
        self.assertContains(response, "Mobile preview")
        self.assertContains(response, "Preview only")
        self.assertContains(response, "does not publish content")

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
