"""Frozen Day 1 wire vocabulary; no queries, records, or endpoint registration."""

NEAREST_CENTER_PATH = "/api/v1/evacuation-centers/nearest/"
NEAREST_CENTER_CONTENT_TYPE = "application/json"
NEAREST_CENTER_ALLOWED_METHODS = ("POST", "OPTIONS")
DEFAULT_LIMIT = 3
MIN_LIMIT = 1
MAX_LIMIT = 10
DISTANCE_METHOD = "APPROXIMATE_STRAIGHT_LINE"
DISTANCE_UNIT = "meters"
DISTANCE_DECIMAL_PLACES = 1

DISTANCE_WARNING = (
    "Distances are approximate straight-line measurements. They do not represent "
    "road distance, route safety, accessibility, availability, or an evacuation recommendation."
)
EMPTY_WARNING = "No eligible verified evacuation centers are currently available for this location."
EMPTY_DISTANCE_WARNING = (
    "Distances, when available, are approximate straight-line measurements "
    "and are not route-safety recommendations."
)
CENTER_LIMITATION = (
    "Verification does not confirm current opening, accessibility, capacity, or route safety."
)
INTERNAL_ERROR_DETAIL = "Nearest-center lookup is temporarily unavailable."

# Reviewed Day 3 HTTP controls; the Day 1 request/response schema is unchanged.
NEAREST_CENTER_MAX_REQUEST_BYTES = 1024
REQUEST_TOO_LARGE_DETAIL = "Nearest-center request is too large."
THROTTLED_DETAIL = "Too many nearest-center requests. Try again later."
MALFORMED_JSON_DETAIL = "Malformed JSON."
UNSUPPORTED_MEDIA_DETAIL = "Unsupported media type. Use application/json."
METHOD_NOT_ALLOWED_DETAIL = "Method not allowed."
