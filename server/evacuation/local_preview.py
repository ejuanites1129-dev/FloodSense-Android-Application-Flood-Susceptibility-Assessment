"""Opt-in local synthetic display QA, separate from verified resident records."""

from core.local_testing import local_testing_enabled
from django.conf import settings
from django.contrib.gis.db.models import PointField
from django.db.models import BooleanField, Case, F, Func, Q, Value, When
from geography.constants import BACOOR_REFERENCE_LIMITATION, BACOOR_REFERENCE_WARNING
from provenance.models import DataSource, PublicationStatus
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .contracts import DISTANCE_METHOD, DISTANCE_UNIT, DISTANCE_WARNING, EMPTY_DISTANCE_WARNING
from .models import EvacuationCenter
from .serializers import (
    ISODateField,
    NearestCenterRequestSerializer,
    PublicCenterSerializer,
    PublicTextField,
    StrictObjectSerializer,
)
from .services import _distance_expression, ready_reference_barangays

LOCAL_PREVIEW_WARNING = (
    "LOCAL DEMONSTRATION - NOT A REAL EVACUATION CENTER. "
    "Display test only; not verified, open, or available for use."
)


def local_preview_enabled():
    database = settings.DATABASES["default"]
    return bool(
        settings.DEBUG
        and settings.ENABLE_LOCAL_CENTER_PREVIEW
        and database.get("HOST") in {"localhost", "127.0.0.1", "::1"}
        and database.get("ENGINE") == "django.contrib.gis.db.backends.postgis"
    )


class LocalPreviewCenterSerializer(PublicCenterSerializer):
    data_status = serializers.ChoiceField((PublicationStatus.DEMONSTRATION,))
    verified_on = ISODateField(allow_null=True)

    def validate_verified_on(self, value):
        if value is not None:
            raise serializers.ValidationError("A synthetic preview is not facility verification.")
        return value

    def validate_name(self, value):
        if self.context.get("require_test_name", True) and not value.startswith("LOCAL TEST -"):
            raise serializers.ValidationError("A local preview requires an explicit test title.")
        return value

    def validate_limitations(self, value):
        if value[:3] != [
            LOCAL_PREVIEW_WARNING,
            BACOOR_REFERENCE_WARNING,
            BACOOR_REFERENCE_LIMITATION,
        ]:
            raise serializers.ValidationError("Local test limitations are required.")
        return value


class LocalPreviewResponseSerializer(StrictObjectSerializer):
    data_status = serializers.ChoiceField((PublicationStatus.DEMONSTRATION,))
    centers = serializers.ListField(child=LocalPreviewCenterSerializer(), max_length=10)
    distance_method = serializers.ChoiceField((DISTANCE_METHOD,))
    warnings = serializers.ListField(child=PublicTextField(), allow_empty=False)

    def validate(self, attrs):
        warning = DISTANCE_WARNING if attrs["centers"] else EMPTY_DISTANCE_WARNING
        if attrs["warnings"] != [LOCAL_PREVIEW_WARNING, warning]:
            raise serializers.ValidationError("Local preview warning is required.")
        identifiers = [row["public_identifier"] for row in attrs["centers"]]
        if len(set(identifiers)) != len(identifiers):
            raise serializers.ValidationError("Duplicate preview identifiers.")
        return attrs


def within_assigned_area_expression():
    """Guard invalid decimal coordinates before checking their recorded polygon."""
    return Func(
        F("geographic_area__geometry"),
        Case(
            When(
                Q(latitude__gte=-90, latitude__lte=90) & Q(longitude__gte=-180, longitude__lte=180),
                then=Func(
                    Func(F("longitude"), F("latitude"), function="ST_MakePoint"),
                    Value(4326),
                    function="ST_SetSRID",
                    output_field=PointField(srid=4326),
                ),
            ),
            default=Value(None),
            output_field=PointField(srid=4326),
        ),
        function="ST_Covers",
        output_field=BooleanField(),
    )


def eligible_local_center_candidates(identities, *, approved_testing=False):
    """Existing temporary-record gates shared by map and nearest-center lookup."""
    candidates = (
        EvacuationCenter.objects.filter(
            publication_status=PublicationStatus.DEMONSTRATION,
            verification_status__in=("VERIFIED",) if approved_testing else ("DRAFT", "IN_REVIEW"),
            verified_on__isnull=True,
            capacity__isnull=True,
            source__source_type=DataSource.SourceType.DEMONSTRATION,
            source__status=PublicationStatus.DEMONSTRATION,
            source__is_publicly_releasable=False,
            geographic_area_id__in=identities,
            geographic_area__is_enabled=True,
            latitude__gte=-90,
            latitude__lte=90,
            longitude__gte=-180,
            longitude__lte=180,
        )
        .annotate(within_area=within_assigned_area_expression())
        .filter(within_area=True)
    )
    if approved_testing:
        return candidates.filter(
            source__reviewed_on__isnull=False, source__reviewed_by__isnull=False
        )
    return candidates.filter(name__startswith="LOCAL TEST -")


def find_nearest_demonstration_centers(*, approved_testing=False, **inputs):
    if not (local_testing_enabled() if approved_testing else local_preview_enabled()):
        raise PermissionDenied
    request = NearestCenterRequestSerializer(data=inputs)
    request.is_valid(raise_exception=True)
    coordinates = request.validated_data
    identities = ready_reference_barangays()
    centers = []
    if identities:
        # These gates deliberately never admit approved/verified facility rows.
        candidates = (
            eligible_local_center_candidates(identities, approved_testing=approved_testing)
            .annotate(
                distance_meters=_distance_expression(
                    latitude=coordinates["latitude"], longitude=coordinates["longitude"]
                ),
            )
            .order_by("distance_meters", "public_id")
            .values(
                "public_id",
                "name",
                "address",
                "geographic_area_id",
                "latitude",
                "longitude",
                "distance_meters",
                "limitations",
                "source__organization",
                "source__limitations",
            )
        )
        for row in candidates:
            limitations = [
                LOCAL_PREVIEW_WARNING,
                BACOOR_REFERENCE_WARNING,
                BACOOR_REFERENCE_LIMITATION,
            ]
            for text in (row["limitations"], row["source__limitations"]):
                if text.strip() and text.strip() not in limitations:
                    limitations.append(text.strip())
            serializer = LocalPreviewCenterSerializer(
                context={"require_test_name": not approved_testing},
                data={
                    "data_status": PublicationStatus.DEMONSTRATION,
                    "public_identifier": str(row["public_id"]),
                    "name": row["name"],
                    "address": row["address"],
                    "barangay": identities[row["geographic_area_id"]],
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "approximate_distance": row["distance_meters"],
                    "distance_unit": DISTANCE_UNIT,
                    "verified_on": None,
                    "source_attribution": row["source__organization"],
                    "limitations": limitations,
                },
            )
            if serializer.is_valid():
                center = dict(serializer.data)
                center["approximate_distance"] = round(center["approximate_distance"], 1)
                centers.append(center)
                if len(centers) == coordinates["limit"]:
                    break
    # Child validation shares the explicit local environment, not a name convention.
    result = LocalPreviewResponseSerializer(
        context={"require_test_name": not approved_testing},
        data={
            "data_status": PublicationStatus.DEMONSTRATION,
            "centers": centers,
            "distance_method": DISTANCE_METHOD,
            "warnings": [
                LOCAL_PREVIEW_WARNING,
                DISTANCE_WARNING if centers else EMPTY_DISTANCE_WARNING,
            ],
        },
    )
    result.is_valid(raise_exception=True)
    return dict(result.data)
