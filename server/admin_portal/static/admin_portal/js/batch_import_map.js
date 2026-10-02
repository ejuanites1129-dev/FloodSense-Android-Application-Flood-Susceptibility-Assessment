"use strict";
(() => {
  const target = document.querySelector("[data-batch-map]");
  if (!target) return;
  const status = document.querySelector("[data-batch-map-status]");
  const config = JSON.parse(document.getElementById("map-provider-config").textContent);
  const features = JSON.parse(document.getElementById("batch-map-points").textContent).filter(feature => {
    const [lon, lat] = feature.geometry.coordinates;
    return String(lon).trim() && String(lat).trim() && Number.isFinite(Number(lon)) && Number.isFinite(Number(lat)) && Math.abs(Number(lon)) <= 180 && Math.abs(Number(lat)) <= 90;
  }).map(feature => ({...feature, geometry: {...feature.geometry, coordinates: feature.geometry.coordinates.map(Number)}}));
  const collection = {type: "FeatureCollection", features};
  status.textContent = `${features.length} finite coordinate previews. A marker does not mean a row is valid, a center is verified, or a route is safe. Review the row report below.`;
  function osm() {
    if (!window.ol) { status.textContent += " Map unavailable; the coordinate table remains usable."; return; }
    target.replaceChildren();
    const source = new ol.source.Vector({features: new ol.format.GeoJSON().readFeatures(collection, {featureProjection: "EPSG:3857"})});
    const map = new ol.Map({target, layers: [new ol.layer.Tile({source: new ol.source.OSM()}), new ol.layer.Vector({source, style: new ol.style.Style({image: new ol.style.Circle({radius: 6, fill: new ol.style.Fill({color: "#236ca5"}), stroke: new ol.style.Stroke({color: "white", width: 2})})})})], view: new ol.View({center: ol.proj.fromLonLat([120.9647, 14.4629]), zoom: 12})});
    if (features.length) map.getView().fit(source.getExtent(), {padding: [35, 35, 35, 35], maxZoom: 15});
    status.textContent += " Basemap: OpenStreetMap background context only.";
  }
  if (config.provider !== "mapbox" || !window.mapboxgl || !config.mapbox_public_token) { osm(); return; }
  mapboxgl.accessToken = config.mapbox_public_token;
  target.replaceChildren();
  let map;
  try { map = new mapboxgl.Map({container: target, style: "mapbox://styles/mapbox/standard", center: [120.9647, 14.4629], zoom: 12, attributionControl: true}); }
  catch { osm(); return; }
  let loaded = false;
  // One-time asset timeout, not monitoring or polling.
  const guard = setTimeout(() => { if (!loaded) { map.remove(); osm(); } }, 12000);
  map.once("load", () => {
    loaded = true; clearTimeout(guard);
    map.addSource("batch-coordinate-preview", {type: "geojson", data: collection});
    map.addLayer({id: "batch-coordinate-preview", type: "circle", source: "batch-coordinate-preview", paint: {"circle-radius": 6, "circle-color": "#236ca5", "circle-stroke-color": "white", "circle-stroke-width": 2}});
    if (features.length) {
      const bounds = new mapboxgl.LngLatBounds();
      features.forEach(f => bounds.extend(f.geometry.coordinates));
      map.fitBounds(bounds, {padding: 35, maxZoom: 15, duration: 0});
    }
    map.on("click", "batch-coordinate-preview", e => new mapboxgl.Popup().setLngLat(e.lngLat).setText(e.features[0].properties.label).addTo(map));
    status.textContent += " Basemap: Mapbox background context only.";
  });
})();
