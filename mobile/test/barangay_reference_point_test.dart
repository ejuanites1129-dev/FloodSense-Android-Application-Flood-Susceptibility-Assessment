import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/geojson_geometry.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/features/location/barangay_reference_point.dart';

GeoJsonGeometry _polygon(List<List<List<num>>> rings) =>
    GeoJsonGeometry.fromJson({'type': 'Polygon', 'coordinates': rings});

void main() {
  test('rectangle uses its interior center deterministically', () {
    final geometry = _polygon([
      [
        [0, 0],
        [4, 0],
        [4, 2],
        [0, 2],
        [0, 0],
      ],
    ]);
    final point = BarangayReferencePoint.interiorCoordinate(geometry)!;
    expect(point.latitude, 1);
    expect(point.longitude, 2);
    expect(BarangayReferencePoint.containsInterior(geometry, point), isTrue);
    final repeated = BarangayReferencePoint.interiorCoordinate(geometry)!;
    expect(repeated.latitude, point.latitude);
    expect(repeated.longitude, point.longitude);
  });

  test('concave polygon does not use the exterior bounding-box center', () {
    final geometry = _polygon([
      [
        [0, 0],
        [6, 0],
        [6, 1],
        [1, 1],
        [1, 6],
        [0, 6],
        [0, 0],
      ],
    ]);
    expect(
      BarangayReferencePoint.containsInterior(
        geometry,
        const MapCoordinate(latitude: 3, longitude: 3),
      ),
      isFalse,
    );
    final point = BarangayReferencePoint.interiorCoordinate(geometry)!;
    expect(BarangayReferencePoint.containsInterior(geometry, point), isTrue);
  });

  test(
    'central and multiple holes are excluded irrespective of ring winding',
    () {
      final geometry = _polygon([
        [
          [0, 0],
          [8, 0],
          [8, 8],
          [0, 8],
          [0, 0],
        ],
        [
          [2, 2],
          [6, 2],
          [6, 6],
          [2, 6],
          [2, 2],
        ],
        [
          [0.5, 0.5],
          [1.5, 0.5],
          [1.5, 1.5],
          [0.5, 1.5],
          [0.5, 0.5],
        ],
      ]);
      final point = BarangayReferencePoint.interiorCoordinate(geometry)!;
      expect(BarangayReferencePoint.containsInterior(geometry, point), isTrue);
      for (final coordinate in const [
        MapCoordinate(latitude: 4, longitude: 4),
        MapCoordinate(latitude: 1, longitude: 1),
        MapCoordinate(latitude: 2, longitude: 4),
      ]) {
        expect(
          BarangayReferencePoint.containsInterior(geometry, coordinate),
          isFalse,
        );
      }
    },
  );

  test('multipart reference chooses an interior point in the largest part', () {
    final geometry = GeoJsonGeometry.fromJson({
      'type': 'MultiPolygon',
      'coordinates': [
        [
          [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
            [0, 0],
          ],
        ],
        [
          [
            [10, 10],
            [14, 10],
            [14, 14],
            [10, 14],
            [10, 10],
          ],
        ],
      ],
    });
    final point = BarangayReferencePoint.interiorCoordinate(geometry)!;
    expect(point.latitude, 12);
    expect(point.longitude, 12);
    expect(BarangayReferencePoint.containsInterior(geometry, point), isTrue);
  });

  test(
    'equal-area parts preserve source order for deterministic selection',
    () {
      final geometry = GeoJsonGeometry.fromJson({
        'type': 'MultiPolygon',
        'coordinates': [
          [
            [
              [10, 10],
              [12, 10],
              [12, 12],
              [10, 12],
              [10, 10],
            ],
          ],
          [
            [
              [0, 0],
              [2, 0],
              [2, 2],
              [0, 2],
              [0, 0],
            ],
          ],
        ],
      });
      final point = BarangayReferencePoint.interiorCoordinate(geometry)!;
      expect(point.latitude, 11);
      expect(point.longitude, 11);
    },
  );

  test('outer boundary is not an interior reference point', () {
    final geometry = _polygon([
      [
        [0, 0],
        [2, 0],
        [2, 2],
        [0, 2],
        [0, 0],
      ],
    ]);
    for (final coordinate in const [
      MapCoordinate(latitude: 0, longitude: 0),
      MapCoordinate(latitude: 1, longitude: 0),
      MapCoordinate(latitude: 2, longitude: 1),
    ]) {
      expect(
        BarangayReferencePoint.containsInterior(geometry, coordinate),
        isFalse,
      );
    }
  });

  test('degenerate collinear polygon yields no fabricated interior point', () {
    final geometry = _polygon([
      [
        [0, 0],
        [1, 0],
        [2, 0],
        [0, 0],
      ],
    ]);
    expect(BarangayReferencePoint.interiorCoordinate(geometry), isNull);
  });

  test('thin and slanted polygon still supplies a strict interior point', () {
    final geometry = _polygon([
      [
        [120, 14],
        [120.02, 14.02],
        [120.01999, 14.02001],
        [120, 14],
      ],
    ]);
    final point = BarangayReferencePoint.interiorCoordinate(geometry)!;
    expect(BarangayReferencePoint.containsInterior(geometry, point), isTrue);
  });
}
