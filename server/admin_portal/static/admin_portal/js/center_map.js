(() => {
  const mapElement = document.querySelector("[data-center-map]");
  if (!mapElement || typeof window.ol === "undefined") return;
  mapElement.textContent = "";

  const latitudeInput = document.querySelector("#id_latitude");
  const longitudeInput = document.querySelector("#id_longitude");
  const defaultLatitude = Number(mapElement.dataset.latitude || 14.4629);
  const defaultLongitude = Number(mapElement.dataset.longitude || 120.9647);
  const point = new ol.Feature();
  point.setStyle(new ol.style.Style({
    image: new ol.style.Circle({
      radius: 8,
      fill: new ol.style.Fill({ color: "#0878b7" }),
      stroke: new ol.style.Stroke({ color: "#ffffff", width: 3 }),
    }),
  }));
  const vectorSource = new ol.source.Vector({ features: [point] });
  const map = new ol.Map({
    target: mapElement,
    layers: [
      new ol.layer.Tile({ source: new ol.source.OSM() }),
      new ol.layer.Vector({ source: vectorSource }),
    ],
    view: new ol.View({
      center: ol.proj.fromLonLat([defaultLongitude, defaultLatitude]),
      zoom: 14,
    }),
  });

  const refresh = () => {
    const latitudeValue = latitudeInput ? latitudeInput.value.trim() : String(defaultLatitude);
    const longitudeValue = longitudeInput ? longitudeInput.value.trim() : String(defaultLongitude);
    if (!latitudeValue || !longitudeValue) {
      point.setGeometry(undefined);
      return;
    }
    const latitude = Number(latitudeValue);
    const longitude = Number(longitudeValue);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      point.setGeometry(undefined);
      return;
    }
    const coordinate = ol.proj.fromLonLat([longitude, latitude]);
    point.setGeometry(new ol.geom.Point(coordinate));
    map.getView().setCenter(coordinate);
  };
  if (latitudeInput && longitudeInput) {
    latitudeInput.addEventListener("input", refresh);
    longitudeInput.addEventListener("input", refresh);
  }
  refresh();
})();
