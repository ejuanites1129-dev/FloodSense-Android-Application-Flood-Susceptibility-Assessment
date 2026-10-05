import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/map/bacoor_coverage_mask.dart';
import 'package:floodsense/features/map/flood_map_palette.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/data/models/map_assessment_result.dart';

void main() {
  for (final scale in [1.0, 2.0]) {
    testWidgets('compact legend fits a 320px screen at text scale $scale', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: MediaQueryData(
              size: const Size(320, 640),
              textScaler: TextScaler.linear(scale),
            ),
            child: const Scaffold(
              body: Align(
                alignment: Alignment.topLeft,
                child: Padding(
                  padding: EdgeInsets.all(14),
                  child: BacoorCoverageLegend(compact: true),
                ),
              ),
            ),
          ),
        ),
      );
      expect(find.text('Outside Bacoor assessment coverage'), findsNothing);
      expect(
        tester.getSize(find.byKey(const Key('bacoor-coverage-legend'))).width,
        lessThan(scale == 1 ? 150 : 230),
      );
      await tester.tap(find.byTooltip('Map legend'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('map-legend-content')), findsOneWidget);
      for (final label in [
        'Low',
        'Moderate',
        'High',
        'Very high',
        'Unclassified / insufficient data\nOutside Bacoor coverage',
      ]) {
        expect(find.text(label), findsOneWidget);
      }
      expect(find.textContaining('Gray outside coverage is'), findsNothing);
      expect(find.textContaining('Shelter icons:'), findsNothing);
      expect(find.byKey(const Key('bacoor-coverage-swatch')), findsNothing);
      final moderate = tester.widget<Container>(
        find.byKey(const ValueKey('legend-swatch-Moderate')),
      );
      expect(
        (moderate.decoration as BoxDecoration).color,
        FloodMapPalette.moderate,
      );
      expect(tester.takeException(), isNull);
      await tester.tapAt(const Offset(300, 620));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('map-legend-content')), findsNothing);
    });
  }

  testWidgets('legend swatches honor versioned backend colors and demo label', (
    tester,
  ) async {
    const result = MapAreaAssessment(
      area: AreaSummary(id: 1, code: 'SYNTHETIC', name: 'Synthetic test'),
      state: AssessmentState.classified,
      rawState: 'CLASSIFIED',
      susceptibility: Susceptibility(
        code: 'MODERATE',
        label: 'Moderate',
        mapColor: '#123456',
      ),
      matchedRuleCodes: [],
      ruleset: null,
      summary: 'Synthetic fixture, not official data',
    );
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Align(
            alignment: Alignment.topLeft,
            child: BacoorCoverageLegend(
              compact: true,
              results: {1: result},
              isDemonstration: true,
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.byTooltip('Map legend'));
    await tester.pumpAndSettle();
    final swatch = tester.widget<Container>(
      find.byKey(const ValueKey('legend-swatch-Moderate')),
    );
    expect((swatch.decoration as BoxDecoration).color, const Color(0xFF123456));
    expect(
      find.text('Demonstration susceptibility—not official data.'),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });
}
