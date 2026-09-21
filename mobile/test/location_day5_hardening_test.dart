import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/models/nearest_center_result.dart';
import 'package:floodsense/data/models/verified_center.dart';
import 'package:floodsense/features/assessment/assessment_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';
import 'package:floodsense/features/evacuation/nearest_centers_section.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/location/location_copy.dart';
import 'package:floodsense/features/location/location_flow_state.dart';
import 'package:floodsense/features/location/location_service.dart';

import 'test_data.dart';

final class DeferredLocationService implements LocationService {
  Completer<bool>? serviceEnabledCompleter;
  Completer<LocationPermissionState>? permissionCompleter;
  int permissionChecks = 0;
  int permissionRequests = 0;
  int acquisitions = 0;
  int clearCalls = 0;

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) async {
    acquisitions++;
    return TemporaryLocation(
      latitude: 14.405,
      longitude: 120.965,
      accuracyMeters: 10,
      acquiredAt: DateTime.utc(2026, 9, 20),
    );
  }

  @override
  Future<LocationPermissionState> checkPermission() {
    permissionChecks++;
    return permissionCompleter?.future ??
        Future.value(LocationPermissionState.foregroundGranted);
  }

  @override
  Future<void> clearTemporaryState() async => clearCalls++;

  @override
  void dispose() {}

  @override
  Future<bool> isLocationServiceEnabled() =>
      serviceEnabledCompleter?.future ?? Future.value(true);

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

final class DeferredResolver implements BarangayResolver {
  Completer<BarangayResolution>? completer;
  int calls = 0;

  @override
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  }) {
    calls++;
    return completer?.future ?? Future.value(sampleBarangayResolution());
  }
}

final class Day5CenterProvider implements NearestCenterProvider {
  Day5CenterProvider(this.handler);

  final Future<List<VerifiedCenter>> Function() handler;
  int calls = 0;

  @override
  Future<NearestCenterResult> findNearest({
    required double latitude,
    required double longitude,
  }) async {
    calls++;
    final centers = await handler();
    return NearestCenterResult(
      centers: centers,
      distanceMethod: nearestCenterDistanceMethod,
      warnings: centers.isEmpty
          ? const [nearestCenterEmptyWarning, nearestCenterEmptyDistanceWarning]
          : const [nearestCenterDistanceWarning],
    );
  }
}

VerifiedCenter day5Center({
  String identifier = 'safe-center',
  String name = 'Synthetic center',
  String address = 'Synthetic address',
  String barangayName = 'Bayanan',
  String source = 'Synthetic test source',
  List<String> limitations = const ['Synthetic limitation'],
  double distance = 100,
}) => VerifiedCenter(
  publicIdentifier: identifier,
  name: name,
  address: address,
  barangay: CenterBarangayIdentity(psgcCode: '0402103004', name: barangayName),
  latitude: 14.406,
  longitude: 120.966,
  approximateDistance: distance,
  distanceUnit: CenterDistanceUnit.meters,
  verifiedOn: DateTime.utc(2026, 9, 20),
  sourceAttribution: source,
  limitations: limitations,
);

Future<void> acquireAndConfirm(LocationController controller) async {
  controller.showPurposeExplanation();
  await controller.continueAfterPurposeExplanation();
  controller.confirmCandidate();
  await Future<void>.delayed(Duration.zero);
}

void main() {
  group('Day 5 location privacy and concurrency', () {
    test(
      'pre-permission copy states purpose, temporary use, and manual fallback',
      () {
        expect(LocationCopy.purpose, contains('likely Bacoor barangay'));
        expect(LocationCopy.purpose, contains('does not determine'));
        expect(LocationCopy.privacy, contains('only during this flow'));
        expect(LocationCopy.privacy, contains('not retained'));
        expect(LocationCopy.privacy, contains('map pin or barangay selector'));
        expect(LocationCopy.purpose, isNot(contains('14.')));
        expect(LocationCopy.privacy, isNot(contains('120.')));
      },
    );

    test(
      'clear during service check prevents the stale permission chain',
      () async {
        final service = DeferredLocationService()
          ..serviceEnabledCompleter = Completer<bool>();
        final controller = LocationController(
          service,
          resolver: DeferredResolver(),
        );
        controller.showPurposeExplanation();

        final pending = controller.continueAfterPurposeExplanation();
        await Future<void>.delayed(Duration.zero);
        await controller.clearLocation();
        service.serviceEnabledCompleter!.complete(true);
        await pending;

        expect(controller.state.phase, LocationFlowPhase.cleared);
        expect(controller.lookupCoordinate, isNull);
        expect(controller.temporaryLocation, isNull);
        expect(service.permissionChecks, 0);
        expect(service.permissionRequests, 0);
        expect(service.acquisitions, 0);
        controller.dispose();
      },
    );

    test(
      'manual selection during permission check prevents a stale prompt',
      () async {
        final service = DeferredLocationService()
          ..permissionCompleter = Completer<LocationPermissionState>();
        final controller = LocationController(
          service,
          resolver: DeferredResolver(),
        );
        controller.showPurposeExplanation();

        final pending = controller.continueAfterPurposeExplanation();
        await Future<void>.delayed(Duration.zero);
        await controller.selectManualBarangay(
          BarangayIdentity(psgcCode: '0402103004', name: 'Bayanan'),
        );
        service.permissionCompleter!.complete(
          LocationPermissionState.notRequested,
        );
        await pending;

        expect(controller.state.phase, LocationFlowPhase.confirmed);
        expect(controller.confirmedBarangay?.psgcCode, '0402103004');
        expect(controller.lookupCoordinate, isNull);
        expect(service.permissionRequests, 0);
        expect(service.acquisitions, 0);
        controller.dispose();
      },
    );

    test(
      'clear during resolver request prevents coordinate restoration',
      () async {
        final resolver = DeferredResolver()
          ..completer = Completer<BarangayResolution>();
        final controller = LocationController(
          DeferredLocationService(),
          resolver: resolver,
        );
        controller.showPurposeExplanation();

        final pending = controller.continueAfterPurposeExplanation();
        await Future<void>.delayed(Duration.zero);
        expect(resolver.calls, 1);
        await controller.clearLocation();
        resolver.completer!.complete(sampleBarangayResolution());
        await pending;

        expect(controller.state.phase, LocationFlowPhase.cleared);
        expect(controller.lookupCoordinate, isNull);
        expect(controller.temporaryLocation, isNull);
        expect(controller.resolution, isNull);
        expect(controller.confirmedBarangay, isNull);
        controller.dispose();
      },
    );

    test(
      'GPS and manual confirmation produce the same barangay identity',
      () async {
        final gps = LocationController(
          DeferredLocationService(),
          resolver: DeferredResolver(),
        );
        await acquireAndConfirm(gps);

        final manual = LocationController(
          DeferredLocationService(),
          resolver: DeferredResolver(),
        );
        await manual.selectManualBarangay(
          BarangayIdentity(psgcCode: '0402103004', name: 'Bayanan'),
        );

        expect(
          manual.confirmedBarangay?.psgcCode,
          gps.confirmedBarangay?.psgcCode,
        );
        expect(manual.confirmedBarangay?.name, gps.confirmedBarangay?.name);
        expect(manual.lookupCoordinate, isNull);
        gps.dispose();
        manual.dispose();
      },
    );

    test(
      'disposing assessment flow invalidates an in-flight pin lookup',
      () async {
        final pending = Completer<PointResolution>();
        final api = FakeFloodSenseApi(pointHandler: (_, _) => pending.future);
        final controller = AssessmentController(api);

        final request = controller.placePin(
          const MapCoordinate(latitude: 14.4, longitude: 120.9),
        );
        await Future<void>.delayed(Duration.zero);
        expect(controller.pinCoordinate, isNotNull);
        controller.dispose();
        pending.complete(samplePointResolution());
        await request;

        expect(controller.pinCoordinate, isNull);
        expect(controller.pointResolution, isNull);
        expect(controller.selectedArea, isNull);
        expect(api.closed, isTrue);
      },
    );
  });

  group('Day 5 center and inference separation', () {
    test('result ordering, empty results, and failure cannot change classification', () async {
      final api = FakeFloodSenseApi();
      final assessment = AssessmentController(api);
      await assessment.load();
      assessment.selectIntensity(assessment.intensities.last);
      assessment.selectDuration(assessment.durations.last);
      assessment.selectArea(assessment.areas.single);
      await assessment.submit();
      final originalResult = assessment.result;
      expect(originalResult?.susceptibility?.code, 'HIGH');

      final cases = <Future<List<VerifiedCenter>> Function()>[
        () async => [
          day5Center(identifier: 'far', distance: 900),
          day5Center(identifier: 'near', distance: 100),
        ],
        () async => [],
        () async => throw const CenterLookupException(
          CenterLookupFailureKind.serverUnavailable,
        ),
      ];
      for (final handler in cases) {
        final location = LocationController(
          DeferredLocationService(),
          resolver: DeferredResolver(),
        );
        final centers = NearestCenterController(
          location,
          provider: Day5CenterProvider(handler),
        );
        await acquireAndConfirm(location);

        expect(assessment.result, same(originalResult));
        expect(assessment.result?.susceptibility?.code, 'HIGH');
        expect(api.evaluateCalls, 1);
        centers.dispose();
        location.dispose();
      }
      assessment.dispose();
    });

    test(
      'center failure messages never include the submitted coordinate',
      () async {
        for (final kind in CenterLookupFailureKind.values) {
          final location = LocationController(
            DeferredLocationService(),
            resolver: DeferredResolver(),
          );
          final centers = NearestCenterController(
            location,
            provider: Day5CenterProvider(
              () async => throw CenterLookupException(kind),
            ),
          );
          await acquireAndConfirm(location);

          expect(centers.message, isNot(contains('14.405')));
          expect(centers.message, isNot(contains('120.965')));
          centers.dispose();
          location.dispose();
        }
      },
    );
  });

  testWidgets('untrusted public center fields render as inert Flutter text', (
    tester,
  ) async {
    final name = '<script>alert("x")</script> \u202ECenter';
    final address = 'A & B\n"quoted" ${List.filled(200, 'long').join(' ')}';
    final barangay = 'Ba\u00F1ayan \u202Dtest';
    final source = '<img src=x onerror=alert(1)> & source';
    final limitation = 'Line one\n<script>not executable</script> \u2067text';
    final location = LocationController(
      DeferredLocationService(),
      resolver: DeferredResolver(),
    );
    final centers = NearestCenterController(
      location,
      provider: Day5CenterProvider(
        () async => [
          day5Center(
            name: name,
            address: address,
            barangayName: barangay,
            source: source,
            limitations: [limitation],
          ),
        ],
      ),
    );
    location.showPurposeExplanation();
    await location.continueAfterPurposeExplanation();
    location.confirmCandidate();
    await tester.pump();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: NearestCentersSection(controller: centers),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text(name), findsOneWidget);
    expect(find.text(address), findsOneWidget);
    expect(find.text('$barangay (0402103004)'), findsOneWidget);
    expect(find.text('Source: $source'), findsOneWidget);
    expect(find.text('Limitation: $limitation'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.pumpWidget(const SizedBox.shrink());
    centers.dispose();
    location.dispose();
  });
}
