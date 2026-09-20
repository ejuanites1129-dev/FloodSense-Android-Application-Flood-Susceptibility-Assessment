import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/verified_center.dart';

VerifiedCenter validCenter({
  double latitude = 14.405,
  double longitude = 120.965,
  double distance = 750,
}) => VerifiedCenter(
  publicIdentifier: 'public-center-a',
  name: 'Synthetic test center',
  address: 'Synthetic public address',
  barangay: CenterBarangayIdentity(psgcCode: '0402103004', name: 'Bayanan'),
  latitude: latitude,
  longitude: longitude,
  approximateDistance: distance,
  distanceUnit: CenterDistanceUnit.meters,
  verifiedOn: DateTime.utc(2026, 9, 1),
  sourceAttribution: 'Synthetic approved test source',
  limitations: const ['Synthetic test limitation'],
);

void main() {
  group('contract-neutral verified center model', () {
    test('retains safe public fields and formats approximate distance', () {
      final center = validCenter();

      expect(center.publicIdentifier, 'public-center-a');
      expect(center.barangay.psgcCode, '0402103004');
      expect(center.distanceLabel, '750 m approximate straight-line distance');
      expect(center.limitations, ['Synthetic test limitation']);
    });

    test('rejects missing required public text', () {
      expect(
        () => VerifiedCenter(
          publicIdentifier: ' ',
          name: 'Synthetic',
          address: 'Address',
          barangay: CenterBarangayIdentity(
            psgcCode: '0402103004',
            name: 'Bayanan',
          ),
          latitude: 14,
          longitude: 120,
          approximateDistance: 1,
          distanceUnit: CenterDistanceUnit.meters,
          verifiedOn: DateTime.utc(2026),
          sourceAttribution: 'Source',
        ),
        throwsArgumentError,
      );
    });

    test('rejects malformed, non-finite, and negative numeric values', () {
      for (final latitude in [91.0, double.nan, double.infinity]) {
        expect(() => validCenter(latitude: latitude), throwsArgumentError);
      }
      for (final longitude in [-181.0, double.nan, double.negativeInfinity]) {
        expect(() => validCenter(longitude: longitude), throwsArgumentError);
      }
      for (final distance in [-0.1, double.nan, double.infinity]) {
        expect(() => validCenter(distance: distance), throwsArgumentError);
      }
    });

    test('rejects absent or invented barangay identities', () {
      for (final code in ['', 'PSGC_0402103004', '123']) {
        expect(
          () => CenterBarangayIdentity(psgcCode: code, name: 'Bayanan'),
          throwsArgumentError,
        );
      }
      expect(
        () => CenterBarangayIdentity(psgcCode: '0402103004', name: ' '),
        throwsArgumentError,
      );
    });

    test(
      'copies limitations so callers cannot mutate trusted presentation data',
      () {
        final limitations = ['Original'];
        final center = VerifiedCenter(
          publicIdentifier: 'public-center-a',
          name: 'Synthetic',
          address: 'Address',
          barangay: CenterBarangayIdentity(
            psgcCode: '0402103004',
            name: 'Bayanan',
          ),
          latitude: 14,
          longitude: 120,
          approximateDistance: 1,
          distanceUnit: CenterDistanceUnit.kilometers,
          verifiedOn: DateTime.utc(2026),
          sourceAttribution: 'Source',
          limitations: limitations,
        );
        limitations[0] = 'Changed';

        expect(center.limitations, ['Original']);
        expect(() => center.limitations.add('unsafe'), throwsUnsupportedError);
        expect(center.distanceLabel, '1 km approximate straight-line distance');
      },
    );
  });
}
