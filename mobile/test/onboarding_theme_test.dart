import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/auth/resident_auth_repository.dart';
import 'package:floodsense/features/auth/setup_screens.dart';

import 'resident_auth_widget_test.dart' show pumpResidentApp;
import 'resident_test_fakes.dart';

class _RecordingAuthRepository extends FakeResidentAuthRepository {
  List<int>? acceptedIds;
  final acknowledgedVersions = <String>[];

  List<LegalDocument> get draftDocuments => documents
      .map(
        (document) => LegalDocument(
          id: document.id,
          type: document.type,
          version: document.version,
          title: document.title,
          summary: document.summary,
          prototypeDraft: true,
          reviewNotice:
              'Prototype drafts require formal review before production use.',
          sections: document.sections,
        ),
      )
      .toList();

  @override
  Future<List<LegalDocument>> requiredLegalDocuments() async => draftDocuments;

  @override
  Future<SetupStage> acceptLegal(List<int> ids) async {
    acceptedIds = List.of(ids);
    return super.acceptLegal(ids);
  }

  @override
  Future<SetupStage> acknowledgeOnboarding(String version) async {
    acknowledgedVersions.add(version);
    return super.acknowledgeOnboarding(version);
  }
}

void _expectFullScreenBlue(WidgetTester tester, Type screen, Size size) {
  final background = find.byKey(const Key('setup-blue-background'));
  expect(tester.getRect(background), Offset.zero & size);
  final decoration =
      tester.widget<DecoratedBox>(background).decoration as BoxDecoration;
  expect(decoration.gradient, isA<LinearGradient>());
  final scaffold = tester.widget<Scaffold>(
    find.descendant(of: find.byType(screen), matching: find.byType(Scaffold)),
  );
  expect(scaffold.backgroundColor, Colors.transparent);
  if (screen == OnboardingScreen) {
    expect(scaffold.appBar, isNull);
    return;
  }
  final appBar = scaffold.appBar! as AppBar;
  expect(appBar.backgroundColor, Colors.transparent);
  expect(appBar.surfaceTintColor, Colors.transparent);
  expect(appBar.elevation, 0);
  expect(appBar.scrolledUnderElevation, 0);
}

void main() {
  testWidgets('legal review is compact without changing documents or consent', (
    tester,
  ) async {
    final repository = _RecordingAuthRepository()
      ..restoration = testSession(SetupStage.awaitingLegalAcceptance);
    await pumpResidentApp(tester, repository, size: const Size(390, 844));
    _expectFullScreenBlue(tester, MandatoryLegalScreen, const Size(390, 844));
    expect(find.text('Terms & Privacy'), findsOneWidget);
    expect(find.text('Your documents'), findsNothing);
    expect(find.textContaining('Read each current version'), findsNothing);
    expect(find.textContaining('Prototype drafts require'), findsNothing);
    expect(find.text('Not reviewed'), findsNothing);
    expect(find.text('Reviewed'), findsNothing);
    expect(
      find.textContaining('Prototype draft • Version 1'),
      findsNWidgets(2),
    );
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('accept-legal-button')))
          .onPressed,
      isNull,
    );
    await tester.tap(find.text('Privacy Policy'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Foreground GPS'));
    await tester.tap(find.text('Foreground GPS'));
    await tester.pumpAndSettle();
    expect(
      find.text('Precise coordinates are not account preferences.'),
      findsOneWidget,
    );
    expect(repository.acceptedIds, isNull);
    await tester.tap(find.byKey(const Key('accept-all-legal')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('accept-legal-button')));
    await tester.pumpAndSettle();
    expect(repository.acceptedIds, [11, 12]);
    expect(find.text('STEP 1 OF 7'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'all seven tutorial steps share blue backdrop and explicit finish',
    (tester) async {
      final repository = _RecordingAuthRepository()
        ..restoration = testSession(SetupStage.awaitingOnboarding);
      final content = await repository.onboarding();
      await pumpResidentApp(tester, repository, size: const Size(390, 844));
      for (var index = 0; index < content.steps.length; index++) {
        _expectFullScreenBlue(tester, OnboardingScreen, const Size(390, 844));
        expect(find.text('Welcome to FloodSense'), findsNothing);
        expect(find.byType(PopupMenuButton<String>), findsNothing);
        expect(find.byTooltip('Open legal documents'), findsNothing);
        expect(find.text('Terms of Use'), findsNothing);
        expect(find.text('Privacy Policy'), findsNothing);
        expect(find.text('STEP ${index + 1} OF 7'), findsOneWidget);
        expect(find.text(content.steps[index].title), findsOneWidget);
        expect(find.text(content.steps[index].body), findsOneWidget);
        expect(repository.acknowledgedVersions, isEmpty);
        final progress = tester.widget<LinearProgressIndicator>(
          find.byType(LinearProgressIndicator),
        );
        final back = find.byKey(const Key('onboarding-back'));
        final next = find.byKey(const Key('onboarding-continue'));
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
        expect(progress.value, (index + 1) / 7);
        final progressRect = tester.getRect(
          find.byKey(const Key('onboarding-progress')),
        );
        expect(progressRect.top, 0);
        expect(progressRect.left, 0);
        expect(progressRect.width, 390);
        final viewportRect = tester.getRect(
          find.byKey(const Key('onboarding-content-viewport')),
        );
        final stepRect = tester.getRect(
          find.byKey(const Key('onboarding-step-content')),
        );
        expect(stepRect.center.dx, closeTo(viewportRect.center.dx, 0.001));
        expect(stepRect.center.dy, closeTo(viewportRect.center.dy, 0.001));
        expect(stepRect.height, lessThanOrEqualTo(viewportRect.height));
        if (index >= 4) {
          expect(
            find.textContaining('Official authorities and emergency services'),
            findsOneWidget,
          );
        }
        await tester.tap(find.byKey(const Key('onboarding-continue')));
        await tester.pumpAndSettle();
      }
      expect(repository.acknowledgedVersions, ['1']);
      expect(
        find.byKey(const Key('resident-bottom-navigation')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('Help tutorial retains step Back and exits from the first step', (
    tester,
  ) async {
    final repository = _RecordingAuthRepository()
      ..restoration = testSession(SetupStage.authenticatedReady);
    await pumpResidentApp(tester, repository, size: const Size(412, 915));
    await tester.tap(find.byIcon(Icons.person_outline));
    await tester.pumpAndSettle();
    final help = find.text('Help & onboarding');
    await tester.scrollUntilVisible(
      help,
      400,
      scrollable: find.descendant(
        of: find.byKey(const Key('profile-secondary-options')),
        matching: find.byType(Scrollable),
      ),
    );
    await tester.drag(
      find.byKey(const Key('profile-secondary-options')),
      const Offset(0, -180),
    );
    await tester.pumpAndSettle();
    await tester.tap(help);
    await tester.pumpAndSettle();
    _expectFullScreenBlue(tester, OnboardingScreen, const Size(412, 915));
    expect(find.byTooltip('Open legal documents'), findsNothing);
    await tester.tap(find.byKey(const Key('onboarding-continue')));
    await tester.pumpAndSettle();
    expect(find.text('STEP 2 OF 7'), findsOneWidget);
    await tester.tap(find.byKey(const Key('onboarding-back')));
    await tester.pumpAndSettle();
    expect(find.text('STEP 1 OF 7'), findsOneWidget);
    await tester.tap(find.byKey(const Key('onboarding-back')));
    await tester.pumpAndSettle();
    expect(find.text('Help & onboarding'), findsOneWidget);
    expect(repository.acknowledgedVersions, isEmpty);
    expect(tester.takeException(), isNull);
  });

  testWidgets('short-screen tutorial scrolls without hiding bottom controls', (
    tester,
  ) async {
    final repository = _RecordingAuthRepository()
      ..restoration = testSession(SetupStage.awaitingOnboarding);
    await pumpResidentApp(
      tester,
      repository,
      size: const Size(320, 480),
      textScale: 2,
    );
    expect(
      tester
          .widget<OutlinedButton>(find.byKey(const Key('onboarding-back')))
          .onPressed,
      isNull,
    );
    for (var index = 0; index < 6; index++) {
      await tester.tap(find.byKey(const Key('onboarding-continue')));
      await tester.pumpAndSettle();
    }
    final scrollable = tester.state<ScrollableState>(
      find.descendant(
        of: find.byType(OnboardingScreen),
        matching: find.byType(Scrollable),
      ),
    );
    expect(scrollable.position.maxScrollExtent, greaterThan(0));
    await tester.ensureVisible(
      find.textContaining('Official authorities and emergency services'),
    );
    await tester.pumpAndSettle();
    final finish = find.byKey(const Key('onboarding-continue'));
    expect(
      tester.getSize(find.byKey(const Key('onboarding-back'))),
      tester.getSize(finish),
    );
    expect(tester.getRect(finish).bottom, lessThanOrEqualTo(480));
    expect(finish.hitTestable(), findsOneWidget);
    await tester.tap(finish);
    await tester.pumpAndSettle();
    expect(repository.acknowledgedVersions, ['1']);
    expect(tester.takeException(), isNull);
  });

  for (final stage in [
    SetupStage.awaitingLegalAcceptance,
    SetupStage.awaitingOnboarding,
  ]) {
    testWidgets('$stage remains usable on a narrow phone with larger text', (
      tester,
    ) async {
      final repository = _RecordingAuthRepository()
        ..restoration = testSession(stage);
      await pumpResidentApp(
        tester,
        repository,
        size: const Size(320, 640),
        textScale: 1.7,
      );
      if (stage == SetupStage.awaitingOnboarding) {
        for (var index = 0; index < 6; index++) {
          await tester.tap(find.byKey(const Key('onboarding-continue')));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
        }
        await tester.tap(find.text('Back'));
        await tester.pumpAndSettle();
        expect(find.text('STEP 6 OF 7'), findsOneWidget);
      } else {
        final scrollable = find.descendant(
          of: find.byType(MandatoryLegalScreen),
          matching: find.byType(Scrollable),
        );
        await tester.scrollUntilVisible(
          find.text('Privacy Policy'),
          140,
          scrollable: scrollable,
        );
        await tester.tap(find.text('Privacy Policy'));
        await tester.pumpAndSettle();
        await tester.scrollUntilVisible(
          find.text('Foreground GPS'),
          100,
          scrollable: scrollable,
        );
        expect(find.byKey(const Key('accept-all-legal')), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
    });
  }
}
