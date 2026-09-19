import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/data/api/api_exception.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/location/location_flow_state.dart';
import 'package:floodsense/features/location/location_service.dart';

import 'test_data.dart';

class FakeDay3LocationService implements LocationService {
  LocationPermissionState checkedPermission =
      LocationPermissionState.notRequested;
  int permissionRequests = 0;
  int acquisitions = 0;
  int clearCalls = 0;
  bool disposed = false;
  Completer<TemporaryLocation>? completer;
  TemporaryLocation location = TemporaryLocation(
    latitude: 14.405,
    longitude: 120.965,
    accuracyMeters: 18,
    acquiredAt: DateTime.utc(2026, 9, 19),
  );

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) {
    acquisitions++;
    return completer?.future ?? Future.value(location);
  }

  @override
  Future<LocationPermissionState> checkPermission() async => checkedPermission;

  @override
  Future<void> clearTemporaryState() async => clearCalls++;

  @override
  void dispose() => disposed = true;

  @override
  Future<bool> isLocationServiceEnabled() async => true;

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;

  @override
  Future<LocationPermissionState> requestForegroundPermission() async {
    permissionRequests++;
    return LocationPermissionState.foregroundGranted;
  }
}

class FakeBarangayResolver implements BarangayResolver {
  int calls = 0;
  double? latitude;
  double? longitude;
  Future<BarangayResolution> Function(double, double)? handler;

  @override
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  }) {
    calls++;
    this.latitude = latitude;
    this.longitude = longitude;
    return handler?.call(latitude, longitude) ??
        Future.value(sampleBarangayResolution());
  }
}

Future<void> acquire(LocationController controller) async {
  controller.showPurposeExplanation();
  await controller.continueAfterPurposeExplanation();
}

void main() {
  group('Day 3 GPS-to-barangay controller', () {
    test(
      'acquires once, maps latitude/longitude, and requires confirmation',
      () async {
        final location = FakeDay3LocationService();
        final resolver = FakeBarangayResolver();
        final controller = LocationController(location, resolver: resolver);

        await acquire(controller);

        expect(location.permissionRequests, 1);
        expect(location.acquisitions, 1);
        expect(resolver.calls, 1);
        expect(resolver.latitude, 14.405);
        expect(resolver.longitude, 120.965);
        expect(controller.lookupCoordinate?.latitude, 14.405);
        expect(controller.state.phase, LocationFlowPhase.resolvedCandidate);
        expect(controller.confirmedBarangay, isNull);

        controller.confirmCandidate();
        expect(controller.state.phase, LocationFlowPhase.confirmed);
        expect(controller.confirmedBarangay?.psgcCode, '0402103004');
        controller.dispose();
      },
    );

    test(
      'maps all neutral resolver states without choosing a barangay',
      () async {
        final cases = {
          'OUTSIDE_BACOOR': LocationFlowPhase.outsideBacoor,
          'AMBIGUOUS_BOUNDARY': LocationFlowPhase.ambiguousBoundary,
          'UNAVAILABLE': LocationFlowPhase.resolverUnavailable,
        };
        for (final entry in cases.entries) {
          final resolver = FakeBarangayResolver()
            ..handler = (_, _) async =>
                sampleBarangayResolution(state: entry.key);
          final controller = LocationController(
            FakeDay3LocationService(),
            resolver: resolver,
          );

          await acquire(controller);

          expect(controller.state.phase, entry.value);
          expect(controller.confirmedBarangay, isNull);
          controller.dispose();
        }
      },
    );

    test(
      'retry reuses retained coordinate without another permission or GPS read',
      () async {
        final location = FakeDay3LocationService();
        final resolver = FakeBarangayResolver();
        var fail = true;
        resolver.handler = (_, _) async {
          if (fail) {
            throw const ApiException(
              'offline',
              kind: ApiFailureKind.connectivity,
            );
          }
          return sampleBarangayResolution();
        };
        final controller = LocationController(location, resolver: resolver);

        await acquire(controller);
        expect(controller.state.phase, LocationFlowPhase.resolverFailure);
        fail = false;
        await controller.retry();

        expect(controller.state.phase, LocationFlowPhase.resolvedCandidate);
        expect(location.permissionRequests, 1);
        expect(location.acquisitions, 1);
        expect(resolver.calls, 2);
        controller.dispose();
      },
    );

    test(
      'duplicate action, stale response, and disposal are safely ignored',
      () async {
        final location = FakeDay3LocationService()
          ..completer = Completer<TemporaryLocation>();
        final resolver = FakeBarangayResolver();
        final controller = LocationController(location, resolver: resolver);
        controller.showPurposeExplanation();

        final first = controller.continueAfterPurposeExplanation();
        final duplicate = controller.continueAfterPurposeExplanation();
        await Future<void>.delayed(Duration.zero);
        expect(location.acquisitions, 1);
        location.completer!.complete(location.location);
        await Future.wait([first, duplicate]);
        expect(resolver.calls, 1);

        final pending = Completer<BarangayResolution>();
        resolver.handler = (_, _) => pending.future;
        final manualLookup = controller.resolveManualPin(
          const MapCoordinate(latitude: 14.41, longitude: 120.97),
        );
        await Future<void>.delayed(Duration.zero);
        final manual = BarangayIdentity(
          psgcCode: '0402103007',
          name: 'Dulong Bayan',
        );
        await controller.selectManualBarangay(manual);
        pending.complete(sampleBarangayResolution());
        await manualLookup;
        expect(controller.confirmedBarangay?.psgcCode, '0402103007');

        final disposedPending = Completer<BarangayResolution>();
        resolver.handler = (_, _) => disposedPending.future;
        final request = controller.resolveManualPin(
          const MapCoordinate(latitude: 14.42, longitude: 120.98),
        );
        await Future<void>.delayed(Duration.zero);
        controller.dispose();
        disposedPending.complete(sampleBarangayResolution());
        await request;
        expect(controller.temporaryLocation, isNull);
        expect(location.disposed, isTrue);
      },
    );

    test('manual pin overrides GPS candidate and clear removes all temporary state', () async {
      final location = FakeDay3LocationService();
      final resolver = FakeBarangayResolver();
      final controller = LocationController(location, resolver: resolver);
      await acquire(controller);

      await controller.resolveManualPin(
        const MapCoordinate(latitude: 14.42, longitude: 120.98),
      );

      expect(resolver.calls, 2);
      expect(resolver.latitude, 14.42);
      expect(resolver.longitude, 120.98);
      expect(controller.temporaryLocation, isNull);
      expect(controller.lookupCoordinate?.latitude, 14.42);
      await controller.clearLocation();
      expect(controller.lookupCoordinate, isNull);
      expect(controller.resolution, isNull);
      expect(controller.confirmedBarangay, isNull);
      controller.dispose();
    });

    test(
      'reject and manual selection replace the unconfirmed candidate',
      () async {
        final controller = LocationController(
          FakeDay3LocationService(),
          resolver: FakeBarangayResolver(),
        );
        await acquire(controller);

        controller.rejectCandidate();
        expect(controller.state.phase, LocationFlowPhase.rejected);
        expect(controller.candidateBarangay, isNull);
        await controller.selectManualBarangay(
          BarangayIdentity(psgcCode: '0402103007', name: 'Dulong Bayan'),
        );

        expect(controller.state.phase, LocationFlowPhase.confirmed);
        expect(controller.confirmedBarangay?.name, 'Dulong Bayan');
        expect(controller.lookupCoordinate, isNull);
        controller.dispose();
      },
    );

    test(
      'typed timeout, server, and malformed failures remain retryable',
      () async {
        final cases = {
          ApiFailureKind.timeout: LocationFlowPhase.resolverTimeout,
          ApiFailureKind.service: LocationFlowPhase.resolverUnavailable,
          ApiFailureKind.malformedResponse: LocationFlowPhase.malformedResponse,
        };
        for (final entry in cases.entries) {
          final resolver = FakeBarangayResolver()
            ..handler = (_, _) async =>
                throw ApiException('safe error', kind: entry.key);
          final controller = LocationController(
            FakeDay3LocationService(),
            resolver: resolver,
          );

          await acquire(controller);

          expect(controller.state.phase, entry.value);
          expect(controller.state.retryAllowed, isTrue);
          controller.dispose();
        }
      },
    );
  });

  testWidgets(
    'resolved flow shows marker, confirmation, preserves rainfall, and does not assess',
    (tester) async {
      final api = FakeFloodSenseApi();
      final location = FakeDay3LocationService();
      await tester.pumpWidget(
        FloodSenseApp(api: api, locationService: location, showBasemap: false),
      );
      await tester.pumpAndSettle();

      final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
      await tester.ensureVisible(intensity);
      await tester.tap(intensity);
      await tester.pump();
      final duration = find.byKey(const Key('duration-DEMO_6_HOURS'));
      await tester.ensureVisible(duration);
      await tester.tap(duration);
      await tester.pumpAndSettle();

      final useLocation = find.byKey(const Key('use-my-location-button'));
      await tester.ensureVisible(useLocation);
      await tester.tap(useLocation);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('location-purpose-continue')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('temporary-location-map-marker')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('temporary-location-accuracy-circle')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('detected-barangay-candidate')),
        findsOneWidget,
      );
      expect(api.barangayCalls, 1);
      expect(api.evaluateCalls, 0);
      final referenceMap = tester.widget<FlutterMap>(
        find.descendant(
          of: find.byKey(const Key('reference-boundary-map')),
          matching: find.byType(FlutterMap),
        ),
      );
      expect(
        referenceMap.mapController!.camera.center.latitude,
        closeTo(14.405, 0.000001),
      );
      expect(
        referenceMap.mapController!.camera.center.longitude,
        closeTo(120.965, 0.000001),
      );
      expect(find.bySemanticsLabel(RegExp('Heavy, selected')), findsOneWidget);
      expect(
        find.bySemanticsLabel(RegExp('6 hours, selected')),
        findsOneWidget,
      );

      final confirm = find.byKey(const Key('confirm-detected-barangay-button'));
      await tester.ensureVisible(confirm);
      await tester.tap(confirm);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('confirmed-barangay')), findsOneWidget);
      expect(api.evaluateCalls, 0);
    },
  );
}
