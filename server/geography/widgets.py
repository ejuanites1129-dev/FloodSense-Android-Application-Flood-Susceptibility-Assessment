"""GeoDjango widgets customized for FloodSense administration."""

from django.contrib.gis.forms.widgets import OSMWidget
from django.forms import Media

OPENLAYERS_VERSION = "10.8.0"
OPENLAYERS_CDN_ROOT = f"https://cdn.jsdelivr.net/npm/ol@v{OPENLAYERS_VERSION}"


class FloodSenseOSMWidget(OSMWidget):
    """Use OpenLayers with the referrer-policy fix required by OSM tiles."""

    @property
    def media(self) -> Media:
        """Replace, rather than extend, Django's inherited OpenLayers media."""
        return Media(
            css={
                "all": (
                    f"{OPENLAYERS_CDN_ROOT}/ol.css",
                    "gis/css/ol3.css",
                )
            },
            js=(
                f"{OPENLAYERS_CDN_ROOT}/dist/ol.js",
                "gis/js/OLMapWidget.js",
            ),
        )
