"""Small shared authorization, revision and portal-write coordination helpers."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.utils.dateparse import parse_datetime


def require_permission(actor, permission):
    if not actor.is_active or not actor.is_staff or not actor.has_perm(permission):
        raise PermissionDenied


def center_write_lock():
    """Serialize reviewed portal center writes; not a claim about external SQL."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [72651007])


def require_fresh(record, expected):
    if isinstance(expected, str):
        expected = parse_datetime(expected)
    if expected != record.updated_at:
        raise ValidationError("This record changed. Reload and review before trying again.")
