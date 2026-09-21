import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/nearest_center_result.dart';
import 'package:floodsense/data/models/scenario_option.dart';
import 'package:floodsense/data/models/verified_center.dart';
import 'package:floodsense/features/assessment/assessment_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';
import 'package:floodsense/features/location/location_service.dart';

import 'test_data.dart';

final class Day6LocationService implements LocationService {
  int acquisitions = 0;

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) async {
    acquisitions++;
    return TemporaryLocation(
      latitude: 14.405,
      longitude: 120.965,
      accuracyMeters: 12,
      acquiredAt: DateTime.utc(2026, 9, 20),
    );
  }

  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.foregroundGranted;

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
      LocationPermissionState.foregroundGranted;
}

final class Day6CenterProvider implements NearestCenterProvider {
  int calls = 0;

  @override
  Future<NearestCenterResult> findNearest({
    required double latitude,
    required double longitude,
  }) async {
    calls++;
    return NearestCenterResult(
      distanceMethod: nearestCenterDistanceMethod,
      warnings: const [nearestCenterDistanceWarning],
      centers: [
        VerifiedCenter(
          publicIdentifier: 'day6-synthetic-center',
          name:
              'Synthetic center with a deliberately long resident-facing name',
          address: 'A deliberately long synthetic address used only to verify responsive layout and text scaling.',
          barangay: CenterBarangayIdentity(
            psgcCode: '0402103004',
            name: 'Synthetic Barangay With A Long Name',
          ),
          latitude: 14.406,
          longitude: 120.966,
          approximateDistance: 275,
          distanceUnit: CenterDistanceUnit.meters,
          verifiedOn: DateTime.utc(2026, 9, 1),
          sourceAttribution: 'Synthetic source for automated tests only',
          limitations: const [
            'Synthetic limitation text that remains readable at large text sizes.',
          ],
        ),
      ],
    );
  }
}

Future<void> confirmSyntheticLocation(WidgetTester tester) async {
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
}

void main() {
  test(
    'disposed assessment controller drops all delayed load responses',
    () async {
      final options = Completer<AssessmentOptions>();
      final areas = Completer<List<GeographicArea>>();
      final references = Completer<List<GeographicArea>>();
      final api = FakeFloodSenseApi(
        optionsCompleter: options,
        areasCompleter: areas,
        referenceAreasCompleter: references,
      );
      final controller = AssessmentController(api);

      final pending = controller.load();
      await Future<void>.delayed(Duration.zero);
      controller.dispose();
      options.complete(sampleOptions());
      areas.complete(sampleAreas());
      references.complete(sampleReferenceAreas());
      await pending;
      await Future<void>.delayed(Duration.zero);

      expect(controller.options, isNull);
      expect(controller.areas, isEmpty);
      expect(controller.referenceAreas, isEmpty);
      expect(api.closed, isTrue);
    },
  );

  testWidgets(
    'screen order follows scenario, location, assessment, then centers',
    (tester) async {
      await tester.pumpWidget(
        FloodSenseApp(
          api: FakeFloodSenseApi(),
          locationService: Day6LocationService(),
          nearestCenterProvider: Day6CenterProvider(),
          showBasemap: false,
        ),
      );
      await tester.pumpAndSettle();

      final scenarioY = tester.getTopLeft(find.text('Plan a scenario')).dy;
      final locationY = tester
          .getTopLeft(find.byKey(const Key('location-card')))
          .dy;
      final referenceMapY = tester
          .getTopLeft(find.byKey(const Key('reference-boundary-card')))
          .dy;
      final assessmentY = tester
          .getTopLeft(find.byKey(const Key('assess-button')))
          .dy;
      final centersY = tester
          .getTopLeft(find.byKey(const Key('nearest-centers-section')))
          .dy;

      expect(scenarioY, lessThan(locationY));
      expect(locationY, lessThan(referenceMapY));
      expect(referenceMapY, lessThan(assessmentY));
      expect(assessmentY, lessThan(centersY));
    },
  );

  testWidgets(
    'reference polygons are reused when unrelated scenario state changes',
    (tester) async {
      await tester.pumpWidget(
        FloodSenseApp(api: FakeFloodSenseApi(), showBasemap: false),
      );
      await tester.pumpAndSettle();

      final before = tester
          .widget<PolygonLayer<int>>(
            find.byKey(const Key('reference-boundary-polygons')),
          )
          .polygons;
      final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
      await tester.ensureVisible(intensity);
      await tester.tap(intensity);
      await tester.pump();
      final after = tester
          .widget<PolygonLayer<int>>(
            find.byKey(const Key('reference-boundary-polygons')),
          )
          .polygons;

      expect(after, same(before));
    },
  );

  testWidgets('purpose dialog scrolls safely on a small large-text viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2.5;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

    await tester.pumpWidget(
      FloodSenseApp(
        api: FakeFloodSenseApi(),
        locationService: Day6LocationService(),
        showBasemap: false,
      ),
    );
    await tester.pumpAndSettle();
    final useLocation = find.byKey(const Key('use-my-location-button'));
    await tester.ensureVisible(useLocation);
    await tester.tap(useLocation);
    await tester.pumpAndSettle();

    expect(
      tester.widget<AlertDialog>(find.byType(AlertDialog)).scrollable,
      isTrue,
    );
    expect(find.text('Use manual selection'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'long center content supports large text, landscape, and state preservation',
    (tester) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      final service = Day6LocationService();
      final provider = Day6CenterProvider();

      await tester.pumpWidget(
        FloodSenseApp(
          api: FakeFloodSenseApi(),
          locationService: service,
          nearestCenterProvider: provider,
          showBasemap: false,
        ),
      );
      await tester.pumpAndSettle();
      final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
      await tester.ensureVisible(intensity);
      await tester.tap(intensity);
      await tester.pump();
      await confirmSyntheticLocation(tester);

      expect(provider.calls, 1);
      expect(service.acquisitions, 1);
      expect(tester.takeException(), isNull);

      tester.view.physicalSize = const Size(640, 320);
      await tester.pumpAndSettle();

      expect(find.bySemanticsLabel(RegExp('Heavy, selected')), findsOneWidget);
      expect(find.byKey(const Key('confirmed-barangay')), findsOneWidget);
      expect(provider.calls, 1);
      expect(service.acquisitions, 1);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('center status and complete card details are accessible', (
    tester,
  ) async {
    final provider = Day6CenterProvider();
    await tester.pumpWidget(
      FloodSenseApp(
        api: FakeFloodSenseApi(),
        locationService: Day6LocationService(),
        nearestCenterProvider: provider,
        showBasemap: false,
      ),
    );
    await tester.pumpAndSettle();
    await confirmSyntheticLocation(tester);

    expect(
      find.bySemanticsLabel(
        RegExp(
          'Synthetic center.*275 m approximate.*Verified on 2026-09-01.*'
          'Limitation: Synthetic limitation',
        ),
      ),
      findsOneWidget,
    );
    final statusSemantics = tester.widget<Semantics>(
      find
          .ancestor(
            of: find.byKey(const Key('nearest-centers-state-message')),
            matching: find.byType(Semantics),
          )
          .first,
    );
    expect(statusSemantics.properties.liveRegion, isTrue);

    for (final label in [
      'Zoom in Bacoor map',
      'Zoom out Bacoor map',
      'Fit all Bacoor barangays',
    ]) {
      final target = find.bySemanticsLabel(label);
      expect(tester.getSize(target).width, greaterThanOrEqualTo(48));
      expect(tester.getSize(target).height, greaterThanOrEqualTo(48));
    }
  });
}
