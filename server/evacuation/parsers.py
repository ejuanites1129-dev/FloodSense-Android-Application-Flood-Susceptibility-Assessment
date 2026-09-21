"""Bounded JSON parsing without body fragments in public errors."""

import codecs
from io import BytesIO

from django.conf import settings
from django.utils.http import parse_header_parameters
from rest_framework.exceptions import APIException, ParseError, UnsupportedMediaType
from rest_framework.parsers import JSONParser
from rest_framework.utils import json

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

    @staticmethod
    def _unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON object member.")
            value[key] = item
        return value

    def parse(self, stream, media_type=None, parser_context=None):
        content_type, _ = parse_header_parameters(media_type or "")
        if content_type != self.media_type:
            raise UnsupportedMediaType("", detail=UNSUPPORTED_MEDIA_DETAIL)
        body = stream.read(NEAREST_CENTER_MAX_REQUEST_BYTES + 1)
        if len(body) > NEAREST_CENTER_MAX_REQUEST_BYTES:
            raise NearestCenterRequestTooLarge()
        parser_context = parser_context or {}
        encoding = parser_context.get("encoding", settings.DEFAULT_CHARSET)
        try:
            decoded_stream = codecs.getreader(encoding)(BytesIO(body))
            return json.load(
                decoded_stream,
                parse_constant=json.strict_constant,
                object_pairs_hook=self._unique_object,
            )
        except (ValueError, UnicodeError, LookupError, RecursionError):
            raise ParseError(MALFORMED_JSON_DETAIL) from None
