import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/location/geolocator_location_service.dart';
import 'package:floodsense/features/location/location_service.dart';
import 'package:geolocator/geolocator.dart';

class FakeGeolocatorGateway implements GeolocatorGateway {
  bool serviceEnabled = true;
  LocationPermission checkedPermission = LocationPermission.denied;
  LocationPermission requestedPermission = LocationPermission.whileInUse;
  Position position = positionWith();
  Object? positionError;
  int permissionRequests = 0;
  int positionRequests = 0;
  LocationSettings? receivedSettings;

  @override
  Future<LocationPermission> checkPermission() async => checkedPermission;

  @override
  Future<Position> getCurrentPosition({
    required LocationSettings locationSettings,
  }) async {
    positionRequests++;
    receivedSettings = locationSettings;
    if (positionError case final error?) throw error;
    return position;
  }

  @override
  Future<bool> isLocationServiceEnabled() async => serviceEnabled;

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;

  @override
  Future<LocationPermission> requestPermission() async {
    permissionRequests++;
    return requestedPermission;
  }
}

Position positionWith({
  double latitude = 14.41,
  double longitude = 120.97,
  double accuracy = 12,
  bool hasAccuracy = false,
}) => Position(
  latitude: latitude,
  longitude: longitude,
  timestamp: DateTime.utc(2026, 9, 19),
  accuracy: accuracy,
  altitude: 0,
  altitudeAccuracy: 0,
  heading: 0,
  headingAccuracy: 0,
  speed: 0,
  speedAccuracy: 0,
  hasAccuracy: hasAccuracy,
);

void main() {
  group('GeolocatorLocationService permission mapping', () {
    test(
      'distinguishes an initial denial from denial after a request',
      () async {
        final gateway = FakeGeolocatorGateway();
        final service = GeolocatorLocationService(gateway: gateway);

        expect(
          await service.checkPermission(),
          LocationPermissionState.notRequested,
        );
        expect(
          await service.requestForegroundPermission(),
          LocationPermissionState.foregroundGranted,
        );
        gateway.checkedPermission = LocationPermission.denied;
        expect(await service.checkPermission(), LocationPermissionState.denied);
        expect(gateway.permissionRequests, 1);
      },
    );

    test('accepts foreground grants and preserves permanent denial', () async {
      final gateway = FakeGeolocatorGateway()
        ..checkedPermission = LocationPermission.always;
      final service = GeolocatorLocationService(gateway: gateway);
      expect(
        await service.checkPermission(),
        LocationPermissionState.foregroundGranted,
      );

      gateway.checkedPermission = LocationPermission.deniedForever;
      expect(
        await service.checkPermission(),
        LocationPermissionState.deniedPermanently,
      );
    });
  });

  group('GeolocatorLocationService one-shot acquisition', () {
    test(
      'returns a project-owned temporary location with policy settings',
      () async {
        final gateway = FakeGeolocatorGateway();
        final service = GeolocatorLocationService(gateway: gateway);
        const policy = LocationAcquisitionPolicy(
          timeout: Duration(seconds: 9),
          maximumAcceptedAccuracyMeters: 25,
        );

        final result = await service.acquireCurrentPosition(policy: policy);

        expect(result.latitude, 14.41);
        expect(result.longitude, 120.97);
        expect(result.accuracyMeters, 12);
        expect(gateway.positionRequests, 1);
        expect(gateway.receivedSettings, isA<AndroidSettings>());
        expect(gateway.receivedSettings?.accuracy, LocationAccuracy.high);
        expect(gateway.receivedSettings?.timeLimit, policy.timeout);
      },
    );

    test(
      'accepts Android numeric accuracy when presence flag is lost',
      () async {
        final gateway = FakeGeolocatorGateway();
        expect(gateway.position.hasAccuracy, isFalse);
        final service = GeolocatorLocationService(gateway: gateway);

        final result = await service.acquireCurrentPosition(
          policy: const LocationAcquisitionPolicy(),
        );

        expect(result.accuracyMeters, 12);
      },
    );

    test('rejects missing or unacceptable numeric accuracy', () async {
      final cases = <Position>[
        positionWith(accuracy: 0),
        positionWith(accuracy: 80),
      ];
      for (final position in cases) {
        final gateway = FakeGeolocatorGateway()..position = position;
        final service = GeolocatorLocationService(gateway: gateway);

        await expectLater(
          service.acquireCurrentPosition(
            policy: const LocationAcquisitionPolicy(
              maximumAcceptedAccuracyMeters: 50,
            ),
          ),
          throwsA(
            isA<LocationFailure>().having(
              (error) => error.kind,
              'kind',
              LocationFailureKind.inaccurate,
            ),
          ),
        );
      }
    });

    test('maps timeout, disabled service, and denied permission', () async {
      final cases = <(Object, LocationFailureKind)>[
        (TimeoutException('synthetic'), LocationFailureKind.timeout),
        (
          const LocationServiceDisabledException(),
          LocationFailureKind.serviceDisabled,
        ),
        (
          const PermissionDeniedException('synthetic'),
          LocationFailureKind.permissionDenied,
        ),
      ];
      for (final (packageError, expectedKind) in cases) {
        final gateway = FakeGeolocatorGateway()..positionError = packageError;
        final service = GeolocatorLocationService(gateway: gateway);

        await expectLater(
          service.acquireCurrentPosition(
            policy: const LocationAcquisitionPolicy(),
          ),
          throwsA(
            isA<LocationFailure>().having(
              (error) => error.kind,
              'kind',
              expectedKind,
            ),
          ),
        );
      }
    });

    test('does not retain a coordinate in adapter cleanup', () async {
      final gateway = FakeGeolocatorGateway();
      final service = GeolocatorLocationService(gateway: gateway);
      await service.acquireCurrentPosition(
        policy: const LocationAcquisitionPolicy(),
      );

      await service.clearTemporaryState();
      await service.acquireCurrentPosition(
        policy: const LocationAcquisitionPolicy(),
      );
      service.dispose();

      // A second acquisition asks the package again; the adapter has no cached
      // coordinate to return.
      expect(gateway.positionRequests, 2);
    });
  });
}
