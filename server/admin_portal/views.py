from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods
from dss.models import GuidanceItem
from dss.workflow import (
    TRANSITIONS,
    available_transitions,
    log_guidance_action,
    transition_guidance,
)
from evacuation.models import EvacuationCenter
from evacuation.workflow import (
    TRANSITIONS as CENTER_TRANSITIONS,
)
from evacuation.workflow import (
    available_transitions as available_center_transitions,
)
from evacuation.workflow import (
    log_center_action,
    transition_center,
)
from expert.models import ScenarioOption
from geography.widgets import OPENLAYERS_CDN_ROOT
from provenance.models import DataSource, PublicationStatus
from provenance.workflow import (
    TRANSITIONS as SOURCE_TRANSITIONS,
)
from provenance.workflow import (
    available_transitions as available_source_transitions,
)
from provenance.workflow import (
    log_source_action,
    transition_source,
)

from .forms import (
    AuditFilterForm,
    DataSourceFilterForm,
    DataSourceForm,
    DataSourceTransitionForm,
    EvacuationCenterFilterForm,
    EvacuationCenterForm,
    EvacuationTransitionForm,
    GuidanceFilterForm,
    GuidanceItemForm,
    GuidanceTransitionForm,
    RainfallReferenceFilterForm,
    SettingsInventoryFilterForm,
    StaffAuthenticationForm,
)
from .services.dashboard import get_dashboard_summary
from .services.map_data import get_map_data
from .services.settings_data import get_settings_data

SECTIONS = {
    "dss-content": {
        "title": "DSS content",
        "eyebrow": "Preparedness guidance",
        "description": (
            "Maintain sourced preparedness guidance and review how it is presented "
            "for each supported susceptibility result."
        ),
        "day": "Day 5",
    },
    "rainfall-references": {
        "title": "Rainfall references",
        "eyebrow": "Scenario parameters",
        "description": (
            "Document rainfall categories, durations, sources, and approval status "
            "without implying live monitoring."
        ),
        "day": "Day 6",
    },
    "evacuation-centers": {
        "title": "Evacuation centers",
        "eyebrow": "Verified resources",
        "description": (
            "Review and verify sourced center records supplied by the responsible data custodian."
        ),
        "day": "Day 6",
    },
    "sources-content": {
        "title": "Sources and content",
        "eyebrow": "Provenance",
        "description": (
            "Track data custody, versions, limitations, and public-facing source information."
        ),
        "day": "Day 6",
    },
    "audit-history": {
        "title": "Audit history",
        "eyebrow": "Accountability",
        "description": "Review activity captured by supported management workflows.",
        "day": "Day 7",
    },
}

AUDIT_MODULES = (
    (("geography", "geographicarea"), "Map data"),
    (("provenance", "datasource"), "Sources and content"),
    (("dss", "guidanceitem"), "DSS content"),
    (("expert", "scenariooption"), "Rainfall references"),
    (("evacuation", "evacuationcenter"), "Evacuation centers"),
)

CENTER_AUDIT_FIELD_LABELS = {
    "name": "name",
    "address": "address",
    "geographic_area": "geographic area",
    "latitude": "latitude",
    "longitude": "longitude",
    "contact_information": "contact information",
    "source": "source association",
    "publication_status": "publication status",
    "notes": "notes",
    "limitations": "public limitations",
}


def _selected_center_source(form: EvacuationCenterForm) -> DataSource | None:
    """Return permitted source metadata for staff presentation, never raw POST data."""
    if form.is_bound:
        source = getattr(form, "cleaned_data", {}).get("source")
        return source if isinstance(source, DataSource) else None
    source_id = form.initial.get("source")
    if not source_id and form.instance and form.instance.source_id:
        source_id = form.instance.source_id
    if not source_id:
        return None
    return form.fields["source"].queryset.filter(pk=source_id).first()


def _center_edit_audit_message(form: EvacuationCenterForm) -> str:
    labels = [
        CENTER_AUDIT_FIELD_LABELS[name]
        for name in form.changed_data
        if name in CENTER_AUDIT_FIELD_LABELS
    ]
    if not labels:
        return "Evacuation-center draft saved without a material field change."
    return (
        "Evacuation-center draft edited through the management portal. Changed fields: "
        + ", ".join(labels)
        + "."
    )


def staff_required(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Require an authenticated active staff account for every portal view."""

    @wraps(view)
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            login_url = reverse_lazy("admin_portal:login")
            next_url = request.get_full_path()
            return redirect(f"{login_url}?next={next_url}")
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def portal_permission_required(permission: str):
    """Require a Django model permission after the common staff boundary."""

    def decorator(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @wraps(view)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            if not request.user.has_perm(permission):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def _portal_context(request: HttpRequest, *, active_section: str) -> dict[str, Any]:
    display_name = request.user.display_name.strip() or request.user.email
    initials = "".join(
        part[0].upper() for part in display_name.replace("@", " ").split()[:2] if part
    )
    context = {
        "active_section": active_section,
        "display_name": display_name,
        "user_initials": initials or "FS",
        "navigation": [
            ("dashboard", "Overview", "▦"),
            ("map-data", "Map data", "◇"),
            ("settings", "Settings", "◎"),
            ("dss-content", "DSS content", "?"),
            ("rainfall-references", "Rainfall references", "≈"),
            ("evacuation-centers", "Evacuation centers", "⌂"),
            ("sources-content", "Sources and content", "○"),
            ("audit-history", "Audit history", "▤"),
        ],
    }
    required_permissions = {
        "dss-content": "dss.view_guidanceitem",
        "rainfall-references": "expert.view_scenariooption",
        "evacuation-centers": "evacuation.view_evacuationcenter",
        "sources-content": "provenance.view_datasource",
        "audit-history": "admin.view_logentry",
    }
    context["navigation"] = [
        item
        for item in context["navigation"]
        if item[0] not in required_permissions
        or request.user.has_perm(required_permissions[item[0]])
    ]
    return context


class AdminLoginView(LoginView):
    template_name = "admin_portal/login.html"
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = False

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_authenticated and request.user.is_staff:
            return redirect("admin_portal:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: StaffAuthenticationForm) -> HttpResponse:
        response = super().form_valid(form)
        if form.cleaned_data["remember_device"]:
            self.request.session.set_expiry(self.request.session.get_session_cookie_age())
        else:
            self.request.session.set_expiry(0)
        return response

    def get_success_url(self) -> str:
        requested_url = self.request.POST.get("next") or self.request.GET.get("next")
        if requested_url and url_has_allowed_host_and_scheme(
            requested_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return requested_url
        return str(reverse_lazy("admin_portal:dashboard"))


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy("admin_portal:login")


@require_GET
def password_help(request: HttpRequest) -> HttpResponse:
    return render(request, "admin_portal/password_help.html")


@staff_required
@require_GET
def dashboard(request: HttpRequest) -> HttpResponse:
    context = _portal_context(request, active_section="dashboard")
    context["dashboard"] = get_dashboard_summary()
    return render(request, "admin_portal/dashboard.html", context)


@staff_required
@require_GET
def map_data(request: HttpRequest) -> HttpResponse:
    context = _portal_context(request, active_section="map-data")
    context["map_data"] = get_map_data(selected_id=request.GET.get("area"))
    context["openlayers_root"] = OPENLAYERS_CDN_ROOT
    return render(request, "admin_portal/map_data.html", context)


@staff_required
@require_GET
def settings_view(request: HttpRequest) -> HttpResponse:
    context = _portal_context(request, active_section="settings")
    filters = SettingsInventoryFilterForm(request.GET)
    valid = filters.is_valid()
    context["inventory_filters"] = filters
    context["settings_data"] = get_settings_data(
        query=filters.cleaned_data.get("q", "") if valid else "",
        category=filters.cleaned_data.get("category", "") if valid else "",
    )
    context["profile"] = {
        "display_name": request.user.display_name,
        "email": request.user.email,
    }
    return render(request, "admin_portal/settings.html", context)


@staff_required
@require_GET
def assessment_parameters(request: HttpRequest) -> HttpResponse:
    return redirect(f"{reverse_lazy('admin_portal:settings')}#parameters")


@staff_required
@portal_permission_required("dss.view_guidanceitem")
@require_GET
def guidance_list(request: HttpRequest) -> HttpResponse:
    filters = GuidanceFilterForm(request.GET)
    queryset = GuidanceItem.objects.select_related("susceptibility_level", "source").order_by(
        "susceptibility_level__display_order", "display_order", "id"
    )
    if filters.is_valid():
        query = filters.cleaned_data["q"]
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(instruction__icontains=query)
                | Q(source__name__icontains=query)
                | Q(source__organization__icontains=query)
                | Q(attribution__icontains=query)
            )
        if category := filters.cleaned_data["category"]:
            queryset = queryset.filter(category=category)
        if workflow_status := filters.cleaned_data["workflow_status"]:
            queryset = queryset.filter(workflow_status=workflow_status)
        if susceptibility_level := filters.cleaned_data["susceptibility_level"]:
            queryset = queryset.filter(susceptibility_level=susceptibility_level)

    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get("page"))
    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    context = _portal_context(request, active_section="dss-content")
    context.update(
        {
            "filters": filters,
            "guidance_page": page,
            "query_without_page": query_without_page.urlencode(),
            "can_add": request.user.has_perm("dss.add_guidanceitem"),
            "can_change": request.user.has_perm("dss.change_guidanceitem"),
            "can_approve": request.user.has_perm("dss.approve_guidanceitem"),
            "can_publish": request.user.has_perm("dss.publish_guidanceitem"),
        }
    )
    for item in page.object_list:
        item.portal_transitions = available_transitions(item, request.user)
    return render(request, "admin_portal/guidance_list.html", context)


@staff_required
@portal_permission_required("dss.add_guidanceitem")
@require_http_methods(["GET", "POST"])
def guidance_create(request: HttpRequest) -> HttpResponse:
    form = GuidanceItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            item.workflow_status = GuidanceItem.WorkflowStatus.DRAFT
            item.is_enabled = False
            item.full_clean()
            item.save()
            log_guidance_action(
                actor=request.user,
                item=item,
                action_flag=ADDITION,
                message="Guidance draft created through the management portal.",
            )
        messages.success(request, "Guidance draft created.")
        return redirect("admin_portal:dss-content")

    context = _portal_context(request, active_section="dss-content")
    context.update({"form": form, "form_mode": "create", "guidance_item": None})
    return render(request, "admin_portal/guidance_form.html", context)


@staff_required
@portal_permission_required("dss.change_guidanceitem")
@require_http_methods(["GET", "POST"])
def guidance_edit(request: HttpRequest, item_id: int) -> HttpResponse:
    item = get_object_or_404(
        GuidanceItem.objects.select_related("source", "susceptibility_level"),
        pk=item_id,
    )
    if item.workflow_status != GuidanceItem.WorkflowStatus.DRAFT:
        messages.error(
            request,
            "Only draft guidance can be edited. Use an available workflow action first.",
        )
        return redirect("admin_portal:dss-content")

    form = GuidanceItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            item.workflow_status = GuidanceItem.WorkflowStatus.DRAFT
            item.is_enabled = False
            item.full_clean()
            item.save()
            log_guidance_action(
                actor=request.user,
                item=item,
                action_flag=CHANGE,
                message="Guidance draft edited through the management portal.",
            )
        messages.success(request, "Guidance draft updated.")
        return redirect("admin_portal:dss-content")

    context = _portal_context(request, active_section="dss-content")
    context.update({"form": form, "form_mode": "edit", "guidance_item": item})
    return render(request, "admin_portal/guidance_form.html", context)


@staff_required
@portal_permission_required("dss.view_guidanceitem")
@require_http_methods(["GET", "POST"])
def guidance_transition(request: HttpRequest, item_id: int, action: str) -> HttpResponse:
    transition = TRANSITIONS.get(action)
    if transition is None:
        raise Http404
    if not request.user.has_perm(transition.permission):
        raise PermissionDenied

    item = get_object_or_404(
        GuidanceItem.objects.select_related("source", "susceptibility_level"),
        pk=item_id,
    )
    if item.workflow_status != transition.source_status:
        messages.error(request, "That workflow action is no longer available.")
        return redirect("admin_portal:dss-content")

    form = GuidanceTransitionForm(
        request.POST or None,
        initial={"expected_status": item.workflow_status},
    )
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            changed_item = transition_guidance(
                item_id=item.pk,
                action=action,
                actor=request.user,
                expected_status=form.cleaned_data["expected_status"],
            )
        except GuidanceItem.DoesNotExist as error:
            raise Http404 from error
        except ValidationError as error:
            form.add_error(None, ValidationError(" ".join(error.messages)))
            response_status = 409
        else:
            messages.success(
                request,
                f"Guidance is now {changed_item.get_workflow_status_display().lower()}.",
            )
            return redirect("admin_portal:dss-content")

    context = _portal_context(request, active_section="dss-content")
    context.update({"form": form, "guidance_item": item, "transition": transition})
    return render(
        request,
        "admin_portal/guidance_transition_confirm.html",
        context,
        status=response_status,
    )


@staff_required
@portal_permission_required("expert.view_scenariooption")
@require_GET
def rainfall_reference_list(request: HttpRequest) -> HttpResponse:
    filters = RainfallReferenceFilterForm(request.GET)
    queryset = ScenarioOption.objects.select_related("source").order_by(
        "category", "display_order", "id"
    )
    if filters.is_valid():
        if query := filters.cleaned_data["q"]:
            queryset = queryset.filter(
                Q(label__icontains=query)
                | Q(code__icontains=query)
                | Q(unit__icontains=query)
                | Q(source__name__icontains=query)
                | Q(source__organization__icontains=query)
            )
        if category := filters.cleaned_data["category"]:
            queryset = queryset.filter(category=category)
        if status := filters.cleaned_data["status"]:
            queryset = queryset.filter(status=status)
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    context = _portal_context(request, active_section="rainfall-references")
    context.update(
        {
            "filters": filters,
            "reference_page": page,
            "query_without_page": query_without_page.urlencode(),
        }
    )
    return render(request, "admin_portal/rainfall_reference_list.html", context)


@staff_required
@portal_permission_required("expert.view_scenariooption")
@require_GET
def rainfall_reference_detail(request: HttpRequest, option_id: int) -> HttpResponse:
    reference = get_object_or_404(
        ScenarioOption.objects.select_related("source", "source__reviewed_by"),
        pk=option_id,
    )
    context = _portal_context(request, active_section="rainfall-references")
    context["reference"] = reference
    return render(request, "admin_portal/rainfall_reference_detail.html", context)


@staff_required
@portal_permission_required("evacuation.view_evacuationcenter")
@require_GET
def evacuation_center_list(request: HttpRequest) -> HttpResponse:
    filters = EvacuationCenterFilterForm(request.GET)
    queryset = EvacuationCenter.objects.select_related("geographic_area", "source").order_by(
        "name", "id"
    )
    if filters.is_valid():
        if query := filters.cleaned_data["q"]:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(address__icontains=query)
                | Q(geographic_area__name__icontains=query)
                | Q(source__name__icontains=query)
            )
        if status := filters.cleaned_data["verification_status"]:
            queryset = queryset.filter(verification_status=status)
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    for center in page.object_list:
        center.portal_transitions = available_center_transitions(center, request.user)
    context = _portal_context(request, active_section="evacuation-centers")
    context.update(
        {
            "filters": filters,
            "center_page": page,
            "query_without_page": query_without_page.urlencode(),
            "can_add": request.user.has_perm("evacuation.add_evacuationcenter"),
            "can_change": request.user.has_perm("evacuation.change_evacuationcenter"),
        }
    )
    return render(request, "admin_portal/evacuation_center_list.html", context)


@staff_required
@portal_permission_required("evacuation.view_evacuationcenter")
@require_GET
def evacuation_center_detail(request: HttpRequest, center_id: int) -> HttpResponse:
    center = get_object_or_404(
        EvacuationCenter.objects.select_related("geographic_area", "source"),
        pk=center_id,
    )
    center.portal_transitions = available_center_transitions(center, request.user)
    context = _portal_context(request, active_section="evacuation-centers")
    context.update(
        {
            "center": center,
            "openlayers_root": OPENLAYERS_CDN_ROOT,
            "can_change": request.user.has_perm("evacuation.change_evacuationcenter"),
        }
    )
    return render(request, "admin_portal/evacuation_center_detail.html", context)


@staff_required
@portal_permission_required("evacuation.add_evacuationcenter")
@require_http_methods(["GET", "POST"])
def evacuation_center_create(request: HttpRequest) -> HttpResponse:
    form = EvacuationCenterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            center = form.save(commit=False)
            center.verification_status = EvacuationCenter.VerificationStatus.DRAFT
            center.full_clean()
            center.save()
            log_center_action(
                actor=request.user,
                center=center,
                action_flag=ADDITION,
                message="Evacuation-center draft created through the management portal.",
            )
        messages.success(request, "Evacuation-center draft created.")
        return redirect("admin_portal:evacuation-center-detail", center_id=center.pk)
    context = _portal_context(request, active_section="evacuation-centers")
    context.update(
        {
            "form": form,
            "center": None,
            "form_mode": "create",
            "openlayers_root": OPENLAYERS_CDN_ROOT,
            "selected_source": _selected_center_source(form),
        }
    )
    return render(request, "admin_portal/evacuation_center_form.html", context)


@staff_required
@portal_permission_required("evacuation.change_evacuationcenter")
@require_http_methods(["GET", "POST"])
def evacuation_center_edit(request: HttpRequest, center_id: int) -> HttpResponse:
    center = get_object_or_404(EvacuationCenter, pk=center_id)
    if center.verification_status != EvacuationCenter.VerificationStatus.DRAFT:
        messages.error(request, "Only draft center records can be edited.")
        return redirect("admin_portal:evacuation-center-detail", center_id=center.pk)
    form = EvacuationCenterForm(request.POST or None, instance=center)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            center = form.save(commit=False)
            center.verification_status = EvacuationCenter.VerificationStatus.DRAFT
            center.full_clean()
            center.save()
            log_center_action(
                actor=request.user,
                center=center,
                message=_center_edit_audit_message(form),
            )
        messages.success(request, "Evacuation-center draft updated.")
        return redirect("admin_portal:evacuation-center-detail", center_id=center.pk)
    context = _portal_context(request, active_section="evacuation-centers")
    context.update(
        {
            "form": form,
            "center": center,
            "form_mode": "edit",
            "openlayers_root": OPENLAYERS_CDN_ROOT,
            "selected_source": _selected_center_source(form),
        }
    )
    return render(request, "admin_portal/evacuation_center_form.html", context)


@staff_required
@portal_permission_required("evacuation.view_evacuationcenter")
@require_http_methods(["GET", "POST"])
def evacuation_center_transition(request: HttpRequest, center_id: int, action: str) -> HttpResponse:
    transition = CENTER_TRANSITIONS.get(action)
    if transition is None:
        raise Http404
    if not request.user.has_perm(transition.permission):
        raise PermissionDenied
    center = get_object_or_404(
        EvacuationCenter.objects.select_related("source", "geographic_area"), pk=center_id
    )
    if center.verification_status != transition.source_status:
        messages.error(request, "That verification action is no longer available.")
        return redirect("admin_portal:evacuation-center-detail", center_id=center.pk)
    form = EvacuationTransitionForm(
        request.POST or None,
        action=action,
        initial={"expected_status": center.verification_status},
    )
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            transition_center(
                center_id=center.pk,
                action=action,
                actor=request.user,
                expected_status=form.cleaned_data["expected_status"],
                verified_on=form.cleaned_data.get("verified_on"),
                capacity=form.cleaned_data.get("capacity"),
            )
        except EvacuationCenter.DoesNotExist:
            raise Http404 from None
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
            response_status = 409
        else:
            messages.success(request, "Evacuation-center verification state updated.")
            return redirect("admin_portal:evacuation-center-detail", center_id=center.pk)
    context = _portal_context(request, active_section="evacuation-centers")
    context.update({"form": form, "center": center, "transition": transition})
    return render(
        request,
        "admin_portal/evacuation_transition_confirm.html",
        context,
        status=response_status,
    )


@staff_required
@portal_permission_required("provenance.view_datasource")
@require_GET
def data_source_list(request: HttpRequest) -> HttpResponse:
    filters = DataSourceFilterForm(request.GET)
    queryset = DataSource.objects.select_related("reviewed_by").order_by("name", "id")
    if filters.is_valid():
        if query := filters.cleaned_data["q"]:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(organization__icontains=query)
                | Q(custodian__icontains=query)
            )
        if source_type := filters.cleaned_data["source_type"]:
            queryset = queryset.filter(source_type=source_type)
        if status := filters.cleaned_data["status"]:
            queryset = queryset.filter(status=status)
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    for source in page.object_list:
        source.portal_transitions = available_source_transitions(source, request.user)
    context = _portal_context(request, active_section="sources-content")
    context.update(
        {
            "filters": filters,
            "source_page": page,
            "query_without_page": query_without_page.urlencode(),
            "can_add": request.user.has_perm("provenance.add_datasource"),
            "can_change": request.user.has_perm("provenance.change_datasource"),
        }
    )
    return render(request, "admin_portal/data_source_list.html", context)


@staff_required
@portal_permission_required("provenance.view_datasource")
@require_GET
def data_source_detail(request: HttpRequest, source_id: int) -> HttpResponse:
    source = get_object_or_404(DataSource.objects.select_related("reviewed_by"), pk=source_id)
    source.portal_transitions = available_source_transitions(source, request.user)
    context = _portal_context(request, active_section="sources-content")
    context.update(
        {
            "source": source,
            "can_change": request.user.has_perm("provenance.change_datasource"),
            "linked_counts": {
                "rainfall": source.scenario_options.count(),
                "guidance": source.guidance_items.count(),
                "areas": source.geographic_areas.count(),
                "centers": source.evacuation_centers.count(),
            },
        }
    )
    return render(request, "admin_portal/data_source_detail.html", context)


@staff_required
@portal_permission_required("provenance.add_datasource")
@require_http_methods(["GET", "POST"])
def data_source_create(request: HttpRequest) -> HttpResponse:
    form = DataSourceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            source = form.save(commit=False)
            source.status = PublicationStatus.PENDING_VALIDATION
            source.is_publicly_releasable = False
            source.full_clean()
            source.save()
            log_source_action(
                actor=request.user,
                source=source,
                action_flag=ADDITION,
                message="Source metadata created for review through the management portal.",
            )
        messages.success(request, "Source metadata created for review.")
        return redirect("admin_portal:data-source-detail", source_id=source.pk)
    context = _portal_context(request, active_section="sources-content")
    context.update({"form": form, "source": None, "form_mode": "create"})
    return render(request, "admin_portal/data_source_form.html", context)


@staff_required
@portal_permission_required("provenance.change_datasource")
@require_http_methods(["GET", "POST"])
def data_source_edit(request: HttpRequest, source_id: int) -> HttpResponse:
    source = get_object_or_404(DataSource, pk=source_id)
    if source.status != PublicationStatus.PENDING_VALIDATION:
        messages.error(request, "Only source metadata under review can be edited.")
        return redirect("admin_portal:data-source-detail", source_id=source.pk)
    form = DataSourceForm(request.POST or None, instance=source)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            source = form.save(commit=False)
            source.status = PublicationStatus.PENDING_VALIDATION
            source.is_publicly_releasable = False
            source.full_clean()
            source.save()
            log_source_action(
                actor=request.user,
                source=source,
                message="Source metadata edited during review through the management portal.",
            )
        messages.success(request, "Source metadata updated.")
        return redirect("admin_portal:data-source-detail", source_id=source.pk)
    context = _portal_context(request, active_section="sources-content")
    context.update({"form": form, "source": source, "form_mode": "edit"})
    return render(request, "admin_portal/data_source_form.html", context)


@staff_required
@portal_permission_required("provenance.view_datasource")
@require_http_methods(["GET", "POST"])
def data_source_transition(request: HttpRequest, source_id: int, action: str) -> HttpResponse:
    transition = SOURCE_TRANSITIONS.get(action)
    if transition is None:
        raise Http404
    if not request.user.has_perm(transition.permission):
        raise PermissionDenied
    source = get_object_or_404(DataSource, pk=source_id)
    if (
        source.status != transition.source_status
        or source.is_publicly_releasable != transition.source_public
    ):
        messages.error(request, "That source workflow action is no longer available.")
        return redirect("admin_portal:data-source-detail", source_id=source.pk)
    form = DataSourceTransitionForm(
        request.POST or None,
        initial={
            "expected_status": source.status,
            "expected_public": source.is_publicly_releasable,
        },
    )
    response_status = 200
    if request.method == "POST" and form.is_valid():
        try:
            transition_source(
                source_id=source.pk,
                action=action,
                actor=request.user,
                expected_status=form.cleaned_data["expected_status"],
                expected_public=form.cleaned_data["expected_public"],
            )
        except DataSource.DoesNotExist:
            raise Http404 from None
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
            response_status = 409
        else:
            messages.success(request, "Source workflow state updated.")
            return redirect("admin_portal:data-source-detail", source_id=source.pk)
    context = _portal_context(request, active_section="sources-content")
    context.update({"form": form, "source": source, "transition": transition})
    return render(
        request,
        "admin_portal/data_source_transition_confirm.html",
        context,
        status=response_status,
    )


@staff_required
@portal_permission_required("admin.view_logentry")
@require_GET
def audit_history(request: HttpRequest) -> HttpResponse:
    module_choices = [
        (f"{app_label}.{model}", label) for (app_label, model), label in AUDIT_MODULES
    ]
    filters = AuditFilterForm(request.GET, module_choices=module_choices)
    allowed = Q()
    for (app_label, model), _label in AUDIT_MODULES:
        allowed |= Q(content_type__app_label=app_label, content_type__model=model)
    queryset = LogEntry.objects.filter(allowed).select_related("user", "content_type")
    if filters.is_valid():
        if actor := filters.cleaned_data["actor"]:
            queryset = queryset.filter(user=actor)
        if module := filters.cleaned_data["module"]:
            app_label, model = module.split(".", 1)
            queryset = queryset.filter(content_type__app_label=app_label, content_type__model=model)
        if action := filters.cleaned_data["action"]:
            queryset = queryset.filter(action_flag=int(action))
        if date_from := filters.cleaned_data["date_from"]:
            queryset = queryset.filter(action_time__date__gte=date_from)
        if date_to := filters.cleaned_data["date_to"]:
            queryset = queryset.filter(action_time__date__lte=date_to)
    page = Paginator(queryset.order_by("-action_time", "-id"), 50).get_page(request.GET.get("page"))
    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    labels = {key: label for key, label in AUDIT_MODULES}
    for entry in page.object_list:
        entry.portal_module = labels.get(
            (entry.content_type.app_label, entry.content_type.model), "Other"
        )
    context = _portal_context(request, active_section="audit-history")
    context.update(
        {
            "filters": filters,
            "audit_page": page,
            "query_without_page": query_without_page.urlencode(),
        }
    )
    return render(request, "admin_portal/audit_history.html", context)


@staff_required
@require_GET
def section(request: HttpRequest, section_slug: str) -> HttpResponse:
    section_details = SECTIONS.get(section_slug)
    if section_details is None:
        raise Http404
    context = _portal_context(request, active_section=section_slug)
    context["section"] = section_details
    return render(request, "admin_portal/section_placeholder.html", context)
