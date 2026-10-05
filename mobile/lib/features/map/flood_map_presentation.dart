import 'dart:convert';
import 'dart:math' as math;

import '../../data/models/geojson_geometry.dart';
import '../../data/models/center_map_record.dart';
import '../../data/models/geographic_area.dart';
import '../../data/models/map_assessment_result.dart';
import '../../data/models/point_resolution.dart';
import '../../data/models/verified_center.dart';
import 'flood_map_palette.dart';

typedef MapCoordinateCallback = void Function(MapCoordinate coordinate);
typedef MapAreaCallback = void Function(int areaId);
typedef MapCenterCallback = void Function(String publicIdentifier);

/// Provider-neutral presentation data for the resident map surfaces.
///
/// It contains only the same boundaries, scenario results, temporary point,
/// and verified centers that the existing OSM renderer already receives.
final class FloodMapPresentation {
  const FloodMapPresentation({
    required this.referenceAreas,
    required this.scenarioAreas,
    required this.scenarioResults,
    required this.onCoordinateTapped,
    this.selectedAreaId,
    this.confirmedAreaCode,
    this.coordinate,
    this.accuracyMeters,
    this.coordinateDescription,
    this.centers = const [],
    this.mapCenters = const [],
    this.mapCentersAreAuthoritative = false,
    this.nearestCenterIdentifier,
    this.nearestIsDemonstration,
    this.selectedCenterIdentifier,
    this.onAreaTapped,
    this.onCenterTapped,
    this.fitPadding = const FloodMapPadding.all(28),
    this.controlsOnRight = false,
  });

  final List<GeographicArea> referenceAreas;
  final List<GeographicArea> scenarioAreas;
  final Map<int, MapAreaAssessment> scenarioResults;
  final int? selectedAreaId;
  final String? confirmedAreaCode;
  final MapCoordinate? coordinate;
  final double? accuracyMeters;
  final String? coordinateDescription;
  final List<VerifiedCenter> centers;
  final List<CenterMapRecord> mapCenters;
  final bool mapCentersAreAuthoritative;
  final String? nearestCenterIdentifier;
  final bool? nearestIsDemonstration;
  final String? selectedCenterIdentifier;
  final MapCoordinateCallback onCoordinateTapped;
  final MapAreaCallback? onAreaTapped;
  final MapCenterCallback? onCenterTapped;
  final FloodMapPadding fitPadding;
  final bool controlsOnRight;

  /// Catalog icons do not fabricate distances; current nearest metadata wins.
  List<CenterMapRecord> get mapMarkers {
    final byIdentifier = <String, CenterMapRecord>{
      for (final center in mapCenters)
        if (nearestIsDemonstration == null ||
            center.isDemonstration == nearestIsDemonstration)
          center.publicIdentifier: center,
    };
    for (final center in centers) {
      if (!mapCentersAreAuthoritative ||
          byIdentifier.containsKey(center.publicIdentifier)) {
        byIdentifier[center.publicIdentifier] =
            CenterMapRecord.fromVerifiedCenter(center);
      }
    }
    return List.unmodifiable(byIdentifier.values);
  }

  FloodMapBounds get bounds => FloodMapBounds.fromGeometries(
    (referenceAreas.isNotEmpty ? referenceAreas : scenarioAreas).map(
      (area) => area.geometry,
    ),
  );

  String get boundaryGeoJson => jsonEncode({
    'type': 'FeatureCollection',
    'features': [
      for (final area in referenceAreas)
        _areaFeature(area, {'confirmed': area.code == confirmedAreaCode}),
    ],
  });

  String get scenarioGeoJson => jsonEncode({
    'type': 'FeatureCollection',
    'features': [
      for (final area in scenarioAreas)
        _areaFeature(area, {
          'selected': area.id == selectedAreaId,
          'color': FloodMapPalette.cssHex(
            FloodMapPalette.forAssessment(scenarioResults[area.id]),
          ),
        }),
    ],
  });

  String get pointGeoJson => jsonEncode({
    'type': 'FeatureCollection',
    'features': [
      if (coordinate case final point?)
        {
          'type': 'Feature',
          'properties': {'kind': 'temporary-point'},
          'geometry': {
            'type': 'Point',
            'coordinates': [point.longitude, point.latitude],
          },
        },
      for (final center in mapMarkers)
        {
          'type': 'Feature',
          'properties': {
            'kind': 'verified-center',
            'public_identifier': center.publicIdentifier,
            'selected': center.publicIdentifier == selectedCenterIdentifier,
            'nearest': center.publicIdentifier == nearestCenterIdentifier,
            'is_demonstration': center.isDemonstration,
            'name': center.name,
          },
          'geometry': {
            'type': 'Point',
            'coordinates': [center.longitude, center.latitude],
          },
        },
    ],
  });

  String get accuracyGeoJson {
    final point = coordinate;
    final radius = accuracyMeters;
    if (point == null || radius == null || radius <= 0 || !radius.isFinite) {
      return _emptyFeatureCollection;
    }
    const steps = 48;
    const metersPerDegreeLatitude = 111320.0;
    final latitudeRadians = point.latitude * math.pi / 180;
    final longitudeScale =
        metersPerDegreeLatitude *
        math.cos(latitudeRadians).abs().clamp(0.01, 1);
    final ring = <List<double>>[];
    for (var index = 0; index <= steps; index++) {
      final angle = 2 * math.pi * index / steps;
      ring.add([
        point.longitude + math.cos(angle) * radius / longitudeScale,
        point.latitude + math.sin(angle) * radius / metersPerDegreeLatitude,
      ]);
    }
    return jsonEncode({
      'type': 'FeatureCollection',
      'features': [
        {
          'type': 'Feature',
          'properties': {'kind': 'temporary-accuracy'},
          'geometry': {
            'type': 'Polygon',
            'coordinates': [ring],
          },
        },
      ],
    });
  }

  String get coverageMaskGeoJson {
    if (referenceAreas.isEmpty) return _emptyFeatureCollection;
    final mapBounds = bounds;
    final latitudeMargin = math.max(mapBounds.latitudeSpan * 8, 1.0);
    final longitudeMargin = math.max(mapBounds.longitudeSpan * 8, 1.0);
    final outer = [
      [mapBounds.west - longitudeMargin, mapBounds.south - latitudeMargin],
      [mapBounds.east + longitudeMargin, mapBounds.south - latitudeMargin],
      [mapBounds.east + longitudeMargin, mapBounds.north + latitudeMargin],
      [mapBounds.west - longitudeMargin, mapBounds.north + latitudeMargin],
      [mapBounds.west - longitudeMargin, mapBounds.south - latitudeMargin],
    ];
    return jsonEncode({
      'type': 'FeatureCollection',
      'features': [
        {
          'type': 'Feature',
          'properties': const {'kind': 'outside-coverage'},
          'geometry': {
            'type': 'Polygon',
            'coordinates': [
              outer,
              for (final area in referenceAreas)
                for (final polygon in area.geometry.polygons)
                  polygon.exterior.reversed
                      .map((point) => [point.longitude, point.latitude])
                      .toList(),
            ],
          },
        },
      ],
    });
  }

  static Map<String, Object?> _areaFeature(
    GeographicArea area,
    Map<String, Object?> additionalProperties,
  ) => {
    'type': 'Feature',
    'id': area.id,
    'properties': {
      'area_id': area.id,
      'code': area.code,
      'name': area.name,
      ...additionalProperties,
    },
    'geometry': _geometryJson(area.geometry),
  };

  static Map<String, Object?> _geometryJson(GeoJsonGeometry geometry) {
    final coordinates = [
      for (final polygon in geometry.polygons)
        [
          polygon.exterior
              .map((point) => [point.longitude, point.latitude])
              .toList(),
          for (final hole in polygon.holes)
            hole.map((point) => [point.longitude, point.latitude]).toList(),
        ],
    ];
    return geometry.polygons.length == 1
        ? {'type': 'Polygon', 'coordinates': coordinates.single}
        : {'type': 'MultiPolygon', 'coordinates': coordinates};
  }
}

const _emptyFeatureCollection = '{"type":"FeatureCollection","features":[]}';

final class FloodMapPadding {
  const FloodMapPadding({
    required this.top,
    required this.right,
    required this.bottom,
    required this.left,
  });

  const FloodMapPadding.all(double value)
    : top = value,
      right = value,
      bottom = value,
      left = value;

  final double top;
  final double right;
  final double bottom;
  final double left;
}

final class FloodMapBounds {
  const FloodMapBounds({
    required this.south,
    required this.west,
    required this.north,
    required this.east,
  });

  factory FloodMapBounds.fromGeometries(Iterable<GeoJsonGeometry> geometries) {
    final points = geometries.expand((geometry) => geometry.allPoints).toList();
    if (points.isEmpty) {
      return const FloodMapBounds(
        south: 14.42,
        west: 120.92,
        north: 14.52,
        east: 121.02,
      );
    }
    return FloodMapBounds(
      south: points.map((point) => point.latitude).reduce(math.min),
      west: points.map((point) => point.longitude).reduce(math.min),
      north: points.map((point) => point.latitude).reduce(math.max),
      east: points.map((point) => point.longitude).reduce(math.max),
    );
  }

  final double south;
  final double west;
  final double north;
  final double east;

  double get latitudeSpan => north - south;
  double get longitudeSpan => east - west;
  double get centerLatitude => (north + south) / 2;
  double get centerLongitude => (east + west) / 2;
}
