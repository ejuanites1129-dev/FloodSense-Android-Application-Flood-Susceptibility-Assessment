(() => {
  "use strict";
  const mapElement = document.querySelector("[data-center-map]");
  const statusElement = document.querySelector("[data-center-map-status]");
  if (!mapElement) return;

  const configElement = document.getElementById("map-provider-config");
  let config = {provider: "osm", allow_3d: false};
  try {
    if (configElement) config = JSON.parse(configElement.textContent);
  } catch {
    config = {provider: "osm", allow_3d: false};
  }

  const latitudeInput = document.querySelector("#id_latitude");
  const longitudeInput = document.querySelector("#id_longitude");
  const defaultLatitude = Number(mapElement.dataset.latitude || 14.4629);
  const defaultLongitude = Number(mapElement.dataset.longitude || 120.9647);
  const markerColor = window.getComputedStyle(document.documentElement)
    .getPropertyValue("--brand").trim() || "#1a94d5";
  let adapter = null;
  let providerFallback = false;
  let bothProvidersUnavailable = false;
  let enhancedBasemapIssue = false;

  function showProviderAttribution(provider) {
    document.querySelectorAll("[data-provider-attribution]").forEach(element => {
      element.hidden = element.dataset.providerAttribution !== provider;
    });
  }

  function coordinateValues() {
    const latitudeValue = latitudeInput ? latitudeInput.value.trim() : String(defaultLatitude);
    const longitudeValue = longitudeInput ? longitudeInput.value.trim() : String(defaultLongitude);
    if (!latitudeValue || !longitudeValue) {
      return {valid: false, empty: true, latitudeValue, longitudeValue};
    }
    const latitude = Number(latitudeValue);
    const longitude = Number(longitudeValue);
    const valid = Number.isFinite(latitude) && Number.isFinite(longitude)
      && latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
    return {valid, empty: false, latitude, longitude, latitudeValue, longitudeValue};
  }

  function refresh() {
    const values = coordinateValues();
    if (!values.valid) {
      adapter?.hidePoint();
      if (statusElement) {
        statusElement.textContent = values.empty
          ? "Enter both latitude and longitude to preview a marker."
          : "The marker is hidden because the coordinates are outside valid WGS 84 ranges.";
      }
      return;
    }
    adapter?.setPoint(values.latitude, values.longitude);
    if (statusElement) {
      const prefix = providerFallback
        ? "Enhanced map unavailable; standard map is active. "
        : bothProvidersUnavailable ? "Map preview unavailable. " : "";
      const suffix = enhancedBasemapIssue
        ? " Some enhanced basemap resources could not load; the coordinate marker remains usable."
        : "";
      statusElement.textContent = `${prefix}Preview marker at latitude ${values.latitudeValue}, longitude ${values.longitudeValue}. This does not verify the center or route safety.${suffix}`;
    }
  }

  function initializeOpenLayers() {
    if (!window.ol) {
      showProviderAttribution(null);
      bothProvidersUnavailable = true;
      adapter = null;
      refresh();
      return false;
    }
    const ol = window.ol;
    showProviderAttribution("osm");
    mapElement.textContent = "";
    const point = new ol.Feature();
    point.setStyle(new ol.style.Style({
      image: new ol.style.Circle({
        radius: 8,
        fill: new ol.style.Fill({color: markerColor}),
        stroke: new ol.style.Stroke({color: "#ffffff", width: 3}),
      }),
    }));
    const basemap = new ol.source.OSM();
    const map = new ol.Map({
      target: mapElement,
      layers: [
        new ol.layer.Tile({source: basemap}),
        new ol.layer.Vector({source: new ol.source.Vector({features: [point]})}),
      ],
      controls: [new ol.control.Zoom(), new ol.control.Attribution({collapsible: false})],
      view: new ol.View({
        center: ol.proj.fromLonLat([defaultLongitude, defaultLatitude]),
        zoom: 14,
      }),
    });
    adapter = {
      kind: "osm",
      hidePoint: () => point.setGeometry(undefined),
      setPoint: (latitude, longitude) => {
        const coordinate = ol.proj.fromLonLat([longitude, latitude]);
        point.setGeometry(new ol.geom.Point(coordinate));
        map.getView().setCenter(coordinate);
      },
    };
    basemap.on("tileloaderror", () => {
      if (statusElement && !statusElement.textContent.includes("Basemap tiles")) {
        statusElement.textContent += " Basemap tiles could not load; the labeled coordinates remain usable.";
      }
    });
    refresh();
    return true;
  }

  function initializeMapbox() {
    return new Promise((resolve, reject) => {
      if (!window.mapboxgl || !config.mapbox_public_token) {
        reject(new Error("Map provider unavailable"));
        return;
      }
      window.mapboxgl.accessToken = config.mapbox_public_token;
      mapElement.textContent = "";
      const map = new window.mapboxgl.Map({
        container: mapElement,
        style: "mapbox://styles/mapbox/standard",
        center: [defaultLongitude, defaultLatitude],
        zoom: 14,
        pitch: 0,
        bearing: 0,
        attributionControl: true,
      });
      map.addControl(new window.mapboxgl.NavigationControl({showCompass: true}), "top-right");
      let loaded = false;
      const loadGuard = window.setTimeout(() => {
        if (!loaded) {
          map.remove();
          reject(new Error("Map provider timed out"));
        }
      }, 12000);
      const marker = new window.mapboxgl.Marker({color: markerColor});
      map.once("load", () => {
        try {
          showProviderAttribution("mapbox");
          loaded = true;
          window.clearTimeout(loadGuard);
          map.setConfigProperty("basemap", "theme", "monochrome");
          map.setConfigProperty("basemap", "lightPreset", "day");
          map.setConfigProperty("basemap", "show3dObjects", Boolean(config.allow_3d));
          adapter = {
            kind: "mapbox",
            hidePoint: () => marker.remove(),
            setPoint: (latitude, longitude) => {
              marker.setLngLat([longitude, latitude]).addTo(map);
              map.easeTo({center: [longitude, latitude], zoom: Math.max(map.getZoom(), 14)});
            },
          };
          refresh();
          resolve();
        } catch (error) {
          map.remove();
          reject(error);
        }
      });
      map.on("error", () => {
        // Recoverable Mapbox resource errors must not remove an otherwise
        // usable preview. A style that never loads is handled by loadGuard.
        if (!loaded || adapter?.kind !== "mapbox") return;
        enhancedBasemapIssue = true;
        refresh();
      });
    });
  }

  if (latitudeInput && longitudeInput) {
    latitudeInput.addEventListener("input", refresh);
    longitudeInput.addEventListener("input", refresh);
  }

  if (config.provider === "mapbox") {
    initializeMapbox().catch(() => {
      providerFallback = true;
      initializeOpenLayers();
    });
  } else if (!initializeOpenLayers()) {
    if (statusElement) {
      statusElement.textContent = "Map preview unavailable. Review the labeled latitude and longitude fields independently.";
    }
  }
})();
