"""Safe client configuration for optional map presentation providers."""

from typing import Any

from django.conf import settings


def get_map_client_config() -> dict[str, Any]:
    requested = str(getattr(settings, "FLOODSENSE_MAP_PROVIDER", "mapbox")).lower()
    if requested not in {"auto", "mapbox", "osm"}:
        requested = "auto"
    token = str(getattr(settings, "MAPBOX_ACCESS_TOKEN", "")).strip()
    public_token = token if token.startswith("pk.") else ""
    mapbox_enabled = requested != "osm" and bool(public_token)
    root = str(
        getattr(
            settings,
            "MAPBOX_GL_JS_ROOT",
            "https://api.mapbox.com/mapbox-gl-js/v3.30.0",
        )
    ).rstrip("/")
    return {
        "provider": "mapbox" if mapbox_enabled else "osm",
        "requested_provider": requested,
        "mapbox_enabled": mapbox_enabled,
        "mapbox_public_token": public_token if mapbox_enabled else "",
        "allow_3d": bool(getattr(settings, "FLOODSENSE_MAP_3D", False)),
        "mapbox_css_url": f"{root}/mapbox-gl.css" if mapbox_enabled else "",
        "mapbox_js_url": f"{root}/mapbox-gl.js" if mapbox_enabled else "",
    }
