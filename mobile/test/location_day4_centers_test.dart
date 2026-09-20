import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/models/verified_center.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/location/location_service.dart';

import 'test_data.dart';

class Day4LocationService implements LocationService {
  LocationPermissionState permission =
      LocationPermissionState.foregroundGranted;
  TemporaryLocation location = TemporaryLocation(
    latitude: 14.405,
    longitude: 120.965,
    accuracyMeters: 12,
    acquiredAt: DateTime.utc(2026, 9, 20),
  );

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) async => location;

  @override
  Future<LocationPermissionState> checkPermission() async => permission;

  @override
  Future<void> clearTemporaryState() async {}

  @override
  void dispose() {}

  @override
  Future<bool> isLocationServiceEnabled() async => true;

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;

  @override
  Future<LocationPermissionState> requestForegroundPermission() async =>
      permission;
}

class Day4Resolver implements BarangayResolver {
  @override
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  }) async => sampleBarangayResolution();
}

class FakeNearestCenterProvider implements NearestCenterProvider {
  int calls = 0;
  double? latitude;
  double? longitude;
  Future<List<VerifiedCenter>> Function(double latitude, double longitude)?
  handler;

  @override
  Future<List<VerifiedCenter>> findNearest({
    required double latitude,
    required double longitude,
  }) {
    calls++;
    this.latitude = latitude;
    this.longitude = longitude;
    return handler?.call(latitude, longitude) ?? Future.value(sampleCenters());
  }
}

List<VerifiedCenter> sampleCenters() => [
  VerifiedCenter(
    publicIdentifier: 'public-near',
    name: 'Synthetic Near Center',
    address: 'Synthetic public address A',
    barangay: CenterBarangayIdentity(psgcCode: '0402103004', name: 'Bayanan'),
    latitude: 14.406,
    longitude: 120.966,
    approximateDistance: 180,
    distanceUnit: CenterDistanceUnit.meters,
    verifiedOn: DateTime.utc(2026, 9, 1),
    sourceAttribution: 'Synthetic approved test source',
    limitations: const ['Test-only public limitation'],
  ),
  VerifiedCenter(
    publicIdentifier: 'public-far',
    name: 'Synthetic Far Center',
    address: 'Synthetic public address B',
    barangay: CenterBarangayIdentity(
      psgcCode: '0402103007',
      name: 'Dulong Bayan',
    ),
    latitude: 14.408,
    longitude: 120.968,
    approximateDistance: 1.2,
    distanceUnit: CenterDistanceUnit.kilometers,
    verifiedOn: DateTime.utc(2026, 8, 15),
    sourceAttribution: 'Second synthetic approved test source',
  ),
];

Future<void> acquireAndConfirm(LocationController location) async {
  location.showPurposeExplanation();
  await location.continueAfterPurposeExplanation();
  location.confirmCandidate();
  await Future<void>.delayed(Duration.zero);
}

void main() {
  group('Day 4 center request timing and state', () {
    test(
      'does not request before confirmation, then maps coordinate once',
      () async {
        final location = LocationController(
          Day4LocationService(),
          resolver: Day4Resolver(),
        );
        final provider = FakeNearestCenterProvider();
        final centers = NearestCenterController(location, provider: provider);

        location.showPurposeExplanation();
        await location.continueAfterPurposeExplanation();
        expect(provider.calls, 0);
        expect(
          centers.phase,
          NearestCenterPhase.waitingForLocationConfirmation,
        );

        location.confirmCandidate();
        await Future<void>.delayed(Duration.zero);

        expect(provider.calls, 1);
        expect(provider.latitude, 14.405);
        expect(provider.longitude, 120.965);
        expect(centers.phase, NearestCenterPhase.resultsAvailable);
        expect(centers.centers.map((center) => center.publicIdentifier), [
          'public-near',
          'public-far',
        ]);
        centers.dispose();
        location.dispose();
      },
    );

    test(
      'requests after confirmed manual pin but not barangay-only choice',
      () async {
        final location = LocationController(
          Day4LocationService(),
          resolver: Day4Resolver(),
        );
        final provider = FakeNearestCenterProvider();
        final centers = NearestCenterController(location, provider: provider);

        await location.selectManualBarangay(
          BarangayIdentity(psgcCode: '0402103004', name: 'Bayanan'),
        );
        expect(provider.calls, 0);
        expect(centers.phase, NearestCenterPhase.coordinateRequired);

        await location.resolveManualPin(
          const MapCoordinate(latitude: 14.41, longitude: 120.97),
        );
        expect(provider.calls, 0);
        location.confirmCandidate();
        await Future<void>.delayed(Duration.zero);

        expect(provider.calls, 1);
        expect(provider.latitude, 14.41);
        expect(provider.longitude, 120.97);
        centers.dispose();
        location.dispose();
      },
    );

    test(
      'maps truthful empty and typed failure states with explicit retry',
      () async {
        final cases = {
          CenterLookupFailureKind.offline: NearestCenterPhase.offline,
          CenterLookupFailureKind.timeout: NearestCenterPhase.timeout,
          CenterLookupFailureKind.serverUnavailable:
              NearestCenterPhase.serverUnavailable,
          CenterLookupFailureKind.malformedResponse:
              NearestCenterPhase.malformedResponse,
          CenterLookupFailureKind.recoverable:
              NearestCenterPhase.recoverableError,
        };
        for (final entry in cases.entries) {
          final location = LocationController(
            Day4LocationService(),
            resolver: Day4Resolver(),
          );
          final provider = FakeNearestCenterProvider()
            ..handler = (_, _) async => throw CenterLookupException(entry.key);
          final centers = NearestCenterController(location, provider: provider);

          await acquireAndConfirm(location);

          expect(centers.phase, entry.value);
          expect(centers.canRetry, isTrue);
          expect(location.confirmedBarangay, isNotNull);
          final before = provider.calls;
          await centers.retry();
          expect(provider.calls, before + 1);
          centers.dispose();
          location.dispose();
        }

        final location = LocationController(
          Day4LocationService(),
          resolver: Day4Resolver(),
        );
        final provider = FakeNearestCenterProvider()
          ..handler = (_, _) async => [];
        final centers = NearestCenterController(location, provider: provider);
        await acquireAndConfirm(location);
        expect(centers.phase, NearestCenterPhase.empty);
        expect(centers.message, contains('does not mean'));
        centers.dispose();
        location.dispose();
      },
    );

    test(
      'prevents duplicates and ignores stale and post-disposal responses',
      () async {
        final first = Completer<List<VerifiedCenter>>();
        final second = Completer<List<VerifiedCenter>>();
        final provider = FakeNearestCenterProvider();
        var request = 0;
        provider.handler = (_, _) =>
            request++ == 0 ? first.future : second.future;
        final location = LocationController(
          Day4LocationService(),
          resolver: Day4Resolver(),
        );
        final centers = NearestCenterController(location, provider: provider);

        await acquireAndConfirm(location);
        location.confirmCandidate();
        expect(provider.calls, 1);

        await location.resolveManualPin(
          const MapCoordinate(latitude: 14.42, longitude: 120.98),
        );
        location.confirmCandidate();
        await Future<void>.delayed(Duration.zero);
        expect(provider.calls, 2);

        first.complete(sampleCenters().reversed.toList());
        await Future<void>.delayed(Duration.zero);
        expect(centers.centers, isEmpty);
        second.complete(sampleCenters());
        await Future<void>.delayed(Duration.zero);
        expect(centers.centers.first.publicIdentifier, 'public-near');

        await location.clearLocation();
        expect(centers.centers, isEmpty);
        expect(centers.phase, NearestCenterPhase.locationCleared);

        final third = Completer<List<VerifiedCenter>>();
        provider.handler = (_, _) => third.future;
        await acquireAndConfirm(location);
        centers.dispose();
        third.complete(sampleCenters());
        await Future<void>.delayed(Duration.zero);
        location.dispose();
      },
    );

    test('permission denial never requests centers and manual flow remains available', () async {
      final service = Day4LocationService()
        ..permission = LocationPermissionState.denied;
      final location = LocationController(service, resolver: Day4Resolver());
      final provider = FakeNearestCenterProvider();
      final centers = NearestCenterController(location, provider: provider);

      expect(centers.phase, NearestCenterPhase.notRequested);
      expect(provider.calls, 0);
      location.showPurposeExplanation();
      await location.continueAfterPurposeExplanation();

      expect(provider.calls, 0);
      expect(centers.phase, NearestCenterPhase.waitingForLocationConfirmation);
      expect(location.state.manualSelectionAvailable, isTrue);
      centers.dispose();
      location.dispose();
    });

    test(
      'missing frozen Stream C contract produces honest unavailable state',
      () async {
        final location = LocationController(
          Day4LocationService(),
          resolver: Day4Resolver(),
        );
        final centers = NearestCenterController(location);

        await acquireAndConfirm(location);

        expect(centers.phase, NearestCenterPhase.contractUnavailable);
        expect(centers.centers, isEmpty);
        centers.dispose();
        location.dispose();
      },
    );

    test('duplicate public identifiers reject the complete result set', () async {
      final duplicate = sampleCenters().first;
      final provider = FakeNearestCenterProvider()
        ..handler = (_, _) async => [duplicate, duplicate];
      final location = LocationController(
        Day4LocationService(),
        resolver: Day4Resolver(),
      );
      final centers = NearestCenterController(location, provider: provider);

      await acquireAndConfirm(location);

      expect(centers.phase, NearestCenterPhase.malformedResponse);
      expect(centers.centers, isEmpty);
      centers.dispose();
      location.dispose();
    });
  });

  testWidgets(
    'renders ordered cards, differentiated markers, and safety copy',
    (tester) async {
      final api = FakeFloodSenseApi();
      final provider = FakeNearestCenterProvider();
      await tester.pumpWidget(
        FloodSenseApp(
          api: api,
          locationService: Day4LocationService(),
          nearestCenterProvider: provider,
          showBasemap: false,
        ),
      );
      await tester.pumpAndSettle();

      final useLocation = find.byKey(const Key('use-my-location-button'));
      await tester.ensureVisible(useLocation);
      await tester.tap(useLocation);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('location-purpose-continue')));
      await tester.pumpAndSettle();
      expect(provider.calls, 0);

      final confirm = find.byKey(const Key('confirm-detected-barangay-button'));
      await tester.ensureVisible(confirm);
      await tester.tap(confirm);
      await tester.pumpAndSettle();

      expect(provider.calls, 1);
      expect(find.byKey(const Key('nearest-center-markers')), findsOneWidget);
      expect(
        find.byKey(const Key('nearest-center-marker-public-near')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('temporary-location-map-marker')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('nearest-center-card-public-near')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('nearest-center-card-public-far')),
        findsOneWidget,
      );
      expect(
        find.text('180 m approximate straight-line distance'),
        findsOneWidget,
      );
      expect(find.text('Verified on 2026-09-01'), findsOneWidget);
      expect(
        find.textContaining('Synthetic approved test source'),
        findsWidgets,
      );
      expect(
        find.textContaining('Test-only public limitation'),
        findsOneWidget,
      );
      expect(find.textContaining('not road distances'), findsOneWidget);
      expect(
        find.textContaining('Nearest does not mean safest'),
        findsOneWidget,
      );
      expect(
        find.textContaining('does not guarantee available space'),
        findsOneWidget,
      );
      expect(api.evaluateCalls, 0);

      final nearCard = find.byKey(const Key('nearest-center-card-public-near'));
      await tester.ensureVisible(nearCard);
      await tester.tap(nearCard);
      await tester.pumpAndSettle();
      final nearMarkerIcon = tester.widget<Icon>(
        find.descendant(
          of: find.byKey(const Key('nearest-center-marker-public-near')),
          matching: find.byIcon(Icons.home_work),
        ),
      );
      expect(nearMarkerIcon.size, 46);

      final farMarker = find.byKey(
        const Key('nearest-center-marker-public-far'),
      );
      await tester.ensureVisible(farMarker);
      await tester.tap(farMarker);
      await tester.pumpAndSettle();
      final farCardContainers = tester.widgetList<Container>(
        find.descendant(
          of: find.byKey(const Key('nearest-center-card-public-far')),
          matching: find.byType(Container),
        ),
      );
      expect(
        farCardContainers.any((container) {
          final decoration = container.decoration;
          return decoration is BoxDecoration &&
              decoration.border is Border &&
              (decoration.border! as Border).top.width == 2;
        }),
        isTrue,
      );

      final map = tester.widget<FlutterMap>(
        find.descendant(
          of: find.byKey(const Key('reference-boundary-map')),
          matching: find.byType(FlutterMap),
        ),
      );
      expect(map.children.any((child) => child is PolylineLayer), isFalse);
      expect(find.textContaining('safe route'), findsNothing);
      expect(find.textContaining('live capacity'), findsNothing);
      expect(find.textContaining('evacuate now'), findsNothing);
      expect(find.textContaining('private contact'), findsNothing);
      expect(find.textContaining('internal notes'), findsNothing);
      expect(api.evaluateCalls, 0);
    },
  );

  testWidgets('center failure preserves rainfall choices and never assesses', (
    tester,
  ) async {
    final api = FakeFloodSenseApi();
    final provider = FakeNearestCenterProvider()
      ..handler = (_, _) async =>
          throw const CenterLookupException(CenterLookupFailureKind.offline);
    await tester.pumpWidget(
      FloodSenseApp(
        api: api,
        locationService: Day4LocationService(),
        nearestCenterProvider: provider,
        showBasemap: false,
      ),
    );
    await tester.pumpAndSettle();

    final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
    await tester.ensureVisible(intensity);
    await tester.tap(intensity);
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
    final confirm = find.byKey(const Key('confirm-detected-barangay-button'));
    await tester.ensureVisible(confirm);
    await tester.tap(confirm);
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel(RegExp('Heavy, selected')), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('6 hours, selected')), findsOneWidget);
    expect(find.byKey(const Key('confirmed-barangay')), findsOneWidget);
    expect(find.byKey(const Key('nearest-centers-retry')), findsOneWidget);
    expect(api.evaluateCalls, 0);
  });
}
