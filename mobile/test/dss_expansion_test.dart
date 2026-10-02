import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/theme/app_theme.dart';
import 'package:floodsense/data/dss/structured_dss_repository.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/features/dss/dss_assessment_context.dart';
import 'package:floodsense/features/dss/dss_controller.dart';
import 'package:floodsense/features/dss/dss_flow_view.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'test_data.dart';

const _visualQa = bool.fromEnvironment('DSS_VISUAL_QA');
bool _visualQaFontsLoaded = false;

ThemeData visualQaTheme() {
  final theme = AppTheme.light();
  return theme.copyWith(
    textTheme: theme.textTheme.apply(fontFamily: 'DssVisualQa'),
    filledButtonTheme: FilledButtonThemeData(
      style: theme.filledButtonTheme.style!.copyWith(
        textStyle: const WidgetStatePropertyAll(
          TextStyle(
            fontFamily: 'DssVisualQa',
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    ),
  );
}

Future<void> loadVisualQaFonts(WidgetTester tester) async {
  if (!_visualQa || _visualQaFontsLoaded) return;
  await tester.runAsync(() async {
    // Capture fonts are deliberately local and optional: no production font
    // asset, dependency, or test fixture font is changed for visual QA.
    final fontDirectory = Platform.environment['DSS_VISUAL_QA_FONT_DIRECTORY'];
    final iconFont = Platform.environment['DSS_VISUAL_QA_ICON_FONT'];
    if (fontDirectory == null || iconFont == null) {
      throw StateError(
        'Visual QA requires local text and Material icon fonts.',
      );
    }
    final textLoader = FontLoader('DssVisualQa');
    for (final name in ['arial.ttf', 'arialbd.ttf']) {
      textLoader.addFont(
        File('$fontDirectory/$name').readAsBytes().then(ByteData.sublistView),
      );
    }
    await textLoader.load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(File(iconFont).readAsBytes().then(ByteData.sublistView))).load();
    _visualQaFontsLoaded = true;
  });
}

const contextSnapshot = DssAssessmentContext(
  susceptibilityCode: 'HIGH',
  susceptibilityLabel: 'High',
  operatingMode: 'OFFICIAL',
  areaCode: 'TEST_AREA',
  areaName: 'Test assessed area',
  intensityCode: 'TEST_INTENSITY',
  intensityLabel: 'Test hypothetical intensity',
  durationCode: 'TEST_DURATION',
  durationLabel: 'Test duration',
  dataStatus: 'APPROVED',
  rulesetName: 'Test knowledge',
  rulesetVersion: '2',
);

Map<String, dynamic> stepJson({bool outcome = false, bool expanded = true}) => {
  'contract_version': expanded ? 2 : 1,
  'kind': outcome ? 'outcome' : 'question',
  'flow': {
    'code': 'preparedness',
    'version': '2',
    'title': 'Test synthetic guide',
    'operating_mode': 'OFFICIAL',
    'data_status': 'APPROVED',
    'warning': 'Test content only; no current event is inferred.',
    if (expanded) ...{
      'source': sourceJson(),
      'source_locator': 'Test pack',
      'attribution': 'Test attribution',
      'limitations': 'Test guide limitation',
      'effective_date': '2026-10-02',
      'reviewed_on': '2026-10-02',
    },
  },
  if (!outcome)
    'question': {
      'code': 'helper',
      'prompt': 'Is a trusted helper assigned?',
      'explanatory_text': 'Choose the answer matching your household plan.',
      'options': [
        {
          'code': 'yes',
          'label': 'A helper is assigned',
          'supporting_text': 'Review the agreed plan.',
        },
        {
          'code': 'no',
          'label': 'A helper is not assigned',
          'supporting_text': 'Discuss support needs.',
        },
      ],
    },
  if (!outcome) 'progress': {'position': 1, 'question_count': 1},
  if (outcome)
    'outcome': {
      'title': 'Test household plan',
      'instruction': 'Test personalized outcome.',
      'warning': 'Guidance does not change the assessment.',
      'source': sourceJson(),
      'guidance': [
        {
          'title': 'Linked action',
          'instruction': 'Test linked action from backend.',
          'data_status': 'APPROVED',
          'source': sourceJson(),
          'attribution': 'Test linked attribution',
        },
      ],
    },
  if (expanded)
    'content_blocks': [
      blockJson(
        1,
        'SCENARIO_EXPLANATION',
        'ALWAYS',
        'Test scenario explanation',
      ),
      blockJson(2, 'HOUSEHOLD_ACTION', 'BEFORE', 'Test household preparation'),
      blockJson(3, 'HOUSEHOLD_ACTION', 'DURING', 'Test during reference'),
      blockJson(4, 'HOUSEHOLD_ACTION', 'AFTER', 'Test after reference'),
      blockJson(5, 'AUTHORITY_ACTIVITY', 'BEFORE', 'Test authority reference'),
      blockJson(
        6,
        'MONITORING_REFERENCE',
        'ALWAYS',
        'Test monitoring reference',
      ),
      {
        ...blockJson(7, 'OFFICIAL_CHANNEL', 'ALWAYS', 'Test public channel'),
        'public_url': 'https://example.org/test-only',
      },
      {
        ...blockJson(8, 'RISK_REFERENCE', 'ALWAYS', 'Staff-only private note'),
        'audience': 'STAFF_ONLY',
      },
    ],
};

Map<String, dynamic> sourceJson() => {
  'name': 'Synthetic public source with a deliberately long title for narrow screens',
  'organization': 'Test organization',
  'custodian': 'Test custodian',
  'version': 'test-2',
  'date': '2026-10-01',
  'reviewed_on': '2026-10-02',
  'data_status': 'APPROVED',
  'limitations': 'Synthetic widget fixture; not resident guidance.',
  'citation_url': 'https://example.org/source-test',
};

Map<String, dynamic> distinctOutcomeSourcesJson() {
  final response = stepJson(outcome: true);
  final outcome = response['outcome'] as Map<String, dynamic>;
  outcome['source'] = {
    ...sourceJson(),
    'name': 'Distinct outcome source',
    'version': 'outcome-3',
    'reviewed_on': '2026-09-24',
    'limitations': 'Outcome-specific public limitation.',
    'citation_url': 'https://example.org/outcome-v3',
  };
  final guidance = (outcome['guidance'] as List).single as Map<String, dynamic>;
  guidance['source'] = {
    ...sourceJson(),
    'name': 'Distinct linked guidance source',
    'version': 'linked-4',
    'reviewed_on': '2026-09-25',
    'limitations': 'Linked guidance public limitation.',
    'citation_url': 'https://example.org/linked-v4',
  };
  return response;
}

Map<String, dynamic> blockJson(
  int id,
  String type,
  String phase,
  String title,
) => {
  'id': id,
  'title': title,
  'body':
      'Synthetic test reference content. ${List.filled(3, 'This fixture checks wrapping and source metadata.').join(' ')}',
  'content_type': type,
  'phase': phase,
  'audience': 'RESIDENT',
  'display_order': id,
  'source': sourceJson(),
  'source_locator': 'Test section $id',
  'attribution': 'Test block attribution',
  'limitations': 'Test item limitation',
  'effective_date': '2026-10-02',
  'reviewed_on': '2026-10-02',
};

class _Repository implements StructuredDssRepository {
  DssStep? supplied;
  bool unavailable = false;
  final List<String> modes = [];
  Completer<DssStep>? pendingStart;
  Completer<DssStep>? pendingAnswer;
  @override
  Future<DssStep> start(
    String susceptibilityCode, {
    required String operatingMode,
  }) async {
    modes.add(operatingMode);
    if (unavailable) {
      throw StateError('The DSS is offline. Check your connection.');
    }
    return pendingStart?.future ?? supplied ?? DssStep.fromJson(stepJson());
  }

  @override
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String operatingMode,
    required String optionCode,
  }) async {
    modes.add(operatingMode);
    return pendingAnswer?.future ?? DssStep.fromJson(stepJson(outcome: true));
  }
}

Future<void> scrollTo(WidgetTester tester, Finder target) async {
  final scrollable = find.descendant(
    of: find.byKey(const Key('dss-flow-view')),
    matching: find.byType(Scrollable),
  );
  if (target.evaluate().isEmpty) {
    tester.state<ScrollableState>(scrollable).position.jumpTo(0);
    await tester.pump();
  }
  await tester.scrollUntilVisible(
    target,
    250,
    scrollable: scrollable,
    maxScrolls: 60,
  );
  await tester.pumpAndSettle();
}

Future<void> pumpGuide(
  WidgetTester tester,
  DssController controller, {
  double width = 390,
  double scale = 1,
  bool settle = true,
}) async {
  await loadVisualQaFonts(tester);
  tester.view.physicalSize = Size(width, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: _visualQa ? visualQaTheme() : null,
      home: MediaQuery(
        data: MediaQueryData(
          size: Size(width, 844),
          textScaler: TextScaler.linear(scale),
        ),
        child: RepaintBoundary(
          key: const Key('dss-qa-boundary'),
          child: Scaffold(
            body: DssFlowView(
              controller: controller,
              assessmentContext: contextSnapshot,
            ),
          ),
        ),
      ),
    ),
  );
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
  }
}

Future<void> capture(WidgetTester tester, String name) async {
  if (!_visualQa) return;
  final boundary = tester.renderObject<RenderRepaintBoundary>(
    find.byKey(const Key('dss-qa-boundary')),
  );
  await tester.runAsync(() async {
    final rendered = await boundary.toImage(pixelRatio: 1);
    final bytes = await rendered.toByteData(format: ui.ImageByteFormat.png);
    final directory = Directory('../tmp/dss-expansion-qa');
    await directory.create(recursive: true);
    await File('${directory.path}/$name.png')
        .writeAsBytes(bytes!.buffer.asUint8List());
    rendered.dispose();
  });
}

void main() {
  test('content block ordering preserves numeric primary-key ties', () {
    final response = stepJson();
    response['content_blocks'] = [
      for (final id in [10, 2, 1])
        {
          ...blockJson(id, 'HOUSEHOLD_ACTION', 'BEFORE', 'Test action $id'),
          'display_order': 4,
        },
    ];
    expect(DssStep.fromJson(response).contentBlocks.map((block) => block.id), [
      '1',
      '2',
      '10',
    ]);
    response['content_blocks'] = [
      for (final id in ['legacy-c', 'legacy-a', 'legacy-b'])
        {
          ...blockJson(1, 'HOUSEHOLD_ACTION', 'BEFORE', 'Legacy test action'),
          'id': id,
          'display_order': 4,
        },
    ];
    expect(DssStep.fromJson(response).contentBlocks.map((block) => block.id), [
      'legacy-a',
      'legacy-b',
      'legacy-c',
    ]);
  });

  test('assessment snapshot uses completed codes and mode, and rejects unclassified results', () {
    final result = AssessmentResult.fromJson({
      ...assessmentJson(),
      'operating_mode': 'OFFICIAL',
    });
    final snapshot = DssAssessmentContext.fromAssessment(
      result,
      intensities: sampleOptions().intensityOptions,
      durations: sampleOptions().durationOptions,
    );
    expect(snapshot.operatingMode, 'OFFICIAL');
    expect(snapshot.intensityLabel, 'Heavy');
    expect(snapshot.durationLabel, '6 hours');
    expect(snapshot.areaName, result.area.name);
    expect(
      () => DssAssessmentContext.fromAssessment(
        sampleResult(state: 'INSUFFICIENT_DATA'),
        intensities: const [],
        durations: const [],
      ),
      throwsStateError,
    );
  });

  test('v2 preserves public provenance and hides staff-only blocks; old responses parse', () {
    final step = DssStep.fromJson(stepJson());
    expect(step.contentBlocks, hasLength(7));
    expect(step.source.referenceDate, '2026-10-01');
    expect(step.source.custodian, 'Test custodian');
    expect(step.source.citationUrl!.scheme, 'https');
    expect(step.contentBlocks.last.publicUrl!.scheme, 'https');
    expect(
      DssContentBlock.fromJson({
        ...blockJson(1, 'OFFICIAL_CHANNEL', 'ALWAYS', 'Test'),
        'public_url': 'http://example.org',
      }).publicUrl,
      isNull,
    );
    expect(DssStep.fromJson(stepJson(expanded: false)).contentBlocks, isEmpty);
    expect(
      DssStep.fromJson(stepJson(outcome: true))
          .outcome!
          .guidance
          .single
          .instruction,
      'Test linked action from backend.',
    );
  });

  test(
    'outcome and linked sources preserve complete distinct public provenance',
    () {
      final outcome = DssStep.fromJson(distinctOutcomeSourcesJson()).outcome!;
      expect(outcome.source, 'Distinct outcome source — Test organization');
      expect(outcome.sourceDetails.version, 'outcome-3');
      expect(outcome.sourceDetails.reviewedOn, '2026-09-24');
      expect(
        outcome.sourceDetails.limitations,
        'Outcome-specific public limitation.',
      );
      expect(
        outcome.sourceDetails.citationUrl.toString(),
        'https://example.org/outcome-v3',
      );
      final linked = outcome.guidance.single;
      expect(linked.source.name, 'Distinct linked guidance source');
      expect(linked.source.version, 'linked-4');
      expect(linked.source.reviewedOn, '2026-09-25');
      expect(linked.source.limitations, 'Linked guidance public limitation.');
      expect(
        linked.source.citationUrl.toString(),
        'https://example.org/linked-v4',
      );
      expect(linked.attribution, 'Test linked attribution');
    },
  );

  testWidgets(
    'expanded outcome and linked guidance sources show metadata and citation addresses',
    (tester) async {
      final controller = DssController(
        _Repository()
          ..supplied = DssStep.fromJson(distinctOutcomeSourcesJson()),
      );
      addTearDown(controller.dispose);
      await pumpGuide(tester, controller, width: 360, scale: 1.5);
      await scrollTo(tester, find.text('Test personalized outcome.'));
      expect(find.text('Test personalized outcome.'), findsOneWidget);
      await scrollTo(tester, find.text('Test linked action from backend.'));
      expect(find.text('Test linked action from backend.'), findsOneWidget);
      final outcomeSource = find.byKey(const Key('dss-outcome-source'));
      await scrollTo(tester, outcomeSource);
      await tester.tap(find.text('Outcome source for Test household plan'));
      await tester.pumpAndSettle();
      for (final text in [
        'Source: Distinct outcome source — Test organization',
        'Source version: outcome-3',
        'Source review date: 2026-09-24',
        'Source limitations: Outcome-specific public limitation.',
      ]) {
        await scrollTo(tester, find.text(text));
        expect(find.text(text), findsOneWidget);
      }
      if (_visualQa) {
        await scrollTo(
          tester,
          find.text('Source: Distinct outcome source — Test organization'),
        );
        await capture(tester, 'resident-360-outcome-source-1p5x');
      }
      final outcomeAddress = find.descendant(
        of: outcomeSource,
        matching: find.text('Verified source and version address'),
      );
      await scrollTo(tester, outcomeAddress);
      await tester.tap(outcomeAddress);
      await tester.pumpAndSettle();
      expect(find.text('https://example.org/outcome-v3'), findsOneWidget);
      await tester.tap(find.text('Close'));
      await tester.pumpAndSettle();
      final linkedTitle = find.text('Linked guidance source for Linked action');
      await scrollTo(tester, linkedTitle);
      await tester.tap(linkedTitle);
      await tester.pumpAndSettle();
      for (final text in [
        'Source: Distinct linked guidance source — Test organization',
        'Source version: linked-4',
        'Source review date: 2026-09-25',
        'Source limitations: Linked guidance public limitation.',
        'Attribution: Test linked attribution',
      ]) {
        await scrollTo(tester, find.text(text));
        expect(find.text(text), findsOneWidget);
      }
      if (_visualQa) {
        await scrollTo(
          tester,
          find.text(
            'Source: Distinct linked guidance source — Test organization',
          ),
        );
        await capture(tester, 'resident-360-linked-source-1p5x');
      }
      final linkedAddress = find.descendant(
        of: find.ancestor(
          of: linkedTitle,
          matching: find.byType(ExpansionTile),
        ),
        matching: find.text('Verified source and version address'),
      );
      await scrollTo(tester, linkedAddress);
      await tester.tap(linkedAddress);
      await tester.pumpAndSettle();
      expect(find.text('https://example.org/linked-v4'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  test('repository sends assessment mode to start and answer without answers persistence', () async {
    final requests = <http.Request>[];
    final repository = HttpStructuredDssRepository(
      baseUrl: 'https://example.org/api/v1',
      client: MockClient((request) async {
        requests.add(request);
        return http.Response(
          jsonEncode(stepJson(outcome: request.method == 'POST')),
          200,
        );
      }),
    );
    final step = await repository.start('HIGH', operatingMode: 'OFFICIAL');
    await repository.answer(
      current: step,
      susceptibilityCode: 'HIGH',
      operatingMode: 'OFFICIAL',
      optionCode: 'yes',
    );
    expect(requests.first.url.queryParameters['mode'], 'OFFICIAL');
    final body = jsonDecode(requests.last.body) as Map;
    expect(body['mode'], 'OFFICIAL');
    expect(
      body.keys,
      unorderedEquals([
        'mode',
        'susceptibility_level',
        'question_code',
        'option_code',
      ]),
    );
  });

  test('late start and answer cannot restore a reset scenario; Back removes local answer recap', () async {
    final repository = _Repository()..pendingStart = Completer<DssStep>();
    final controller = DssController(repository);
    final pending = controller.start(contextSnapshot);
    controller.resetForScenarioChange();
    repository.pendingStart!.complete(DssStep.fromJson(stepJson()));
    await pending;
    expect(controller.current, isNull);
    expect(controller.busy, isFalse);
    repository.pendingStart = null;
    await controller.start(contextSnapshot);
    controller.select('yes');
    await controller.continueFlow();
    expect(controller.answers.single.question, 'Is a trusted helper assigned?');
    controller.goBack();
    expect(controller.answers, isEmpty);
    repository.pendingAnswer = Completer<DssStep>();
    controller.select('yes');
    final answer = controller.continueFlow();
    controller.resetForScenarioChange();
    repository.pendingAnswer!.complete(
      DssStep.fromJson(stepJson(outcome: true)),
    );
    await answer;
    expect(controller.current, isNull);
    expect(controller.answers, isEmpty);
    expect(controller.assessmentContext, isNull);
    controller.dispose();
  });

  test(
    'a guide with an explicit different operating mode is unavailable',
    () async {
      final raw = stepJson();
      (raw['flow'] as Map)['operating_mode'] = 'DEMONSTRATION';
      final controller = DssController(
        _Repository()..supplied = DssStep.fromJson(raw),
      );
      await controller.start(contextSnapshot);
      expect(controller.current, isNull);
      expect(
        controller.error,
        'Preparedness guidance is unavailable for this assessment mode.',
      );
      expect(controller.assessmentContext, contextSnapshot);
      controller.dispose();
    },
  );

  test(
    'connection failures and malformed responses show readable retry errors',
    () async {
      final offline = HttpStructuredDssRepository(
        baseUrl: 'https://example.org/api/v1',
        client: MockClient(
          (_) async =>
              throw http.ClientException('Test browser connection failure'),
        ),
      );
      await expectLater(
        offline.start('HIGH', operatingMode: 'OFFICIAL'),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            'The DSS is offline. Check your connection.',
          ),
        ),
      );
      final malformed = HttpStructuredDssRepository(
        baseUrl: 'https://example.org/api/v1',
        client: MockClient(
          (_) async =>
              http.Response('<html>Test unavailable response</html>', 503),
        ),
      );
      await expectLater(
        malformed.start('HIGH', operatingMode: 'OFFICIAL'),
        throwsA(
          isA<StateError>().having(
            (error) => error.message,
            'message',
            'Structured guidance could not be read. Please try again.',
          ),
        ),
      );
    },
  );

  for (final width in [360.0, 390.0]) {
    testWidgets(
      'expanded guide renders separated phases and sources at $width with text scaling',
      (tester) async {
        final repository = _Repository();
        final controller = DssController(repository);
        addTearDown(controller.dispose);
        await pumpGuide(tester, controller, width: width, scale: 1.5);
        expect(repository.modes.single, 'OFFICIAL');
        expect(
          find.text('Scenario-based susceptibility: High'),
          findsOneWidget,
        );
        await capture(tester, 'resident-${width.toInt()}-scaled-header');
        for (final heading in [
          dssScenarioDisclaimer,
          'What this scenario may mean',
          'What your household can prepare',
          'During a flood — educational reference',
          'After a flood — educational reference',
          'Official information channels',
          'What local authorities may coordinate',
          'FloodSense does not monitor these sources live.',
        ]) {
          await scrollTo(tester, find.text(heading));
          expect(find.text(heading), findsOneWidget);
          expect(tester.takeException(), isNull);
          if (heading == 'What your household can prepare') {
            await capture(tester, 'resident-${width.toInt()}-scaled-household');
          }
          if (width == 390 &&
              heading == 'During a flood — educational reference') {
            await capture(tester, 'resident-390-scaled-during');
          }
          if (width == 390 &&
              heading == 'After a flood — educational reference') {
            await capture(tester, 'resident-390-scaled-after');
          }
        }
        await capture(tester, 'resident-${width.toInt()}-scaled-references');
        expect(find.text('Staff-only private note'), findsNothing);
        await scrollTo(tester, find.text('Is a trusted helper assigned?'));
        await scrollTo(tester, find.byKey(const Key('dss-option-yes')));
        await tester.tap(find.byKey(const Key('dss-option-yes')));
        await tester.pump();
        await scrollTo(tester, find.text('Continue'));
        await tester.tap(find.text('Continue'));
        await tester.pumpAndSettle();
        await scrollTo(tester, find.text('Test household plan'));
        expect(find.text('Test personalized outcome.'), findsOneWidget);
        await scrollTo(tester, find.text('Test linked action from backend.'));
        await scrollTo(tester, find.text('Your household support answers'));
        await tester.tap(find.text('Your household support answers'));
        await tester.pumpAndSettle();
        await scrollTo(tester, find.text('Is a trusted helper assigned?'));
        expect(find.text('Is a trusted helper assigned?'), findsOneWidget);
        await scrollTo(tester, find.text('Sources and limitations'));
        await capture(
          tester,
          'resident-${width.toInt()}-scaled-provenance-header',
        );
        await scrollTo(tester, find.text('Attribution: Test attribution'));
        await capture(tester, 'resident-${width.toInt()}-scaled-sources');
        await scrollTo(tester, find.text('Back'));
        await tester.tap(find.text('Back'));
        await tester.pumpAndSettle();
        await scrollTo(tester, find.text('Is a trusted helper assigned?'));
        expect(controller.answers, isEmpty);
        expect(controller.assessmentContext, contextSnapshot);
        await scrollTo(tester, find.byKey(const Key('dss-option-no')));
        await tester.tap(find.byKey(const Key('dss-option-no')));
        await tester.pump();
        await scrollTo(tester, find.text('Continue'));
        await tester.tap(find.text('Continue'));
        await tester.pumpAndSettle();
        await scrollTo(tester, find.text('Restart'));
        await tester.tap(find.text('Restart'));
        await tester.pumpAndSettle();
        await scrollTo(tester, find.text('Is a trusted helper assigned?'));
        expect(controller.answers, isEmpty);
        expect(controller.selectedOptionCode, isNull);
        expect(controller.assessmentContext, contextSnapshot);
        expect(repository.modes, [
          'OFFICIAL',
          'OFFICIAL',
          'OFFICIAL',
          'OFFICIAL',
        ]);
        await scrollTo(tester, find.byKey(const Key('dss-data-sources')));
        await tester.tap(find.byKey(const Key('dss-data-sources')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('data-sources-screen')), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets('the standard API warning repeats no scenario disclaimer', (
    tester,
  ) async {
    final response = stepJson(expanded: false);
    (response['flow'] as Map)['warning'] = dssScenarioDisclaimer;
    final controller = DssController(
      _Repository()..supplied = DssStep.fromJson(response),
    );
    addTearDown(controller.dispose);
    await pumpGuide(tester, controller, width: 800);
    expect(find.text(dssScenarioDisclaimer), findsOneWidget);
    expect(find.text('Test synthetic guide'), findsOneWidget);
    expect(find.text('Household support check'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'loading and no-flow retain immutable scenario context and disclaimer',
    (tester) async {
      final repository = _Repository()..pendingStart = Completer<DssStep>();
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await pumpGuide(tester, controller, width: 360, settle: false);
      expect(find.text(dssScenarioDisclaimer), findsOneWidget);
      expect(find.text('Scenario-based susceptibility: High'), findsOneWidget);
      expect(controller.assessmentContext, contextSnapshot);
      await tester.scrollUntilVisible(
        find.byType(CircularProgressIndicator),
        250,
        scrollable: find.descendant(
          of: find.byKey(const Key('dss-flow-view')),
          matching: find.byType(Scrollable),
        ),
      );
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      repository.pendingStart!.completeError(
        StateError(
          'Published structured guidance is not available for this result.',
        ),
      );
      await tester.pumpAndSettle();
      await scrollTo(
        tester,
        find.text(
          'Published structured guidance is not available for this result.',
        ),
      );
      expect(
        find.text('An unavailable guide does not change your scenario result.'),
        findsOneWidget,
      );
      expect(controller.current, isNull);
      expect(repository.modes, ['OFFICIAL']);
      expect(controller.assessmentContext, contextSnapshot);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'offline state retains scenario disclaimer and retries at 360px, 2x text',
    (tester) async {
      final repository = _Repository()..unavailable = true;
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await pumpGuide(tester, controller, width: 360, scale: 2);
      await scrollTo(
        tester,
        find.text('The DSS is offline. Check your connection.'),
      );
      await capture(tester, 'resident-360-unavailable-2x');
      await scrollTo(tester, find.text('Try again'));
      repository.unavailable = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(controller.current, isNotNull);
      expect(controller.assessmentContext, contextSnapshot);
      expect(repository.modes, ['OFFICIAL', 'OFFICIAL']);
      expect(tester.takeException(), isNull);
    },
  );
}
