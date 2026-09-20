"""SELECT-only internal nearest-center service; no HTTP endpoint or location history."""

from math import isfinite

from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.contrib.gis.db.models.functions import IsEmpty, IsValid
from django.db.models import BooleanField, Case, F, FloatField, Func, Q, Value, When
from django.db.models.functions import Cast
from geography.constants import (
    BACOOR_CITY_CODE,
    BACOOR_REFERENCE_BARANGAY_COUNT,
    BACOOR_REFERENCE_LIMITATION,
    BACOOR_REFERENCE_SOURCE_NAME,
    BACOOR_REFERENCE_WARNING,
)
from geography.models import GeographicArea
from geography.services import eligible_bacoor_reference_barangays, public_psgc_code
from provenance.models import DataSource, PublicationStatus

from .contracts import (
    CENTER_LIMITATION,
    DEFAULT_LIMIT,
    DISTANCE_DECIMAL_PLACES,
    DISTANCE_METHOD,
    DISTANCE_UNIT,
    DISTANCE_WARNING,
    EMPTY_DISTANCE_WARNING,
    EMPTY_WARNING,
)
from .models import EvacuationCenter
from .serializers import (
    CenterBarangaySerializer,
    NearestCenterRequestSerializer,
    NearestCenterResponseSerializer,
    PublicCenterSerializer,
)


def ready_reference_barangays() -> dict[int, dict[str, str]]:
    """Recheck the entire controlled reference set; return no guessed identities."""
    sources = list(
        DataSource.objects.filter(
            name=BACOOR_REFERENCE_SOURCE_NAME,
            source_type=DataSource.SourceType.AGENCY_DATASET,
            status=PublicationStatus.PENDING_VALIDATION,
            is_publicly_releasable=True,
        ).values_list("pk", flat=True)[:2]
    )
    if len(sources) != 1:
        return {}
    cities = list(
        GeographicArea.objects.filter(
            code=BACOOR_CITY_CODE,
            source_id=sources[0],
            area_type=GeographicArea.AreaType.CITY,
            status=PublicationStatus.PENDING_VALIDATION,
            is_enabled=True,
        )
        .annotate(empty=IsEmpty("geometry"), valid=IsValid("geometry"))
        .values("geometry", "empty", "valid")[:2]
    )
    if len(cities) != 1 or cities[0]["empty"] or not cities[0]["valid"]:
        return {}
    rows = list(
        eligible_bacoor_reference_barangays()
        .filter(source_id=sources[0])
        .annotate(empty=IsEmpty("geometry"), valid=IsValid("geometry"))
        .annotate(
            within_city=Case(
                When(
                    valid=True,
                    empty=False,
                    then=Func(
                        F("geometry"),
                        Value(cities[0]["geometry"], output_field=MultiPolygonField(srid=4326)),
                        function="ST_CoveredBy",
                        output_field=BooleanField(),
                    ),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .values("pk", "code", "name", "empty", "valid", "within_city")
    )
    if len(rows) != BACOOR_REFERENCE_BARANGAY_COUNT:
        return {}
    identities = {}
    for row in rows:
        if row["empty"] or not row["valid"] or not row["within_city"]:
            return {}
        identity = CenterBarangaySerializer(
            data={"psgc_code": public_psgc_code(row["code"]), "name": row["name"]}
        )
        if not identity.is_valid():
            return {}
        identities[row["pk"]] = dict(identity.data)
    if len({item["psgc_code"] for item in identities.values()}) != len(rows) or len(
        {item["name"].casefold() for item in identities.values()}
    ) != len(rows):
        return {}
    return identities


def eligible_center_candidates(barangay_ids):
    """Database gates; each candidate still needs strict public-schema validation.

    Only fields needed for public mapping are fetched. No private contact, notes,
    capacity, permitted-use, reviewer, audit or user field enters these rows.
    """
    return (
        EvacuationCenter.objects.filter(
            verification_status=EvacuationCenter.VerificationStatus.VERIFIED,
            publication_status=PublicationStatus.APPROVED,
            verified_on__isnull=False,
            public_id__isnull=False,
            latitude__gte=-90,
            latitude__lte=90,
            longitude__gte=-180,
            longitude__lte=180,
            geographic_area_id__in=barangay_ids,
            geographic_area__is_enabled=True,
            geographic_area__status=PublicationStatus.PENDING_VALIDATION,
            geographic_area__area_type=GeographicArea.AreaType.BARANGAY,
            geographic_area__source__name=BACOOR_REFERENCE_SOURCE_NAME,
            geographic_area__source__source_type=DataSource.SourceType.AGENCY_DATASET,
            geographic_area__source__status=PublicationStatus.PENDING_VALIDATION,
            geographic_area__source__is_publicly_releasable=True,
            source__status=PublicationStatus.APPROVED,
            source__is_publicly_releasable=True,
        )
        .exclude(source__source_type=DataSource.SourceType.DEMONSTRATION)
        .values(
            "public_id",
            "name",
            "address",
            "geographic_area_id",
            "latitude",
            "longitude",
            "verified_on",
            "limitations",
            "source__organization",
            "source__limitations",
        )
    )


def _geography_point(longitude, latitude):
    return Cast(
        Func(
            Func(longitude, latitude, function="ST_MakePoint", output_field=PointField()),
            Value(4326),
            function="ST_SetSRID",
            output_field=PointField(srid=4326),
        ),
        output_field=PointField(srid=4326, geography=True),
    )


def _distance_expression(*, latitude, longitude):
    # Numeric NaN sorts above finite numbers in PostgreSQL; these upper/lower
    # bounds exclude NaN and infinities as well as out-of-range finite values.
    # CASE guards ST_MakePoint itself, independently of WHERE evaluation order.
    valid_coordinate = Q(latitude__gte=-90, latitude__lte=90) & Q(
        longitude__gte=-180, longitude__lte=180
    )
    return Case(
        When(
            valid_coordinate,
            then=Func(
                _geography_point(
                    Cast(F("longitude"), FloatField()), Cast(F("latitude"), FloatField())
                ),
                _geography_point(Value(longitude, FloatField()), Value(latitude, FloatField())),
                Value(True),
                function="ST_Distance",
                output_field=FloatField(),
            ),
        ),
        default=Value(None),
        output_field=FloatField(),
    )


def _public_center(row, barangay):
    """Reject malformed public data before it can consume the requested limit."""
    distance = row["distance_meters"]
    if distance is None or not isfinite(distance) or distance < 0:
        return None
    # Do not silently discard malformed optional caveats and thereby publish a
    # record without a material limitation. PublicTextField checks each value.
    limitations = [CENTER_LIMITATION, BACOOR_REFERENCE_WARNING, BACOOR_REFERENCE_LIMITATION]
    for value in (row["limitations"], row["source__limitations"]):
        if not isinstance(value, str):
            return None
        if text := value.strip():
            if text not in limitations:
                limitations.append(text)
    try:
        payload = {
            "public_identifier": str(row["public_id"]),
            "name": row["name"],
            "address": row["address"],
            "barangay": barangay,
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "approximate_distance": distance,
            "distance_unit": DISTANCE_UNIT,
            "verified_on": row["verified_on"].isoformat(),
            "source_attribution": row["source__organization"],
            "limitations": limitations,
        }
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None
    serializer = PublicCenterSerializer(data=payload)
    if not serializer.is_valid():
        return None
    return dict(serializer.data)


def find_nearest_eligible_centers(*, latitude: float, longitude: float, limit: int = DEFAULT_LIMIT):
    """Return the frozen wire envelope, without persisting or logging user input.

    Invalid caller inputs raise safe DRF ValidationError before any SQL. Database
    failures propagate for the future view's generic failure boundary.
    """
    request = NearestCenterRequestSerializer(
        data={"latitude": latitude, "longitude": longitude, "limit": limit}
    )
    request.is_valid(raise_exception=True)
    inputs = request.validated_data
    identities = ready_reference_barangays()
    centers = []
    if identities:
        candidates = (
            eligible_center_candidates(identities)
            .annotate(
                distance_meters=_distance_expression(
                    latitude=inputs["latitude"], longitude=inputs["longitude"]
                )
            )
            .order_by("distance_meters", "public_id")
        )
        # No SQL slice before validation: an unsafe nearby row must not hide a
        # valid later candidate. One query, no deferred/private model fetches.
        for row in candidates:
            center = _public_center(row, identities[row["geographic_area_id"]])
            if center is not None:
                centers.append(center)
                if len(centers) == inputs["limit"]:
                    break
    for center in centers:
        center["approximate_distance"] = round(
            center["approximate_distance"], DISTANCE_DECIMAL_PLACES
        )
    response = NearestCenterResponseSerializer(
        data={
            "centers": centers,
            "distance_method": DISTANCE_METHOD,
            "warnings": [DISTANCE_WARNING] if centers else [EMPTY_WARNING, EMPTY_DISTANCE_WARNING],
        }
    )
    # This is a programming invariant, not an empty-result fallback.
    response.is_valid(raise_exception=True)
    return dict(response.data)
