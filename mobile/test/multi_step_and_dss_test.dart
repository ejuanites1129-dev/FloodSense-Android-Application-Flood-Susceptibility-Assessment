import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/dss/structured_dss_repository.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/features/assessment/multi_step_assessment_screen.dart';
import 'package:floodsense/features/dss/dss_controller.dart';

import 'test_data.dart';

class FakeDssRepository implements StructuredDssRepository {
  int starts = 0;
  int answers = 0;
  @override
  Future<DssStep> start(String susceptibilityCode) async {
    starts++;
    return const DssStep(
      flowCode: 'preparedness',
      flowVersion: '1',
      title: 'Preparedness guidance',
      dataStatus: 'DEMONSTRATION',
      warning: 'Not an evacuation order.',
      position: 1,
      total: 2,
      question: DssQuestion(
        code: 'ready',
        prompt: 'Are essential supplies ready?',
        explanation: 'Choose the answer that best matches this scenario.',
        options: [
          DssOption(code: 'yes', label: 'Yes', supportingText: ''),
          DssOption(
            code: 'no',
            label: 'No',
            supportingText: 'Review supplies.',
          ),
        ],
      ),
    );
  }

  @override
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String optionCode,
  }) async {
    answers++;
    return const DssStep(
      flowCode: 'preparedness',
      flowVersion: '1',
      title: 'Preparedness guidance',
      dataStatus: 'DEMONSTRATION',
      warning: 'Not an evacuation order.',
      position: 2,
      total: 2,
      outcome: DssOutcome(
        title: 'Prepare safely',
        instruction: 'Review supplies and monitor official information.',
        warning: 'This does not change the High classification.',
        source: 'TEST DEMONSTRATION SOURCE',
      ),
    );
  }
}

Future<void> selectScenario(WidgetTester tester) async {
  final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
  await tester.ensureVisible(intensity);
  await tester.tap(intensity);
  await tester.pump();
  final duration = find.byKey(const Key('duration-DEMO_6_HOURS'));
  await tester.ensureVisible(duration);
  await tester.tap(duration);
  await tester.pump();
}

Future<void> selectZone(WidgetTester tester) async {
  final page = find.byKey(const Key('assessment-page-1'));
  await tester.drag(page, const Offset(0, -900));
  await tester.pumpAndSettle();
  final zone = find.byType(DropdownButtonFormField<GeographicArea>);
  await tester.tap(zone);
  await tester.pumpAndSettle();
  await tester.tap(find.text('Demo Zone A (DEMO_ZONE_A)').last);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('multi-step assessment preserves scenario when moving backward', (
    tester,
  ) async {
    final api = FakeFloodSenseApi();
    await tester.pumpWidget(
      MaterialApp(
        home: MultiStepAssessmentScreen(
          api: api,
          dssRepository: FakeDssRepository(),
          showBasemap: false,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Step 1 of 5'), findsOneWidget);
    await selectScenario(tester);
    await tester.tap(find.byKey(const Key('assessment-continue')));
    await tester.pumpAndSettle();
    expect(find.text('Step 2 of 5'), findsOneWidget);
    expect(api.evaluateCalls, 0);

    await selectZone(tester);
    await tester.tap(find.byKey(const Key('assessment-back')));
    await tester.pump();
    expect(find.bySemanticsLabel(RegExp('Heavy, selected')), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('6 hours, selected')), findsOneWidget);
  });

  testWidgets('review requires explicit assessment then exposes DSS', (
    tester,
  ) async {
    final api = FakeFloodSenseApi();
    final dss = FakeDssRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: MultiStepAssessmentScreen(
          api: api,
          dssRepository: dss,
          showBasemap: false,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await selectScenario(tester);
    await tester.tap(find.byKey(const Key('assessment-continue')));
    await tester.pumpAndSettle();
    await selectZone(tester);
    await tester.tap(find.byKey(const Key('assessment-continue')));
    await tester.pump();
    expect(find.text('Review before assessment'), findsOneWidget);
    expect(api.evaluateCalls, 0);
    await tester.tap(find.byKey(const Key('assessment-continue')));
    await tester.pumpAndSettle();
    expect(api.evaluateCalls, 1);
    expect(find.text('High susceptibility'), findsOneWidget);
    await tester.tap(find.byKey(const Key('assessment-continue')));
    await tester.pumpAndSettle();
    expect(find.text('Are essential supplies ready?'), findsOneWidget);
  });

  testWidgets('MGB barangays replace the separate demonstration-zone choice', (
    tester,
  ) async {
    final barangays = sampleMgbBarangayAreas();
    await tester.pumpWidget(
      MaterialApp(
        home: MultiStepAssessmentScreen(
          api: FakeFloodSenseApi(areas: barangays, referenceAreas: barangays),
          showBasemap: false,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await selectScenario(tester);
    await tester.tap(find.byKey(const Key('assessment-continue')));
    await tester.pumpAndSettle();

    expect(find.text('Assessment demonstration zone'), findsNothing);
    expect(find.text('Choose a barangay manually'), findsOneWidget);
    expect(find.text('Barangay'), findsOneWidget);
  });

  test(
    'DSS navigation is client-side, supports back/restart, and resets',
    () async {
      final repository = FakeDssRepository();
      final controller = DssController(repository);
      await controller.start('HIGH');
      controller.select('yes');
      await controller.continueFlow();
      expect(controller.current!.isOutcome, isTrue);
      expect(controller.canGoBack, isTrue);
      controller.goBack();
      expect(controller.current!.question!.code, 'ready');
      await controller.restart();
      expect(repository.starts, 2);
      controller.resetForScenarioChange();
      expect(controller.current, isNull);
      expect(controller.susceptibilityCode, isNull);
      controller.dispose();
    },
  );
}
