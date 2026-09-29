/* Progressive enhancement: the GET form and detail panel work without this file. */
(() => {
  "use strict";
  const payloadElement = document.getElementById("map-data-payload");
  const configElement = document.getElementById("map-provider-config");
  if (!payloadElement) return;
  const status = document.getElementById("map-status");
  let payload;
  let config = {provider: "osm", allow_3d: false};
  try {
    payload = JSON.parse(payloadElement.textContent);
    if (configElement) config = JSON.parse(configElement.textContent);
  } catch {
    status.textContent = "Map data could not be read. Use the server-rendered area list and details, or reload the page.";
    return;
  }

  const records = new Map(payload.records.map(record => [record.id, record]));
  const buttons = Array.from(document.querySelectorAll("[data-record-id]"));
  const detail = document.getElementById("record-details");
  const search = document.getElementById("area-search");
  const announcement = document.getElementById("selection-announcement");
  const fitButton = document.getElementById("fit-boundaries");
  const perspectiveButton = document.getElementById("toggle-perspective");
  const mapElement = document.getElementById("geographic-map");
  const rootStyles = window.getComputedStyle(document.documentElement);
  const cssColor = (name, fallback) => rootStyles.getPropertyValue(name).trim() || fallback;
  const mapColors = Object.freeze({
    selection: cssColor("--map-selection", "#1a94d5"),
    boundary: cssColor("--map-boundary", "#64748b"),
    boundaryFill: cssColor("--map-boundary-fill", "#94a3b8"),
    demonstration: cssColor("--map-demonstration", "#665477"),
    outside: cssColor("--map-outside", "#475467"),
  });
  let selectedId = detail.dataset.selectedId;
  let showOnMap = () => {};
  let providerFallback = false;
  let enhancedBasemapIssue = false;

  function withAlpha(hexColor, alpha) {
    const match = /^#([0-9a-f]{6})$/i.exec(hexColor);
    if (!match) return hexColor;
    const value = Number.parseInt(match[1], 16);
    return `rgba(${value >> 16},${(value >> 8) & 255},${value & 255},${alpha})`;
  }

  function showProviderAttribution(provider) {
    document.querySelectorAll("[data-provider-attribution]").forEach(element => {
      element.hidden = element.dataset.providerAttribution !== provider;
    });
  }

  function filterRecords() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    buttons.forEach(button => {
      const record = records.get(button.dataset.recordId);
      const matches = `${record.name} ${record.code}`.toLocaleLowerCase().includes(query);
      button.closest("li").hidden = !matches;
      if (matches) visible += 1;
    });
    document.getElementById("area-results").textContent = `${visible} of ${records.size} records shown.`;
    document.getElementById("area-no-results").hidden = visible > 0 || records.size === 0;
  }

  function selectRecord(id, fromMap = false) {
    const record = records.get(id);
    if (!record) return;
    selectedId = id;
    detail.dataset.selectedId = id;
    document.getElementById("detail-heading").textContent = record.name;
    document.getElementById("detail-category").textContent = record.layer_label;
    const fields = record.details.map(field => {
      const row = document.createElement("div");
      const label = document.createElement("dt");
      const value = document.createElement("dd");
      label.textContent = field.label;
      value.textContent = field.value;
      value.dataset.detail = field.key;
      row.append(label, value);
      return row;
    });
    document.getElementById("detail-fields").replaceChildren(...fields);
    document.getElementById("detail-warnings").replaceChildren(...record.warnings.map(warning => {
      const item = document.createElement("li");
      item.textContent = warning;
      return item;
    }));
    buttons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.recordId === id)));
    if (fromMap) {
      const button = buttons.find(item => item.dataset.recordId === id);
      if (button.closest("li").hidden) {
        search.value = "";
        filterRecords();
      }
      const list = document.getElementById("area-list");
      list.scrollTop += button.getBoundingClientRect().top - list.getBoundingClientRect().top - 6;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("area", id);
    window.history.replaceState(null, "", url);
    showOnMap(record, !fromMap);
    announcement.textContent = `Selected ${record.name}. ${record.layer_label}. ${record.status}. ${record.mapped ? "Details updated." : "Not displayed on the map."}`;
  }

  document.getElementById("map-search-controls").hidden = records.size === 0;
  search.addEventListener("input", filterRecords);
  document.getElementById("area-selection-form").addEventListener("submit", event => {
    const id = event.submitter?.dataset.recordId;
    if (!records.has(id)) return;
    event.preventDefault();
    selectRecord(id);
  });
  document.getElementById("area-list").addEventListener("keydown", event => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const visible = buttons.filter(button => !button.closest("li").hidden);
    const current = visible.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const target = event.key === "Home" ? 0 : event.key === "End" ? visible.length - 1
      : Math.max(0, Math.min(visible.length - 1, current + (event.key === "ArrowDown" ? 1 : -1)));
    visible[target].focus();
  });
  filterRecords();

  function unavailableMapStatus() {
    showProviderAttribution(null);
    document.querySelectorAll("[data-layer]").forEach(control => {
      control.disabled = true;
      control.checked = false;
    });
    fitButton.disabled = true;
    if (perspectiveButton) perspectiveButton.disabled = true;
    status.textContent = "The interactive map could not load. Search, area selection, and record details remain available. Reload to retry.";
  }

  function initializeOpenLayers() {
    if (!window.ol) {
      unavailableMapStatus();
      return false;
    }
    try {
      const ol = window.ol;
      showProviderAttribution("osm");
      mapElement.textContent = "";
      const layers = new Map();
      const format = new ol.format.GeoJSON();
      let tileError = false;
      const styleCache = new Map();
      function boundaryStyle(feature) {
        const selected = feature.get("record_id") === selectedId;
        const demo = feature.get("layer_kind") === "demonstration";
        const city = feature.get("area_type") === "CITY";
        const key = `${selected}-${demo}-${city}`;
        if (!styleCache.has(key)) {
          styleCache.set(key, new ol.style.Style({
            stroke: new ol.style.Stroke({
              color: selected ? mapColors.selection : demo ? mapColors.demonstration : mapColors.boundary,
              width: selected ? 3.5 : city ? 2 : 1.5,
              lineDash: demo ? [7, 5] : undefined,
            }),
            fill: city ? undefined : new ol.style.Fill({
              color: selected ? withAlpha(mapColors.selection, 0.28)
                : demo ? withAlpha(mapColors.demonstration, 0.10)
                : withAlpha(mapColors.boundaryFill, 0.12),
            }),
            zIndex: selected ? 3 : city ? 0 : 1,
          }));
        }
        return styleCache.get(key);
      }
      const basemap = new ol.source.OSM();
      const map = new ol.Map({
        target: mapElement,
        layers: [new ol.layer.Tile({source: basemap})],
        controls: [new ol.control.Zoom(), new ol.control.Attribution({collapsible: false})],
        view: new ol.View({center: ol.proj.fromLonLat([120.96, 14.42]), zoom: 12}),
      });

      const cityFeatureJson = payload.layers.administrative.features.find(
        feature => feature.properties.area_type === "CITY",
      );
      let coverageMaskLayer = null;
      if (cityFeatureJson) {
        const cityFeature = format.readFeature(cityFeatureJson, {
          dataProjection: "EPSG:4326",
          featureProjection: "EPSG:3857",
        });
        const cityGeometry = cityFeature.getGeometry();
        const cityPolygons = cityGeometry.getType() === "MultiPolygon"
          ? cityGeometry.getPolygons() : [cityGeometry];
        const outsideGeometry = ol.geom.Polygon.fromExtent(ol.proj.get("EPSG:3857").getExtent());
        const maskFeatures = [new ol.Feature({geometry: outsideGeometry})];
        cityPolygons.forEach(polygon => {
          outsideGeometry.appendLinearRing(polygon.getLinearRing(0).clone());
          for (let index = 1; index < polygon.getLinearRingCount(); index += 1) {
            maskFeatures.push(new ol.Feature({
              geometry: new ol.geom.Polygon([polygon.getLinearRing(index).getCoordinates()]),
            }));
          }
        });
        coverageMaskLayer = new ol.layer.Vector({
          source: new ol.source.Vector({features: maskFeatures}),
          style: new ol.style.Style({fill: new ol.style.Fill({color: withAlpha(mapColors.outside, 0.62)})}),
        });
        map.addLayer(coverageMaskLayer);
      }

      function visibleFeatures() {
        return Array.from(layers.values()).filter(layer => layer.getVisible())
          .flatMap(layer => layer.getSource().getFeatures());
      }
      function updateMapStatus() {
        const visible = visibleFeatures();
        fitButton.disabled = visible.length === 0;
        const admin = visible.filter(feature => feature.get("layer_kind") === "administrative").length;
        const demo = visible.length - admin;
        const prefix = providerFallback ? "Enhanced map unavailable; standard map is active. " : "";
        status.textContent = visible.length
          ? `${prefix}${admin} administrative reference features · ${demo} demonstration-only features visible. No susceptibility classifications are shown.${coverageMaskLayer ? " Gray areas are outside Bacoor assessment coverage." : ""}`
          : `${prefix}No geographic features are visible. Enable an available layer, or use the area list to review records.`;
        if (tileError) status.textContent += " Basemap tiles could not load. Available boundaries and record details remain usable.";
        if (selectedId && !records.get(selectedId)?.mapped) status.textContent += " The selected record is not displayable.";
      }
      function fitVisible() {
        const features = visibleFeatures();
        if (!features.length) return;
        const extent = ol.extent.createEmpty();
        features.forEach(feature => ol.extent.extend(extent, feature.getGeometry().getExtent()));
        map.getView().fit(extent, {padding: [32, 32, 32, 32], maxZoom: 16});
      }
      for (const [key, collection] of Object.entries(payload.layers)) {
        const source = new ol.source.Vector({
          features: format.readFeatures(collection, {dataProjection: "EPSG:4326", featureProjection: "EPSG:3857"}),
        });
        const control = document.querySelector(`[data-layer="${key}"]`);
        control.disabled = source.getFeatures().length === 0;
        control.checked = !control.disabled && (key === "administrative" || payload.layers.administrative.features.length === 0);
        const layer = new ol.layer.Vector({source, style: boundaryStyle, visible: control.checked});
        layers.set(key, layer);
        map.addLayer(layer);
        control.addEventListener("change", () => {
          layer.setVisible(control.checked);
          updateMapStatus();
          if (control.checked) fitVisible();
        });
      }
      showOnMap = (record, fit) => {
        layers.forEach(layer => layer.changed());
        const layer = layers.get(record.layer);
        if (record.mapped && fit) {
          layer.setVisible(true);
          document.querySelector(`[data-layer="${record.layer}"]`).checked = true;
          const feature = layer.getSource().getFeatureById(record.id);
          if (feature) map.getView().fit(feature.getGeometry(), {padding: [40, 40, 40, 40], maxZoom: 16});
        }
        updateMapStatus();
      };
      basemap.on("tileloaderror", () => { tileError = true; updateMapStatus(); });
      fitButton.addEventListener("click", fitVisible);
      map.on("singleclick", event => {
        const hits = [];
        map.forEachFeatureAtPixel(event.pixel, feature => { hits.push(feature); }, {
          hitTolerance: 3,
          layerFilter: layer => layer !== coverageMaskLayer,
        });
        hits.sort((a, b) => Number(a.get("area_type") === "CITY") - Number(b.get("area_type") === "CITY"));
        if (hits.length) selectRecord(hits[0].get("record_id"), true);
      });
      const initial = records.get(selectedId);
      if (initial?.mapped) {
        layers.get(initial.layer).setVisible(true);
        document.querySelector(`[data-layer="${initial.layer}"]`).checked = true;
      }
      fitVisible();
      updateMapStatus();
      observeMapSize(() => map.updateSize());
      return true;
    } catch {
      unavailableMapStatus();
      return false;
    }
  }

  // Observe actual container dimensions during sidebar transitions; never refit
  // bounds here, so zoom, selected record, and layer visibility survive resizing.
  let stopMapResize = () => {};
  function observeMapSize(resize) {
    stopMapResize();
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(resize) : null;
    observer?.observe(mapElement);
    window.addEventListener("resize", resize);
    document.addEventListener("portal:layoutchange", resize);
    stopMapResize = () => {
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      document.removeEventListener("portal:layoutchange", resize);
    };
  }

  function geometryPositions(geometry) {
    const positions = [];
    function visit(value) {
      if (!Array.isArray(value)) return;
      if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
        positions.push(value);
      } else {
        value.forEach(visit);
      }
    }
    visit(geometry.coordinates);
    return positions;
  }

  function coverageMaskFeature(cityFeature) {
    if (!cityFeature) return null;
    const positions = geometryPositions(cityFeature.geometry);
    if (!positions.length) return null;
    const west = Math.min(...positions.map(point => point[0]));
    const east = Math.max(...positions.map(point => point[0]));
    const south = Math.min(...positions.map(point => point[1]));
    const north = Math.max(...positions.map(point => point[1]));
    const margin = Math.max(east - west, north - south, 0.1) * 8;
    const outer = [
      [west - margin, south - margin], [east + margin, south - margin],
      [east + margin, north + margin], [west - margin, north + margin],
      [west - margin, south - margin],
    ];
    const polygons = cityFeature.geometry.type === "MultiPolygon"
      ? cityFeature.geometry.coordinates : [cityFeature.geometry.coordinates];
    return {
      type: "Feature",
      properties: {kind: "outside-coverage"},
      geometry: {
        type: "Polygon",
        coordinates: [outer, ...polygons.map(polygon => [...polygon[0]].reverse())],
      },
    };
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
        center: [120.96, 14.42],
        zoom: 12,
        pitch: 0,
        bearing: 0,
        attributionControl: true,
      });
      observeMapSize(() => map.resize());
      map.addControl(new window.mapboxgl.NavigationControl({showCompass: true}), "top-right");
      let loaded = false;
      let fallbackStarted = false;
      let refreshMapboxStatus = () => {};
      const loadGuard = window.setTimeout(() => {
        if (!loaded) {
          reject(new Error("Map provider timed out"));
          startFallback();
        }
      }, 12000);

      function startFallback() {
        if (fallbackStarted) return;
        fallbackStarted = true;
        providerFallback = true;
        stopMapResize();
        try { map.remove(); } catch { /* The provider may already be detached. */ }
        initializeOpenLayers();
      }

      map.once("load", () => {
        try {
          showProviderAttribution("mapbox");
          map.setConfigProperty("basemap", "theme", "monochrome");
          map.setConfigProperty("basemap", "lightPreset", "day");
          map.setConfigProperty("basemap", "show3dObjects", Boolean(config.allow_3d));

          const cityFeature = payload.layers.administrative.features.find(
            feature => feature.properties.area_type === "CITY",
          );
          const mask = coverageMaskFeature(cityFeature);
          if (mask) {
            map.addSource("floodsense-coverage-mask", {type: "geojson", data: mask});
            map.addLayer({
              id: "floodsense-coverage-mask-fill", type: "fill", source: "floodsense-coverage-mask",
              slot: "middle", paint: {"fill-color": mapColors.outside, "fill-opacity": 0.62},
            });
          }

          const layerDefinitions = new Map();
          for (const [key, collection] of Object.entries(payload.layers)) {
            const sourceId = `floodsense-${key}-source`;
            const fillId = `floodsense-${key}-fill`;
            const lineId = `floodsense-${key}-line`;
            map.addSource(sourceId, {type: "geojson", data: collection});
            map.addLayer({
              id: fillId, type: "fill", source: sourceId, slot: "middle",
              paint: {
                "fill-color": key === "demonstration" ? mapColors.demonstration : mapColors.boundaryFill,
                "fill-opacity": ["case", ["==", ["get", "area_type"], "CITY"], 0,
                  ["==", ["get", "record_id"], selectedId], 0.28,
                  key === "demonstration" ? 0.10 : 0.12],
              },
            });
            map.addLayer({
              id: lineId, type: "line", source: sourceId, slot: "middle",
              paint: {
                "line-color": ["case", ["==", ["get", "record_id"], selectedId], mapColors.selection,
                  key === "demonstration" ? mapColors.demonstration : mapColors.boundary],
                "line-width": ["case", ["==", ["get", "record_id"], selectedId], 3.5,
                  ["==", ["get", "area_type"], "CITY"], 2, 1.5],
                ...(key === "demonstration" ? {"line-dasharray": [3, 2]} : {}),
              },
            });
            const control = document.querySelector(`[data-layer="${key}"]`);
            const enabled = collection.features.length > 0;
            const visible = enabled && (key === "administrative" || payload.layers.administrative.features.length === 0);
            control.disabled = !enabled;
            control.checked = visible;
            map.setLayoutProperty(fillId, "visibility", visible ? "visible" : "none");
            map.setLayoutProperty(lineId, "visibility", visible ? "visible" : "none");
            layerDefinitions.set(key, {collection, fillId, lineId, sourceId, control});
          }

          layerDefinitions.forEach((layer, key) => {
            layer.selectionId = `floodsense-${key}-selection`;
            map.addLayer({
              id: layer.selectionId,
              type: "line",
              source: layer.sourceId,
              slot: "top",
              filter: ["==", ["get", "record_id"], selectedId],
              paint: {"line-color": mapColors.selection, "line-width": 4.5},
            });
            map.setLayoutProperty(
              layer.selectionId,
              "visibility",
              layer.control.checked ? "visible" : "none",
            );
          });

          function visibleFeatures() {
            return Array.from(layerDefinitions.values())
              .filter(layer => layer.control.checked)
              .flatMap(layer => layer.collection.features);
          }
          function updateMapStatus() {
            const visible = visibleFeatures();
            fitButton.disabled = visible.length === 0;
            const admin = visible.filter(feature => feature.properties.layer_kind === "administrative").length;
            const demo = visible.length - admin;
            status.textContent = visible.length
              ? `${admin} administrative reference features · ${demo} demonstration-only features visible. No susceptibility classifications are shown.${mask ? " Gray areas are outside Bacoor assessment coverage." : ""}`
              : "No geographic features are visible. Enable an available layer, or use the area list to review records.";
            if (selectedId && !records.get(selectedId)?.mapped) status.textContent += " The selected record is not displayable.";
            if (enhancedBasemapIssue) status.textContent += " Some enhanced basemap resources could not load; boundaries and record details remain usable.";
          }
          refreshMapboxStatus = updateMapStatus;
          function fitFeatures(features, maximumZoom = 16) {
            const positions = features.flatMap(feature => geometryPositions(feature.geometry));
            if (!positions.length) return;
            const bounds = positions.reduce(
              (result, point) => result.extend(point),
              new window.mapboxgl.LngLatBounds(positions[0], positions[0]),
            );
            map.fitBounds(bounds, {padding: 40, maxZoom: maximumZoom, duration: 400});
          }
          function refreshSelectionPaint() {
            layerDefinitions.forEach((layer, key) => {
              map.setPaintProperty(layer.fillId, "fill-opacity", [
                "case", ["==", ["get", "area_type"], "CITY"], 0,
                ["==", ["get", "record_id"], selectedId], 0.28,
                key === "demonstration" ? 0.10 : 0.12,
              ]);
              map.setPaintProperty(layer.lineId, "line-color", [
                "case", ["==", ["get", "record_id"], selectedId], mapColors.selection,
                key === "demonstration" ? mapColors.demonstration : mapColors.boundary,
              ]);
              map.setPaintProperty(layer.lineId, "line-width", [
                "case", ["==", ["get", "record_id"], selectedId], 3.5,
                ["==", ["get", "area_type"], "CITY"], 2, 1.5,
              ]);
              map.setFilter(layer.selectionId, ["==", ["get", "record_id"], selectedId]);
            });
          }
          layerDefinitions.forEach(layer => {
            layer.control.addEventListener("change", () => {
              const visibility = layer.control.checked ? "visible" : "none";
              map.setLayoutProperty(layer.fillId, "visibility", visibility);
              map.setLayoutProperty(layer.lineId, "visibility", visibility);
              map.setLayoutProperty(layer.selectionId, "visibility", visibility);
              updateMapStatus();
              if (layer.control.checked) fitFeatures(visibleFeatures());
            });
          });
          showOnMap = (record, fit) => {
            refreshSelectionPaint();
            const layer = layerDefinitions.get(record.layer);
            if (record.mapped && fit) {
              layer.control.checked = true;
              map.setLayoutProperty(layer.fillId, "visibility", "visible");
              map.setLayoutProperty(layer.lineId, "visibility", "visible");
              map.setLayoutProperty(layer.selectionId, "visibility", "visible");
              const feature = layer.collection.features.find(item => item.id === record.id);
              if (feature) fitFeatures([feature]);
            }
            updateMapStatus();
          };
          fitButton.addEventListener("click", () => fitFeatures(visibleFeatures()));
          map.on("click", event => {
            const visibleFillLayers = Array.from(layerDefinitions.values())
              .filter(layer => layer.control.checked).map(layer => layer.fillId);
            const hits = map.queryRenderedFeatures(event.point, {layers: visibleFillLayers});
            hits.sort((a, b) => Number(a.properties.area_type === "CITY") - Number(b.properties.area_type === "CITY"));
            if (hits.length) selectRecord(String(hits[0].properties.record_id), true);
          });
          if (perspectiveButton) {
            perspectiveButton.disabled = false;
            perspectiveButton.addEventListener("click", () => {
              const active = perspectiveButton.getAttribute("aria-pressed") !== "true";
              perspectiveButton.setAttribute("aria-pressed", String(active));
              perspectiveButton.textContent = active ? "Overhead view" : "Perspective view";
              map.easeTo({pitch: active ? 45 : 0, bearing: active ? -18 : 0, duration: 450});
            });
          }
          const initial = records.get(selectedId);
          if (initial?.mapped) {
            const layer = layerDefinitions.get(initial.layer);
            layer.control.checked = true;
            map.setLayoutProperty(layer.fillId, "visibility", "visible");
            map.setLayoutProperty(layer.lineId, "visibility", "visible");
            map.setLayoutProperty(layer.selectionId, "visibility", "visible");
          }
          fitFeatures(visibleFeatures(), 14);
          updateMapStatus();
          loaded = true;
          window.clearTimeout(loadGuard);
          resolve();
        } catch (error) {
          reject(error);
          startFallback();
        }
      });
      map.on("error", () => {
        // Mapbox emits `error` for recoverable tile, glyph, image, and model
        // failures as well as fatal style failures. The load timeout handles a
        // style that never becomes usable; do not discard an already usable
        // map and its local GeoJSON overlays because one resource failed.
        if (!loaded) return;
        enhancedBasemapIssue = true;
        refreshMapboxStatus();
      });
    });
  }

  if (config.provider === "mapbox") {
    initializeMapbox().catch(() => {
      if (!providerFallback) {
        providerFallback = true;
        initializeOpenLayers();
      }
    });
  } else {
    initializeOpenLayers();
  }
})();
