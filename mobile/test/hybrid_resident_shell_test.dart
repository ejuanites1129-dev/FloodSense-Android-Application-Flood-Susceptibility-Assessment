import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/data/auth/resident_auth_repository.dart';
import 'package:floodsense/data/dss/structured_dss_repository.dart';
import 'package:floodsense/data/models/geographic_area.dart';

import 'resident_test_fakes.dart';
import 'test_data.dart';

class _FakeDssRepository implements StructuredDssRepository {
  @override
  Future<DssStep> start(String susceptibilityCode) async => const DssStep(
    flowCode: 'preparedness',
    flowVersion: '1',
    title: 'Preparedness guidance',
    dataStatus: 'DEMONSTRATION',
    warning: 'This is not an evacuation order.',
    position: 1,
    total: 2,
    question: DssQuestion(
      code: 'supplies',
      prompt: 'Are essential supplies ready?',
      explanation: 'Choose the answer that matches your household plan.',
      options: [
        DssOption(code: 'yes', label: 'Yes', supportingText: ''),
        DssOption(
          code: 'no',
          label: 'No',
          supportingText: 'Review supplies before an emergency.',
        ),
      ],
    ),
  );

  @override
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String optionCode,
  }) async => const DssStep(
    flowCode: 'preparedness',
    flowVersion: '1',
    title: 'Preparedness guidance',
    dataStatus: 'DEMONSTRATION',
    warning: 'This is not an evacuation order.',
    position: 2,
    total: 2,
    outcome: DssOutcome(
      title: 'Prepare safely',
      instruction: 'Review supplies and follow official authorities.',
      warning: 'This does not change the susceptibility classification.',
      source: 'TEST DEMONSTRATION SOURCE',
    ),
  );
}

Future<void> _pumpApp(
  WidgetTester tester, {
  required FakeResidentAuthRepository auth,
  FakeFloodSenseApi? api,
  Size size = const Size(390, 844),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    FloodSenseApp(
      api: api ?? FakeFloodSenseApi(),
      authRepository: auth,
      dssRepository: _FakeDssRepository(),
      enableResidentAuthentication: true,
      showBasemap: false,
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _scrollTo(
  WidgetTester tester,
  Finder target,
  Key scrollableKey,
) async {
  await tester.scrollUntilVisible(
    target,
    300,
    scrollable: find.descendant(
      of: find.byKey(scrollableKey),
      matching: find.byType(Scrollable),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('login remains card-free and has no resident navigation', (
    tester,
  ) async {
    await _pumpApp(tester, auth: FakeResidentAuthRepository());

    expect(find.text('Resident sign in'), findsOneWidget);
    expect(find.byType(Card), findsNothing);
    expect(find.byKey(const Key('resident-bottom-navigation')), findsNothing);
    expect(find.textContaining('Planning scenarios only'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'hybrid navigation preserves choices and assessment returns to Map result',
    (tester) async {
      final api = FakeFloodSenseApi();
      final auth = FakeResidentAuthRepository()
        ..restoration = testSession(SetupStage.authenticatedReady);
      await _pumpApp(tester, auth: auth, api: api, size: const Size(320, 640));

      expect(find.byKey(const Key('resident-hybrid-map')), findsOneWidget);
      final coverage = tester.widget<PolygonLayer<int>>(
        find.byKey(const Key('hybrid-bacoor-coverage-mask')),
      );
      expect(coverage.polygons, hasLength(1));
      expect(coverage.invertedFill, const Color(0xA6677280));
      expect(find.text('Outside Bacoor assessment coverage'), findsOneWidget);
      expect(find.text('Map'), findsOneWidget);
      expect(find.text('Assess'), findsOneWidget);
      expect(find.text('Prepare'), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);

      await tester.tap(find.byKey(const Key('resident-nav-assess')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('hybrid-assessment-scenario')),
        findsOneWidget,
      );

      final intensity = find.byKey(const Key('option-DEMO_HEAVY'));
      await _scrollTo(
        tester,
        intensity,
        const Key('hybrid-assessment-scenario'),
      );
      await tester.tap(intensity);
      await tester.pump();
      final duration = find.byKey(const Key('duration-DEMO_6_HOURS'));
      await _scrollTo(
        tester,
        duration,
        const Key('hybrid-assessment-scenario'),
      );
      await tester.tap(duration);
      await tester.pump();

      await tester.tap(find.byKey(const Key('resident-nav-map')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Heavy rainfall'), findsOneWidget);
      expect(find.textContaining('6 hours'), findsOneWidget);
      await tester.tap(find.byKey(const Key('resident-nav-assess')));
      await tester.pumpAndSettle();
      expect(find.bySemanticsLabel(RegExp('Heavy, selected')), findsOneWidget);

      final scenarioContinue = find.byKey(
        const Key('hybrid-assessment-continue'),
      );
      await _scrollTo(
        tester,
        scenarioContinue,
        const Key('hybrid-assessment-scenario'),
      );
      await tester.tap(scenarioContinue);
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('hybrid-assessment-location')),
        findsOneWidget,
      );

      final zone = find.byType(DropdownButtonFormField<GeographicArea>);
      await _scrollTo(tester, zone, const Key('hybrid-assessment-location'));
      await tester.tap(zone);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Demo Zone A (DEMO_ZONE_A)').last);
      await tester.pumpAndSettle();
      final locationContinue = find.byKey(
        const Key('hybrid-assessment-continue'),
      );
      await _scrollTo(
        tester,
        locationContinue,
        const Key('hybrid-assessment-location'),
      );
      await tester.tap(locationContinue);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('hybrid-assessment-review')), findsOneWidget);

      final runAssessment = find.byKey(const Key('hybrid-run-assessment'));
      await _scrollTo(
        tester,
        runAssessment,
        const Key('hybrid-assessment-review'),
      );
      await tester.tap(runAssessment);
      await tester.pumpAndSettle();

      expect(api.evaluateCalls, 1);
      expect(find.byKey(const Key('hybrid-result-banner')), findsOneWidget);
      expect(find.text('High susceptibility'), findsOneWidget);
      final preparedness = find.byKey(const Key('result-view-preparedness'));
      await _scrollTo(
        tester,
        preparedness,
        const Key('map-context-sheet-content'),
      );
      await tester.tap(preparedness);
      await tester.pumpAndSettle();
      final warning = find.text('This is not an evacuation order.');
      await _scrollTo(tester, warning, const Key('dss-flow-view'));
      expect(warning, findsOneWidget);
      final question = find.text('Are essential supplies ready?');
      await _scrollTo(tester, question, const Key('dss-flow-view'));
      expect(question, findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Profile exposes secondary options and scenario limitation', (
    tester,
  ) async {
    final auth = FakeResidentAuthRepository()
      ..restoration = testSession(SetupStage.authenticatedReady);
    await _pumpApp(tester, auth: auth, size: const Size(320, 640));

    await tester.tap(find.byKey(const Key('resident-nav-profile')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('profile-secondary-options')), findsOneWidget);
    expect(find.byKey(const Key('profile-preferences')), findsOneWidget);
    expect(find.textContaining('Live alerts are not enabled'), findsOneWidget);
    final methodology = find.text('Data & methodology');
    await _scrollTo(
      tester,
      methodology,
      const Key('profile-secondary-options'),
    );
    expect(methodology, findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
