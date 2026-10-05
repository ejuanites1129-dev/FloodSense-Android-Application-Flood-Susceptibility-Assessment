"""Public, bounded, read-only nearest-center HTTP boundary."""

from urllib.parse import urlsplit

from rest_framework.exceptions import (
    MethodNotAllowed,
    NotFound,
    ParseError,
    Throttled,
    UnsupportedMediaType,
)
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .catalog import NearbyMapRequestSerializer
from .contracts import (
    INTERNAL_ERROR_DETAIL,
    MALFORMED_JSON_DETAIL,
    METHOD_NOT_ALLOWED_DETAIL,
    NEAREST_CENTER_ALLOWED_METHODS,
    NEAREST_CENTER_MAX_REQUEST_BYTES,
    THROTTLED_DETAIL,
    UNSUPPORTED_MEDIA_DETAIL,
)
from .parsers import LimitedJSONParser, NearestCenterRequestTooLarge
from .serializers import NearestCenterRequestSerializer
from .services import find_nearest_eligible_centers
from .throttles import NearestCenterThrottle


class NearestCenterView(APIView):
    request_serializer_class = NearestCenterRequestSerializer
    authentication_classes = ()
    permission_classes = (AllowAny,)
    parser_classes = (LimitedJSONParser,)
    renderer_classes = (JSONRenderer,)
    throttle_classes = (NearestCenterThrottle,)
    throttle_scope = "nearest_centers"
    http_method_names = ("post", "options")

    def perform_content_negotiation(self, request, force=False):
        # This endpoint always speaks JSON, including for HTML Accept/format
        # preferences. No browsable renderer or reflected negotiation errors.
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get_throttles(self):
        # Metadata and rejected methods never run spatial work or consume quota.
        return super().get_throttles() if self.request.method == "POST" else []

    def post(self, request):
        try:
            declared_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            raise ParseError(MALFORMED_JSON_DETAIL) from None
        if declared_length > NEAREST_CENTER_MAX_REQUEST_BYTES:
            raise NearestCenterRequestTooLarge()
        if declared_length < 0:
            raise ParseError(MALFORMED_JSON_DETAIL)

        # Read the exposed request stream directly: DRF's request.data skips
        # parsing when Content-Length is missing/zero, even on an ASGI stream
        # containing bytes. The parser bounds actual bytes, independently.
        data = self.get_parsers()[0].parse(
            request,
            media_type=request.content_type,
            parser_context={"encoding": request.encoding or "utf-8"},
        )
        serializer = self.request_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = self.lookup_centers(serializer.validated_data)
        except Exception:
            # Service already validates its output. Fail closed on DB failures
            # or broken service invariants, without logging exceptions/locals.
            return Response({"detail": INTERNAL_ERROR_DETAIL}, status=500)
        return Response(payload)

    def lookup_centers(self, inputs):
        from core.local_testing import local_testing_enabled

        if local_testing_enabled(self.request):
            from .local_preview import find_nearest_demonstration_centers

            return find_nearest_demonstration_centers(approved_testing=True, **inputs)
        return find_nearest_eligible_centers(**inputs)

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        for exception_type, detail in (
            (ParseError, MALFORMED_JSON_DETAIL),
            (UnsupportedMediaType, UNSUPPORTED_MEDIA_DETAIL),
            (MethodNotAllowed, METHOD_NOT_ALLOWED_DETAIL),
            (Throttled, THROTTLED_DETAIL),
        ):
            if isinstance(exc, exception_type):
                response.data = {"detail": detail}
                break
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Pragma"] = "no-cache"
        response["Allow"] = ", ".join(NEAREST_CENTER_ALLOWED_METHODS)
        return response


class LocalPreviewNearestCenterView(NearestCenterView):
    """Unavailable outside an explicitly enabled loopback development session."""

    def initial(self, request, *args, **kwargs):
        from .local_preview import local_preview_enabled

        if (
            not local_preview_enabled()
            or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
            or urlsplit("http://" + request.get_host()).hostname
            not in {"127.0.0.1", "localhost", "::1"}
        ):
            raise NotFound
        super().initial(request, *args, **kwargs)

    def lookup_centers(self, inputs):
        from .local_preview import find_nearest_demonstration_centers

        return find_nearest_demonstration_centers(**inputs)


class MapCenterView(NearestCenterView):
    """Public reference GET or bounded, read-only pin-centered POST."""

    request_serializer_class = NearbyMapRequestSerializer

    http_method_names = ("get", "post", "options")

    def get_throttles(self):
        # Share the existing bounded public discovery budget, not its payload.
        return APIView.get_throttles(self) if self.request.method in {"GET", "POST"} else []

    def post(self, request):
        from .catalog import MAP_INPUT_ERROR

        if request.query_params:
            return Response({"detail": MAP_INPUT_ERROR}, status=400)
        return super().post(request)

    def lookup_centers(self, inputs):
        from core.local_testing import local_testing_enabled

        from .catalog import find_map_centers

        return find_map_centers(approved_testing=local_testing_enabled(self.request), **inputs)

    def get(self, request):
        from core.local_testing import local_testing_enabled

        from .catalog import MAP_INPUT_ERROR, MAP_INTERNAL_ERROR, find_map_centers

        if request.query_params or request.META.get("CONTENT_LENGTH") not in (None, "", "0"):
            return Response({"detail": MAP_INPUT_ERROR}, status=400)
        try:
            payload = find_map_centers(approved_testing=local_testing_enabled(request))
        except Exception:
            return Response({"detail": MAP_INTERNAL_ERROR}, status=500)
        return Response(payload)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Allow"] = "GET, POST, OPTIONS"
        return response
