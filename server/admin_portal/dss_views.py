"""Permission-controlled staff maintenance of the resident Prepare graph."""

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from dss.flow_workflow import (
    clone_dss_flow,
    publish_dss_flow,
    retire_dss_flow,
    return_dss_flow_to_draft,
    submit_dss_flow,
)
from dss.models import DSSContentBlock, DSSFlowVersion, DSSOption, DSSOutcome, DSSQuestion
from dss.services import serialize_dss_preview, validate_dss_flow

from .dss_forms import (
    StructuredBlockForm,
    StructuredCloneForm,
    StructuredFlowForm,
    StructuredOptionForm,
    StructuredOutcomeForm,
    StructuredQuestionForm,
    StructuredTransitionForm,
)
from .views import _portal_context, portal_permission_required, staff_required


def _context(request, **extra):
    context = _portal_context(request, active_section="dss-content")
    context.update(extra)
    return context


def _log(actor, obj, *, created=False):
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[obj],
        action_flag=ADDITION if created else CHANGE,
        change_message="Created structured DSS draft record."
        if created
        else "Edited structured DSS draft record.",
        single_object=True,
    )


def _editable(flow):
    if flow.workflow_status != DSSFlowVersion.WorkflowStatus.DRAFT:
        raise ValidationError(
            "Only a draft can be edited. Create a new draft version for published history."
        )


def _fresh(flow, data):
    if data.get("expected_updated_at") != flow.updated_at:
        raise ValidationError(
            "This flow changed after you opened it. Reload and review the latest version."
        )


def _save_actions(actor):
    actions = [("save", "Save draft"), ("add-another", "Save and add another")]
    if actor.has_perm("dss.review_dssflowversion"):
        actions.append(("submit", "Save and submit complete graph for review"))
    return actions


def _after_save(flow, request):
    action = request.POST.get("save_action", "save")
    if action not in dict(_save_actions(request.user)):
        raise PermissionDenied
    if action == "submit":
        flow.refresh_from_db()
        submit_dss_flow(flow_id=flow.pk, actor=request.user, expected_updated_at=flow.updated_at)
    return action


@staff_required
@portal_permission_required("dss.view_dssflowversion")
@require_GET
def structured_flow_list(request):
    flows = (
        DSSFlowVersion.objects.select_related("source")
        .annotate(
            question_count=Count("questions", distinct=True),
            outcome_count=Count("outcomes", distinct=True),
            block_count=Count("content_blocks", distinct=True),
            option_count=Count("questions__options", distinct=True),
            linked_guidance_count=Count("outcomes__guidance_item", distinct=True),
        )
        .order_by("code", "-id")
    )
    query = request.GET.get("q", "").strip()[:120]
    if query:
        flows = flows.filter(
            Q(title__icontains=query) | Q(code__icontains=query) | Q(source__name__icontains=query)
        )
    return render(
        request,
        "admin_portal/dss_flow_list.html",
        _context(
            request,
            flows=Paginator(flows, 25).get_page(request.GET.get("page")),
            query=query,
            can_add=request.user.has_perm("dss.add_dssflowversion"),
        ),
    )


@staff_required
@portal_permission_required("dss.view_dssflowversion")
@require_GET
def structured_flow_detail(request, flow_id):
    flow = get_object_or_404(DSSFlowVersion.objects.select_related("source"), pk=flow_id)
    failures = []
    try:
        validate_dss_flow(flow)
    except ValidationError as error:
        failures = error.messages
    editable = flow.workflow_status == "DRAFT"
    perms = request.user
    actions = []
    for action, label, state, permission in (
        ("submit", "Submit for review", "DRAFT", "review_dssflowversion"),
        ("return", "Return to draft", "IN_REVIEW", "review_dssflowversion"),
        ("publish", "Publish reviewed flow", "IN_REVIEW", "publish_dssflowversion"),
        ("retire", "Retire / unpublish", "PUBLISHED", "publish_dssflowversion"),
    ):
        if flow.workflow_status == state and perms.has_perm(f"dss.{permission}"):
            actions.append((action, label))
    return render(
        request,
        "admin_portal/dss_flow_detail.html",
        _context(
            request,
            flow=flow,
            failures=failures,
            questions=flow.questions.prefetch_related("options__next_question", "options__outcome"),
            outcomes=flow.outcomes.select_related("source", "guidance_item"),
            blocks=flow.content_blocks.select_related("source", "outcome"),
            option_count=DSSOption.objects.filter(question__flow=flow).count(),
            linked_guidance_count=flow.outcomes.filter(guidance_item__isnull=False)
            .values("guidance_item_id")
            .distinct()
            .count(),
            actions=actions,
            can_edit=editable and perms.has_perm("dss.change_dssflowversion"),
            can_add_question=editable
            and perms.has_perm("dss.change_dssflowversion")
            and perms.has_perm("dss.add_dssquestion"),
            can_add_option=editable
            and perms.has_perm("dss.change_dssflowversion")
            and perms.has_perm("dss.add_dssoption"),
            can_add_outcome=editable
            and perms.has_perm("dss.change_dssflowversion")
            and perms.has_perm("dss.add_dssoutcome"),
            can_add_block=editable
            and perms.has_perm("dss.change_dssflowversion")
            and perms.has_perm("dss.add_dsscontentblock"),
            can_clone=perms.has_perm("dss.add_dssflowversion")
            and perms.has_perm("dss.change_dssflowversion"),
        ),
    )


@staff_required
@portal_permission_required("dss.add_dssflowversion")
@require_http_methods(["GET", "POST"])
def structured_flow_create(request):
    form = StructuredFlowForm(request.POST or None)
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                flow = form.save()
                _log(request.user, flow, created=True)
                action = _after_save(flow, request)
        except ValidationError as error:
            form.add_error(None, "Nothing saved. " + " ".join(error.messages))
            response_status = 409
        else:
            if action == "add-another":
                return redirect("admin_portal:dss-flow-create")
            return redirect("admin_portal:dss-flow-detail", flow_id=flow.pk)
    return render(
        request,
        "admin_portal/dss_editor.html",
        _context(
            request,
            form=form,
            title="Create structured Prepare draft",
            save_actions=_save_actions(request.user),
        ),
        status=response_status,
    )


@staff_required
@portal_permission_required("dss.change_dssflowversion")
@require_http_methods(["GET", "POST"])
def structured_flow_edit(request, flow_id):
    flow = get_object_or_404(DSSFlowVersion, pk=flow_id)
    if flow.workflow_status != "DRAFT":
        raise PermissionDenied("Published and reviewed records cannot be edited here.")
    form = StructuredFlowForm(request.POST or None, instance=flow, flow=flow)
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                locked = DSSFlowVersion.objects.select_for_update().get(pk=flow.pk)
                _editable(locked)
                _fresh(locked, form.cleaned_data)
                flow = form.save()
                _log(request.user, flow)
                action = _after_save(flow, request)
            if action == "add-another":
                return redirect("admin_portal:dss-flow-create")
            return redirect("admin_portal:dss-flow-detail", flow_id=flow.pk)
        except ValidationError as error:
            form.add_error(None, error)
            response_status = 409
    return render(
        request,
        "admin_portal/dss_editor.html",
        _context(
            request,
            form=form,
            flow=flow,
            title="Edit structured Prepare draft",
            save_actions=_save_actions(request.user),
        ),
        status=response_status,
    )


EDITORS = {
    "question": (DSSQuestion, StructuredQuestionForm),
    "outcome": (DSSOutcome, StructuredOutcomeForm),
    "option": (DSSOption, StructuredOptionForm),
    "block": (DSSContentBlock, StructuredBlockForm),
}


@staff_required
@portal_permission_required("dss.change_dssflowversion")
@require_http_methods(["GET", "POST"])
def structured_node_edit(request, flow_id, kind, node_id=None):
    if kind not in EDITORS:
        raise Http404
    model, form_type = EDITORS[kind]
    action = "change" if node_id is not None else "add"
    if not request.user.has_perm(f"dss.{action}_{model._meta.model_name}"):
        raise PermissionDenied
    flow = get_object_or_404(DSSFlowVersion, pk=flow_id)
    if flow.workflow_status != "DRAFT":
        raise PermissionDenied("Only draft graph records are editable.")
    lookup = {"question__flow": flow} if kind == "option" else {"flow": flow}
    if node_id is not None:
        node = get_object_or_404(model, pk=node_id, **lookup)
    elif kind == "option":
        question_id = request.GET.get("question", "")
        if not question_id.isdecimal():
            raise Http404("Select a question from this draft before adding an option.")
        question = get_object_or_404(DSSQuestion, pk=question_id, flow=flow)
        node = DSSOption(question=question)
    else:
        node = model(flow=flow)
    form = form_type(request.POST or None, instance=node, flow=flow)
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                locked = DSSFlowVersion.objects.select_for_update().get(pk=flow.pk)
                _editable(locked)
                _fresh(locked, form.cleaned_data)
                node = form.save()
                locked.updated_at = timezone.now()
                locked.save(update_fields=("updated_at",))
                _log(request.user, node, created=node_id is None)
            return redirect("admin_portal:dss-flow-detail", flow_id=flow.pk)
        except ValidationError as error:
            form.add_error(None, error)
            response_status = 409
    return render(
        request,
        "admin_portal/dss_editor.html",
        _context(
            request,
            form=form,
            flow=flow,
            title=f"{'Edit' if node_id else 'Add'} {kind} in draft",
        ),
        status=response_status,
    )


@staff_required
@portal_permission_required("dss.view_dssflowversion")
@require_http_methods(["GET", "POST"])
def structured_flow_transition(request, flow_id, action):
    specifications = {
        "submit": ("review_dssflowversion", "Submit for review", submit_dss_flow),
        "return": ("review_dssflowversion", "Return to draft", return_dss_flow_to_draft),
        "publish": ("publish_dssflowversion", "Publish reviewed flow", publish_dss_flow),
        "retire": ("publish_dssflowversion", "Retire / unpublish", retire_dss_flow),
        "clone": ("add_dssflowversion", "Create next version as draft", clone_dss_flow),
    }
    if action not in specifications:
        raise Http404
    permission, label, service = specifications[action]
    if not request.user.has_perm(f"dss.{permission}"):
        raise PermissionDenied
    if action == "clone" and not request.user.has_perm("dss.change_dssflowversion"):
        raise PermissionDenied
    flow = get_object_or_404(DSSFlowVersion, pk=flow_id)
    form_type = StructuredCloneForm if action == "clone" else StructuredTransitionForm
    form = form_type(
        request.POST or None, initial={"expected_updated_at": flow.updated_at.isoformat()}
    )
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            kwargs = {
                "flow_id": flow.pk,
                "actor": request.user,
                "expected_updated_at": form.cleaned_data["expected_updated_at"],
            }
            if action == "clone":
                kwargs["version"] = form.cleaned_data["version"]
            changed = service(**kwargs)
            messages.success(request, f"{label}: completed.")
            return redirect("admin_portal:dss-flow-detail", flow_id=changed.pk)
        except ValidationError as error:
            form.add_error(None, error)
            response_status = 409
    return render(
        request,
        "admin_portal/dss_editor.html",
        _context(
            request,
            form=form,
            flow=flow,
            title=label,
            transition=True,
        ),
        status=response_status,
    )


@staff_required
@portal_permission_required("dss.view_dssflowversion")
@require_GET
def structured_flow_preview(request, flow_id):
    flow = get_object_or_404(DSSFlowVersion, pk=flow_id)
    structure = serialize_dss_preview(flow)
    return render(
        request,
        "admin_portal/dss_flow_preview.html",
        _context(
            request,
            flow=flow,
            structure=structure,
        ),
    )
