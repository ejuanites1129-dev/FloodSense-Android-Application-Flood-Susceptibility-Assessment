from django import forms
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from dss.models import GuidanceItem
from evacuation.models import EvacuationCenter
from expert.models import ScenarioOption, SusceptibilityLevel
from provenance.models import DataSource, PublicationStatus


class MapDataFilterForm(forms.Form):
    status = forms.ChoiceField(
        label="Record status",
        required=False,
        choices=[
            ("", "All reviewable statuses"),
            (PublicationStatus.PENDING_VALIDATION, PublicationStatus.PENDING_VALIDATION.label),
            (PublicationStatus.DEMONSTRATION, PublicationStatus.DEMONSTRATION.label),
        ],
    )


class RainfallReferenceFilterForm(forms.Form):
    q = forms.CharField(
        label="Search references",
        required=False,
        max_length=120,
        widget=forms.SearchInput(attrs={"placeholder": "Label, code, unit, or source"}),
    )
    category = forms.ChoiceField(
        label="Category",
        required=False,
        choices=[("", "All categories"), *ScenarioOption.Category.choices],
    )
    status = forms.ChoiceField(
        label="Validation status",
        required=False,
        choices=[("", "All statuses"), *PublicationStatus.choices],
    )


class EvacuationCenterFilterForm(forms.Form):
    q = forms.CharField(
        label="Search centers",
        required=False,
        max_length=140,
        widget=forms.SearchInput(attrs={"placeholder": "Name, address, area, or source"}),
    )
    verification_status = forms.ChoiceField(
        label="Verification status",
        required=False,
        choices=[("", "All verification states"), *EvacuationCenter.VerificationStatus.choices],
    )


class EvacuationCenterForm(forms.ModelForm):
    duplicate_review_confirmed = forms.BooleanField(
        label=(
            "I reviewed the possible duplicate records and confirm this draft should "
            "remain a separate record."
        ),
        required=False,
    )

    class Meta:
        model = EvacuationCenter
        fields = (
            "name",
            "address",
            "geographic_area",
            "latitude",
            "longitude",
            "contact_information",
            "source",
            "publication_status",
            "notes",
            "limitations",
        )
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
            "limitations": forms.Textarea(attrs={"rows": 4}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate_warnings = []
        self.fields["geographic_area"].help_text = (
            "Assign the supported administrative area when known. A missing or unsupported "
            "association keeps the record out of resident results; association does not "
            "verify the facility, assign flood susceptibility, or establish route safety."
        )
        self.fields["contact_information"].help_text = (
            "Optional. Add only contact details authorized for this staff record; "
            "this field is never returned by the resident nearest-center API."
        )
        self.fields[
            "limitations"
        ].help_text = "Record public-facing caveats required to interpret this center safely."
        self.fields["source"].queryset = DataSource.objects.exclude(
            status__in=(PublicationStatus.RESTRICTED, PublicationStatus.RETIRED)
        ).order_by("name", "id")
        self.fields["publication_status"].choices = [
            choice
            for choice in PublicationStatus.choices
            if choice[0] in (PublicationStatus.DEMONSTRATION, PublicationStatus.PENDING_VALIDATION)
        ]

    @staticmethod
    def _reject_control_characters(value):
        if value and any(ord(char) < 32 and char not in "\n\t\r" for char in value):
            raise forms.ValidationError("Remove unsupported control characters.")
        return value

    def clean_name(self):
        return self._reject_control_characters(self.cleaned_data["name"])

    def clean_address(self):
        return self._reject_control_characters(self.cleaned_data["address"])

    def clean_contact_information(self):
        return self._reject_control_characters(self.cleaned_data["contact_information"])

    def clean_limitations(self):
        return self._reject_control_characters(self.cleaned_data["limitations"])

    def clean_notes(self):
        return self._reject_control_characters(self.cleaned_data["notes"])

    def clean(self):
        cleaned = super().clean()
        if self._errors:
            return cleaned
        name = cleaned.get("name")
        latitude = cleaned.get("latitude")
        longitude = cleaned.get("longitude")
        if not name and (latitude is None or longitude is None):
            return cleaned

        candidates = EvacuationCenter.objects.select_related("geographic_area").all()
        if self.instance.pk:
            candidates = candidates.exclude(pk=self.instance.pk)

        matches = {}
        if name:
            normalized_name = name.strip().lower()
            for center in candidates.annotate(normalized_name=Lower(Trim("name"))).filter(
                normalized_name=normalized_name
            ):
                matches.setdefault(center.pk, {"center": center, "reasons": []})["reasons"].append(
                    "same normalized name"
                )
        if latitude is not None and longitude is not None:
            for center in candidates.filter(latitude=latitude, longitude=longitude):
                matches.setdefault(center.pk, {"center": center, "reasons": []})["reasons"].append(
                    "same exact coordinates"
                )

        self.duplicate_warnings = [
            {
                "name": item["center"].name,
                "area": (
                    item["center"].geographic_area.name
                    if item["center"].geographic_area_id
                    else "No area assigned"
                ),
                "reasons": tuple(item["reasons"]),
            }
            for _, item in sorted(matches.items())
        ]
        if self.duplicate_warnings and not cleaned.get("duplicate_review_confirmed"):
            self.add_error(
                "duplicate_review_confirmed",
                "Review the possible matches before saving this separate draft.",
            )
        return cleaned


class EvacuationTransitionForm(forms.Form):
    expected_status = forms.CharField(widget=forms.HiddenInput)
    verified_on = forms.DateField(
        label="Verification date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    capacity = forms.IntegerField(
        label="Verified capacity",
        required=False,
        min_value=1,
        help_text="Optional. Record only a capacity documented by the approved source.",
    )
    confirm = forms.BooleanField(
        label="I understand that this changes the verification state.",
        required=True,
    )

    def __init__(self, *args, action: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.action = action
        if action != "verify":
            self.fields["verified_on"].widget = forms.HiddenInput()
            self.fields["capacity"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        if self.action == "verify" and not cleaned.get("verified_on"):
            self.add_error("verified_on", "A verification date is required.")
        elif self.action == "verify" and cleaned["verified_on"] > timezone.localdate():
            self.add_error("verified_on", "The verification date cannot be in the future.")
        return cleaned


class DataSourceFilterForm(forms.Form):
    q = forms.CharField(
        label="Search sources",
        required=False,
        max_length=140,
        widget=forms.SearchInput(attrs={"placeholder": "Title, custodian, or organization"}),
    )
    source_type = forms.ChoiceField(
        label="Source type",
        required=False,
        choices=[("", "All source types"), *DataSource.SourceType.choices],
    )
    status = forms.ChoiceField(
        label="Review status",
        required=False,
        choices=[("", "All statuses"), *PublicationStatus.choices],
    )


class DataSourceForm(forms.ModelForm):
    class Meta:
        model = DataSource
        fields = (
            "name",
            "organization",
            "custodian",
            "source_type",
            "coverage_description",
            "record_period_start",
            "record_period_end",
            "received_or_created_on",
            "version",
            "permitted_use",
            "processing_notes",
            "limitations",
            "citation_url",
            "notes",
        )
        widgets = {
            "record_period_start": forms.DateInput(attrs={"type": "date"}),
            "record_period_end": forms.DateInput(attrs={"type": "date"}),
            "received_or_created_on": forms.DateInput(attrs={"type": "date"}),
            "coverage_description": forms.Textarea(attrs={"rows": 3}),
            "permitted_use": forms.Textarea(attrs={"rows": 3}),
            "processing_notes": forms.Textarea(attrs={"rows": 3}),
            "limitations": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_type"].choices = [
            choice
            for choice in DataSource.SourceType.choices
            if choice[0] != DataSource.SourceType.DEMONSTRATION
        ]


class DataSourceTransitionForm(forms.Form):
    expected_status = forms.CharField(widget=forms.HiddenInput)
    expected_public = forms.BooleanField(required=False, widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        label="I understand that this changes source review or release status.",
        required=True,
    )


class AuditFilterForm(forms.Form):
    actor = forms.ModelChoiceField(
        label="Administrator",
        required=False,
        empty_label="All administrators",
        queryset=get_user_model().objects.none(),
    )
    module = forms.ChoiceField(label="Module", required=False, choices=())
    action = forms.ChoiceField(
        label="Action",
        required=False,
        choices=(
            ("", "All actions"),
            (str(ADDITION), "Created"),
            (str(CHANGE), "Changed"),
            (str(DELETION), "Deleted"),
        ),
    )
    date_from = forms.DateField(
        label="From",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="To",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, module_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["actor"].queryset = (
            get_user_model().objects.filter(is_staff=True).order_by("display_name", "email")
        )
        self.fields["module"].choices = [("", "All modules"), *module_choices]

    def clean(self):
        cleaned = super().clean()
        if (
            cleaned.get("date_from")
            and cleaned.get("date_to")
            and cleaned["date_from"] > cleaned["date_to"]
        ):
            self.add_error("date_to", "The end date cannot precede the start date.")
        return cleaned


class GuidanceFilterForm(forms.Form):
    q = forms.CharField(
        label="Search guidance",
        required=False,
        max_length=160,
        widget=forms.SearchInput(
            attrs={"placeholder": "Title, instruction, source, or attribution"}
        ),
    )
    category = forms.ChoiceField(
        label="Category",
        required=False,
        choices=[("", "All categories"), *GuidanceItem.Category.choices],
    )
    workflow_status = forms.ChoiceField(
        label="Workflow status",
        required=False,
        choices=[("", "All workflow statuses"), *GuidanceItem.WorkflowStatus.choices],
    )
    review_attention = forms.ChoiceField(
        label="Review attention",
        required=False,
        choices=[("", "All records"), ("needs_review", "Needs review")],
    )
    susceptibility_level = forms.ModelChoiceField(
        label="Susceptibility result",
        required=False,
        empty_label="All susceptibility results",
        queryset=SusceptibilityLevel.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["susceptibility_level"].queryset = SusceptibilityLevel.objects.order_by(
            "display_order", "id"
        )


class GuidanceItemForm(forms.ModelForm):
    class Meta:
        model = GuidanceItem
        fields = (
            "susceptibility_level",
            "title",
            "instruction",
            "category",
            "source",
            "attribution",
            "status",
            "display_order",
        )
        widgets = {
            "instruction": forms.Textarea(attrs={"rows": 6}),
            "attribution": forms.Textarea(attrs={"rows": 3}),
            "display_order": forms.NumberInput(attrs={"min": 0, "max": 32767}),
        }
        help_texts = {
            "status": (
                "This describes data provenance. It is separate from the content "
                "review and publication workflow."
            ),
            "display_order": (
                "Use 0 through 32767. Equal values are resolved deterministically by record ID."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = DataSource.objects.filter(
            status__in=(
                PublicationStatus.DEMONSTRATION,
                PublicationStatus.PENDING_VALIDATION,
                PublicationStatus.APPROVED,
            )
        ).order_by("name", "id")
        self.fields["susceptibility_level"].queryset = (
            SusceptibilityLevel.objects.filter(
                status__in=(
                    PublicationStatus.DEMONSTRATION,
                    PublicationStatus.PENDING_VALIDATION,
                    PublicationStatus.APPROVED,
                )
            )
            .select_related("source")
            .order_by("display_order", "id")
        )
        self.fields["status"].choices = [
            choice
            for choice in PublicationStatus.choices
            if choice[0]
            in (
                PublicationStatus.DEMONSTRATION,
                PublicationStatus.PENDING_VALIDATION,
                PublicationStatus.APPROVED,
            )
        ]


class GuidanceTransitionForm(forms.Form):
    expected_status = forms.CharField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        label="I understand that this changes the content workflow state.",
        required=True,
    )


class SettingsInventoryFilterForm(forms.Form):
    """GET filters only; this form cannot save or change scenario values."""

    q = forms.CharField(
        label="Search references",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"type": "search", "placeholder": "Label or code"}),
    )
    category = forms.ChoiceField(
        label="Category",
        required=False,
        choices=[("", "All categories"), *ScenarioOption.Category.choices],
    )


class StaffAuthenticationForm(AuthenticationForm):
    """Authenticate active staff without exposing why a login was rejected."""

    username = forms.EmailField(
        label="Work email",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "username",
                "autofocus": True,
                "placeholder": "name@example.com",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
    )
    remember_device = forms.BooleanField(
        label="Remember this device",
        required=False,
        initial=False,
    )

    error_messages = {
        "invalid_login": ("The sign-in details are incorrect or this account is not authorized."),
        "inactive": "This account is unavailable.",
        "not_staff": ("The sign-in details are incorrect or this account is not authorized."),
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                self.error_messages["not_staff"],
                code="not_staff",
            )
