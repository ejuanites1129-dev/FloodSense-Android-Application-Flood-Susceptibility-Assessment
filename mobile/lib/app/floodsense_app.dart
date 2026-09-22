import 'package:flutter/material.dart';

import '../data/api/floodsense_api_client.dart';
import '../data/auth/resident_auth_repository.dart';
import '../data/dss/structured_dss_repository.dart';
import '../features/assessment/assessment_screen.dart';
import '../features/auth/auth_screens.dart';
import '../features/auth/session_controller.dart';
import '../features/auth/setup_screens.dart';
import '../features/evacuation/nearest_center_provider.dart';
import '../features/home/resident_shell.dart';
import '../features/location/location_service.dart';
import 'theme/app_theme.dart';

class FloodSenseApp extends StatelessWidget {
  const FloodSenseApp({
    super.key,
    this.api,
    this.authRepository,
    this.dssRepository,
    this.locationService,
    this.nearestCenterProvider,
    this.showBasemap = true,
    this.enableResidentAuthentication,
  });

  final FloodSenseApi? api;
  final ResidentAuthRepository? authRepository;
  final StructuredDssRepository? dssRepository;
  final LocationService? locationService;
  final NearestCenterProvider? nearestCenterProvider;
  final bool showBasemap;
  final bool? enableResidentAuthentication;

  @override
  Widget build(BuildContext context) {
    final activeApi = api ?? FloodSenseApiClient();
    NearestCenterProvider? activeCenterProvider = nearestCenterProvider;
    if (activeCenterProvider == null && activeApi is NearestCenterProvider) {
      activeCenterProvider = activeApi as NearestCenterProvider;
    }
    final authenticationEnabled = enableResidentAuthentication ?? api == null;
    if (!authenticationEnabled) {
      return MaterialApp(
        title: 'FloodSense',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light(),
        home: AssessmentScreen(
          api: activeApi,
          locationService: locationService,
          nearestCenterProvider: activeCenterProvider,
          showBasemap: showBasemap,
        ),
      );
    }
    return _ResidentApplication(
      api: activeApi,
      repository: authRepository ?? HttpResidentAuthRepository(),
      dssRepository: dssRepository,
      locationService: locationService,
      nearestCenterProvider: activeCenterProvider,
      showBasemap: showBasemap,
    );
  }
}

class _ResidentApplication extends StatefulWidget {
  const _ResidentApplication({
    required this.api,
    required this.repository,
    required this.dssRepository,
    required this.locationService,
    required this.nearestCenterProvider,
    required this.showBasemap,
  });
  final FloodSenseApi api;
  final ResidentAuthRepository repository;
  final StructuredDssRepository? dssRepository;
  final LocationService? locationService;
  final NearestCenterProvider? nearestCenterProvider;
  final bool showBasemap;
  @override
  State<_ResidentApplication> createState() => _ResidentApplicationState();
}

class _ResidentApplicationState extends State<_ResidentApplication> {
  late final SessionController _session;
  @override
  void initState() {
    super.initState();
    _session = SessionController(widget.repository)..initialize();
  }

  @override
  void dispose() {
    _session.dispose();
    widget.api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'FloodSense',
    debugShowCheckedModeBanner: false,
    theme: AppTheme.light(),
    home: AnimatedBuilder(
      animation: _session,
      builder: (context, _) => switch (_session.state) {
        ResidentSessionState.initializing => const _SplashScreen(),
        ResidentSessionState.unauthenticated => AuthenticationScreen(
          controller: _session,
        ),
        ResidentSessionState.configurationRequired =>
          _ConfigurationRequiredScreen(session: _session),
        ResidentSessionState.awaitingEmailVerification =>
          EmailVerificationScreen(controller: _session),
        ResidentSessionState.awaitingLegalAcceptance => MandatoryLegalScreen(
          controller: _session,
        ),
        ResidentSessionState.awaitingOnboarding => OnboardingScreen(
          controller: _session,
        ),
        ResidentSessionState.authenticatedReady => ResidentShell(
          session: _session,
          api: widget.api,
          locationService: widget.locationService,
          nearestCenterProvider: widget.nearestCenterProvider,
          dssRepository: widget.dssRepository,
          showBasemap: widget.showBasemap,
        ),
        ResidentSessionState.refreshFailed => _RefreshFailedScreen(
          session: _session,
        ),
      },
    ),
  );
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();
  @override
  Widget build(BuildContext context) => const Scaffold(
    body: SafeArea(
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.water_drop_outlined, size: 68),
            SizedBox(height: 16),
            Text('FloodSense'),
            SizedBox(height: 18),
            CircularProgressIndicator(
              semanticsLabel: 'Restoring secure resident session',
            ),
          ],
        ),
      ),
    ),
  );
}

class _RefreshFailedScreen extends StatelessWidget {
  const _RefreshFailedScreen({required this.session});
  final SessionController session;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.lock_clock_outlined, size: 54),
            const SizedBox(height: 12),
            Text(
              session.message ??
                  'Your remembered session could not be restored.',
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: session.showLogin,
              child: const Text('Return to Login'),
            ),
          ],
        ),
      ),
    ),
  );
}

class _ConfigurationRequiredScreen extends StatelessWidget {
  const _ConfigurationRequiredScreen({required this.session});
  final SessionController session;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Setup review required')),
    body: ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const Icon(Icons.policy_outlined, size: 64),
        const SizedBox(height: 16),
        Text(
          'Resident access is not open yet',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        const Text(
          'An authorized reviewer must publish approved Terms of Use, Privacy '
          'Policy, and onboarding versions. Prototype drafts are not silently '
          'treated as approved policy.',
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 20),
        FilledButton(
          onPressed: session.busy ? null : session.refreshSetup,
          child: const Text('Check Again'),
        ),
        OutlinedButton(
          onPressed: session.busy ? null : session.logout,
          child: const Text('Log out'),
        ),
        if (session.message != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(session.message!),
          ),
      ],
    ),
  );
}
