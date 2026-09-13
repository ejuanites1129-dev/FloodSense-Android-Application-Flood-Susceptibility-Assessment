import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/json_parsing.dart';
import 'package:floodsense/data/models/scenario_option.dart';

import 'test_data.dart';

void main() {
  group('typed model parsing', () {
    test('1 assessment options parse both option groups', () {
      final parsed = AssessmentOptions.fromJson(optionsJson());
      expect(parsed.intensityOptions.map((item) => item.label), [
        'Light',
        'Heavy',
      ]);
      expect(parsed.durationOptions.map((item) => item.label), [
        '1 hour',
        '6 hours',
      ]);
      expect(parsed.warnings.first, 'DEMONSTRATION DATA—NOT OFFICIAL');
    });

    test('2 GeoJSON FeatureCollection parses area properties and geometry', () {
      final areas = GeographicArea.listFromFeatureCollection(
        areaCollectionJson(),
      );
      expect(areas.single.code, 'DEMO_ZONE_A');
      expect(areas.single.name, 'Demo Zone A');
      expect(areas.single.geometry.polygons, hasLength(1));
    });

    test('3 classified result parses full explainability and guidance', () {
      final parsed = sampleResult();
      expect(parsed.state, AssessmentState.classified);
      expect(parsed.susceptibility?.code, 'HIGH');
      expect(parsed.matchedRuleCodes, ['DEMO-RULE-300']);
      expect(parsed.ruleset?.version, '1.0');
      expect(parsed.guidance.length, 2);
      expect(parsed.warnings.first, 'DEMONSTRATION DATA—NOT OFFICIAL');
    });

    test('4 uncertain result keeps susceptibility nullable', () {
      final parsed = sampleResult(state: 'UNCERTAIN');
      expect(parsed.state, AssessmentState.uncertain);
      expect(parsed.susceptibility, isNull);
      expect(parsed.matchedRuleCodes, hasLength(2));
    });

    test('5 insufficient-data result parses empty guidance', () {
      final parsed = sampleResult(state: 'INSUFFICIENT_DATA');
      expect(parsed.state, AssessmentState.insufficientData);
      expect(parsed.susceptibility, isNull);
      expect(parsed.guidance, isEmpty);
    });

    test('6 empty arrays parse without fallback records', () {
      final parsed = AssessmentOptions.fromJson(optionsJson(empty: true));
      expect(parsed.intensityOptions, isEmpty);
      expect(parsed.durationOptions, isEmpty);
      expect(
        GeographicArea.listFromFeatureCollection(
          areaCollectionJson(empty: true),
        ),
        isEmpty,
      );
    });

    test('7 malformed required fields produce controlled parsing error', () {
      final malformed = assessmentJson()..remove('area');
      expect(
        () => AssessmentResult.fromJson(malformed),
        throwsA(isA<ModelParsingException>()),
      );
    });

    test('8 valid server hex colors convert to opaque ARGB', () {
      expect(sampleResult().susceptibility?.colorValue, 0xFFE2691B);
    });

    test('9 invalid server colors use neutral fallback', () {
      final json = assessmentJson();
      (json['susceptibility'] as Map<String, dynamic>)['map_color'] = 'orange';
      final parsed = AssessmentResult.fromJson(json);
      expect(
        parsed.susceptibility?.colorValue,
        Susceptibility.neutralColorValue,
      );
    });

    test('10 unknown response fields are ignored', () {
      final json = assessmentJson()..['future_field'] = {'new': true};
      expect(AssessmentResult.fromJson(json).state, AssessmentState.classified);
    });

    test('11 a classified state without susceptibility is rejected', () {
      final json = assessmentJson()..['susceptibility'] = null;
      expect(
        () => AssessmentResult.fromJson(json),
        throwsA(isA<ModelParsingException>()),
      );
    });
  });
}
