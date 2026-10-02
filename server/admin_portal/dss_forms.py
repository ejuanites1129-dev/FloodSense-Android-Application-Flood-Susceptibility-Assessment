"""Ordered, accessible editors over the canonical structured DSS records."""

from django import forms
from dss.models import DSSContentBlock, DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion
from provenance.models import DataSource, PublicationStatus


class DraftEditorForm(forms.ModelForm):
    expected_updated_at = forms.DateTimeField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, flow=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.flow = flow
        if flow:
            self.initial["expected_updated_at"] = flow.updated_at.isoformat()
        if "source" in self.fields:
            self.fields["source"].queryset = DataSource.objects.exclude(
                status__in=(PublicationStatus.RESTRICTED, PublicationStatus.RETIRED)
            )
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 4


class StructuredFlowForm(DraftEditorForm):
    class Meta:
        model = DSSFlowVersion
        fields = (
            "code",
            "title",
            "version",
            "operating_mode",
            "susceptibility_levels",
            "source",
            "data_status",
            "effective_date",
            "source_locator",
            "attribution",
            "limitations",
            "expires_on",
        )
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
        }


class StructuredQuestionForm(DraftEditorForm):
    class Meta:
        model = DSSQuestion
        fields = ("code", "prompt", "explanatory_text", "display_order", "is_start")


class StructuredOutcomeForm(DraftEditorForm):
    class Meta:
        model = DSSOutcome
        fields = ("code", "title", "instruction", "category", "source", "warning", "guidance_item")


class StructuredOptionForm(DraftEditorForm):
    class Meta:
        model = DSSOption
        fields = ("code", "label", "supporting_text", "display_order", "next_question", "outcome")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["next_question"].queryset = self.flow.questions.all()
        self.fields["outcome"].queryset = self.flow.outcomes.all()


class StructuredBlockForm(DraftEditorForm):
    class Meta:
        model = DSSContentBlock
        fields = (
            "outcome",
            "title",
            "body",
            "phase",
            "content_type",
            "audience",
            "reference_stage",
            "display_order",
            "source",
            "data_status",
            "source_locator",
            "attribution",
            "limitations",
            "effective_date",
            "expires_on",
            "public_url",
            "url_verified_on",
        )
        widgets = {
            "effective_date": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
            "url_verified_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["outcome"].queryset = self.flow.outcomes.all()
        self.fields[
            "outcome"
        ].help_text = "Leave empty for content shared by every household outcome."
        self.fields[
            "reference_stage"
        ].help_text = (
            "Board reference only, restricted to staff. Never a mapping from susceptibility."
        )
        self.fields[
            "public_url"
        ].help_text = (
            "Verified public HTTPS official channel only; leave unverified contacts empty."
        )


class StructuredTransitionForm(forms.Form):
    expected_updated_at = forms.DateTimeField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(label="I confirm this workflow action.")


class StructuredCloneForm(StructuredTransitionForm):
    version = forms.SlugField(max_length=40, label="New draft version")
