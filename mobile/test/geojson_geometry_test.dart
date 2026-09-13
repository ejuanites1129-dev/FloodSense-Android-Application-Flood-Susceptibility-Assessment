import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/geojson_geometry.dart';
import 'package:floodsense/data/models/json_parsing.dart';

List<List<double>> ring({double west = 120, double south = 14}) => [
  [west, south],
  [west, south + 0.01],
  [west + 0.01, south + 0.01],
  [west + 0.01, south],
  [west, south],
];

void main() {
  group('GeoJSON geometry', () {
    test('parses a Polygon exterior ring', () {
      final geometry = GeoJsonGeometry.fromJson({
        'type': 'Polygon',
        'coordinates': [ring()],
      });

      expect(geometry.polygons, hasLength(1));
      expect(geometry.polygons.single.exterior, hasLength(5));
    });

    test('parses every MultiPolygon part', () {
      final geometry = GeoJsonGeometry.fromJson({
        'type': 'MultiPolygon',
        'coordinates': [
          [ring()],
          [ring(west: 121, south: 15)],
        ],
      });

      expect(geometry.polygons, hasLength(2));
    });

    test('converts GeoJSON longitude latitude to LatLng correctly', () {
      final geometry = GeoJsonGeometry.fromJson({
        'type': 'Polygon',
        'coordinates': [ring()],
      });

      final point = geometry.polygons.single.exterior.first;
      expect(point.latitude, 14);
      expect(point.longitude, 120);
    });

    test('retains interior rings as polygon holes', () {
      final geometry = GeoJsonGeometry.fromJson({
        'type': 'Polygon',
        'coordinates': [ring(), ring(west: 120.002, south: 14.002)],
      });

      expect(geometry.polygons.single.holes, hasLength(1));
      expect(geometry.polygons.single.holes.single, hasLength(5));
    });

    test('rejects reversed coordinate order when latitude is invalid', () {
      expect(
        () => GeoJsonGeometry.fromJson({
          'type': 'Polygon',
          'coordinates': [
            [
              [14, 120],
              [14, 121],
              [15, 121],
              [15, 120],
              [14, 120],
            ],
          ],
        }),
        throwsA(isA<ModelParsingException>()),
      );
    });

    test('rejects invalid ranges, malformed rings, and unsupported types', () {
      final invalid = [
        {
          'type': 'Polygon',
          'coordinates': [
            [
              [181, 14],
              [181, 15],
              [179, 15],
              [181, 14],
            ],
          ],
        },
        {
          'type': 'Polygon',
          'coordinates': [
            [
              [120, 14],
              [120, 15],
              [121, 15],
              [121, 14],
            ],
          ],
        },
        {
          'type': 'Point',
          'coordinates': [120, 14],
        },
      ];
      for (final json in invalid) {
        expect(
          () => GeoJsonGeometry.fromJson(json),
          throwsA(isA<ModelParsingException>()),
        );
      }
    });

    test('rejects empty Polygon and MultiPolygon geometry', () {
      for (final json in [
        {'type': 'Polygon', 'coordinates': <dynamic>[]},
        {'type': 'MultiPolygon', 'coordinates': <dynamic>[]},
      ]) {
        expect(
          () => GeoJsonGeometry.fromJson(json),
          throwsA(isA<ModelParsingException>()),
        );
      }
    });

    test('camera bounds include every polygon part', () {
      final first = GeoJsonGeometry.fromJson({
        'type': 'Polygon',
        'coordinates': [ring(west: 120, south: 14)],
      });
      final second = GeoJsonGeometry.fromJson({
        'type': 'MultiPolygon',
        'coordinates': [
          [ring(west: 122, south: 16)],
        ],
      });

      final bounds = GeoJsonGeometry.boundsFor([first, second]);

      expect(bounds.southWest.latitude, 14);
      expect(bounds.southWest.longitude, 120);
      expect(bounds.northEast.latitude, 16.01);
      expect(bounds.northEast.longitude, 122.01);
    });

    test('parsed polygon collections are immutable', () {
      final geometry = GeoJsonGeometry.fromJson({
        'type': 'Polygon',
        'coordinates': [ring()],
      });

      expect(
        () => geometry.polygons.single.exterior.add(
          geometry.polygons.single.exterior.first,
        ),
        throwsUnsupportedError,
      );
      expect(
        () => geometry.polygons.add(geometry.polygons.single),
        throwsUnsupportedError,
      );
    });
  });
}
