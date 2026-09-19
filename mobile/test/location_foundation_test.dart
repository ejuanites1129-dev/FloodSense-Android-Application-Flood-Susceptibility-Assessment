import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/location/location_flow_state.dart';
import 'package:floodsense/features/location/location_service.dart';

class FakeLocationService implements LocationService {
  bool requestedPermission = false;
  bool cleared = false;
  bool disposed = false;

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) async => TemporaryLocation(
    latitude: 14.41,
    longitude: 120.97,
    accuracyMeters: 10,
    acquiredAt: DateTime.utc(2026, 9, 19),
  );

  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.notRequested;

  @override
  Future<void> clearTemporaryState() async {
    cleared = true;
  }

  @override
  void dispose() {
    disposed = true;
  }

  @override
  Future<bool> isLocationServiceEnabled() async => true;

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;

  @override
  Future<LocationPermissionState> requestForegroundPermission() async {
    requestedPermission = true;
    return LocationPermissionState.foregroundGranted;
  }
}

void main() {
  TemporaryLocation location({double accuracy = 12}) => TemporaryLocation(
    latitude: 14.41,
    longitude: 120.97,
    accuracyMeters: accuracy,
    acquiredAt: DateTime.utc(2026, 9, 19),
  );

  group('LocationService foundation', () {
    test('platform contract is fakeable without a location plugin', () async {
      final service = FakeLocationService();

      expect(await service.isLocationServiceEnabled(), isTrue);
      expect(
        await service.checkPermission(),
        LocationPermissionState.notRequested,
      );
      expect(
        await service.requestForegroundPermission(),
        LocationPermissionState.foregroundGranted,
      );
      expect(service.requestedPermission, isTrue);
      expect(
        (await service.acquireCurrentPosition(
          policy: const LocationAcquisitionPolicy(),
        )).accuracyMeters,
        10,
      );
      await service.clearTemporaryState();
      service.dispose();
      expect(service.cleared, isTrue);
      expect(service.disposed, isTrue);
    });

    test('default policy accepts only timely-policy accuracy', () {
      const policy = LocationAcquisitionPolicy();

      expect(policy.timeout, const Duration(seconds: 15));
      expect(policy.maximumAcceptedAccuracyMeters, 50);
      expect(policy.accepts(location(accuracy: 50)), isTrue);
      expect(policy.accepts(location(accuracy: 50.01)), isFalse);
    });

    test('temporary coordinate is cleared on clear, reset, and dispose', () {
      final session = TemporaryLocationSession()..retain(location());

      session.clear();
      expect(session.location, isNull);
      session.retain(location());
      session.reset();
      expect(session.location, isNull);
      session.retain(location());
      session.dispose();
      expect(session.location, isNull);
      expect(session.isDisposed, isTrue);
      expect(() => session.retain(location()), throwsStateError);
    });

    test('temporary coordinate rejects invalid or non-finite values', () {
      expect(
        () => TemporaryLocation(
          latitude: double.nan,
          longitude: 120,
          accuracyMeters: 10,
          acquiredAt: DateTime.utc(2026),
        ),
        throwsArgumentError,
      );
      expect(
        () => TemporaryLocation(
          latitude: 14,
          longitude: 181,
          accuracyMeters: 10,
          acquiredAt: DateTime.utc(2026),
        ),
        throwsArgumentError,
      );
    });
  });

  group('LocationFlowState contract', () {
    test('all states retain manual pin and barangay fallbacks', () {
      for (final phase in LocationFlowPhase.values) {
        final state = LocationFlowState(
          phase,
          temporaryLocation: switch (phase) {
            LocationFlowPhase.acquired ||
            LocationFlowPhase.resolvingBarangay ||
            LocationFlowPhase.resolvedCandidate ||
            LocationFlowPhase.confirmed ||
            LocationFlowPhase.rejected ||
            LocationFlowPhase.outsideBacoor ||
            LocationFlowPhase.ambiguousBoundary ||
            LocationFlowPhase.resolverUnavailable ||
            LocationFlowPhase.resolverTimeout ||
            LocationFlowPhase.resolverFailure ||
            LocationFlowPhase.malformedResponse ||
            LocationFlowPhase.recoverableError => location(),
            _ => null,
          },
        );

        expect(state.message, isNotEmpty, reason: '$phase needs visible copy');
        expect(state.manualSelectionAvailable, isTrue, reason: '$phase');
      }
    });

    test('only post-acquisition states may retain a coordinate', () {
      for (final phase in LocationFlowPhase.values) {
        if (phase == LocationFlowPhase.acquired ||
            phase == LocationFlowPhase.resolvingBarangay ||
            phase == LocationFlowPhase.resolvedCandidate ||
            phase == LocationFlowPhase.confirmed ||
            phase == LocationFlowPhase.rejected ||
            phase == LocationFlowPhase.outsideBacoor ||
            phase == LocationFlowPhase.ambiguousBoundary ||
            phase == LocationFlowPhase.resolverUnavailable ||
            phase == LocationFlowPhase.resolverTimeout ||
            phase == LocationFlowPhase.resolverFailure ||
            phase == LocationFlowPhase.malformedResponse ||
            phase == LocationFlowPhase.recoverableError) {
          continue;
        }
        expect(
          () => LocationFlowState(phase, temporaryLocation: location()),
          throwsArgumentError,
        );
      }
    });

    test(
      'clear removes a retained coordinate and exposes safe restart actions',
      () {
        final cleared = LocationFlowState(
          LocationFlowPhase.acquired,
          temporaryLocation: location(),
        ).clear();

        expect(cleared.phase, LocationFlowPhase.cleared);
        expect(cleared.temporaryLocation, isNull);
        expect(
          cleared.allowedActions,
          contains(LocationFlowAction.showPurpose),
        );
      },
    );

    test('permanent denial uses settings instead of another prompt', () {
      final state = LocationFlowState(
        LocationFlowPhase.permissionDeniedPermanently,
      );

      expect(state.retryAllowed, isFalse);
      expect(
        state.allowedActions,
        contains(LocationFlowAction.openAppSettings),
      );
    });
  });
}
