"""Explicit, single-record cleanup in the normal portal; never an automatic purge."""

from core.local_testing import local_testing_enabled
from core.record_workflow import center_write_lock, require_fresh, require_permission
from django import forms
from django.contrib import messages
from django.contrib.admin.models import DELETION
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from evacuation.models import EvacuationCenter
from evacuation.workflow import log_center_action
from provenance.models import DataSource
from provenance.workflow import log_source_action

from .views import _portal_context, staff_required


class RemoveTemporaryForm(forms.Form):
    expected_updated_at = forms.DateTimeField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        label="Remove only this temporary record. This cannot be undone through the portal."
    )


@staff_required
@require_http_methods(["GET", "POST"])
def remove_temporary(request, record_id, kind):
    if not local_testing_enabled(request):
        raise PermissionDenied
    model = EvacuationCenter if kind == "center" else DataSource
    require_permission(request.user, f"{model._meta.app_label}.delete_{model._meta.model_name}")
    record = get_object_or_404(model, pk=record_id)
    if not record.is_temporary:
        raise PermissionDenied("This cleanup action cannot delete genuine records.")
    form = RemoveTemporaryForm(
        request.POST or None, initial={"expected_updated_at": record.updated_at.isoformat()}
    )
    status = 200
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if kind == "center":
                    center_write_lock()
                    DataSource.objects.select_for_update().get(pk=record.source_id)
                record = get_object_or_404(model.objects.select_for_update(), pk=record_id)
                require_fresh(record, form.cleaned_data["expected_updated_at"])
                if not record.is_temporary:
                    raise ValidationError("The record is no longer temporary. Nothing removed.")
                # Source relationships use PROTECT. Never cascade away connected data.
                logger = log_center_action if kind == "center" else log_source_action
                logger(
                    actor=request.user,
                    **{kind: record},
                    action_flag=DELETION,
                    message="Explicitly removed one temporary local test record "
                    "through the portal.",
                )
                record.delete()
        except (ProtectedError, RestrictedError):
            form.add_error(
                None,
                "This source still has connected records. Remove the intended temporary "
                "dependents first; genuine data will not be deleted.",
            )
            status = 409
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
            status = 409
        else:
            messages.success(
                request, "Removed one temporary record. No other records were removed."
            )
            return redirect(
                "admin_portal:evacuation-centers"
                if kind == "center"
                else "admin_portal:sources-content"
            )
    context = _portal_context(
        request, active_section="evacuation-centers" if kind == "center" else "sources-content"
    )
    context.update(record=record, kind=kind, form=form)
    return render(request, "admin_portal/remove_temporary.html", context, status=status)
