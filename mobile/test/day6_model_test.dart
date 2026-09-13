import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/data/models/map_assessment_result.dart';
import 'package:floodsense/data/models/point_resolution.dart';

import 'test_data.dart';

void main() {
  group('Day 6 response models', () {
    test('resolved point parses coordinate and safe area fields', () {
      final result = PointResolution.fromJson(pointResolutionJson());

      expect(result.state, PointResolutionState.resolved);
      expect(result.coordinate.latitude, 14.005);
      expect(result.coordinate.longitude, 120.005);
      expect(result.area?.code, 'DEMO_ZONE_A');
    });

    test('outside and ambiguous points remain unclassified', () {
      for (final state in ['OUTSIDE_SUPPORTED_AREA', 'AMBIGUOUS_AREA']) {
        final result = PointResolution.fromJson(
          pointResolutionJson(state: state),
        );
        expect(result.area, isNull);
        expect(result.state, isNot(PointResolutionState.resolved));
      }
    });

    test('point coordinates outside WGS 84 ranges are rejected', () {
      expect(
        () => PointResolution.fromJson(pointResolutionJson(latitude: 91)),
        throwsFormatException,
      );
      expect(
        () => PointResolution.fromJson(pointResolutionJson(longitude: 181)),
        throwsFormatException,
      );
    });

    test('classified map result retains server color and matched rule', () {
      final result = MapAssessmentResult.fromJson(mapAssessmentJson());
      final area = result.results.single;

      expect(area.state, AssessmentState.classified);
      expect(area.susceptibility?.mapColor, '#E2691B');
      expect(area.matchedRuleCodes, ['DEMO-RULE-300']);
      expect(result.resultsByAreaId[7], same(area));
    });

    test('map limitation has no fabricated susceptibility', () {
      final result = MapAssessmentResult.fromJson(
        mapAssessmentJson(state: 'INSUFFICIENT_DATA'),
      );

      expect(result.results.single.state, AssessmentState.insufficientData);
      expect(result.results.single.susceptibility, isNull);
    });
  });
}
