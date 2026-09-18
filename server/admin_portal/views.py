from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from geography.widgets import OPENLAYERS_CDN_ROOT

from .forms import SettingsInventoryFilterForm, StaffAuthenticationForm
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
            "Prepare the management surface for verified center records supplied by "
            "the responsible data custodian."
        ),
        "day": "Day 6",
    },
    "sources-content": {
        "title": "Sources and content",
        "eyebrow": "Provenance",
        "description": (
            "Track data custody, versions, limitations, and public-facing source "
            "information."
        ),
        "day": "Day 6",
    },
    "audit-history": {
        "title": "Audit history",
        "eyebrow": "Accountability",
        "description": (
            "Review controlled administrative activity once the audit workflow is "
            "implemented."
        ),
        "day": "Day 7",
    },
}


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


def _portal_context(request: HttpRequest, *, active_section: str) -> dict[str, Any]:
    display_name = request.user.display_name.strip() or request.user.email
    initials = "".join(
        part[0].upper() for part in display_name.replace("@", " ").split()[:2] if part
    )
    return {
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
@require_GET
def section(request: HttpRequest, section_slug: str) -> HttpResponse:
    section_details = SECTIONS.get(section_slug)
    if section_details is None:
        raise Http404
    context = _portal_context(request, active_section=section_slug)
    context["section"] = section_details
    return render(request, "admin_portal/section_placeholder.html", context)
