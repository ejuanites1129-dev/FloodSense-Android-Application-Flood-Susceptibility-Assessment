import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/data/api/api_exception.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/features/assessment/widgets/guidance_section.dart';

import 'test_data.dart';

Future<void> pumpLoaded(WidgetTester tester, FakeFloodSenseApi api) async {
  await tester.pumpWidget(FloodSenseApp(api: api, showBasemap: false));
  await tester.pumpAndSettle();
}

Future<void> selectAll(WidgetTester tester) async {
  final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
  await tester.ensureVisible(intensity);
  await tester.tap(intensity);
  await tester.pump();
  final duration = find.byKey(const Key('duration-DEMO_6_HOURS'));
  await tester.ensureVisible(duration);
  await tester.tap(duration);
  await tester.pump();
  final zone = find.byType(DropdownButtonFormField<GeographicArea>);
  await tester.ensureVisible(zone);
  await tester.tap(zone);
  await tester.pumpAndSettle();
  await tester.tap(find.text('Demo Zone A (DEMO_ZONE_A)').last);
  await tester.pumpAndSettle();
}

Future<void> submitAssessment(WidgetTester tester) async {
  final button = find.byKey(const Key('assess-button'));
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

void setPhoneSize(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

void main() {
  testWidgets('29 the default counter application is gone', (tester) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    expect(find.textContaining('pushed the button'), findsNothing);
    expect(find.byType(FloatingActionButton), findsNothing);
    expect(find.text('FloodSense'), findsOneWidget);
  });

  testWidgets('30 permanent warning is visible before data finishes loading', (
    tester,
  ) async {
    final api = FakeFloodSenseApi(
      optionsCompleter: Completer(),
      areasCompleter: Completer(),
    );
    await tester.pumpWidget(FloodSenseApp(api: api, showBasemap: false));
    await tester.pump();
    expect(find.text('DEMONSTRATION DATA—NOT OFFICIAL'), findsOneWidget);
    expect(find.byKey(const Key('initial-loading')), findsOneWidget);
  });

  testWidgets('31 initial loading has an accessible progress state', (
    tester,
  ) async {
    final api = FakeFloodSenseApi(
      optionsCompleter: Completer(),
      areasCompleter: Completer(),
    );
    await tester.pumpWidget(FloodSenseApp(api: api, showBasemap: false));
    await tester.pump();
    expect(
      find.bySemanticsLabel('Loading demonstration options and zones'),
      findsOneWidget,
    );
  });

  testWidgets('32 successful load displays all three selectors', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    expect(find.text('Rainfall intensity'), findsOneWidget);
    expect(find.text('Rainfall duration'), findsOneWidget);
    expect(find.text('Demonstration zone'), findsOneWidget);
  });

  testWidgets('33 submit stays disabled until every selection is made', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    FilledButton button = tester.widget(find.byKey(const Key('assess-button')));
    expect(button.onPressed, isNull);
    await selectAll(tester);
    button = tester.widget(find.byKey(const Key('assess-button')));
    expect(button.onPressed, isNotNull);
  });

  testWidgets('34 selected intensity has visible and semantic selected state', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    final option = find.byKey(const Key('option-DEMO_LIGHT'));
    await tester.ensureVisible(option);
    await tester.tap(option);
    await tester.pump();
    expect(find.text('Selected'), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Light, selected')), findsOneWidget);
  });

  testWidgets('35 selected duration has visible and semantic selected state', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    final option = find.byKey(const Key('duration-DEMO_1_HOUR'));
    await tester.ensureVisible(option);
    await tester.tap(option);
    await tester.pump();
    expect(find.bySemanticsLabel(RegExp('1 hour, selected')), findsOneWidget);
  });

  testWidgets('36 selected zone remains visible after selection', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    await selectAll(tester);
    expect(find.text('Demo Zone A (DEMO_ZONE_A)'), findsWidgets);
  });

  testWidgets('37 pressing Assess shows progress and blocks duplicates', (
    tester,
  ) async {
    final completer = Completer<AssessmentResult>();
    final api = FakeFloodSenseApi(evaluateCompleter: completer);
    await pumpLoaded(tester, api);
    await selectAll(tester);
    final button = find.byKey(const Key('assess-button'));
    await tester.ensureVisible(button);
    await tester.tap(button);
    await tester.pump();
    expect(find.text('Assessing…'), findsOneWidget);
    await tester.tap(button);
    expect(api.evaluateCalls, 1);
    completer.complete(sampleResult());
    await tester.pumpAndSettle();
  });

  testWidgets('38 classified result displays label and area', (tester) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.text('High susceptibility'), findsOneWidget);
    expect(find.textContaining('Demo Zone A (DEMO_ZONE_A)'), findsWidgets);
  });

  testWidgets(
    '39 classified result displays matched rule and ruleset version',
    (tester) async {
      await pumpLoaded(tester, FakeFloodSenseApi());
      await selectAll(tester);
      await submitAssessment(tester);
      expect(find.textContaining('DEMO-RULE-300'), findsWidgets);
      expect(find.textContaining('Demonstration Rules v1.0'), findsWidgets);
    },
  );

  testWidgets('40 guidance items preserve API order', (tester) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    await selectAll(tester);
    await submitAssessment(tester);
    final second = tester.getTopLeft(find.text('Second API action')).dy;
    final third = tester.getTopLeft(find.text('Third API action')).dy;
    expect(second, lessThan(third));
  });

  testWidgets('41 classified empty guidance displays safe fallback', (
    tester,
  ) async {
    await pumpLoaded(
      tester,
      FakeFloodSenseApi(result: sampleResult(guidance: false)),
    );
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.text(GuidanceSection.emptyMessage), findsOneWidget);
  });

  testWidgets('42 uncertain state is neutral and has no guidance section', (
    tester,
  ) async {
    await pumpLoaded(
      tester,
      FakeFloodSenseApi(result: sampleResult(state: 'UNCERTAIN')),
    );
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.text('Uncertain'), findsOneWidget);
    expect(
      find.textContaining('Equally ranked stored rules conflict'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('guidance-section')), findsNothing);
    expect(find.text('Low susceptibility'), findsNothing);
  });

  testWidgets('43 insufficient data is neutral and has no guidance section', (
    tester,
  ) async {
    await pumpLoaded(
      tester,
      FakeFloodSenseApi(result: sampleResult(state: 'INSUFFICIENT_DATA')),
    );
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.text('Insufficient Data'), findsOneWidget);
    expect(
      find.textContaining('No eligible stored rule matched'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('guidance-section')), findsNothing);
  });

  testWidgets('44 changing a selection clears the previous result', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.byKey(const Key('classified-result')), findsOneWidget);
    final option = find.byKey(const Key('option-DEMO_LIGHT'));
    await tester.ensureVisible(option);
    await tester.tap(option);
    await tester.pump();
    expect(find.byKey(const Key('classified-result')), findsNothing);
  });

  testWidgets('45 network error preserves selections and offers Retry', (
    tester,
  ) async {
    final api = FakeFloodSenseApi(
      evaluateError: const ApiException(
        'Unable to reach FloodSense.',
        kind: ApiFailureKind.connectivity,
      ),
    );
    await pumpLoaded(tester, api);
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.text('Cannot connect to FloodSense'), findsOneWidget);
    expect(find.byKey(const Key('retry-button')), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Heavy, selected')), findsOneWidget);
    expect(find.text('Demo Zone A (DEMO_ZONE_A)'), findsWidgets);
  });

  testWidgets('46 initial load error can be retried', (tester) async {
    final api = FakeFloodSenseApi(
      loadError: const ApiException(
        'Unable to reach FloodSense.',
        kind: ApiFailureKind.connectivity,
      ),
    );
    await pumpLoaded(tester, api);
    expect(find.byKey(const Key('initial-load-error')), findsOneWidget);
    api.loadError = null;
    await tester.tap(find.byKey(const Key('retry-button')));
    await tester.pumpAndSettle();
    expect(find.text('Rainfall intensity'), findsOneWidget);
    expect(api.optionsCalls, 2);
  });

  testWidgets('47 missing options or areas show administrator empty state', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi(areas: const []));
    expect(find.byKey(const Key('empty-state')), findsOneWidget);
    expect(
      find.textContaining('Ask an administrator to configure and enable'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('assess-button')), findsNothing);
  });

  testWidgets('48 long result remains scrollable without overflow', (
    tester,
  ) async {
    setPhoneSize(tester, const Size(390, 844));
    await pumpLoaded(
      tester,
      FakeFloodSenseApi(result: sampleResult(longText: true)),
    );
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.byKey(const Key('assessment-scroll-view')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('49 interface renders on a narrow phone without overflow', (
    tester,
  ) async {
    setPhoneSize(tester, const Size(320, 640));
    await pumpLoaded(tester, FakeFloodSenseApi());
    expect(find.text('DEMONSTRATION DATA—NOT OFFICIAL'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('50 safety notice and assess button have useful semantics', (
    tester,
  ) async {
    await pumpLoaded(tester, FakeFloodSenseApi());
    expect(
      find.bySemanticsLabel(RegExp('Permanent demonstration safety notice')),
      findsOneWidget,
    );
    expect(
      find.bySemanticsLabel(RegExp('Assess Susceptibility')),
      findsWidgets,
    );
  });

  testWidgets('51 validation error is distinct and does not offer Retry', (
    tester,
  ) async {
    final api = FakeFloodSenseApi(
      evaluateError: const ApiException(
        'The selected option is unavailable.',
        kind: ApiFailureKind.validation,
      ),
    );
    await pumpLoaded(tester, api);
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.text('Check your selections'), findsOneWidget);
    expect(find.byKey(const Key('retry-button')), findsNothing);
  });

  testWidgets('52 unknown assessment state never fabricates a class', (
    tester,
  ) async {
    await pumpLoaded(
      tester,
      FakeFloodSenseApi(result: sampleResult(state: 'FUTURE_STATE')),
    );
    await selectAll(tester);
    await submitAssessment(tester);
    expect(find.text('Unable to Display Result'), findsOneWidget);
    expect(
      find.textContaining('No classification was assumed'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('classified-result')), findsNothing);
  });
}
