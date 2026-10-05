import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/evacuation/evacuation_center_marker.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_centers_section.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/location/location_card.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/features/map/map_pin_location_notice.dart';

import 'location_day4_centers_test.dart';

Widget markerHost({
  bool nearest = true,
  bool reducedMotion = false,
  bool tickerEnabled = true,
  bool temporary = false,
  VoidCallback? onTap,
}) => MaterialApp(
  home: MediaQuery(
    data: MediaQueryData(disableAnimations: reducedMotion),
    child: TickerMode(
      enabled: tickerEnabled,
      child: Center(
        child: EvacuationCenterMarker(
          name: 'Shelter A',
          isNearest: nearest,
          isSelected: false,
          isDemonstration: temporary,
          onTap: onTap,
        ),
      ),
    ),
  ),
);

void main() {
  test('decorative pulse has a quiet start and end and three finite beats', () {
    expect(evacuationPulseStrength(0), 0);
    expect(evacuationPulseStrength(1), 0);
    expect(evacuationPulseStrength(2), 0);
    for (final peak in [1 / 6, 1 / 2, 5 / 6]) {
      expect(evacuationPulseStrength(peak), closeTo(1, 0.00001));
    }
  });

  test(
    'shared shelter painter produces an actual transparent style image',
    () async {
      final recorder = ui.PictureRecorder();
      paintEvacuationShelter(
        Canvas(recorder),
        const Rect.fromLTWH(0, 0, 96, 96),
        Colors.purple,
      );
      final picture = recorder.endRecording();
      final image = await picture.toImage(96, 96);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
      expect(bytes!.lengthInBytes, 96 * 96 * 4);
      // Transparent outside the rounded badge; opaque, white doorway within it.
      expect(bytes.getUint8(3), 0);
      expect(bytes.getUint8((65 * 96 + 48) * 4 + 3), 255);
      image.dispose();
      picture.dispose();
    },
  );

  testWidgets(
    'nearest marker beats briefly then settles and remains tappable',
    (tester) async {
      final semantics = tester.ensureSemantics();
      var taps = 0;
      await tester.pumpWidget(markerHost(onTap: () => taps++));
      await tester.pump(const Duration(milliseconds: 600));
      expect(tester.binding.hasScheduledFrame, isTrue);
      expect(find.byKey(const Key('evacuation-shelter-icon')), findsOneWidget);
      expect(
        find.bySemanticsLabel(
          RegExp('Shelter A.*Nearest by approximate straight-line distance'),
        ),
        findsOneWidget,
      );
      await tester.pumpAndSettle();
      expect(tester.binding.hasScheduledFrame, isFalse);
      await tester.tap(find.byType(EvacuationCenterMarker));
      expect(taps, 1);
      await tester.pumpWidget(const SizedBox());
      semantics.dispose();
    },
  );

  testWidgets('reduced motion and hidden surfaces use static emphasis', (
    tester,
  ) async {
    for (final host in [
      markerHost(reducedMotion: true),
      markerHost(tickerEnabled: false),
      markerHost(nearest: false),
    ]) {
      await tester.pumpWidget(host);
      await tester.pump();
      expect(tester.binding.hasScheduledFrame, isFalse);
      expect(find.byType(EvacuationCenterMarker), findsOneWidget);
    }
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets(
    'temporary marker never claims a real facility or live availability',
    (tester) async {
      final semantics = tester.ensureSemantics();
      await tester.pumpWidget(markerHost(temporary: true, reducedMotion: true));
      expect(
        find.bySemanticsLabel(RegExp('Local test—not a real facility')),
        findsOneWidget,
      );
      expect(find.bySemanticsLabel(RegExp('center is open')), findsNothing);
      await tester.pumpWidget(const SizedBox());
      semantics.dispose();
    },
  );

  testWidgets('decorative beating stops when the app leaves the foreground', (
    tester,
  ) async {
    await tester.pumpWidget(markerHost());
    await tester.pump(const Duration(milliseconds: 400));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    expect(tester.binding.hasScheduledFrame, isFalse);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(tester.binding.hasScheduledFrame, isFalse);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('pin notice distinguishes a barangay anchor from device GPS', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    const approximate =
        'Approximate barangay reference point—not your actual location. '
        'Drag the pin to refine your location.';
    await tester.pumpWidget(
      const MaterialApp(
        home: SizedBox(
          width: 300,
          child: MapPinLocationNotice(description: approximate),
        ),
      ),
    );
    expect(find.text(approximate), findsOneWidget);
    expect(
      find.bySemanticsLabel(RegExp('not your actual location.*not saved')),
      findsOneWidget,
    );
    await tester.pumpWidget(
      const MaterialApp(
        home: MapPinLocationNotice(
          description: 'Temporary device GPS location',
        ),
      ),
    );
    expect(find.text('Temporary device GPS location'), findsOneWidget);
    expect(find.textContaining('Approximate barangay'), findsNothing);
    semantics.dispose();
  });

  testWidgets('selected pin label lives inside the location card and clears', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 720);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final location = LocationController(
      Day4LocationService(),
      resolver: Day4Resolver(),
    );
    addTearDown(location.dispose);
    await location.resolveManualPin(
      const MapCoordinate(latitude: 14.405, longitude: 120.965),
    );
    location.confirmCandidate();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: LocationCard(controller: location),
          ),
        ),
      ),
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('location-card')),
        matching: find.text('Your selected map pin'),
      ),
      findsOneWidget,
    );
    expect(find.byType(MapPinLocationNotice), findsOneWidget);
    expect(tester.takeException(), isNull);
    await location.clearLocation();
    await tester.pumpAndSettle();
    expect(find.byType(MapPinLocationNotice), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('GPS origin remains visible inside the location card', (
    tester,
  ) async {
    final location = LocationController(
      Day4LocationService(),
      resolver: Day4Resolver(),
    );
    addTearDown(location.dispose);
    location.showPurposeExplanation();
    await location.continueAfterPurposeExplanation();
    location.confirmCandidate();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: LocationCard(controller: location),
          ),
        ),
      ),
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('location-card')),
        matching: find.text('Temporary device GPS location'),
      ),
      findsOneWidget,
    );
    expect(find.text('Your selected map pin'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Prepare emphasizes the nearest distance without choosing a route',
    (tester) async {
      final location = LocationController(
        Day4LocationService(),
        resolver: Day4Resolver(),
      );
      final provider = FakeNearestCenterProvider();
      final centers = NearestCenterController(location, provider: provider);
      location.showPurposeExplanation();
      await location.continueAfterPurposeExplanation();
      location.confirmCandidate();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: NearestCentersSection(controller: centers),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final summary = find.byKey(const Key('nearest-center-distance-summary'));
      expect(summary, findsOneWidget);
      expect(
        find.descendant(
          of: summary,
          matching: find.text('Nearest: Synthetic Near Center'),
        ),
        findsOneWidget,
      );
      expect(
        find.text('Distance: 180 m approximate straight-line distance'),
        findsOneWidget,
      );
      expect(find.text('From your confirmed GPS location'), findsOneWidget);
      expect(find.textContaining('Not road distance'), findsOneWidget);
      expect(find.byKey(const Key('nearest-centers-refresh')), findsOneWidget);
      expect(provider.calls, 1);
      expect(centers.selectedCenterIdentifier, isNull);
      await tester.pumpWidget(const SizedBox());
      centers.dispose();
      location.dispose();
    },
  );
}
