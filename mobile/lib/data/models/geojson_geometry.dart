import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import 'json_parsing.dart';

class GeoJsonPolygon {
  GeoJsonPolygon({required List<LatLng> exterior, List<List<LatLng>>? holes})
    : exterior = List.unmodifiable(exterior),
      holes = List.unmodifiable(
        (holes ?? const <List<LatLng>>[]).map(List<LatLng>.unmodifiable),
      );

  final List<LatLng> exterior;
  final List<List<LatLng>> holes;
}

class GeoJsonGeometry {
  GeoJsonGeometry._(List<GeoJsonPolygon> polygons)
    : polygons = List.unmodifiable(polygons);

  final List<GeoJsonPolygon> polygons;

  List<LatLng> get allPoints => List.unmodifiable(
    polygons.expand(
      (polygon) => <LatLng>[
        ...polygon.exterior,
        ...polygon.holes.expand((hole) => hole),
      ],
    ),
  );

  LatLngBounds get bounds => LatLngBounds.fromPoints(allPoints);

  factory GeoJsonGeometry.fromJson(Map<String, dynamic> json) {
    final type = requireString(json, 'type');
    final coordinates = requireList(json['coordinates'], 'coordinates');
    final polygons = switch (type) {
      'Polygon' => [_parsePolygon(coordinates, 'coordinates')],
      'MultiPolygon' =>
        coordinates
            .asMap()
            .entries
            .map(
              (entry) => _parsePolygon(
                requireList(entry.value, 'coordinates[${entry.key}]'),
                'coordinates[${entry.key}]',
              ),
            )
            .toList(),
      _ => throw ModelParsingException(
        'Unsupported GeoJSON geometry type "$type".',
      ),
    };
    if (polygons.isEmpty) {
      throw const ModelParsingException(
        'GeoJSON geometry must contain at least one polygon.',
      );
    }
    return GeoJsonGeometry._(polygons);
  }

  static LatLngBounds boundsFor(Iterable<GeoJsonGeometry> geometries) {
    final points = geometries.expand((geometry) => geometry.allPoints).toList();
    if (points.isEmpty) {
      throw const ModelParsingException(
        'Cannot calculate map bounds without geometry coordinates.',
      );
    }
    return LatLngBounds.fromPoints(points);
  }

  static GeoJsonPolygon _parsePolygon(List<dynamic> rings, String field) {
    if (rings.isEmpty) {
      throw ModelParsingException('$field must contain an exterior ring.');
    }
    final parsedRings = rings
        .asMap()
        .entries
        .map(
          (entry) => _parseRing(
            requireList(entry.value, '$field[${entry.key}]'),
            '$field[${entry.key}]',
          ),
        )
        .toList();
    return GeoJsonPolygon(
      exterior: parsedRings.first,
      holes: parsedRings.skip(1).toList(),
    );
  }

  static List<LatLng> _parseRing(List<dynamic> positions, String field) {
    if (positions.length < 4) {
      throw ModelParsingException(
        '$field must contain at least four positions.',
      );
    }
    final ring = positions
        .asMap()
        .entries
        .map(
          (entry) => _parsePosition(
            requireList(entry.value, '$field[${entry.key}]'),
            '$field[${entry.key}]',
          ),
        )
        .toList();
    final first = ring.first;
    final last = ring.last;
    if (first.latitude != last.latitude || first.longitude != last.longitude) {
      throw ModelParsingException('$field must be a closed linear ring.');
    }
    final uniquePositions = ring
        .take(ring.length - 1)
        .map((point) => '${point.latitude},${point.longitude}')
        .toSet();
    if (uniquePositions.length < 3) {
      throw ModelParsingException(
        '$field must contain three distinct positions.',
      );
    }
    return List.unmodifiable(ring);
  }

  static LatLng _parsePosition(List<dynamic> position, String field) {
    if (position.length < 2 || position[0] is! num || position[1] is! num) {
      throw ModelParsingException(
        '$field must begin with numeric longitude and latitude.',
      );
    }
    final longitude = (position[0] as num).toDouble();
    final latitude = (position[1] as num).toDouble();
    if (!longitude.isFinite || !latitude.isFinite) {
      throw ModelParsingException('$field contains a non-finite coordinate.');
    }
    if (longitude < -180 || longitude > 180) {
      throw ModelParsingException(
        '$field longitude must be between -180 and 180.',
      );
    }
    if (latitude < -90 || latitude > 90) {
      throw ModelParsingException(
        '$field latitude must be between -90 and 90.',
      );
    }
    return LatLng(latitude, longitude);
  }
}
