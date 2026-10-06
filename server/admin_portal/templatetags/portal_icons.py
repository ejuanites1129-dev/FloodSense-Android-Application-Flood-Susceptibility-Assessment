"""Approved decorative icons; navigation and permissions stay in the existing views."""

from django import template

register = template.Library()

NAVIGATION_ICONS = {
    "dashboard": "monitor",
    "reports": "chart-column-increasing",
    "map-data": "map-pinned",
    "dss-content": "book-bookmark",
    "rainfall-references": "cloud",
    "evacuation-centers": "house",
    "sources-content": "folder",
    "audit-history": "clock",
}

PORTAL_ICONS = {
    **NAVIGATION_ICONS,
    "settings": "settings",
    "sign-out": "square-arrow-right-exit",
}


@register.inclusion_tag("admin_portal/includes/icon.html")
def portal_icon(slug, fallback=""):
    icon = PORTAL_ICONS.get(slug)
    return {
        "asset": f"admin_portal/icons/lucide/{icon}.svg" if icon else None,
        "fallback": fallback,
    }
