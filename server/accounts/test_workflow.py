from django.contrib.admin import site
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from expert.admin import ExpertRuleAdmin, ExpertRuleConditionAdmin, RuleSetAdmin
from expert.models import ExpertRule, ExpertRuleCondition, RuleSet

from .models import (
    LegalDocumentSection,
    LegalDocumentVersion,
    OnboardingVersion,
    User,
)
from .workflow import publish_legal, publish_onboarding, submit_legal_for_review


class ContentGovernanceTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            email="reviewer@example.com",
            password="Reviewer-Test-Password-482!",
            display_name="Reviewer",
            is_staff=True,
        )
        self.document = LegalDocumentVersion.objects.create(
            document_type=LegalDocumentVersion.DocumentType.TERMS,
            version="review-test",
            title="Review test",
            summary="Test only.",
            effective_date=timezone.localdate(),
        )
        LegalDocumentSection.objects.create(
            document_version=self.document,
            section_key="scope",
            title="Scope",
            short_summary="Test scope.",
            body="Test content only.",
            display_order=1,
        )

    def _permission(self, codename):
        self.actor.user_permissions.add(Permission.objects.get(codename=codename))
        self.actor = User.objects.get(pk=self.actor.pk)

    def test_legal_review_and_publish_require_separate_permissions_and_audit(self):
        with self.assertRaises(PermissionDenied):
            submit_legal_for_review(document_id=self.document.pk, actor=self.actor)
        self._permission("change_legaldocumentversion")
        submitted = submit_legal_for_review(
            document_id=self.document.pk, actor=self.actor
        )
        self.assertEqual(submitted.status, LegalDocumentVersion.Status.REVIEW)
        with self.assertRaises(PermissionDenied):
            publish_legal(document_id=self.document.pk, actor=self.actor)
        self._permission("publish_legaldocumentversion")
        published = publish_legal(document_id=self.document.pk, actor=self.actor)
        self.assertEqual(published.status, LegalDocumentVersion.Status.PUBLISHED)
        self.assertEqual(published.reviewed_by, self.actor)
        self.assertEqual(LogEntry.objects.count(), 2)

    def test_published_legal_text_is_append_only(self):
        self._permission("change_legaldocumentversion")
        submit_legal_for_review(document_id=self.document.pk, actor=self.actor)
        self._permission("publish_legaldocumentversion")
        published = publish_legal(document_id=self.document.pk, actor=self.actor)
        published.summary = "Changed after publication."
        with self.assertRaises(ValidationError):
            published.full_clean()
        section = published.sections.get()
        section.body = "Changed."
        with self.assertRaises(ValidationError):
            section.full_clean()

    def test_onboarding_publication_requires_permission(self):
        version = OnboardingVersion.objects.create(version="review-test")
        with self.assertRaises(PermissionDenied):
            publish_onboarding(version_id=version.pk, actor=self.actor)
        self._permission("publish_onboardingversion")
        published = publish_onboarding(version_id=version.pk, actor=self.actor)
        self.assertEqual(published.status, OnboardingVersion.Status.PUBLISHED)

    def test_raw_expert_configuration_is_view_only_in_technical_admin(self):
        request = RequestFactory().get("/admin/")
        request.user = self.actor
        for model, admin_class in (
            (RuleSet, RuleSetAdmin),
            (ExpertRule, ExpertRuleAdmin),
            (ExpertRuleCondition, ExpertRuleConditionAdmin),
        ):
            model_admin = admin_class(model, site)
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
