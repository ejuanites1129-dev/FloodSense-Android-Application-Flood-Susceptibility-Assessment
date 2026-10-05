import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/app/widgets/measured_scroll_view.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/auth/resident_auth_repository.dart';
import 'package:floodsense/features/home/hybrid_map_surface.dart';
import 'package:floodsense/features/location/location_card.dart';
import 'package:floodsense/features/location/location_flow_state.dart';
import 'package:floodsense/features/location/location_service.dart';

import 'location_day2_test.dart' show FakeDay2LocationService;
import 'manual_barangay_pin_test.dart' show FakeNearestCenterProvider;
import 'resident_test_fakes.dart';
import 'test_data.dart';

const _continue = Key('hybrid-assessment-continue');
const _scenario = Key('hybrid-assessment-scenario');
const _location = Key('hybrid-assessment-location');
const _review = Key('hybrid-assessment-review');

Future<void> _scrollTo(WidgetTester tester, Finder target, Key section) async {
  await tester.scrollUntilVisible(
    target,
    180,
    scrollable: find
        .descendant(of: find.byKey(section), matching: find.byType(Scrollable))
        .first,
  );
  await tester.pumpAndSettle();
}

Future<void> _pumpResident(
  WidgetTester tester,
  FakeFloodSenseApi api,
  FakeDay2LocationService gps,
  FakeNearestCenterProvider nearest, {
  Size size = const Size(390, 844),
  double textScale = 1,
  bool reducedMotion = false,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final auth = FakeResidentAuthRepository()
    ..restoration = testSession(SetupStage.authenticatedReady);
  await tester.pumpWidget(
    MediaQuery(
      data: MediaQueryData(
        size: size,
        textScaler: TextScaler.linear(textScale),
        disableAnimations: reducedMotion,
      ),
      child: FloodSenseApp(
        api: api,
        authRepository: auth,
        locationService: gps,
        nearestCenterProvider: nearest,
        enableResidentAuthentication: true,
        showBasemap: false,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _openLocationStep(WidgetTester tester) async {
  await tester.drag(
    find.byKey(const Key('resident-sheet-handle')),
    const Offset(0, -2000),
  );
  await tester.pumpAndSettle();
  final start = find.byKey(const Key('map-start-assessment'));
  await _scrollTo(tester, start, const Key('map-context-sheet-content'));
  await tester.tap(start);
  await tester.pumpAndSettle();
  final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
  await _scrollTo(tester, intensity, _scenario);
  await tester.tap(intensity);
  await tester.pump();
  final duration = find.byKey(const Key('duration-DEMO_6_HOURS'));
  await _scrollTo(tester, duration, _scenario);
  await tester.tap(duration);
  await tester.pump();
  await _scrollTo(tester, find.byKey(_continue), _scenario);
  await tester.tap(find.byKey(_continue));
  await tester.pumpAndSettle();
  expect(find.byKey(_location), findsOneWidget);
}

void main() {
  for (final (size, scale) in [
    (const Size(390, 844), 1.0),
    (const Size(320, 640), 2.0),
  ]) {
    testWidgets(
      'panels stop at content and buttons match at $size scale $scale',
      (tester) async {
        final api = FakeFloodSenseApi(
          areas: sampleMgbBarangayAreas(),
          referenceAreas: sampleMgbBarangayAreas(),
          barangayResult: sampleBarangayResolution(),
        );
        await _pumpResident(
          tester,
          api,
          FakeDay2LocationService(),
          FakeNearestCenterProvider(),
          size: size,
          textScale: scale,
        );
        await _openLocationStep(tester);
        final controller = tester
            .widget<LocationCard>(find.byType(LocationCard))
            .controller;
        await controller.resolveManualPin(
          const MapCoordinate(latitude: 14.405, longitude: 120.965),
        );
        await tester.pumpAndSettle();

        Future<void> expectContentCap(Key contentKey) async {
          final content = find.byKey(contentKey);
          final naturalHeight = tester
              .getSize(
                find
                    .descendant(of: content, matching: find.byType(Padding))
                    .first,
              )
              .height;
          final availableHeight = tester
              .getSize(find.byType(HybridMapSurface))
              .height;
          final expectedHeight = (naturalHeight + 48).clamp(
            0,
            availableHeight * 0.9,
          );
          final handle = find.byKey(const Key('resident-sheet-handle'));
          await tester.drag(handle, const Offset(0, -2000));
          await tester.pumpAndSettle();
          expect(
            tester
                .getSize(find.byKey(const Key('resident-context-sheet')))
                .height,
            closeTo(expectedHeight, 0.01),
          );
          await tester.drag(handle, const Offset(0, -200));
          await tester.pumpAndSettle();
          expect(
            tester
                .getSize(find.byKey(const Key('resident-context-sheet')))
                .height,
            closeTo(expectedHeight, 0.01),
          );
          final scrollable = tester.state<ScrollableState>(
            find
                .descendant(of: content, matching: find.byType(Scrollable))
                .first,
          );
          if (naturalHeight + 48 <= availableHeight * 0.9) {
            expect(scrollable.position.maxScrollExtent, closeTo(0, 0.01));
          } else {
            expect(scrollable.position.maxScrollExtent, greaterThan(0));
          }
        }

        void expectMatchingButtons(Key continueKey) {
          final back = find.byKey(const Key('hybrid-assessment-back'));
          final next = find.byKey(continueKey);
          expect(tester.getSize(back), tester.getSize(next));
          expect(tester.getTopLeft(back).dy, tester.getTopLeft(next).dy);
          final theme = Theme.of(tester.element(back));
          final backShape =
              theme.outlinedButtonTheme.style!.shape!.resolve({})!
                  as RoundedRectangleBorder;
          final nextShape =
              theme.filledButtonTheme.style!.shape!.resolve({})!
                  as RoundedRectangleBorder;
          expect(backShape.borderRadius, nextShape.borderRadius);
        }

        await expectContentCap(_location);
        expectMatchingButtons(_continue);
        // Removing the clear action also changes the height limit immediately.
        await controller.clearLocation();
        await tester.pumpAndSettle();
        await expectContentCap(_location);
        await controller.resolveManualPin(
          const MapCoordinate(latitude: 14.405, longitude: 120.965),
        );
        await tester.pumpAndSettle();
        await _scrollTo(tester, find.byKey(_continue), _location);
        await tester.tap(find.byKey(_continue));
        await tester.pumpAndSettle();
        await expectContentCap(_review);
        expectMatchingButtons(const Key('hybrid-run-assessment'));
        await tester.tap(find.byKey(const Key('resident-nav-prepare')));
        await tester.pumpAndSettle();
        await expectContentCap(const Key('prepare-empty-state'));
        expect(find.byType(MeasuredScrollView), findsOneWidget);
        expect(api.evaluateCalls, 0);
        expect(tester.takeException(), isNull);
      },
    );
  }

  for (final (size, scale) in [
    (const Size(390, 844), 1.0),
    (const Size(320, 640), 1.0),
    (const Size(320, 640), 2.0),
  ]) {
    testWidgets('brand fits its contents at ${size.width}px and scale $scale', (
      tester,
    ) async {
      await _pumpResident(
        tester,
        FakeFloodSenseApi(),
        FakeDay2LocationService(),
        FakeNearestCenterProvider(),
        size: size,
        textScale: scale,
      );
      final brand = find.byKey(const Key('map-brand'));
      final bounds = tester.getRect(brand);
      final logo = tester.getRect(
        find.descendant(of: brand, matching: find.byIcon(Icons.waves)),
      );
      final title = tester.getRect(
        find.descendant(of: brand, matching: find.text('FloodSense')),
      );
      expect(title.left - logo.right, closeTo(6, 0.01));
      expect(logo.left - bounds.left, closeTo(12, 0.01));
      expect(bounds.right - title.right, closeTo(12, 0.01));
      expect(bounds.left, 14);
      expect(
        bounds.overlaps(tester.getRect(find.byTooltip('Zoom in'))),
        isFalse,
      );
      expect(tester.takeException(), isNull);
    });
  }

  for (final useGps in [false, true]) {
    testWidgets(
      '${useGps ? 'GPS' : 'dragged pin'} needs one Confirm area and keeps detail in Review',
      (tester) async {
        final api = FakeFloodSenseApi(
          areas: sampleMgbBarangayAreas(),
          referenceAreas: sampleMgbBarangayAreas(),
          barangayResult: sampleBarangayResolution(),
        );
        final gps = FakeDay2LocationService()
          ..checkedPermission = LocationPermissionState.foregroundGranted;
        final nearest = FakeNearestCenterProvider();
        await _pumpResident(tester, api, gps, nearest);
        expect(gps.acquisitions, 0);
        await _openLocationStep(tester);
        final card = tester.widget<LocationCard>(find.byType(LocationCard));
        final controller = card.controller;
        expect(card.showAreaConfirmation, isFalse);
        await _scrollTo(tester, find.byKey(_continue), _location);
        expect(
          tester.widget<FilledButton>(find.byKey(_continue)).onPressed,
          isNull,
        );
        const pin = MapCoordinate(latitude: 14.405123, longitude: 120.965987);
        if (useGps) {
          await _scrollTo(
            tester,
            find.byKey(const Key('use-my-location-button')),
            _location,
          );
          await tester.tap(find.byKey(const Key('use-my-location-button')));
          await tester.pumpAndSettle();
          expect(gps.acquisitions, 0);
          await tester.tap(find.byKey(const Key('location-purpose-continue')));
        } else {
          await controller.resolveManualPin(pin);
        }
        await tester.pumpAndSettle();
        await _scrollTo(
          tester,
          find.byKey(const Key('detected-barangay-candidate')),
          _location,
        );
        expect(controller.state.phase, LocationFlowPhase.resolvedCandidate);
        expect(controller.confirmedBarangay, isNull);
        expect(api.evaluateCalls, 0);
        expect(nearest.calls, 0);
        expect(find.text('Confirm barangay'), findsNothing);
        expect(find.text('Correct manually'), findsNothing);
        expect(
          find.byKey(const Key('confirm-detected-barangay-button')),
          findsNothing,
        );
        expect(
          find.byKey(const Key('temporary-location-indicator')),
          findsNothing,
        );
        expect(
          find.textContaining('Review and confirm the proposed'),
          findsNothing,
        );
        expect(find.textContaining('Proposed barangay'), findsNothing);
        expect(find.textContaining('GPS is optional'), findsNothing);
        expect(
          find.textContaining('Provisional MGB-derived baseline'),
          findsNothing,
        );
        await _scrollTo(
          tester,
          find.byKey(const Key('detected-barangay-candidate')),
          _location,
        );
        expect(find.text('Bayanan'), findsOneWidget);
        await _scrollTo(tester, find.byKey(_continue), _location);
        expect(find.text('Confirm area'), findsOneWidget);
        expect(
          tester.widget<FilledButton>(find.byKey(_continue)).onPressed,
          isNotNull,
        );
        await tester.tap(find.byKey(_continue));
        await tester.pumpAndSettle();
        expect(find.byKey(_review), findsOneWidget);
        expect(controller.state.phase, LocationFlowPhase.confirmed);
        expect(controller.confirmedBarangay!.name, 'Bayanan');
        expect(nearest.calls, 1);
        expect(api.evaluateCalls, 0);
        final expected = useGps
            ? MapCoordinate(
                latitude: gps.location.latitude,
                longitude: gps.location.longitude,
              )
            : pin;
        expect(controller.lookupCoordinate!.latitude, expected.latitude);
        expect(controller.lookupCoordinate!.longitude, expected.longitude);
        expect(
          tester
              .widget<HybridMapSurface>(find.byType(HybridMapSurface))
              .controller
              .selectedArea!
              .name,
          'Bayanan',
        );
        await _scrollTo(
          tester,
          find.text('Provisional MGB-derived baseline'),
          _review,
        );
        expect(find.textContaining('60.00% of barangay area'), findsOneWidget);
        await _scrollTo(
          tester,
          find.byKey(const Key('location-review-provenance')),
          _review,
        );
        await tester.tap(find.text('Boundary source and limitations'));
        await tester.pumpAndSettle();
        await _scrollTo(
          tester,
          find.textContaining('Administrative boundaries only'),
          _review,
        );
        expect(find.textContaining('NOT CITY-VERIFIED'), findsOneWidget);
        expect(api.evaluateCalls, 0);
        expect(tester.takeException(), isNull);
      },
    );
  }

  for (final mode in ['manual barangay', 'map pin', 'GPS']) {
    testWidgets('clear stays below the manual selector for $mode', (
      tester,
    ) async {
      final api = FakeFloodSenseApi(
        areas: sampleMgbBarangayAreas(),
        referenceAreas: sampleMgbBarangayAreas(),
        barangayResult: sampleBarangayResolution(),
      );
      final gps = FakeDay2LocationService();
      await _pumpResident(tester, api, gps, FakeNearestCenterProvider());
      await _openLocationStep(tester);
      final controller = tester
          .widget<LocationCard>(find.byType(LocationCard))
          .controller;
      switch (mode) {
        case 'manual barangay':
          tester
              .widget<DropdownButtonFormField<GeographicArea>>(
                find.byType(DropdownButtonFormField<GeographicArea>),
              )
              .onChanged!(api.referenceAreas.single);
        case 'map pin':
          await controller.resolveManualPin(
            const MapCoordinate(latitude: 14.405, longitude: 120.965),
          );
        case 'GPS':
          controller.showPurposeExplanation();
          await controller.continueAfterPurposeExplanation();
      }
      await tester.pumpAndSettle();
      final clear = find.byKey(const Key('clear-location-button'));
      await _scrollTo(tester, clear, _location);
      final useLocationBounds = tester.getRect(
        find.byKey(const Key('use-my-location-button')),
      );
      final selectorBounds = tester.getRect(
        find.byKey(const Key('manual-barangay-selector')),
      );
      final clearBounds = tester.getRect(clear);
      expect(useLocationBounds.bottom, lessThan(selectorBounds.top));
      expect(selectorBounds.bottom, lessThan(clearBounds.top));
      expect(
        find.descendant(
          of: clear,
          matching: find.text(
            mode == 'GPS'
                ? 'Clear temporary location'
                : 'Clear location choice',
          ),
        ),
        findsOneWidget,
      );
      final acquisitionCount = gps.acquisitions;
      await tester.tap(clear);
      await tester.pumpAndSettle();
      expect(controller.lookupCoordinate, isNull);
      expect(controller.candidateBarangay, isNull);
      expect(controller.confirmedBarangay, isNull);
      expect(controller.hasTemporaryLocation, isFalse);
      expect(clear, findsNothing);
      expect(gps.acquisitions, acquisitionCount);
      expect(api.evaluateCalls, 0);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('switching location modes removes the stale pin-origin label', (
    tester,
  ) async {
    final api = FakeFloodSenseApi(
      areas: sampleMgbBarangayAreas(),
      referenceAreas: sampleMgbBarangayAreas(),
      barangayResult: sampleBarangayResolution(),
    );
    final gps = FakeDay2LocationService();
    await _pumpResident(tester, api, gps, FakeNearestCenterProvider());
    await _openLocationStep(tester);
    final controller = tester
        .widget<LocationCard>(find.byType(LocationCard))
        .controller;
    await controller.resolveManualPin(
      const MapCoordinate(latitude: 14.405, longitude: 120.965),
    );
    await tester.pumpAndSettle();
    expect(find.text('Your selected map pin'), findsOneWidget);
    controller.showPurposeExplanation();
    await controller.continueAfterPurposeExplanation();
    await tester.pumpAndSettle();
    expect(find.text('Your selected map pin'), findsNothing);
    expect(find.text('Temporary device GPS location'), findsOneWidget);
    await controller.clearLocation();
    final selector = tester.widget<DropdownButtonFormField<GeographicArea>>(
      find.byType(DropdownButtonFormField<GeographicArea>),
    );
    selector.onChanged!(api.referenceAreas.single);
    await tester.pumpAndSettle();
    expect(find.text('Your selected map pin'), findsNothing);
    expect(find.text('Temporary device GPS location'), findsNothing);
    expect(find.text('Approximate barangay reference point'), findsOneWidget);
    expect(controller.isApproximateCoordinate, isTrue);
    await controller.resolveManualPin(
      const MapCoordinate(latitude: 14.405, longitude: 120.965),
    );
    await tester.pumpAndSettle();
    expect(find.text('Your selected map pin'), findsOneWidget);
    expect(find.text('Approximate barangay reference point'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  for (final scale in [1.0, 2.0]) {
    testWidgets('sheet controls never overlap at 320px and scale $scale', (
      tester,
    ) async {
      await _pumpResident(
        tester,
        FakeFloodSenseApi(),
        FakeDay2LocationService(),
        FakeNearestCenterProvider(),
        size: const Size(320, 640),
        textScale: scale,
      );
      final drag = tester.getRect(
        find.byKey(const Key('resident-sheet-drag-indicator')),
      );
      final down = tester.getRect(
        find.byKey(const Key('resident-sheet-collapse-button')),
      );
      expect(drag.overlaps(down), isFalse);
      expect(down.size, const Size(48, 48));
      await tester.tap(find.byKey(const Key('resident-sheet-collapse-button')));
      await tester.pumpAndSettle();
      expect(
        tester.getSize(find.byKey(const Key('resident-sheet-expand-tab'))),
        const Size(108, 34),
      );
      expect(
        tester.getSize(
          find.byKey(const Key('resident-sheet-expand-touch-target')),
        ),
        const Size(108, 48),
      );
      expect(
        tester
            .widget<Transform>(
              find.byKey(const Key('resident-sheet-hint-arrow')),
            )
            .transform
            .storage[13],
        0,
      );
      await tester.tap(
        find.byKey(const Key('resident-sheet-expand-touch-target')),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('resident-sheet-expand-tab')), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  for (final reducedMotion in [false, true]) {
    testWidgets(
      'arrow hint is finite and respects reduced motion $reducedMotion',
      (tester) async {
        await _pumpResident(
          tester,
          FakeFloodSenseApi(),
          FakeDay2LocationService(),
          FakeNearestCenterProvider(),
          reducedMotion: reducedMotion,
        );
        await tester.tap(
          find.byKey(const Key('resident-sheet-collapse-button')),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 300));
        await tester.pump(const Duration(milliseconds: 200));
        double offset() => tester
            .widget<Transform>(
              find.byKey(const Key('resident-sheet-hint-arrow')),
            )
            .transform
            .storage[13];
        if (reducedMotion) {
          expect(offset(), 0);
        } else {
          expect(offset(), inExclusiveRange(-3.01, 0));
        }
        await tester.pumpAndSettle();
        expect(offset(), 0);
        await tester.pump(const Duration(seconds: 4));
        expect(offset(), 0);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets('arrow hint stops when the app leaves the foreground', (
    tester,
  ) async {
    await _pumpResident(
      tester,
      FakeFloodSenseApi(),
      FakeDay2LocationService(),
      FakeNearestCenterProvider(),
    );
    await tester.tap(find.byKey(const Key('resident-sheet-collapse-button')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 200));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    await tester.pump();
    expect(
      tester
          .widget<Transform>(find.byKey(const Key('resident-sheet-hint-arrow')))
          .transform
          .storage[13],
      0,
    );
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<Transform>(find.byKey(const Key('resident-sheet-hint-arrow')))
          .transform
          .storage[13],
      0,
    );
    expect(tester.takeException(), isNull);
  });
}
