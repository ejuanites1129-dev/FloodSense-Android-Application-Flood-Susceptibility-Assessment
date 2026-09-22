import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/app/theme/app_colors.dart';
import 'package:floodsense/data/api/api_exception.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/map_assessment_result.dart';
import 'package:latlong2/latlong.dart';

import 'test_data.dart';

Future<void> pumpMap(WidgetTester tester, FakeFloodSenseApi api) async {
  await tester.pumpWidget(FloodSenseApp(api: api, showBasemap: false));
  await tester.pumpAndSettle();
}

Future<void> chooseScenario(WidgetTester tester) async {
  final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
  await tester.ensureVisible(intensity);
  await tester.tap(intensity);
  await tester.pump();
  final duration = find.byKey(const Key('duration-DEMO_6_HOURS'));
  await tester.ensureVisible(duration);
  await tester.tap(duration);
  await tester.pumpAndSettle();
}

Future<void> chooseZone(WidgetTester tester) async {
  final dropdown = find.byType(DropdownButtonFormField<GeographicArea>);
  await tester.ensureVisible(dropdown);
  await tester.tap(dropdown);
  await tester.pumpAndSettle();
  await tester.tap(find.text('Demo Zone A (DEMO_ZONE_A)').last);
  await tester.pumpAndSettle();
}

void tapMapCoordinate(WidgetTester tester, LatLng point) {
  final map = tester.widget<FlutterMap>(
    find.descendant(
      of: find.byKey(const Key('reference-boundary-map')),
      matching: find.byType(FlutterMap),
    ),
  );
  map.options.onTap!(const TapPosition(Offset.zero, Offset.zero), point);
}

List<Polygon<int>> renderedPolygons(WidgetTester tester) => tester
    .widget<PolygonLayer<int>>(find.byKey(const Key('demonstration-polygons')))
    .polygons;

void main() {
  group('Unified Bacoor map', () {
    testWidgets('renders barangay boundaries and scenario data in one map', (
      tester,
    ) async {
      await pumpMap(tester, FakeFloodSenseApi());

      expect(find.byKey(const Key('reference-boundary-map')), findsOneWidget);
      expect(
        find.text('1 Bacoor barangay boundaries loaded from Django/PostGIS.'),
        findsOneWidget,
      );
      final layer = tester.widget<PolygonLayer<int>>(
        find.byKey(const Key('reference-boundary-polygons')),
      );
      expect(layer.polygons, hasLength(1));
      expect(layer.polygons.single.borderColor, AppColors.primary);
      final coverage = tester.widget<PolygonLayer<int>>(
        find.byKey(const Key('bacoor-coverage-mask')),
      );
      expect(coverage.polygons, hasLength(1));
      expect(coverage.invertedFill, const Color(0xA6677280));
      expect(find.text('Outside Bacoor assessment coverage'), findsOneWidget);
      expect(find.byKey(const Key('bacoor-map-data-note')), findsOneWidget);
      expect(find.byKey(const Key('dynamic-map')), findsNothing);
    });

    testWidgets('renders API polygons neutrally before a complete scenario', (
      tester,
    ) async {
      await pumpMap(tester, FakeFloodSenseApi());

      final polygons = renderedPolygons(tester);
      expect(polygons, hasLength(1));
      expect(polygons.single.borderColor, AppColors.limitation);
      expect(polygons.single.label, contains('No scenario result'));
    });

    testWidgets('classified polygon uses the backend-returned map color', (
      tester,
    ) async {
      await pumpMap(tester, FakeFloodSenseApi());
      await chooseScenario(tester);

      final polygon = renderedPolygons(tester).single;
      expect(polygon.borderColor, const Color(0xFFE2691B));
      expect(polygon.label, contains('High'));
    });

    testWidgets('limitation polygon remains neutral and text-labeled', (
      tester,
    ) async {
      await pumpMap(
        tester,
        FakeFloodSenseApi(
          mapResult: sampleMapAssessment(state: 'INSUFFICIENT_DATA'),
        ),
      );
      await chooseScenario(tester);

      final polygon = renderedPolygons(tester).single;
      expect(polygon.borderColor, AppColors.limitation);
      expect(polygon.label, contains('Insufficient Data'));
    });

    testWidgets('zone selector applies a distinct polygon selection border', (
      tester,
    ) async {
      await pumpMap(tester, FakeFloodSenseApi());
      await chooseZone(tester);

      final polygon = renderedPolygons(tester).single;
      expect(polygon.borderColor, AppColors.primary);
      expect(polygon.borderStrokeWidth, 4);
      expect(find.byKey(const Key('selected-zone-preview')), findsOneWidget);
    });

    testWidgets('legend, warning, attribution, and map controls stay visible', (
      tester,
    ) async {
      await pumpMap(tester, FakeFloodSenseApi());

      for (final label in [
        'Low',
        'Moderate',
        'High',
        'Very High',
        'Uncertain / Insufficient Data',
      ]) {
        expect(find.text(label), findsWidgets);
      }
      expect(find.byKey(const Key('bacoor-map-data-note')), findsOneWidget);
      expect(find.byKey(const Key('osm-attribution')), findsOneWidget);
      expect(find.bySemanticsLabel('Zoom in Bacoor map'), findsOneWidget);
      expect(find.bySemanticsLabel('Zoom out Bacoor map'), findsOneWidget);
      expect(find.bySemanticsLabel('Fit all Bacoor barangays'), findsOneWidget);
    });

    testWidgets('map taps place and reposition one temporary pin', (
      tester,
    ) async {
      final api = FakeFloodSenseApi();
      await pumpMap(tester, api);

      tapMapCoordinate(tester, const LatLng(14.005, 120.005));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('temporary-pin-marker')), findsOneWidget);
      expect(api.lastLatitude, 14.005);

      tapMapCoordinate(tester, const LatLng(14.006, 120.006));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('temporary-pin-marker')), findsOneWidget);
      expect(api.pointCalls, 2);
      expect(api.lastLongitude, 120.006);
    });

    testWidgets('resolved pin synchronizes the zone selector and highlight', (
      tester,
    ) async {
      await pumpMap(tester, FakeFloodSenseApi());

      tapMapCoordinate(tester, const LatLng(14.005, 120.005));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('point-state-RESOLVED')), findsOneWidget);
      expect(find.text('Demo Zone A (DEMO_ZONE_A)'), findsWidgets);
      expect(renderedPolygons(tester).single.borderStrokeWidth, 4);
    });

    testWidgets('outside pin shows no classification or selected zone', (
      tester,
    ) async {
      await pumpMap(
        tester,
        FakeFloodSenseApi(
          pointResult: samplePointResolution(state: 'OUTSIDE_SUPPORTED_AREA'),
        ),
      );

      tapMapCoordinate(tester, const LatLng(13, 119));
      await tester.pumpAndSettle();

      expect(find.text('Outside supported area'), findsOneWidget);
      expect(find.byKey(const Key('selected-zone-preview')), findsNothing);
    });

    testWidgets('ambiguous pin shows neutral repositioning guidance', (
      tester,
    ) async {
      await pumpMap(
        tester,
        FakeFloodSenseApi(
          pointResult: samplePointResolution(state: 'AMBIGUOUS_AREA'),
        ),
      );

      tapMapCoordinate(tester, const LatLng(14.005, 120.005));
      await tester.pumpAndSettle();

      expect(find.text('Point overlaps multiple zones'), findsOneWidget);
      expect(find.textContaining('Reposition the pin'), findsOneWidget);
      expect(find.byKey(const Key('selected-zone-preview')), findsNothing);
    });

    testWidgets('map result failure is neutral and can be retried', (
      tester,
    ) async {
      final api = FakeFloodSenseApi(
        mapError: const ApiException(
          'Network unavailable.',
          kind: ApiFailureKind.connectivity,
        ),
      );
      await pumpMap(tester, api);
      await chooseScenario(tester);
      expect(find.byKey(const Key('map-assessment-error')), findsOneWidget);
      expect(renderedPolygons(tester).single.borderColor, AppColors.limitation);

      api.mapError = null;
      final retry = find.byKey(const Key('map-retry-button'));
      await tester.ensureVisible(retry);
      await tester.tap(retry);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('map-assessment-error')), findsNothing);
      expect(
        renderedPolygons(tester).single.borderColor,
        const Color(0xFFE2691B),
      );
    });

    testWidgets('pending map request displays an accessible loading overlay', (
      tester,
    ) async {
      final completer = Completer<MapAssessmentResult>();
      final api = FakeFloodSenseApi(mapHandler: (_, _) => completer.future);
      await pumpMap(tester, api);
      final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
      await tester.ensureVisible(intensity);
      await tester.tap(intensity);
      final duration = find.byKey(const Key('duration-DEMO_6_HOURS'));
      await tester.ensureVisible(duration);
      await tester.tap(duration);
      await tester.pump();

      expect(find.text('Updating map…'), findsOneWidget);
      final semantics = tester.widget<Semantics>(
        find.byKey(const Key('map-loading-overlay')),
      );
      expect(
        semantics.properties.label,
        'Updating polygon results for the selected scenario',
      );
      completer.complete(sampleMapAssessment());
      await tester.pumpAndSettle();
    });

    testWidgets('full assessment still displays explanation and DSS guidance', (
      tester,
    ) async {
      await pumpMap(tester, FakeFloodSenseApi());
      await chooseScenario(tester);
      await chooseZone(tester);
      final button = find.byKey(const Key('assess-button'));
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('classified-result')), findsOneWidget);
      expect(find.text('Why this result?'), findsOneWidget);
      expect(find.byKey(const Key('guidance-section')), findsOneWidget);
    });

    testWidgets('map layout does not overflow at 320 by 640', (tester) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await pumpMap(tester, FakeFloodSenseApi());

      expect(find.byKey(const Key('reference-boundary-map')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}
