import 'geojson_geometry.dart';
import 'json_parsing.dart';

class BarangaySusceptibilitySummary {
  const BarangaySusceptibilitySummary({
    required this.method,
    required this.dataStatus,
    required this.datasetVersion,
    required this.dominantClassCode,
    required this.dominantClassLabel,
    required this.dominantPercent,
    required this.mappedPercent,
    required this.unmappedPercent,
    required this.conflictPercent,
  });

  final String method;
  final String dataStatus;
  final String datasetVersion;
  final String? dominantClassCode;
  final String? dominantClassLabel;
  final double? dominantPercent;
  final double mappedPercent;
  final double unmappedPercent;
  final double conflictPercent;

  bool get hasDominantClass => dominantClassCode != null;

  factory BarangaySusceptibilitySummary.fromJson(Map<String, dynamic> json) =>
      BarangaySusceptibilitySummary(
        method: requireString(json, 'method'),
        dataStatus: requireString(json, 'data_status'),
        datasetVersion: requireString(json, 'dataset_version'),
        dominantClassCode: nullableString(json, 'dominant_class_code'),
        dominantClassLabel: nullableString(json, 'dominant_class_label'),
        dominantPercent: _nullableNumber(json, 'dominant_percent'),
        mappedPercent: requireNumber(json, 'mapped_percent').toDouble(),
        unmappedPercent: requireNumber(json, 'unmapped_percent').toDouble(),
        conflictPercent: requireNumber(json, 'conflict_percent').toDouble(),
      );

  static double? _nullableNumber(Map<String, dynamic> json, String field) {
    if (json[field] == null) return null;
    return requireNumber(json, field).toDouble();
  }
}

class GeographicArea {
  const GeographicArea({
    required this.id,
    required this.code,
    required this.name,
    required this.areaType,
    required this.dataStatus,
    required this.geometry,
    this.susceptibilitySummary,
  });

  final int id;
  final String code;
  final String name;
  final String areaType;
  final String dataStatus;
  final GeoJsonGeometry geometry;
  final BarangaySusceptibilitySummary? susceptibilitySummary;

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
    final susceptibilityJson = nullableMap(
      properties['susceptibility_summary'],
      'susceptibility_summary',
    );
    return GeographicArea(
      id: propertyId,
      code: requireString(properties, 'code'),
      name: requireString(properties, 'name'),
      areaType: requireString(properties, 'area_type'),
      dataStatus: requireString(properties, 'data_status'),
      geometry: GeoJsonGeometry.fromJson(
        requireMap(json['geometry'], 'geometry'),
      ),
      susceptibilitySummary: susceptibilityJson == null
          ? null
          : BarangaySusceptibilitySummary.fromJson(susceptibilityJson),
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
