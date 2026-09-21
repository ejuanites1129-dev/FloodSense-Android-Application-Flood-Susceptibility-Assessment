"""Short-lived request-rate metadata, never location or response caching."""

from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle


class NearestCenterThrottle(ScopedRateThrottle):
    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]

    def get_ident(self, request):
        # Ignore client-supplied forwarding headers. A trusted ingress must set
        # REMOTE_ADDR correctly or enforce a per-client limit upstream.
        return request.META.get("REMOTE_ADDR") or "unknown"
