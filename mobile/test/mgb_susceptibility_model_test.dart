import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/geographic_area.dart';

Map<String, dynamic> collection({Map<String, dynamic>? summary}) => {
  'type': 'FeatureCollection',
  'features': [
    {
      'type': 'Feature',
      'id': 101,
      'geometry': {
        'type': 'MultiPolygon',
        'coordinates': [
          [
            [
              [120.96, 14.40],
              [120.96, 14.41],
              [120.97, 14.41],
              [120.97, 14.40],
              [120.96, 14.40],
            ],
          ],
        ],
      },
      'properties': {
        'id': 101,
        'code': 'PSGC_0402103004',
        'name': 'Bayanan',
        'area_type': 'BARANGAY',
        'data_status': 'PENDING_VALIDATION',
        'susceptibility_summary': summary,
      },
    },
  ],
};

void main() {
  test('parses a provisional MGB-derived barangay summary', () {
    final area = GeographicArea.listFromFeatureCollection(
      collection(
        summary: {
          'method': 'DOMINANT_MAPPED_AREA',
          'data_status': 'PENDING_VALIDATION',
          'dataset_version': '2026-09-16-example',
          'dominant_class_code': 'LF',
          'dominant_class_label': 'Low',
          'dominant_percent': 91.6058,
          'mapped_percent': 94.0662,
          'unmapped_percent': 5.9337,
          'conflict_percent': 0,
        },
      ),
    ).single;

    expect(area.areaType, 'BARANGAY');
    expect(area.susceptibilitySummary?.dominantClassCode, 'LF');
    expect(area.susceptibilitySummary?.dominantClassLabel, 'Low');
    expect(
      area.susceptibilitySummary?.mappedPercent,
      closeTo(94.0662, 0.00001),
    );
    expect(area.susceptibilitySummary?.dataStatus, 'PENDING_VALIDATION');
  });

  test('preserves an explicit no-dominant-class summary', () {
    final area = GeographicArea.listFromFeatureCollection(
      collection(
        summary: {
          'method': 'DOMINANT_MAPPED_AREA',
          'data_status': 'PENDING_VALIDATION',
          'dataset_version': '2026-09-16-example',
          'dominant_class_code': null,
          'dominant_class_label': null,
          'dominant_percent': null,
          'mapped_percent': 0,
          'unmapped_percent': 100,
          'conflict_percent': 0,
        },
      ),
    ).single;

    expect(area.susceptibilitySummary?.hasDominantClass, isFalse);
    expect(area.susceptibilitySummary?.unmappedPercent, 100);
  });
}
