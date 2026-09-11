"""Database-driven preparedness-guidance selection for FloodSense."""

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError
from expert.models import SusceptibilityLevel
from provenance.policies import normalize_operating_mode, permitted_records

from .models import GuidanceItem


class GuidanceSelectionError(ValidationError):
    """Raised when a requested guidance classification is invalid or ineligible."""


def select_guidance(assessment_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Select guidance for a completed assessment without changing that assessment."""

    assessment_snapshot = deepcopy(assessment_result)
    if assessment_result.get("assessment_state") != "CLASSIFIED":
        return []

    susceptibility = assessment_result.get("susceptibility") or {}
    scenario = assessment_result.get("scenario") or {}
    susceptibility_code = susceptibility.get("code")
    mode = assessment_result.get("operating_mode")
    if not all(
        (
            susceptibility_code,
            mode,
            scenario.get("rainfall_intensity_code"),
            scenario.get("rainfall_duration_code"),
        )
    ):
        return []

    try:
        guidance = select_guidance_for_level(
            susceptibility_code=susceptibility_code,
            mode=mode,
        )
    except GuidanceSelectionError:
        guidance = []
    if assessment_result != assessment_snapshot:
        raise RuntimeError("DSS guidance selection must not modify the assessment result.")
    return guidance


def select_guidance_for_level(
    *,
    susceptibility_code: str,
    mode: str,
) -> list[dict[str, Any]]:
    """Return enabled, mode-permitted guidance in administrator-defined order."""

    try:
        normalized_mode = normalize_operating_mode(mode)
    except ValueError as error:
        raise GuidanceSelectionError({"mode": str(error)}) from None

    levels = permitted_records(
        SusceptibilityLevel.objects.select_related("source").filter(
            code=str(susceptibility_code).strip().upper(),
            is_enabled=True,
        ),
        normalized_mode,
    )
    level = levels.first()
    if level is None:
        raise GuidanceSelectionError(
            {
                "susceptibility_level": (
                    "The selected susceptibility level is unavailable in this mode."
                )
            }
        )

    guidance_items = permitted_records(
        GuidanceItem.objects.select_related("source").filter(
            susceptibility_level=level,
            is_enabled=True,
        ),
        normalized_mode,
    ).order_by("display_order", "id")

    return [_serialize_guidance_item(item) for item in guidance_items]


def _serialize_guidance_item(item: GuidanceItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "instruction": item.instruction,
        "category": item.category,
        "display_order": item.display_order,
        "data_status": item.status,
        "source": {
            "id": item.source_id,
            "name": item.source.name,
            "organization": item.source.organization,
        },
    }
