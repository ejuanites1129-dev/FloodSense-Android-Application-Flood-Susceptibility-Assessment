"""Read-only map catalog and pin-centered shortlist; no coordinate persistence."""

from core.local_testing import local_testing_enabled
from geography.constants import BACOOR_REFERENCE_LIMITATION, BACOOR_REFERENCE_WARNING
from provenance.models import PublicationStatus
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from .contracts import CENTER_LIMITATION
from .local_preview import (
    LOCAL_PREVIEW_WARNING,
    LocalPreviewCenterSerializer,
    eligible_local_center_candidates,
    within_assigned_area_expression,
)
from .serializers import (
    FiniteJsonNumberField,
    PublicCenterSerializer,
    PublicTextField,
    StrictObjectSerializer,
)
from .services import _distance_expression, eligible_center_candidates, ready_reference_barangays

MAP_MAX_CENTERS = 1000
MAP_NEARBY_CENTERS = 25
MAP_WARNING = (
    "Evacuation-center reference information only. This map does not confirm "
    "that a center is open, available, reachable, or safe."
)
EMPTY_MAP_WARNING = "No eligible verified evacuation-center information is available for this map."
LOCAL_EMPTY_MAP_WARNING = (
    "No locally approved temporary evacuation-center records are available for this map."
)
MAP_LIMIT_WARNING = (
    "Only the first 1,000 eligible centers are shown. Other eligible centers may exist."
)
MAP_NEARBY_LIMIT_WARNING = (
    "Only the 25 nearest eligible centers around the map pin are shown. "
    "Other centers remain hidden until the pin location changes."
)
MAP_INPUT_ERROR = "This map catalog does not accept query parameters or a request body."
MAP_INTERNAL_ERROR = "Evacuation-center map information is temporarily unavailable."


class PublicMapCenterSerializer(PublicCenterSerializer):
    def get_fields(self):
        fields = super().get_fields()
        fields.pop("approximate_distance")
        fields.pop("distance_unit")
        return fields


class LocalMapCenterSerializer(LocalPreviewCenterSerializer):
    def get_fields(self):
        fields = super().get_fields()
        fields.pop("approximate_distance")
        fields.pop("distance_unit")
        return fields


class NearbyMapRequestSerializer(StrictObjectSerializer):
    latitude = FiniteJsonNumberField(min_value=-90, max_value=90)
    longitude = FiniteJsonNumberField(min_value=-180, max_value=180)


def map_warnings(*, populated, temporary=False, has_more=False, nearby=False):
    if temporary:
        warnings = [LOCAL_PREVIEW_WARNING]
        if not populated:
            warnings.append(LOCAL_EMPTY_MAP_WARNING)
    else:
        warnings = [] if populated else [EMPTY_MAP_WARNING]
    warnings.append(MAP_WARNING)
    if has_more:
        warnings.append(MAP_NEARBY_LIMIT_WARNING if nearby else MAP_LIMIT_WARNING)
    return warnings


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid")
        return super().to_internal_value(data)


class MapCenterResponseSerializer(StrictObjectSerializer):
    centers = serializers.ListField(child=PublicMapCenterSerializer(), max_length=MAP_MAX_CENTERS)
    warnings = serializers.ListField(child=PublicTextField(), allow_empty=False)
    has_more = StrictBooleanField()

    def validate(self, attrs):
        nearby = self.context.get("nearby", False)
        maximum = MAP_NEARBY_CENTERS if nearby else MAP_MAX_CENTERS
        if len(attrs["centers"]) > maximum:
            raise serializers.ValidationError("Too many map centers.")
        expected = map_warnings(
            populated=bool(attrs["centers"]),
            temporary="data_status" in attrs,
            has_more=attrs["has_more"],
            nearby=nearby,
        )
        if attrs["warnings"] != expected:
            raise serializers.ValidationError("Map limitations are required.")
        identifiers = [row["public_identifier"] for row in attrs["centers"]]
        if len(set(identifiers)) != len(identifiers):
            raise serializers.ValidationError("Duplicate public identifiers.")
        if attrs["has_more"] and len(attrs["centers"]) != maximum:
            raise serializers.ValidationError("Truncation requires a full result page.")
        return attrs


class LocalMapResponseSerializer(MapCenterResponseSerializer):
    data_status = serializers.ChoiceField((PublicationStatus.DEMONSTRATION,))
    centers = serializers.ListField(child=LocalMapCenterSerializer(), max_length=MAP_MAX_CENTERS)


def _map_center(row, barangay, *, temporary):
    limitations = [
        LOCAL_PREVIEW_WARNING if temporary else CENTER_LIMITATION,
        BACOOR_REFERENCE_WARNING,
        BACOOR_REFERENCE_LIMITATION,
    ]
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
            "verified_on": None if temporary else row["verified_on"].isoformat(),
            "source_attribution": row["source__organization"],
            "limitations": limitations,
        }
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None
    serializer_class = LocalMapCenterSerializer if temporary else PublicMapCenterSerializer
    if temporary:
        payload["data_status"] = PublicationStatus.DEMONSTRATION
    serializer = serializer_class(data=payload, context={"require_test_name": False})
    return dict(serializer.data) if serializer.is_valid() else None


def find_map_centers(*, approved_testing=False, latitude=None, longitude=None):
    """Recheck eligibility; POST ranks all candidates, not a truncated GET page."""
    if approved_testing and not local_testing_enabled():
        raise PermissionDenied
    nearby = latitude is not None or longitude is not None
    if nearby:
        inputs = NearbyMapRequestSerializer(data={"latitude": latitude, "longitude": longitude})
        inputs.is_valid(raise_exception=True)
        latitude = inputs.validated_data["latitude"]
        longitude = inputs.validated_data["longitude"]
    maximum = MAP_NEARBY_CENTERS if nearby else MAP_MAX_CENTERS
    identities = ready_reference_barangays()
    centers = []
    has_more = False
    if identities:
        candidates = (
            eligible_local_center_candidates(identities, approved_testing=True)
            if approved_testing
            else eligible_center_candidates(identities)
            .annotate(within_area=within_assigned_area_expression())
            .filter(within_area=True)
        )
        # Only allowlisted public inputs are loaded, never model/private fields.
        if nearby:
            candidates = candidates.annotate(
                distance_m=_distance_expression(latitude=latitude, longitude=longitude)
            ).order_by("distance_m", "public_id")
        else:
            candidates = candidates.order_by("public_id")
        rows = candidates.values(
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
        # Validate before consuming the cap; one malformed row must not hide a
        # later releasable row. Iterator avoids loading all candidates in memory.
        for row in rows.iterator(chunk_size=200):
            center = _map_center(
                row, identities[row["geographic_area_id"]], temporary=approved_testing
            )
            if center is None:
                continue
            if len(centers) == maximum:
                has_more = True
                break
            centers.append(center)
    payload = {
        "centers": centers,
        "warnings": map_warnings(
            populated=bool(centers), temporary=approved_testing, has_more=has_more, nearby=nearby
        ),
        "has_more": has_more,
    }
    serializer_class = (
        LocalMapResponseSerializer if approved_testing else MapCenterResponseSerializer
    )
    if approved_testing:
        payload["data_status"] = PublicationStatus.DEMONSTRATION
    response = serializer_class(
        data=payload, context={"require_test_name": False, "nearby": nearby}
    )
    response.is_valid(raise_exception=True)
    return dict(response.data)
