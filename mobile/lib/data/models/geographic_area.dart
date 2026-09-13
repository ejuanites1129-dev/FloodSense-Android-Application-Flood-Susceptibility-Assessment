import 'geojson_geometry.dart';
import 'json_parsing.dart';

class GeographicArea {
  const GeographicArea({
    required this.id,
    required this.code,
    required this.name,
    required this.areaType,
    required this.dataStatus,
    required this.geometry,
  });

  final int id;
  final String code;
  final String name;
  final String areaType;
  final String dataStatus;
  final GeoJsonGeometry geometry;

  factory GeographicArea.fromGeoJsonFeature(Map<String, dynamic> json) {
    if (requireString(json, 'type') != 'Feature') {
      throw const ModelParsingException('Expected a GeoJSON Feature.');
    }
    final properties = requireMap(json['properties'], 'properties');
    final featureId = requireInt(json, 'id');
    final propertyId = requireInt(properties, 'id');
    if (featureId != propertyId) {
      throw const ModelParsingException('GeoJSON feature IDs do not match.');
    }
    return GeographicArea(
      id: propertyId,
      code: requireString(properties, 'code'),
      name: requireString(properties, 'name'),
      areaType: requireString(properties, 'area_type'),
      dataStatus: requireString(properties, 'data_status'),
      geometry: GeoJsonGeometry.fromJson(
        requireMap(json['geometry'], 'geometry'),
      ),
    );
  }

  static List<GeographicArea> listFromFeatureCollection(
    Map<String, dynamic> json,
  ) {
    if (requireString(json, 'type') != 'FeatureCollection') {
      throw const ModelParsingException(
        'Expected a GeoJSON FeatureCollection.',
      );
    }
    return List.unmodifiable(
      requireList(json['features'], 'features').map(
        (feature) =>
            GeographicArea.fromGeoJsonFeature(requireMap(feature, 'features')),
      ),
    );
  }
}
