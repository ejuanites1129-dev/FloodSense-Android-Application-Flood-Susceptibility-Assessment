import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/data/auth/resident_auth_repository.dart';

import 'resident_test_fakes.dart';
import 'test_data.dart';

Future<void> pumpResidentApp(
  WidgetTester tester,
  FakeResidentAuthRepository repository, {
  FakeFloodSenseApi? api,
  Size? size,
  double textScale = 1,
}) async {
  if (size != null) {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }
  await tester.pumpWidget(
    MediaQuery(
      data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
      child: FloodSenseApp(
        api: api ?? FakeFloodSenseApi(),
        authRepository: repository,
        enableResidentAuthentication: true,
        showBasemap: false,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'resident login validates fields and toggles password visibility',
    (tester) async {
      final repository = FakeResidentAuthRepository();
      await pumpResidentApp(tester, repository);
      await tester.tap(find.byKey(const Key('sign-in-button')));
      await tester.pump();
      expect(find.text('Enter your username or email.'), findsOneWidget);
      expect(find.text('Enter your password.'), findsOneWidget);
      EditableText field = tester.widget(
        find.descendant(
          of: find.byKey(const Key('login-password')),
          matching: find.byType(EditableText),
        ),
      );
      expect(field.obscureText, isTrue);
      await tester.tap(find.byKey(const Key('login-password-visibility')));
      await tester.pump();
      field = tester.widget(
        find.descendant(
          of: find.byKey(const Key('login-password')),
          matching: find.byType(EditableText),
        ),
      );
      expect(field.obscureText, isFalse);
    },
  );

  testWidgets('Remember Me selection is passed to session foundation', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository();
    await pumpResidentApp(tester, repository);
    await tester.enterText(
      find.byKey(const Key('login-identifier')),
      'resident',
    );
    await tester.enterText(find.byKey(const Key('login-password')), 'password');
    await tester.tap(find.byKey(const Key('remember-me')));
    await tester.tap(find.byKey(const Key('sign-in-button')));
    await tester.pumpAndSettle();
    expect(repository.loginRememberMe, isTrue);
    expect(find.byKey(const Key('resident-bottom-navigation')), findsOneWidget);
    expect(find.byKey(const Key('resident-hybrid-map')), findsOneWidget);
  });

  testWidgets(
    'registration retains non-password values after full legal page',
    (tester) async {
      final repository = FakeResidentAuthRepository();
      await pumpResidentApp(tester, repository);
      await tester.ensureVisible(find.text('Create Account'));
      await tester.tap(find.text('Create Account'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('register-username')),
        'resident.one',
      );
      final terms = find.text('Terms of Use');
      await tester.ensureVisible(terms);
      await tester.tap(terms);
      await tester.pumpAndSettle();
      expect(find.text('Scenario limitations'), findsOneWidget);
      await tester.tap(find.text('Back to Registration'));
      await tester.pumpAndSettle();
      final field = tester.widget<TextFormField>(
        find.byKey(const Key('register-username')),
      );
      expect(field.controller!.text, 'resident.one');
      final privacy = find.text('Privacy Policy');
      await tester.ensureVisible(privacy);
      await tester.tap(privacy);
      await tester.pumpAndSettle();
      expect(find.text('Foreground GPS'), findsOneWidget);
    },
  );

  testWidgets('registration validates fields and toggles password visibility', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository();
    await pumpResidentApp(tester, repository);
    await tester.ensureVisible(find.text('Create Account'));
    await tester.tap(find.text('Create Account'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('create-account-button')));
    await tester.pump();
    expect(find.textContaining('beginning with a letter'), findsOneWidget);
    expect(find.text('Enter a valid email address.'), findsOneWidget);
    expect(find.text('Use at least 8 characters.'), findsOneWidget);
    expect(find.text('Confirm your password.'), findsOneWidget);
    EditableText field = tester.widget(
      find.descendant(
        of: find.byKey(const Key('register-password')),
        matching: find.byType(EditableText),
      ),
    );
    expect(field.obscureText, isTrue);
    await tester.tap(find.byKey(const Key('register-password-visibility')));
    await tester.pump();
    field = tester.widget(
      find.descendant(
        of: find.byKey(const Key('register-password')),
        matching: find.byType(EditableText),
      ),
    );
    expect(field.obscureText, isFalse);
  });

  testWidgets('new Google resident completes username from Registration', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository()
      ..requireGoogleUsername = true;
    await pumpResidentApp(tester, repository);
    await tester.ensureVisible(find.text('Create Account'));
    await tester.tap(find.text('Create Account'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Continue with Google'));
    await tester.pumpAndSettle();
    expect(find.text('Choose a resident username'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('google-resident-username')),
      'google.resident',
    );
    await tester.tap(find.text('Continue with Google'));
    await tester.pumpAndSettle();
    expect(repository.googleUsername, 'google.resident');
    expect(find.byKey(const Key('resident-bottom-navigation')), findsOneWidget);
  });

  testWidgets('forgot password gives non-enumerating confirmation', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository();
    await pumpResidentApp(tester, repository);
    await tester.tap(find.text('Forgot Password?'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('forgot-email')),
      'anyone@example.com',
    );
    await tester.tap(find.text('Send reset instructions'));
    await tester.pumpAndSettle();
    expect(repository.resetRequested, isTrue);
    expect(find.textContaining('If eligible'), findsOneWidget);
  });

  testWidgets('Google cancellation and missing configuration are graceful', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository()..googleSession = null;
    await pumpResidentApp(tester, repository);
    await tester.tap(find.byKey(const Key('google-sign-in')));
    await tester.pumpAndSettle();
    expect(find.text('Google sign-in was cancelled.'), findsOneWidget);

    repository.googleError = const ResidentAuthException(
      'Google sign-in is not configured for this build.',
      code: 'google_not_configured',
    );
    await tester.tap(find.byKey(const Key('google-sign-in')));
    await tester.pumpAndSettle();
    expect(find.textContaining('not configured'), findsOneWidget);
  });

  testWidgets('secure restoration reaches Home and logout returns to Login', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository()
      ..restoration = testSession(SetupStage.authenticatedReady);
    await pumpResidentApp(tester, repository);
    expect(find.byKey(const Key('resident-hybrid-map')), findsOneWidget);
    await tester.tap(find.byIcon(Icons.person_outline));
    await tester.pumpAndSettle();
    expect(find.text('Verified email address'), findsOneWidget);
    final logout = find.byKey(const Key('profile-logout'));
    await tester.scrollUntilVisible(
      logout,
      500,
      scrollable: find.descendant(
        of: find.byKey(const Key('profile-secondary-options')),
        matching: find.byType(Scrollable),
      ),
    );
    await tester.tap(logout);
    await tester.pumpAndSettle();
    expect(repository.logoutCalled, isTrue);
    expect(find.text('Resident sign in'), findsOneWidget);
  });

  testWidgets('Account preferences save without running an assessment', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository()
      ..restoration = testSession(SetupStage.authenticatedReady);
    final api = FakeFloodSenseApi();
    await pumpResidentApp(tester, repository, api: api);
    await tester.tap(find.byIcon(Icons.person_outline));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('profile-preferences')));
    await tester.pumpAndSettle();
    expect(find.textContaining('never store exact GPS'), findsOneWidget);
    await tester.tap(find.text('High contrast'));
    await tester.tap(find.text('Save Preferences'));
    await tester.pumpAndSettle();
    expect(repository.preferencesSaved, isTrue);
    expect(api.evaluateCalls, 0);
    expect(
      find.text('Preferences saved. No assessment was run.'),
      findsOneWidget,
    );
  });

  testWidgets('resident schedules deletion and is signed out', (tester) async {
    final repository = FakeResidentAuthRepository()
      ..restoration = testSession(SetupStage.authenticatedReady);
    await pumpResidentApp(tester, repository);
    await tester.tap(find.byIcon(Icons.person_outline));
    await tester.pumpAndSettle();
    final deleteAccount = find.text('Delete account');
    await tester.scrollUntilVisible(
      deleteAccount,
      400,
      scrollable: find.descendant(
        of: find.byKey(const Key('profile-secondary-options')),
        matching: find.byType(Scrollable),
      ),
    );
    await tester.tap(deleteAccount);
    await tester.pumpAndSettle();
    expect(find.textContaining('30 days'), findsOneWidget);
    await tester.tap(find.text('Delete my account'));
    await tester.pumpAndSettle();
    expect(repository.deletionScheduled, isTrue);
    expect(repository.logoutCalled, isTrue);
    expect(find.text('Resident sign in'), findsOneWidget);
  });

  testWidgets(
    'mandatory legal consent gates onboarding and accordions expand',
    (tester) async {
      final repository = FakeResidentAuthRepository()
        ..restoration = testSession(SetupStage.awaitingLegalAcceptance);
      await pumpResidentApp(tester, repository);
      FilledButton button = tester.widget(
        find.byKey(const Key('accept-legal-button')),
      );
      expect(button.onPressed, isNull);
      await tester.tap(find.text('Terms of Use'));
      await tester.pumpAndSettle();
      final scenario = find.text('Scenario limitations');
      await tester.ensureVisible(scenario);
      await tester.drag(find.byType(ListView), const Offset(0, -180));
      await tester.pumpAndSettle();
      await tester.tap(scenario);
      await tester.pumpAndSettle();
      expect(find.textContaining('not an official warning'), findsOneWidget);
      expect(find.byType(CheckboxListTile), findsOneWidget);
      await tester.tap(find.byKey(const Key('accept-all-legal')));
      await tester.pump();
      button = tester.widget(find.byKey(const Key('accept-legal-button')));
      expect(button.onPressed, isNotNull);
      await tester.tap(find.byKey(const Key('accept-legal-button')));
      await tester.pumpAndSettle();
      expect(find.text('What FloodSense does'), findsOneWidget);
    },
  );

  testWidgets('onboarding uses explicit back and continue without timers', (
    tester,
  ) async {
    final repository = FakeResidentAuthRepository()
      ..restoration = testSession(SetupStage.awaitingOnboarding);
    await pumpResidentApp(
      tester,
      repository,
      size: const Size(320, 640),
      textScale: 1.4,
    );
    expect(find.text('STEP 1 OF 7'), findsOneWidget);
    await tester.tap(find.byKey(const Key('onboarding-continue')));
    await tester.pumpAndSettle();
    expect(find.text('STEP 2 OF 7'), findsOneWidget);
    await tester.tap(find.text('Back'));
    await tester.pumpAndSettle();
    expect(find.text('STEP 1 OF 7'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
