"""Practical record entry, inline provenance, reviewed import and review queue."""

import csv
from collections import Counter

from core.local_testing import local_testing_enabled
from core.record_workflow import require_fresh
from django import forms
from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from dss.models import GuidanceItem
from dss.workflow import log_guidance_action, transition_guidance
from evacuation.imports import HEADERS, import_batch, stage_batch
from evacuation.models import CenterImportBatch, EvacuationCenter
from evacuation.services import (
    _public_center,
    eligible_center_candidates,
    ready_reference_barangays,
)
from geography.boundaries import is_bacoor_boundary_source
from geography.widgets import OPENLAYERS_CDN_ROOT
from provenance.models import DataSource, PublicationStatus

from .bulk_workflows import (
    LIMIT,
    MODELS,
    execute_bulk,
    permitted_actions,
    preview_bulk,
    view_permission,
)
from .forms import DataSourceForm, EvacuationCenterForm, GuidanceItemForm
from .record_workflows import require_permission, save_center, save_source
from .views import _portal_context, _selected_center_source, staff_required


class FastCenterForm(EvacuationCenterForm):
    expected_updated_at = forms.DateTimeField(required=False, widget=forms.HiddenInput)
    expected_source_updated_at = forms.DateTimeField(required=False, widget=forms.HiddenInput)
    verified_on = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Documented verification date (only used when verifying)",
    )
    capacity = forms.IntegerField(
        required=False,
        min_value=1,
        label="Documented static capacity",
        help_text="Optional; blank means capacity not documented. Never live occupancy.",
    )
    confirm = forms.BooleanField(
        required=False,
        label="I confirm verification / source approval / public release for the selected action.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["expected_updated_at"] = self.instance.updated_at.isoformat()
            self.initial["expected_source_updated_at"] = self.instance.source.updated_at.isoformat()
            if self.allow_temporary and self.instance.is_temporary:
                # Validate the unsaved edit as a draft, not as the old approval.
                # save_center locks/rechecks the real row and explicitly reapproves.
                self.instance.verification_status = EvacuationCenter.VerificationStatus.DRAFT
        # Capacity belongs exclusively to the normal verification transition.
        self.fields["capacity"].help_text += " Draft saves do not record this value."

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("verified_on") and cleaned["verified_on"] > timezone.localdate():
            self.add_error("verified_on", "The verification date cannot be in the future.")
        return cleaned


class FastSourceForm(DataSourceForm):
    expected_updated_at = forms.DateTimeField(required=False, widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        required=False,
        label="I confirm source approval and any explicitly selected public release.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["expected_updated_at"] = self.instance.updated_at.isoformat()


class FastGuidanceForm(GuidanceItemForm):
    expected_updated_at = forms.DateTimeField(required=False, widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        required=False, label="I confirm the selected approval/publication action."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["expected_updated_at"] = self.instance.updated_at.isoformat()


def guidance_save_actions(actor):
    actions = [("save", "Save draft"), ("add-another", "Save and add another")]
    if actor.has_perm("dss.change_guidanceitem"):
        actions.append(("submit", "Save and submit for review"))
        if actor.has_perm("dss.approve_guidanceitem"):
            actions.append(("approve", "Save, submit and approve"))
            if actor.has_perm("dss.publish_guidanceitem"):
                actions.append(("publish", "Save, approve and publish"))
    return actions


@staff_required
@require_http_methods(["GET", "POST"])
def guidance_editor(request, item_id=None):
    require_permission(request.user, f"dss.{'change' if item_id else 'add'}_guidanceitem")
    item = get_object_or_404(GuidanceItem, pk=item_id) if item_id else None
    if item and item.workflow_status != "DRAFT":
        messages.error(request, "Only draft guidance can be edited. Use a workflow action first.")
        return redirect("admin_portal:dss-content")
    form = FastGuidanceForm(request.POST or None, instance=item)
    status = 200
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("save_action", "save")
        if action not in dict(guidance_save_actions(request.user)):
            raise PermissionDenied
        try:
            with transaction.atomic():
                if item_id:
                    locked = GuidanceItem.objects.select_for_update().get(pk=item_id)
                    require_fresh(locked, form.cleaned_data["expected_updated_at"])
                    if locked.workflow_status != "DRAFT":
                        raise ValidationError("Only drafts may be edited.")
                if action in {"approve", "publish"} and not form.cleaned_data["confirm"]:
                    raise ValidationError("Explicit approval/publication confirmation is required.")
                changed = form.save(commit=False)
                changed.workflow_status = "DRAFT"
                changed.is_enabled = False
                changed.full_clean()
                changed.save()
                log_guidance_action(
                    actor=request.user,
                    item=changed,
                    action_flag=CHANGE if item_id else ADDITION,
                    message="Saved sourced guidance draft through the management portal.",
                )
                if action in {"submit", "approve", "publish"}:
                    changed = transition_guidance(
                        item_id=changed.pk,
                        actor=request.user,
                        action="submit",
                        expected_status="DRAFT",
                    )
                if action in {"approve", "publish"}:
                    changed = transition_guidance(
                        item_id=changed.pk,
                        actor=request.user,
                        action="approve",
                        expected_status="IN_REVIEW",
                    )
                if action == "publish":
                    changed = transition_guidance(
                        item_id=changed.pk,
                        actor=request.user,
                        action="publish",
                        expected_status="APPROVED",
                    )
        except ValidationError as error:
            form.add_error(None, "Nothing saved. " + " ".join(error.messages))
            status = 409
        else:
            messages.success(request, f"Guidance saved as {changed.get_workflow_status_display()}.")
            return redirect(
                "admin_portal:guidance-create"
                if action == "add-another"
                else "admin_portal:dss-content"
            )
    context = _portal_context(request, active_section="dss-content")
    context.update(
        form=form,
        guidance_item=item,
        form_mode="edit" if item else "create",
        save_actions=guidance_save_actions(request.user),
    )
    return render(request, "admin_portal/guidance_form.html", context, status=status)


def center_actions(actor):
    actions = [("save", "Save draft"), ("add-another", "Save and add another")]
    if actor.has_perm("evacuation.change_evacuationcenter"):
        actions.append(("submit", "Save and submit for review"))
        if actor.has_perm("provenance.change_datasource"):
            actions.append(("submit-both", "Save and submit source + center"))
        if actor.has_perm("evacuation.verify_evacuationcenter"):
            actions.append(("verify", "Save and verify"))
            if actor.has_perm("provenance.approve_datasource"):
                actions.append(("approve-verify", "Save, approve source and verify center"))
            if actor.has_perm("provenance.publish_datasource"):
                actions.append(("verify-release", "Save, verify and release approved source"))
    return actions


def source_actions(actor):
    actions = [("save", "Save for review"), ("add-another", "Save and add another")]
    if actor.has_perm("provenance.approve_datasource"):
        actions.append(("approve", "Save and approve metadata"))
        if actor.has_perm("provenance.publish_datasource"):
            actions.append(("approve-publish", "Save, approve and mark publicly releasable"))
    return actions


@staff_required
@require_http_methods(["GET", "POST"])
def center_editor(request, center_id=None):
    require_permission(
        request.user, f"evacuation.{'change' if center_id else 'add'}_evacuationcenter"
    )
    center = get_object_or_404(EvacuationCenter, pk=center_id) if center_id else None
    if (
        center
        and center.verification_status != "DRAFT"
        and not (center.is_temporary and local_testing_enabled(request))
    ):
        raise PermissionDenied("Only drafts can be edited; use the review actions first.")
    form = FastCenterForm(
        request.POST or None,
        instance=center,
        initial=request.session.get("center_entry_defaults", {}) if center is None else {},
        allow_temporary=local_testing_enabled(request),
    )
    status = 200
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("save_action", "save")
        try:
            if action not in dict(center_actions(request.user)):
                raise PermissionDenied
            if (
                action in {"verify", "approve-verify", "verify-release"}
                and not form.cleaned_data["confirm"]
            ):
                raise ValidationError("Confirm the verification and any source release explicitly.")
            changed = save_center(
                form=form,
                actor=request.user,
                action=action,
                expected=form.cleaned_data["expected_updated_at"],
                verified_on=form.cleaned_data["verified_on"],
                capacity=form.cleaned_data["capacity"],
            )
        except ValidationError as error:
            form.add_error(None, "Nothing saved. " + " ".join(error.messages))
            status = 409
        else:
            request.session["center_entry_defaults"] = {
                "source": changed.source_id,
                "geographic_area": changed.geographic_area_id,
                "limitations": changed.limitations,
                "verified_on": form.cleaned_data["verified_on"].isoformat()
                if form.cleaned_data["verified_on"]
                else None,
            }
            messages.success(
                request,
                f"Center saved as {changed.get_verification_status_display()}. "
                "Resident eligibility is checked separately; no current availability is asserted.",
            )
            if (
                changed.source.status != PublicationStatus.APPROVED
                and not changed.source.is_temporary
            ):
                messages.warning(
                    request,
                    f"Saved unverified: source '{changed.source.name}' is pending. "
                    "Review its metadata inline or submit source and center together.",
                )
            if form.cleaned_data["capacity"] is not None and action not in {
                "verify",
                "approve-verify",
                "verify-release",
            }:
                messages.warning(
                    request,
                    "Capacity was not recorded: draft/review saves cannot store "
                    "a verified capacity. Enter it during documented verification.",
                )
            if action == "add-another":
                return redirect("admin_portal:evacuation-center-create")
            return redirect("admin_portal:evacuation-center-detail", center_id=changed.pk)
    from .map_config import get_map_client_config

    context = _portal_context(request, active_section="evacuation-centers")
    context.update(
        form=form,
        center=center,
        form_mode="edit" if center else "create",
        selected_source=_selected_center_source(form),
        save_actions=center_actions(request.user),
        source_form=FastSourceForm(prefix="inline", allow_temporary=local_testing_enabled(request)),
        openlayers_root=OPENLAYERS_CDN_ROOT,
        map_config=get_map_client_config(),
        source_metadata={
            str(s.pk): {
                "name": s.name,
                "organization": s.organization,
                "custodian": s.custodian,
                "status": s.get_status_display(),
                "public": s.is_publicly_releasable,
                "version": s.version,
                "date": str(s.received_or_created_on or "Not recorded"),
                "limitations": s.limitations,
                "revision": s.updated_at.isoformat(),
            }
            for s in form.fields["source"].queryset
        },
    )
    if local_testing_enabled(request):
        context["save_actions"] = [
            (
                a,
                {
                    "verify": "Save and verify / approve temporary record for testing",
                    "approve-verify": "Save and approve source + center "
                    "(local approval if temporary)",
                }.get(a, label),
            )
            for a, label in context["save_actions"]
        ]
    return render(request, "admin_portal/evacuation_center_form.html", context, status=status)


@staff_required
@require_http_methods(["GET", "POST"])
def source_editor(request, source_id=None, inline=False):
    require_permission(request.user, f"provenance.{'change' if source_id else 'add'}_datasource")
    source = get_object_or_404(DataSource, pk=source_id) if source_id else None
    if inline and source and is_bacoor_boundary_source(source):
        raise PermissionDenied(
            "This is the map reference source, not facility evidence. Its maintenance is separate."
        )
    if (
        source
        and source.status != PublicationStatus.PENDING_VALIDATION
        and not (source.is_temporary and local_testing_enabled(request))
    ):
        raise PermissionDenied("Only pending metadata can be edited.")
    form = FastSourceForm(
        request.POST or None,
        instance=source,
        prefix="inline" if inline else None,
        allow_temporary=local_testing_enabled(request),
    )
    status = 200
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("save_action", "save")
        try:
            if action not in dict(source_actions(request.user)):
                raise PermissionDenied
            if action in {"approve", "approve-publish"} and not form.cleaned_data["confirm"]:
                raise ValidationError(
                    "Confirm metadata approval and any public release explicitly."
                )
            changed = save_source(
                form=form,
                actor=request.user,
                action=action,
                expected=form.cleaned_data["expected_updated_at"],
            )
        except ValidationError as error:
            form.add_error(None, "Nothing saved. " + " ".join(error.messages))
            status = 409
        else:
            if inline:
                return JsonResponse(
                    {
                        "id": changed.pk,
                        "label": changed.name,
                        "state": changed.get_status_display(),
                        "public": changed.is_publicly_releasable,
                        "metadata": {
                            "name": changed.name,
                            "organization": changed.organization,
                            "custodian": changed.custodian,
                            "status": changed.get_status_display(),
                            "public": changed.is_publicly_releasable,
                            "version": changed.version,
                            "date": str(changed.received_or_created_on or "Not recorded"),
                            "limitations": changed.limitations,
                            "revision": changed.updated_at.isoformat(),
                        },
                    }
                )
            messages.success(
                request,
                f"Source saved: {changed.get_status_display()}; "
                f"public release {'enabled' if changed.is_publicly_releasable else 'disabled'}.",
            )
            if action == "add-another":
                return redirect("admin_portal:data-source-create")
            return redirect("admin_portal:data-source-detail", source_id=changed.pk)
    context = _portal_context(request, active_section="sources-content")
    context.update(
        form=form,
        source=source,
        form_mode="edit" if source else "create",
        save_actions=source_actions(request.user),
    )
    if local_testing_enabled(request):
        context["save_actions"] = [
            (
                a,
                "Save and approve metadata (local approval if temporary)"
                if a == "approve"
                else label,
            )
            for a, label in context["save_actions"]
        ]
    if inline:
        if request.method == "POST" and form.errors and status == 200:
            status = 400
        return JsonResponse(
            {
                "html": render_to_string(
                    "admin_portal/includes/inline_source_form.html", context, request=request
                )
            },
            status=status,
        )
    return render(request, "admin_portal/data_source_form.html", context, status=status)


def resident_checklist(center):
    """Delegate final eligibility to the SAME strict SELECT-only public service."""
    identities = ready_reference_barangays()
    row = eligible_center_candidates(identities).filter(public_id=center.public_id).first()
    public_ok = False
    if row:
        row["distance_meters"] = 0.0  # validation only; no distance claim is displayed
        public_ok = _public_center(row, identities[center.geographic_area_id]) is not None
    return [
        (
            "Center verified with documented date",
            center.verification_status == "VERIFIED" and bool(center.verified_on),
        ),
        ("Center publication approved", center.publication_status == "APPROVED"),
        (
            "Source approved (not demonstration)",
            center.source.status == "APPROVED" and center.source.source_type != "DEMONSTRATION",
        ),
        ("Source public release permitted", center.source.is_publicly_releasable),
        ("Supported geographic identity", center.geographic_area_id in identities),
        ("All current API gates and safe public fields", public_ok),
    ]


class ImportUploadForm(forms.Form):
    source = forms.ModelChoiceField(queryset=DataSource.objects.none())
    shared_limitations = forms.CharField(
        required=False,
        max_length=10000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Used only where a row's limitations field is blank. No invented defaults.",
    )
    upload = forms.FileField(label="CSV or Excel (.xlsx)")
    authorized = forms.BooleanField(
        label=(
            "I am authorized to upload these records; "
            "they contain no restricted data or personal contacts."
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = DataSource.objects.filter(
            status__in=("PENDING_VALIDATION", "APPROVED")
        ).exclude(source_type="DEMONSTRATION")


@staff_required
@require_http_methods(["GET", "POST"])
def center_import(request):
    require_permission(request.user, "evacuation.add_evacuationcenter")
    form = ImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            batch = stage_batch(
                upload=form.cleaned_data["upload"],
                source=form.cleaned_data["source"],
                shared_limitations=form.cleaned_data["shared_limitations"],
                actor=request.user,
            )
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            return redirect("admin_portal:center-import-detail", batch_id=batch.pk)
    context = _portal_context(request, active_section="evacuation-centers")
    context.update(
        form=form, batches=CenterImportBatch.objects.select_related("source", "actor")[:20]
    )
    return render(request, "admin_portal/center_import.html", context)


@staff_required
@require_GET
def center_import_template(request):
    require_permission(request.user, "evacuation.add_evacuationcenter")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="center-import-template.csv"'
    csv.writer(response).writerow(HEADERS)
    return response


@staff_required
@require_http_methods(["GET", "POST"])
def center_import_detail(request, batch_id):
    require_permission(request.user, "evacuation.view_evacuationcenter")
    batch = get_object_or_404(
        CenterImportBatch.objects.select_related("source", "actor"), pk=batch_id
    )
    status = 200
    if request.method == "POST":
        if request.POST.get("confirm") != "on":
            messages.error(request, "Confirm the exact valid/invalid counts before importing.")
            status = 400
        else:
            try:
                batch = import_batch(batch_id=batch.pk, actor=request.user)
            except ValidationError as error:
                messages.error(request, "Nothing imported. " + " ".join(error.messages))
                status = 409
            else:
                messages.success(
                    request,
                    f"Imported {batch.imported_count} unverified drafts. "
                    f"{batch.invalid_count} invalid rows were NOT imported; see the error report.",
                )
                return redirect("admin_portal:center-import-detail", batch_id=batch.pk)
    context = _portal_context(request, active_section="evacuation-centers")
    context.update(batch=batch, can_import=request.user.has_perm("evacuation.add_evacuationcenter"))
    from .map_config import get_map_client_config

    context.update(
        map_config=get_map_client_config(),
        openlayers_root=OPENLAYERS_CDN_ROOT,
        batch_points=[
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        r["values"].get("longitude", ""),
                        r["values"].get("latitude", ""),
                    ],
                },
                "properties": {"label": f"Row {r['number']}: {r['values'].get('name', '')}"},
            }
            for r in batch.rows
        ],
    )
    return render(request, "admin_portal/center_import_detail.html", context, status=status)


def csv_literal(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@staff_required
@require_GET
def center_import_errors(request, batch_id):
    require_permission(request.user, "evacuation.view_evacuationcenter")
    batch = get_object_or_404(CenterImportBatch, pk=batch_id)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="batch-{batch.public_id}-report.csv"'
    writer = csv.writer(response)
    writer.writerow(("row", "name", "result", "errors", "warnings"))
    for row in batch.rows:
        writer.writerow(
            [
                csv_literal(v)
                for v in (
                    row["number"],
                    row["values"].get("name", ""),
                    "INVALID" if row["errors"] else "VALID",
                    "; ".join(row["errors"]),
                    "; ".join(row["warnings"]),
                )
            ]
        )
    return response


def _review_queryset(module, data):
    queryset = MODELS[module].objects.order_by("pk")
    if q := data.get("q", "").strip()[:140]:
        field = "title" if module in {"flows", "guidance"} else "name"
        queryset = queryset.filter(Q(**{field + "__icontains": q}))
    state_field = {
        "centers": "verification_status",
        "sources": "status",
        "guidance": "workflow_status",
        "flows": "workflow_status",
    }[module]
    if state := data.get("state", ""):
        choices = dict(MODELS[module]._meta.get_field(state_field).choices)
        if state not in choices:
            raise ValidationError("Unknown review-state filter.")
        queryset = queryset.filter(**{state_field: state})
    if module == "centers" and data.get("batch", ""):
        if not data["batch"].isdecimal():
            raise ValidationError("Invalid batch filter. No records selected or changed.")
        batch = get_object_or_404(CenterImportBatch, pk=data["batch"])
        queryset = queryset.filter(
            pk__in=[r["center_id"] for r in batch.rows if r.get("center_id")]
        )
    if module != "sources":
        queryset = queryset.select_related("source")
    return queryset


@staff_required
@require_http_methods(["GET", "POST"])
def review_queue(request, module):
    if module not in MODELS:
        raise Http404
    require_permission(request.user, view_permission(module))
    context = _portal_context(
        request,
        active_section="sources-content"
        if module == "sources"
        else "evacuation-centers"
        if module == "centers"
        else "dss-content",
    )
    context.update(module=module, actions=permitted_actions(module, request.user))
    state_field = {
        "centers": "verification_status",
        "sources": "status",
        "guidance": "workflow_status",
        "flows": "workflow_status",
    }[module]
    context["state_choices"] = MODELS[module]._meta.get_field(state_field).choices
    status = 200
    data = request.POST if request.method == "POST" else request.GET
    try:
        queryset = _review_queryset(module, data)
        if request.method == "POST" and request.POST.get("token"):
            if request.POST.get("confirm") != "on":
                raise ValidationError("Confirm the eligible subset and excluded-record counts.")
            count, rejected = execute_bulk(token=request.POST["token"], actor=request.user)
            messages.success(
                request,
                f"Updated all {count} confirmed eligible records. "
                f"{rejected} explicitly excluded records unchanged.",
            )
            return redirect(reverse("admin_portal:review-queue", args=[module]))
        if request.method == "POST":
            if request.POST.get("all_matching") == "on":
                ids = list(queryset.values_list("pk", flat=True)[: LIMIT + 1])
            else:
                raw = request.POST.getlist("ids")
                if any(not v.isdecimal() for v in raw):
                    raise ValidationError("Invalid selected record.")
                ids = [int(v) for v in raw]
                if set(ids) - set(queryset.filter(pk__in=ids).values_list("pk", flat=True)):
                    raise ValidationError("Selection no longer matches the displayed filters.")
            date_form = forms.DateField(required=False)
            verified_on = date_form.clean(request.POST.get("verified_on"))
            context["preview"] = preview_bulk(
                module=module,
                ids=ids,
                action=request.POST.get("action"),
                actor=request.user,
                verified_on=verified_on,
            )
        records = list(queryset[:LIMIT])
        names = (
            Counter(c.name.strip().casefold() for c in EvacuationCenter.objects.only("name"))
            if module == "centers"
            else Counter()
        )
        coordinates = (
            Counter(EvacuationCenter.objects.values_list("latitude", "longitude"))
            if module == "centers"
            else Counter()
        )
        attention = []
        for record in records:
            source = record if module == "sources" else record.source
            missing = [
                label
                for label in (
                    "organization",
                    "custodian",
                    "coverage_description",
                    "permitted_use",
                    "limitations",
                )
                if not getattr(source, label).strip()
            ]
            reasons = ["Missing source metadata: " + ", ".join(missing)] if missing else []
            if source.status == "PENDING_VALIDATION":
                reasons.append("Source pending: approval required before verified/public use.")
            if not source.is_publicly_releasable:
                reasons.append("Source public release not permitted.")
            if module == "centers":
                if not record.geographic_area_id:
                    reasons.append("Geographic identity not assigned.")
                if (
                    names[record.name.strip().casefold()] > 1
                    or coordinates[(record.latitude, record.longitude)] > 1
                ):
                    reasons.append(
                        "Possible duplicate name or exact coordinates: "
                        "review before further action."
                    )
                try:
                    record.full_clean()
                except ValidationError as error:
                    reasons.extend(error.messages)
                record.state_label = record.get_verification_status_display()
            elif module == "sources":
                record.state_label = record.get_status_display()
            else:
                if module == "flows":
                    from dss.services import validate_dss_flow

                    try:
                        validate_dss_flow(record)
                    except ValidationError as error:
                        reasons.extend(error.messages)
                record.state_label = record.get_workflow_status_display()
            attention.append(
                {
                    "record": record,
                    "reasons": reasons,
                    "next_actions": _next_actions(module, record, request.user),
                }
            )
        context.update(
            attention=attention,
            matching=queryset.count(),
            query=data.get("q", ""),
            state=data.get("state", ""),
            batch_filter=data.get("batch", ""),
        )
    except ValidationError as error:
        context["errors"] = error.messages
        status = 409
    return render(request, "admin_portal/review_queue.html", context, status=status)


def _next_actions(module, record, actor):
    if module == "flows":
        allowed = {"DRAFT": "submit", "IN_REVIEW": "publish", "PUBLISHED": "retire"}.get(
            record.workflow_status
        )
        return [label for action, label in permitted_actions(module, actor) if action == allowed]
    from .bulk_workflows import ACTION_MAPS

    field = (
        "verification_status"
        if module == "centers"
        else "status"
        if module == "sources"
        else "workflow_status"
    )
    return [
        spec.label
        for spec in ACTION_MAPS[module].values()
        if spec.source_status == getattr(record, field)
        and actor.has_perm(spec.permission)
        and (module != "sources" or spec.source_public == record.is_publicly_releasable)
    ]
