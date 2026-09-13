import 'package:latlong2/latlong.dart';

import 'json_parsing.dart';

enum PointResolutionState {
  resolved,
  outsideSupportedArea,
  ambiguousArea,
  unknown,
}

class MapCoordinate {
  const MapCoordinate({required this.latitude, required this.longitude});

  final double latitude;
  final double longitude;

  LatLng get latLng => LatLng(latitude, longitude);

  factory MapCoordinate.fromJson(Map<String, dynamic> json) {
    final latitude = requireNumber(json, 'latitude').toDouble();
    final longitude = requireNumber(json, 'longitude').toDouble();
    if (latitude < -90 || latitude > 90) {
      throw const ModelParsingException(
        'Expected "latitude" to be between -90 and 90.',
      );
    }
    if (longitude < -180 || longitude > 180) {
      throw const ModelParsingException(
        'Expected "longitude" to be between -180 and 180.',
      );
    }
    return MapCoordinate(latitude: latitude, longitude: longitude);
  }
}

class ResolvedGeographicArea {
  const ResolvedGeographicArea({
    required this.id,
    required this.code,
    required this.name,
    required this.areaType,
    required this.dataStatus,
  });

  final int id;
  final String code;
  final String name;
  final String areaType;
  final String dataStatus;

  factory ResolvedGeographicArea.fromJson(Map<String, dynamic> json) =>
      ResolvedGeographicArea(
        id: requireInt(json, 'id'),
        code: requireString(json, 'code'),
        name: requireString(json, 'name'),
        areaType: requireString(json, 'area_type'),
        dataStatus: requireString(json, 'data_status'),
      );
}

class PointResolution {
  const PointResolution({
    required this.state,
    required this.rawState,
    required this.coordinate,
    required this.area,
    required this.operatingMode,
    required this.dataStatus,
    required this.warnings,
  });

  final PointResolutionState state;
  final String rawState;
  final MapCoordinate coordinate;
  final ResolvedGeographicArea? area;
  final String operatingMode;
  final String dataStatus;
  final List<String> warnings;

  factory PointResolution.fromJson(Map<String, dynamic> json) {
    final rawState = requireString(json, 'resolution_state');
    final state = switch (rawState) {
      'RESOLVED' => PointResolutionState.resolved,
      'OUTSIDE_SUPPORTED_AREA' => PointResolutionState.outsideSupportedArea,
      'AMBIGUOUS_AREA' => PointResolutionState.ambiguousArea,
      _ => PointResolutionState.unknown,
    };
    final areaJson = nullableMap(json['area'], 'area');
    final area = areaJson == null
        ? null
        : ResolvedGeographicArea.fromJson(areaJson);
    if (state == PointResolutionState.resolved && area == null) {
      throw const ModelParsingException('A resolved point requires an area.');
    }
    if (state != PointResolutionState.resolved && area != null) {
      throw const ModelParsingException(
        'An unresolved point cannot contain a selected area.',
      );
    }
    return PointResolution(
      state: state,
      rawState: rawState,
      coordinate: MapCoordinate.fromJson(
        requireMap(json['coordinate'], 'coordinate'),
      ),
      area: area,
      operatingMode: requireString(json, 'operating_mode'),
      dataStatus: requireString(json, 'data_status'),
      warnings: requireStringList(json['warnings'], 'warnings'),
    );
  }
}
