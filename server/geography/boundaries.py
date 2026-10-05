"""Stable boundary identity; display names and local primary keys are not identifiers."""

from django.db.models import Exists, OuterRef

from .constants import BACOOR_CITY_CODE, BACOOR_REFERENCE_SOURCE_NAME
from .models import GeographicArea


def bacoor_boundary_source_id():
    """Follow the unique PSGC City record, including withdrawn records for ownership checks."""
    return (
        GeographicArea.objects.filter(code=BACOOR_CITY_CODE, area_type=GeographicArea.AreaType.CITY)
        .values_list("source_id", flat=True)
        .first()
    )


def bacoor_boundary_source_ids():
    """A SQL subquery avoids extra round trips in resident spatial lookups."""
    return GeographicArea.objects.filter(
        code=BACOOR_CITY_CODE, area_type=GeographicArea.AreaType.CITY
    ).values("source_id")


def is_bacoor_boundary_source(source):
    """Keep renamed/withdrawn boundary provenance distinct from facility evidence."""
    if source.name == BACOOR_REFERENCE_SOURCE_NAME:
        return True
    annotated = getattr(source, "_is_bacoor_boundary_source", None)
    if annotated is not None:
        return annotated
    return source.pk is not None and source.pk == bacoor_boundary_source_id()


def annotate_boundary_source_identity(queryset):
    """Resolve identity inside source-list SQL, not once per displayed row."""
    return queryset.annotate(
        _is_bacoor_boundary_source=Exists(
            GeographicArea.objects.filter(
                code=BACOOR_CITY_CODE,
                area_type=GeographicArea.AreaType.CITY,
                source_id=OuterRef("pk"),
            )
        )
    )
