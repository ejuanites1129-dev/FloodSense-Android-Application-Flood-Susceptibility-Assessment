import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/dss/structured_dss_repository.dart';
import 'package:floodsense/data/models/guidance_item.dart';
import 'package:floodsense/features/dss/dss_assessment_context.dart';
import 'package:floodsense/features/dss/dss_controller.dart';
import 'package:floodsense/features/dss/preparedness_dashboard.dart';
import 'package:floodsense/features/evacuation/evacuation_map_status.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_centers_section.dart';
import 'package:floodsense/features/location/location_controller.dart';

import 'dss_expansion_test.dart' as qa;
import 'location_day4_centers_test.dart'
    show Day4LocationService, Day4Resolver, FakeNearestCenterProvider;
import 'test_data.dart';

const _captureQa = bool.fromEnvironment('DSS_VISUAL_QA');
const _source = DssSource(
  name: 'Synthetic test source',
  dataStatus: 'DEMONSTRATION',
  version: 'test-1',
  limitations: 'Widget fixture only.',
);
const _context = DssAssessmentContext(
  susceptibilityCode: 'HIGH',
  susceptibilityLabel: 'High',
  operatingMode: 'DEMONSTRATION',
  areaCode: 'TEST_AREA',
  areaName: 'Test assessed area',
  intensityCode: 'TEST_RAIN',
  intensityLabel: 'Heavy',
  durationCode: 'TEST_DURATION',
  durationLabel: '6 hours',
  dataStatus: 'DEMONSTRATION',
  rulesetName: 'Test knowledge',
  rulesetVersion: '1',
);
const _changedContext = DssAssessmentContext(
  susceptibilityCode: 'LOW',
  susceptibilityLabel: 'Low',
  operatingMode: 'DEMONSTRATION',
  areaCode: 'OTHER_TEST_AREA',
  areaName: 'Changed test area',
  intensityCode: 'TEST_RAIN',
  intensityLabel: 'Heavy',
  durationCode: 'TEST_DURATION',
  durationLabel: '6 hours',
  dataStatus: 'DEMONSTRATION',
);

DssStep _step({int position = 1, bool expanded = false}) => DssStep(
  flowCode: 'test-guide',
  flowVersion: 'test-1',
  title: 'Synthetic household check',
  operatingMode: 'DEMONSTRATION',
  dataStatus: 'DEMONSTRATION',
  warning: '',
  source: _source,
  position: position,
  total: 2,
  contentBlocks: expanded
      ? [
          for (var i = 1; i <= 4; i++)
            DssContentBlock(
              id: '$i',
              title: 'Test preparation $i',
              body: 'Synthetic action $i from the API.',
              contentType: 'HOUSEHOLD_ACTION',
              phase: 'BEFORE',
              audience: 'RESIDENT',
              displayOrder: i,
              source: _source,
              sourceLocator: 'Test section $i',
              reviewedOn: '2026-10-09',
              effectiveDate: '2026-10-09',
            ),
          const DssContentBlock(
            id: '5',
            title: 'Test during reference',
            body: 'Synthetic during reference.',
            phase: 'DURING',
            contentType: 'HOUSEHOLD_ACTION',
            audience: 'RESIDENT',
            source: _source,
          ),
        ]
      : const [],
  question: DssQuestion(
    code: position == 1 ? 'support' : 'supplies',
    prompt: position == 1
        ? 'Is a trusted helper assigned?'
        : 'Are supplies ready?',
    explanation: 'Optional test question.',
    options: const [
      DssOption(code: 'yes', label: 'Yes', supportingText: ''),
      DssOption(code: 'no', label: 'No', supportingText: ''),
    ],
  ),
);

class _Repository implements StructuredDssRepository {
  bool expanded = false;
  bool unavailable = false;
  Completer<DssStep>? pendingStart;
  Completer<DssStep>? pendingAnswer;
  final starts = <String>[];
  int answers = 0;

  @override
  Future<DssStep> start(String code, {required String operatingMode}) async {
    starts.add(code);
    if (unavailable) {
      throw StateError('No eligible household flow is available.');
    }
    return pendingStart?.future ?? _step(expanded: expanded);
  }

  @override
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String operatingMode,
    required String optionCode,
  }) async {
    answers++;
    if (pendingAnswer != null) {
      return pendingAnswer!.future;
    }
    if (current.position == 1) return _step(position: 2, expanded: expanded);
    return const DssStep(
      flowCode: 'test-guide',
      flowVersion: 'test-1',
      title: 'Synthetic household check',
      dataStatus: 'DEMONSTRATION',
      operatingMode: 'DEMONSTRATION',
      warning: '',
      position: 2,
      total: 2,
      source: _source,
      outcome: DssOutcome(
        title: 'Synthetic household priority',
        instruction: 'Test personalized instruction from the API.',
        warning: 'Fixture only.',
        source: 'Synthetic test source',
        sourceDetails: _source,
      ),
    );
  }
}

Future<void> _pump(
  WidgetTester tester,
  DssController controller, {
  double width = 390,
  double scale = 1,
  bool settle = true,
  DssAssessmentContext context = _context,
  List<GuidanceItem>? guidance,
}) async {
  await qa.loadVisualQaFonts(tester);
  tester.view.physicalSize = Size(width, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: _captureQa
          ? qa.visualQaTheme().copyWith(
              outlinedButtonTheme: OutlinedButtonThemeData(
                style: OutlinedButton.styleFrom(
                  textStyle: const TextStyle(
                    fontFamily: 'DssVisualQa',
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              textButtonTheme: TextButtonThemeData(
                style: TextButton.styleFrom(
                  textStyle: const TextStyle(
                    fontFamily: 'DssVisualQa',
                    fontSize: 16,
                  ),
                ),
              ),
            )
          : null,
      home: MediaQuery(
        data: MediaQueryData(
          size: Size(width, 844),
          textScaler: TextScaler.linear(scale),
        ),
        child: RepaintBoundary(
          key: const Key('prepare-qa-boundary'),
          child: Scaffold(
            body: PreparednessDashboard(
              controller: controller,
              assessmentContext: context,
              guidance: guidance ?? sampleResult().guidance,
              resources: const ExpansionTile(
                title: Text('Test center resources'),
                children: [Text('Synthetic center details')],
              ),
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

Future<void> _scrollTo(WidgetTester tester, Finder target) async {
  final key = find.byKey(const Key('prepare-dashboard')).evaluate().isNotEmpty
      ? const Key('prepare-dashboard')
      : const Key('dss-flow-view');
  final scrollable = find.descendant(
    of: find.byKey(key),
    matching: find.byType(Scrollable),
  );
  tester.state<ScrollableState>(scrollable).position.jumpTo(0);
  await tester.pump();
  await tester.scrollUntilVisible(
    target,
    200,
    scrollable: scrollable,
    maxScrolls: 70,
  );
  await tester.pumpAndSettle();
}

Future<void> _tap(WidgetTester tester, Finder target) async {
  await _scrollTo(tester, target);
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> _capture(WidgetTester tester, String name) async {
  if (!_captureQa) return;
  final boundary = tester.renderObject<RenderRepaintBoundary>(
    find.byKey(const Key('prepare-qa-boundary')),
  );
  await tester.runAsync(() async {
    final rendered = await boundary.toImage(pixelRatio: 1);
    final bytes = await rendered.toByteData(format: ui.ImageByteFormat.png);
    final directory = Directory('../tmp/prepare-dashboard-qa');
    await directory.create(recursive: true);
    await File('${directory.path}/$name.png')
        .writeAsBytes(bytes!.buffer.asUint8List());
    rendered.dispose();
  });
}

void main() {
  testWidgets(
    'assessment actions appear without household answers or center expansion',
    (tester) async {
      final repository = _Repository();
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await _pump(tester, controller);
      expect(find.byKey(const Key('prepare-priorities')), findsOneWidget);
      expect(find.byKey(const Key('prepare-action-1')), findsOneWidget);
      expect(find.text('Is a trusted helper assigned?'), findsNothing);
      expect(find.text('Synthetic center details'), findsNothing);
      expect(repository.answers, 0);
      expect(controller.answers, isEmpty);
      expect(find.text('Demonstration — pending validation'), findsOneWidget);
      await _capture(tester, 'answer-first-390');
      await _tap(tester, find.byKey(const Key('prepare-tailor-household')));
      expect(find.text('Is a trusted helper assigned?'), findsOneWidget);
      expect(find.text('Test center resources'), findsNothing);
      expect(find.text('Exit and restart guidance'), findsNothing);
      await _capture(tester, 'focused-household-390');
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'closing, remounting and resuming preserve answers; reset is explicit',
    (tester) async {
      final repository = _Repository();
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await _pump(tester, controller);
      await _tap(tester, find.byKey(const Key('prepare-tailor-household')));
      await _tap(tester, find.byKey(const Key('dss-option-yes')));
      await _tap(tester, find.text('Continue'));
      expect(controller.answers, hasLength(1));
      expect(controller.current!.position, 2);
      await _tap(tester, find.byKey(const Key('dss-close-household')));
      expect(controller.answers, hasLength(1));
      await tester.pumpWidget(const SizedBox());
      await _pump(tester, controller);
      expect(repository.starts, ['HIGH']);
      await _tap(tester, find.byKey(const Key('prepare-tailor-household')));
      expect(find.text('Are supplies ready?'), findsOneWidget);
      await _tap(tester, find.text('Back'));
      expect(controller.selectedOptionCode, 'yes');
      await _tap(tester, find.byKey(const Key('dss-reset-answers')));
      expect(controller.answers, isEmpty);
      expect(controller.selectedOptionCode, isNull);
      expect(controller.householdCheckOpen, isTrue);
      expect(controller.assessmentContext, _context);
      expect(repository.starts, ['HIGH', 'HIGH']);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'completed household priority remains separate from susceptibility',
    (tester) async {
      final repository = _Repository();
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await _pump(tester, controller);
      await _tap(tester, find.byKey(const Key('prepare-tailor-household')));
      for (var i = 0; i < 2; i++) {
        await _tap(tester, find.byKey(const Key('dss-option-no')));
        await _tap(tester, find.text('Continue'));
      }
      expect(controller.current!.isOutcome, isTrue);
      await _tap(tester, find.byKey(const Key('dss-close-household')));
      await _scrollTo(tester, find.text('Your household recommendation'));
      expect(find.text('Synthetic household priority'), findsOneWidget);
      expect(controller.susceptibilityCode, 'HIGH');
      expect(controller.assessmentContext, _context);
      expect(repository.answers, 2);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'published actions are capped at three; references and metadata are expandable',
    (tester) async {
      final repository = _Repository()..expanded = true;
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await _pump(tester, controller);
      expect(find.byKey(const Key('prepare-action-3')), findsOneWidget);
      expect(find.text('Test preparation 4'), findsNothing);
      expect(find.text('Synthetic during reference.'), findsNothing);
      await _tap(tester, find.byKey(const Key('prepare-more-actions')));
      await _scrollTo(tester, find.text('Test preparation 4'));
      expect(find.text('Test preparation 4'), findsOneWidget);
      await _tap(
        tester,
        find.byKey(const Key('prepare-reference-HOUSEHOLD_ACTION')),
      );
      await _scrollTo(tester, find.text('Test during reference'));
      expect(find.textContaining('does not indicate a flood'), findsOneWidget);
      await _tap(tester, find.byKey(const Key('prepare-sources-details')));
      await _scrollTo(
        tester,
        find.text('Assessment knowledge version: Test knowledge 1'),
      );
      expect(find.text('Source version: test-1'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'unavailable or loading household flow never blocks assessment guidance',
    (tester) async {
      final repository = _Repository()..pendingStart = Completer<DssStep>();
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await _pump(tester, controller, settle: false);
      expect(find.byKey(const Key('prepare-action-1')), findsOneWidget);
      repository.pendingStart!.completeError(
        StateError('No eligible household flow is available.'),
      );
      await tester.pumpAndSettle();
      await _scrollTo(
        tester,
        find.byKey(const Key('prepare-household-unavailable')),
      );
      expect(controller.answers, isEmpty);
      expect(find.byKey(const Key('prepare-action-1')), findsOneWidget);
      expect(find.text('Is a trusted helper assigned?'), findsNothing);
    },
  );

  testWidgets(
    'no eligible guidance is honest, not filled with invented actions',
    (tester) async {
      final controller = DssController(_Repository()..unavailable = true);
      addTearDown(controller.dispose);
      await _pump(tester, controller, guidance: const []);
      expect(
        find.textContaining('No eligible preparation actions'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('prepare-action-1')), findsNothing);
      expect(controller.susceptibilityCode, 'HIGH');
    },
  );

  testWidgets(
    'scenario changes clear optional answers and reject late prior results',
    (tester) async {
      final repository = _Repository();
      final controller = DssController(repository);
      addTearDown(controller.dispose);
      await _pump(tester, controller);
      await _tap(tester, find.byKey(const Key('prepare-tailor-household')));
      controller.select('yes');
      repository.pendingAnswer = Completer<DssStep>();
      final pending = controller.continueFlow();
      await tester.pump();
      await _pump(tester, controller, context: _changedContext);
      expect(controller.answers, isEmpty);
      expect(controller.householdCheckOpen, isFalse);
      expect(controller.susceptibilityCode, 'LOW');
      repository.pendingAnswer!.complete(_step(position: 2));
      await pending;
      await tester.pumpAndSettle();
      expect(controller.current!.position, 1);
      expect(controller.answers, isEmpty);
      expect(repository.starts, ['HIGH', 'LOW']);
      expect(tester.takeException(), isNull);
    },
  );

  for (final width in [320.0, 360.0]) {
    testWidgets('dashboard and focused check wrap at $width with 2x text', (
      tester,
    ) async {
      final controller = DssController(_Repository()..expanded = true);
      addTearDown(controller.dispose);
      await _pump(tester, controller, width: width, scale: 2);
      await _scrollTo(tester, find.byKey(const Key('prepare-action-1')));
      await _capture(tester, 'answer-first-${width.toInt()}-scaled');
      await _tap(tester, find.byKey(const Key('prepare-tailor-household')));
      await _scrollTo(tester, find.byKey(const Key('dss-option-yes')));
      await _capture(tester, 'household-${width.toInt()}-scaled');
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets(
    'compact center panel has one record per center and only one refresh',
    (tester) async {
      final location = LocationController(
        Day4LocationService(),
        resolver: Day4Resolver(),
      );
      final provider = FakeNearestCenterProvider();
      final controller = NearestCenterController(location, provider: provider);
      addTearDown(() {
        controller.dispose();
        location.dispose();
      });
      location.showPurposeExplanation();
      await location.continueAfterPurposeExplanation();
      location.confirmCandidate();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: NearestCentersSection(
                controller: controller,
                compact: true,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Synthetic Near Center'), findsNothing);
      expect(
        find.text('Nearest: 180 m approximate straight-line distance'),
        findsOneWidget,
      );
      expect(find.text('From your confirmed GPS location'), findsOneWidget);
      await tester.tap(find.text('Nearby centers'));
      await tester.pumpAndSettle();
      expect(find.text('Synthetic Near Center'), findsOneWidget);
      expect(find.byKey(const Key('nearest-centers-refresh')), findsOneWidget);
      expect(find.byType(EvacuationMapStatus), findsNothing);
      expect(provider.calls, 1);
      expect(controller.selectedCenterIdentifier, isNull);
      expect(tester.takeException(), isNull);
    },
  );
}
