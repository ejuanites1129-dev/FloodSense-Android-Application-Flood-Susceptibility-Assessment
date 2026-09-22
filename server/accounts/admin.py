from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied, ValidationError

from .models import (
    AccountDeletionRequest,
    EmailVerificationChallenge,
    ExternalIdentity,
    LegalAcceptance,
    LegalDocumentSection,
    LegalDocumentVersion,
    OnboardingAcknowledgement,
    OnboardingVersion,
    ResidentPreference,
    User,
)
from .workflow import publish_legal, publish_onboarding, submit_legal_for_review


@admin.register(User)
class FloodSenseUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "resident_username",
        "email_verified_at",
        "is_staff",
        "is_active",
    )
    search_fields = ("email", "resident_username", "display_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Resident profile",
            {
                "fields": (
                    "resident_username",
                    "display_name",
                    "email_verified_at",
                    "home_barangay",
                    "disclaimer_version_accepted",
                    "disclaimer_accepted_at",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "resident_username",
                    "display_name",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


class LegalDocumentSectionInline(admin.StackedInline):
    model = LegalDocumentSection
    extra = 0

    def has_add_permission(self, request, obj=None):
        return obj is None or obj.status == LegalDocumentVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.status == LegalDocumentVersion.Status.DRAFT

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.status == LegalDocumentVersion.Status.DRAFT


@admin.register(LegalDocumentVersion)
class LegalDocumentVersionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "document_type",
        "version",
        "status",
        "requires_acceptance",
        "effective_date",
    )
    list_filter = ("document_type", "status", "requires_acceptance")
    search_fields = ("title", "version", "summary")
    inlines = (LegalDocumentSectionInline,)
    readonly_fields = ("status", "published_at", "reviewed_by", "created_at", "updated_at")
    actions = ("submit_for_review", "publish_reviewed")

    @admin.action(description="Submit selected draft for review")
    def submit_for_review(self, request, queryset):
        for document in queryset:
            try:
                submit_legal_for_review(document_id=document.pk, actor=request.user)
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")

    @admin.action(description="Publish selected reviewed legal version")
    def publish_reviewed(self, request, queryset):
        for document in queryset:
            try:
                publish_legal(document_id=document.pk, actor=request.user)
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")


@admin.register(OnboardingVersion)
class OnboardingVersionAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "status", "published_at")
    list_filter = ("status",)
    readonly_fields = ("status", "published_at", "created_at")
    actions = ("publish_selected",)

    @admin.action(description="Publish selected onboarding version")
    def publish_selected(self, request, queryset):
        for version in queryset:
            try:
                publish_onboarding(version_id=version.pk, actor=request.user)
            except (PermissionDenied, ValidationError) as error:
                self.message_user(request, str(error), level="ERROR")


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "requested_at",
        "scheduled_for",
        "resolved_at",
    )
    list_filter = ("status",)
    readonly_fields = ("user", "requested_at", "scheduled_for", "resolved_at")


@admin.register(ExternalIdentity, LegalAcceptance, OnboardingAcknowledgement, ResidentPreference)
class ResidentRelatedAdmin(admin.ModelAdmin):
    readonly_fields = ("id",)


@admin.register(EmailVerificationChallenge)
class EmailVerificationChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    readonly_fields = ("user", "token_digest", "created_at", "expires_at", "used_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
