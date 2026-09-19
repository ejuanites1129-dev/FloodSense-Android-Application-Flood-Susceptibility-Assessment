import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/json_parsing.dart';

import 'test_data.dart';

void main() {
  group('BarangayResolution frozen contract', () {
    test('parses every documented state', () {
      final cases = {
        'RESOLVED': BarangayResolutionState.resolved,
        'OUTSIDE_BACOOR': BarangayResolutionState.outsideBacoor,
        'AMBIGUOUS_BOUNDARY': BarangayResolutionState.ambiguousBoundary,
        'UNAVAILABLE': BarangayResolutionState.unavailable,
      };

      for (final entry in cases.entries) {
        final result = BarangayResolution.fromJson(
          barangayResolutionJson(state: entry.key),
        );
        expect(result.state, entry.value);
        expect(result.barangay != null, entry.key == 'RESOLVED');
        expect(result.boundary.cityVerified, isFalse);
        expect(result.limitations, isNotEmpty);
      }
    });

    test('rejects unknown state, missing fields, and incorrect types', () {
      final unknown = barangayResolutionJson()..['resolution_state'] = 'MAYBE';
      final missing = barangayResolutionJson()..remove('boundary');
      final wrongType = barangayResolutionJson();
      (wrongType['boundary'] as Map<String, dynamic>)['city_verified'] = 'no';

      for (final payload in [unknown, missing, wrongType]) {
        expect(
          () => BarangayResolution.fromJson(payload),
          throwsA(isA<ModelParsingException>()),
        );
      }
    });

    test('rejects malformed stable identity and state/identity mismatch', () {
      final badCode = barangayResolutionJson();
      (badCode['barangay'] as Map<String, dynamic>)['psgc_code'] = 'row-12';
      final neutralWithBarangay = barangayResolutionJson(
        state: 'OUTSIDE_BACOOR',
      )..['barangay'] = {'psgc_code': '0402103004', 'name': 'Bayanan'};

      expect(
        () => BarangayResolution.fromJson(badCode),
        throwsA(isA<ModelParsingException>()),
      );
      expect(
        () => BarangayResolution.fromJson(neutralWithBarangay),
        throwsA(isA<ModelParsingException>()),
      );
    });

    test(
      'ignores unrelated fields without exposing them to assessment state',
      () {
        final payload = barangayResolutionJson()
          ..['susceptibility'] = {'classification': 'VERY_HIGH'}
          ..['internal_note'] = 'unsafe';

        final result = BarangayResolution.fromJson(payload);

        expect(result.state, BarangayResolutionState.resolved);
        expect(result.barangay?.name, 'Bayanan');
      },
    );
  });
}
