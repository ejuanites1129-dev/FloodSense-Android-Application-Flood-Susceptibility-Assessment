/* Progressive enhancement: the GET form and detail panel work without this file. */
(() => {
  "use strict";
  const payloadElement = document.getElementById("map-data-payload");
  if (!payloadElement) return;
  const status = document.getElementById("map-status");
  let payload;
  try {
    payload = JSON.parse(payloadElement.textContent);
  } catch {
    status.textContent = "Map data could not be read. Use the server-rendered area list and details, or reload the page.";
    return;
  }
  const records = new Map(payload.records.map(record => [record.id, record]));
  const buttons = Array.from(document.querySelectorAll("[data-record-id]"));
  const detail = document.getElementById("record-details");
  const search = document.getElementById("area-search");
  const announcement = document.getElementById("selection-announcement");
  let selectedId = detail.dataset.selectedId;
  let showOnMap = () => {};

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
      // Scroll only the list, keeping the map and the user's keyboard focus in place.
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

  try {
    if (!window.ol) throw new Error("Mapping library unavailable");
    const ol = window.ol;
    const layers = new Map();
    const format = new ol.format.GeoJSON();
    const fitButton = document.getElementById("fit-boundaries");
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
            color: selected ? "#172b4d" : demo ? "#665477" : "#64748b",
            width: selected ? 3.5 : city ? 2 : 1.5,
            lineDash: demo ? [7, 5] : undefined,
          }),
          fill: city ? undefined : new ol.style.Fill({
            color: selected ? "rgba(71,85,105,0.28)" : demo ? "rgba(102,84,119,0.10)" : "rgba(148,163,184,0.12)",
          }),
          zIndex: selected ? 3 : city ? 0 : 1,
        }));
      }
      return styleCache.get(key);
    }
    const basemap = new ol.source.OSM();
    const map = new ol.Map({
      target: "geographic-map",
      layers: [new ol.layer.Tile({source: basemap})],
      controls: [new ol.control.Zoom(), new ol.control.Attribution({collapsible: false})],
      view: new ol.View({center: ol.proj.fromLonLat([120.96, 14.42]), zoom: 12}),
    });

    function visibleFeatures() {
      return Array.from(layers.values()).filter(layer => layer.getVisible())
        .flatMap(layer => layer.getSource().getFeatures());
    }
    function updateMapStatus() {
      const visible = visibleFeatures();
      fitButton.disabled = visible.length === 0;
      const admin = visible.filter(feature => feature.get("layer_kind") === "administrative").length;
      const demo = visible.length - admin;
      status.textContent = visible.length
        ? `${admin} administrative reference features · ${demo} demonstration-only features visible. No susceptibility classifications are shown.`
        : "No geographic features are visible. Enable an available layer, or use the area list to review records.";
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
      map.forEachFeatureAtPixel(event.pixel, feature => { hits.push(feature); }, {hitTolerance: 3});
      // Prefer a barangay over the encompassing city outline at shared borders.
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
  } catch {
    document.querySelectorAll("[data-layer]").forEach(control => { control.disabled = true; control.checked = false; });
    document.getElementById("fit-boundaries").disabled = true;
    status.textContent = "The interactive map could not load. Search, area selection, and record details remain available. Reload to retry.";
  }
})();
