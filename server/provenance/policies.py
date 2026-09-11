"""Shared operating-mode and publication policies for public data use."""

from typing import Any

from django.db.models import QuerySet

from .models import DataSource, PublicationStatus

DEMONSTRATION_MODE = "DEMONSTRATION"
OFFICIAL_MODE = "OFFICIAL"
OPERATING_MODES = (DEMONSTRATION_MODE, OFFICIAL_MODE)

DEMONSTRATION_WARNING = "DEMONSTRATION DATA—NOT OFFICIAL"
NON_AUTHORITY_WARNING = (
    "This result is not an official flood forecast, warning, or emergency instruction."
)


def normalize_operating_mode(mode: str) -> str:
    """Return a controlled uppercase operating mode or raise ``ValueError``."""

    normalized_mode = str(mode).strip().upper()
    if normalized_mode not in OPERATING_MODES:
        choices = ", ".join(OPERATING_MODES)
        raise ValueError(f"Choose one of: {choices}.")
    return normalized_mode


def permitted_records(queryset: QuerySet, mode: str) -> QuerySet:
    """Filter source-backed records to those usable in an operating mode."""

    normalized_mode = normalize_operating_mode(mode)
    if normalized_mode == DEMONSTRATION_MODE:
        return queryset.filter(
            status=PublicationStatus.DEMONSTRATION,
            source__status=PublicationStatus.DEMONSTRATION,
            source__source_type=DataSource.SourceType.DEMONSTRATION,
        )
    return queryset.filter(
        status=PublicationStatus.APPROVED,
        source__status=PublicationStatus.APPROVED,
        source__is_publicly_releasable=True,
    ).exclude(source__source_type=DataSource.SourceType.DEMONSTRATION)


def record_is_permitted(record: Any, mode: str) -> bool:
    """Check one source-backed model instance against the shared mode policy."""

    normalized_mode = normalize_operating_mode(mode)
    source: DataSource = record.source
    if normalized_mode == DEMONSTRATION_MODE:
        return (
            record.status == PublicationStatus.DEMONSTRATION
            and source.status == PublicationStatus.DEMONSTRATION
            and source.source_type == DataSource.SourceType.DEMONSTRATION
        )
    return (
        record.status == PublicationStatus.APPROVED
        and source.status == PublicationStatus.APPROVED
        and source.source_type != DataSource.SourceType.DEMONSTRATION
        and source.is_publicly_releasable
    )


def data_status_for_mode(mode: str) -> str:
    """Return the publication status represented by an operating mode."""

    normalized_mode = normalize_operating_mode(mode)
    if normalized_mode == DEMONSTRATION_MODE:
        return PublicationStatus.DEMONSTRATION
    return PublicationStatus.APPROVED


def warnings_for_mode(mode: str) -> list[str]:
    """Return permanent user-facing limitations for an operating mode."""

    normalized_mode = normalize_operating_mode(mode)
    if normalized_mode == DEMONSTRATION_MODE:
        return [DEMONSTRATION_WARNING, NON_AUTHORITY_WARNING]
    return [NON_AUTHORITY_WARNING]
