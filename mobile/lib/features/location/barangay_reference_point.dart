import 'dart:math' as math;

import 'package:latlong2/latlong.dart';

import '../../data/models/geojson_geometry.dart';
import '../../data/models/point_resolution.dart';

/// A reference point for manual barangay selection, never a device location.
///
/// A bounding-box center or centroid alone can lie outside a concave polygon,
/// inside a hole, or between the parts of a multipolygon. Every returned point
/// is checked against the exterior and holes. Degenerate geometry returns null.
abstract final class BarangayReferencePoint {
  static MapCoordinate? interiorCoordinate(GeoJsonGeometry geometry) {
    final polygons = geometry.polygons.asMap().entries.toList(growable: false)
      ..sort((a, b) {
        final areaOrder = _area(b.value).compareTo(_area(a.value));
        return areaOrder == 0 ? a.key.compareTo(b.key) : areaOrder;
      });
    for (final polygon in polygons) {
      final point = _interiorPoint(polygon.value);
      if (point != null) {
        return MapCoordinate(
          latitude: point.latitude,
          longitude: point.longitude,
        );
      }
    }
    return null;
  }

  static bool containsInterior(
    GeoJsonGeometry geometry,
    MapCoordinate coordinate,
  ) => geometry.polygons.any(
    (polygon) => _insidePolygon(polygon, coordinate.latLng),
  );

  static LatLng? _interiorPoint(GeoJsonPolygon polygon) {
    final points = polygon.exterior;
    final latitudes = points.map((point) => point.latitude);
    final longitudes = points.map((point) => point.longitude);
    final center = LatLng(
      (latitudes.reduce(math.min) + latitudes.reduce(math.max)) / 2,
      (longitudes.reduce(math.min) + longitudes.reduce(math.max)) / 2,
    );
    if (_insidePolygon(polygon, center)) return center;

    // Within a slab between consecutive vertex latitudes, a scanline cannot
    // run through a vertex or horizontal edge. Odd/even intersections across
    // all rings identify interior intervals, excluding each hole.
    final rings = [polygon.exterior, ...polygon.holes];
    final levels =
        rings
            .expand((ring) => ring)
            .map((point) => point.latitude)
            .toSet()
            .toList(growable: false)
          ..sort();
    LatLng? best;
    var bestWidth = 0.0;
    for (var level = 0; level + 1 < levels.length; level++) {
      final latitude = (levels[level] + levels[level + 1]) / 2;
      final crossings = <double>[];
      for (final ring in rings) {
        for (var index = 0; index + 1 < ring.length; index++) {
          final a = ring[index];
          final b = ring[index + 1];
          if ((a.latitude > latitude) == (b.latitude > latitude)) continue;
          crossings.add(
            a.longitude +
                (latitude - a.latitude) *
                    (b.longitude - a.longitude) /
                    (b.latitude - a.latitude),
          );
        }
      }
      crossings.sort();
      for (var index = 0; index + 1 < crossings.length; index += 2) {
        final width = crossings[index + 1] - crossings[index];
        if (width <= bestWidth) continue;
        final candidate = LatLng(
          latitude,
          (crossings[index] + crossings[index + 1]) / 2,
        );
        if (_insidePolygon(polygon, candidate)) {
          best = candidate;
          bestWidth = width;
        }
      }
    }
    return best;
  }

  static bool _insidePolygon(GeoJsonPolygon polygon, LatLng point) =>
      _ringLocation(polygon.exterior, point) == _RingLocation.inside &&
      polygon.holes.every(
        (hole) => _ringLocation(hole, point) == _RingLocation.outside,
      );

  static _RingLocation _ringLocation(List<LatLng> ring, LatLng point) {
    var inside = false;
    for (var index = 0; index + 1 < ring.length; index++) {
      final a = ring[index];
      final b = ring[index + 1];
      final dx = b.longitude - a.longitude;
      final dy = b.latitude - a.latitude;
      final cross =
          (point.longitude - a.longitude) * dy -
          (point.latitude - a.latitude) * dx;
      final tolerance = 1e-12 * math.max(dx.abs(), dy.abs());
      if (cross.abs() <= tolerance &&
          point.longitude >= math.min(a.longitude, b.longitude) &&
          point.longitude <= math.max(a.longitude, b.longitude) &&
          point.latitude >= math.min(a.latitude, b.latitude) &&
          point.latitude <= math.max(a.latitude, b.latitude)) {
        return _RingLocation.boundary;
      }
      if ((a.latitude > point.latitude) != (b.latitude > point.latitude) &&
          point.longitude <
              a.longitude + (point.latitude - a.latitude) * dx / dy) {
        inside = !inside;
      }
    }
    return inside ? _RingLocation.inside : _RingLocation.outside;
  }

  static double _area(GeoJsonPolygon polygon) => math.max(
    0,
    _ringArea(polygon.exterior) -
        polygon.holes.fold(0.0, (total, hole) => total + _ringArea(hole)),
  );

  static double _ringArea(List<LatLng> ring) {
    final origin = ring.first;
    var area = 0.0;
    for (var index = 0; index + 1 < ring.length; index++) {
      final a = ring[index];
      final b = ring[index + 1];
      area +=
          (a.longitude - origin.longitude) * (b.latitude - origin.latitude) -
          (b.longitude - origin.longitude) * (a.latitude - origin.latitude);
    }
    return area.abs() / 2;
  }
}

enum _RingLocation { outside, inside, boundary }
