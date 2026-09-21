"""Bounded JSON parsing without body fragments in public errors."""

from io import BytesIO

from django.utils.http import parse_header_parameters
from rest_framework.exceptions import APIException, ParseError, UnsupportedMediaType
from rest_framework.parsers import JSONParser

from .contracts import (
    MALFORMED_JSON_DETAIL,
    NEAREST_CENTER_MAX_REQUEST_BYTES,
    REQUEST_TOO_LARGE_DETAIL,
    UNSUPPORTED_MEDIA_DETAIL,
)


class NearestCenterRequestTooLarge(APIException):
    status_code = 413
    default_detail = REQUEST_TOO_LARGE_DETAIL
    default_code = "request_too_large"


class LimitedJSONParser(JSONParser):
    strict = True

    def parse(self, stream, media_type=None, parser_context=None):
        content_type, _ = parse_header_parameters(media_type or "")
        if content_type != self.media_type:
            raise UnsupportedMediaType("", detail=UNSUPPORTED_MEDIA_DETAIL)
        body = stream.read(NEAREST_CENTER_MAX_REQUEST_BYTES + 1)
        if len(body) > NEAREST_CENTER_MAX_REQUEST_BYTES:
            raise NearestCenterRequestTooLarge()
        try:
            return super().parse(BytesIO(body), media_type, parser_context)
        except (ParseError, UnicodeError, LookupError, RecursionError):
            raise ParseError(MALFORMED_JSON_DETAIL) from None
