(() => {
  const mapElement = document.querySelector("[data-center-map]");
  const statusElement = document.querySelector("[data-center-map-status]");
  if (!mapElement) return;
  if (typeof window.ol === "undefined") {
    if (statusElement) {
      statusElement.textContent = "Map preview unavailable. Review the labeled latitude and longitude fields independently.";
    }
    return;
  }
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
      if (statusElement) {
        statusElement.textContent = "Enter both latitude and longitude to preview a marker.";
      }
      return;
    }
    const latitude = Number(latitudeValue);
    const longitude = Number(longitudeValue);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)
        || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
      point.setGeometry(undefined);
      if (statusElement) {
        statusElement.textContent = "The marker is hidden because the coordinates are outside valid WGS 84 ranges.";
      }
      return;
    }
    const coordinate = ol.proj.fromLonLat([longitude, latitude]);
    point.setGeometry(new ol.geom.Point(coordinate));
    map.getView().setCenter(coordinate);
    if (statusElement) {
      statusElement.textContent = `Preview marker at latitude ${latitudeValue}, longitude ${longitudeValue}. This does not verify the center or route safety.`;
    }
  };
  if (latitudeInput && longitudeInput) {
    latitudeInput.addEventListener("input", refresh);
    longitudeInput.addEventListener("input", refresh);
  }
  refresh();
})();
