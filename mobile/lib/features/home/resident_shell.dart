import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/api/floodsense_api_client.dart';
import '../../data/auth/resident_auth_repository.dart';
import '../../data/dss/structured_dss_repository.dart';
import '../../data/models/geographic_area.dart';
import '../../data/models/scenario_option.dart';
import '../assessment/multi_step_assessment_screen.dart';
import '../auth/auth_screens.dart';
import '../auth/session_controller.dart';
import '../auth/setup_screens.dart';
import '../evacuation/nearest_center_provider.dart';
import '../location/location_service.dart';

class ResidentShell extends StatefulWidget {
  const ResidentShell({
    required this.session,
    required this.api,
    this.locationService,
    this.nearestCenterProvider,
    this.dssRepository,
    this.showBasemap = true,
    super.key,
  });
  final SessionController session;
  final FloodSenseApi api;
  final LocationService? locationService;
  final NearestCenterProvider? nearestCenterProvider;
  final StructuredDssRepository? dssRepository;
  final bool showBasemap;
  @override
  State<ResidentShell> createState() => _ResidentShellState();
}

class _ResidentShellState extends State<ResidentShell> {
  int _index = 0;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: IndexedStack(
      index: _index,
      children: [
        HomeScreen(
          username: widget.session.user?.username,
          onAssess: () => setState(() => _index = 1),
        ),
        MultiStepAssessmentScreen(
          api: widget.api,
          locationService: widget.locationService,
          nearestCenterProvider: widget.nearestCenterProvider,
          dssRepository: widget.dssRepository,
          showBasemap: widget.showBasemap,
        ),
        AccountScreen(session: widget.session, api: widget.api),
      ],
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: _index,
      onDestinationSelected: (value) => setState(() => _index = value),
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.home_outlined),
          selectedIcon: Icon(Icons.home),
          label: 'Home',
        ),
        NavigationDestination(
          icon: Icon(Icons.fact_check_outlined),
          selectedIcon: Icon(Icons.fact_check),
          label: 'Assess',
        ),
        NavigationDestination(
          icon: Icon(Icons.person_outline),
          selectedIcon: Icon(Icons.person),
          label: 'Account',
        ),
      ],
    ),
  );
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.username, required this.onAssess, super.key});
  final String? username;
  final VoidCallback onAssess;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('FloodSense')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          'Hello${username == null ? '' : ', $username'}',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 8),
        const Text(
          'Explore a hypothetical rainfall scenario and review deterministic preparedness guidance.',
        ),
        const SizedBox(height: 20),
        const Card(
          color: AppColors.warningSurface,
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'FloodSense is a scenario-based research prototype. It is not live monitoring, an official forecast, an alert, or an evacuation order.',
            ),
          ),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: onAssess,
          icon: const Icon(Icons.play_arrow),
          label: const Text('Start an Assessment'),
        ),
        const SizedBox(height: 20),
        const ListTile(
          leading: Icon(Icons.touch_app_outlined),
          title: Text('You control every step'),
          subtitle: Text(
            'No timers, automatic reassessment, or background location tracking.',
          ),
        ),
        const ListTile(
          leading: Icon(Icons.location_on_outlined),
          title: Text('Foreground location only'),
          subtitle: Text(
            'GPS is optional and requested only after your action. Manual selection remains available.',
          ),
        ),
        const ListTile(
          leading: Icon(Icons.campaign_outlined),
          title: Text('Follow official information'),
          subtitle: Text(
            'Use PAGASA, MGB, Bacoor CDRRMO/LGU, barangay officials, and emergency services.',
          ),
        ),
      ],
    ),
  );
}

class AccountScreen extends StatelessWidget {
  const AccountScreen({required this.session, required this.api, super.key});
  final SessionController session;
  final FloodSenseApi api;

  Future<String?> _password(BuildContext context, String title) async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Current password'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Continue'),
          ),
        ],
      ),
    );
    controller.dispose();
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final user = session.user!;
    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ListTile(
            leading: const Icon(Icons.alternate_email),
            title: const Text('Username'),
            subtitle: Text(user.username ?? 'Not set'),
            trailing: IconButton(
              icon: const Icon(Icons.edit),
              tooltip: 'Edit username',
              onPressed: () => _editUsername(context),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.verified_user_outlined),
            title: const Text('Verified email address'),
            subtitle: Text(user.email),
            trailing: Icon(
              user.emailVerified ? Icons.verified : Icons.warning_amber,
            ),
          ),
          ListTile(
            leading: const Icon(Icons.tune),
            title: const Text('Preferences'),
            subtitle: const Text(
              'Home barangay, scenario defaults, and accessibility',
            ),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) =>
                    PreferencesScreen(repository: session.repository, api: api),
              ),
            ),
          ),
          if (user.passwordLoginAvailable)
            ListTile(
              leading: const Icon(Icons.password),
              title: const Text('Change password'),
              onTap: () => _changePassword(context),
            ),
          if (user.linkedProviders.contains('GOOGLE'))
            ListTile(
              leading: const Icon(Icons.link_off),
              title: const Text('Unlink Google'),
              subtitle: const Text('Password reauthentication required'),
              onTap: () async {
                final password = await _password(context, 'Unlink Google');
                if (password != null) await session.unlinkGoogle(password);
              },
            )
          else if (user.passwordLoginAvailable)
            ListTile(
              leading: const Icon(Icons.add_link),
              title: const Text('Link Google'),
              subtitle: const Text(
                'Password and Google reauthentication required',
              ),
              onTap: () async {
                final password = await _password(context, 'Link Google');
                if (password != null) await session.linkGoogle(password);
              },
            ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.description_outlined),
            title: const Text('Terms of Use'),
            onTap: () => _legal(context, 'terms'),
          ),
          ListTile(
            leading: const Icon(Icons.privacy_tip_outlined),
            title: const Text('Privacy Policy'),
            onTap: () => _legal(context, 'privacy'),
          ),
          ListTile(
            leading: const Icon(Icons.help_outline),
            title: const Text('Reopen onboarding and help'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => OnboardingScreen(controller: session),
              ),
            ),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.delete_outline),
            title: const Text('Request account deletion'),
            subtitle: const Text('Records a request for authorized review'),
            onTap: () => _requestDeletion(context),
          ),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Log out'),
            onTap: session.busy ? null : session.logout,
          ),
          if (session.message != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                session.message!,
                style: const TextStyle(color: AppColors.error),
              ),
            ),
        ],
      ),
    );
  }

  void _legal(BuildContext context, String type) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => LegalDocumentScreen(
        repository: session.repository,
        type: type,
        originLabel: 'Account',
      ),
    ),
  );

  Future<void> _editUsername(BuildContext context) async {
    final input = TextEditingController(text: session.user?.username ?? '');
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit username'),
        content: TextField(
          controller: input,
          decoration: const InputDecoration(labelText: 'Username'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    input.dispose();
    if (value != null) await session.updateUsername(value);
  }

  Future<void> _changePassword(BuildContext context) async {
    final current = TextEditingController();
    final replacement = TextEditingController();
    final values = await showDialog<List<String>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Change password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: current,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Current password'),
            ),
            TextField(
              controller: replacement,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'New password'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, [current.text, replacement.text]),
            child: const Text('Change'),
          ),
        ],
      ),
    );
    current.dispose();
    replacement.dispose();
    if (values != null) {
      try {
        await session.repository.changePassword(values[0], values[1]);
      } on ResidentAuthException catch (error) {
        session.message = error.message;
      }
    }
  }

  Future<void> _requestDeletion(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Request account deletion?'),
        content: const Text(
          'This records a request for authorized review. It does not immediately erase records subject to an approved retention policy.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Request deletion'),
          ),
        ],
      ),
    );
    if (confirmed ?? false) await session.repository.requestDeletion();
  }
}

class PreferencesScreen extends StatefulWidget {
  const PreferencesScreen({
    required this.repository,
    required this.api,
    super.key,
  });
  final ResidentAuthRepository repository;
  final FloodSenseApi api;
  @override
  State<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends State<PreferencesScreen> {
  List<GeographicArea> _barangays = const [];
  List<ScenarioOption> _intensities = const [];
  List<ScenarioOption> _durations = const [];
  int? _barangayId;
  int? _intensityId;
  int? _durationId;
  bool _highContrast = false;
  bool _reduceMotion = false;
  bool _loading = true;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final values = await Future.wait([
        widget.repository.preferences(),
        widget.api.fetchAssessmentOptions(),
        widget.api.fetchReferenceBoundaries(),
      ]);
      final preferences = values[0] as Map<String, dynamic>;
      final options = values[1] as AssessmentOptions;
      _barangays = (values[2] as List<GeographicArea>)
          .where((area) => area.areaType == 'BARANGAY')
          .toList();
      _intensities = options.intensityOptions;
      _durations = options.durationOptions;
      _barangayId = (preferences['home_barangay'] as Map?)?['id'] as int?;
      _intensityId =
          (preferences['default_rainfall_intensity'] as Map?)?['id'] as int?;
      _durationId =
          (preferences['default_rainfall_duration'] as Map?)?['id'] as int?;
      _highContrast = preferences['high_contrast'] as bool? ?? false;
      _reduceMotion = preferences['reduce_motion'] as bool? ?? false;
    } catch (error) {
      _message = '$error';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Preferences')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Text(
                'Preferences never store exact GPS coordinates and never run an assessment automatically.',
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<int?>(
                key: ValueKey('barangay-$_barangayId'),
                initialValue: _barangays.any((item) => item.id == _barangayId)
                    ? _barangayId
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Home barangay (optional)',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: null,
                    child: Text('No default'),
                  ),
                  ..._barangays.map(
                    (item) => DropdownMenuItem(
                      value: item.id,
                      child: Text(item.name),
                    ),
                  ),
                ],
                onChanged: (value) => setState(() => _barangayId = value),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<int?>(
                key: ValueKey('intensity-$_intensityId'),
                initialValue:
                    _intensities.any((item) => item.id == _intensityId)
                    ? _intensityId
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Default hypothetical intensity',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: null,
                    child: Text('No default'),
                  ),
                  ..._intensities.map(
                    (item) => DropdownMenuItem(
                      value: item.id,
                      child: Text(item.label),
                    ),
                  ),
                ],
                onChanged: (value) => setState(() => _intensityId = value),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<int?>(
                key: ValueKey('duration-$_durationId'),
                initialValue: _durations.any((item) => item.id == _durationId)
                    ? _durationId
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Default hypothetical duration',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: null,
                    child: Text('No default'),
                  ),
                  ..._durations.map(
                    (item) => DropdownMenuItem(
                      value: item.id,
                      child: Text(item.label),
                    ),
                  ),
                ],
                onChanged: (value) => setState(() => _durationId = value),
              ),
              SwitchListTile(
                value: _highContrast,
                onChanged: (value) => setState(() => _highContrast = value),
                title: const Text('High contrast'),
              ),
              SwitchListTile(
                value: _reduceMotion,
                onChanged: (value) => setState(() => _reduceMotion = value),
                title: const Text('Reduce motion'),
              ),
              FilledButton(
                onPressed: _save,
                child: const Text('Save Preferences'),
              ),
              if (_message != null)
                Semantics(liveRegion: true, child: Text(_message!)),
            ],
          ),
  );

  Future<void> _save() async {
    try {
      await widget.repository.updatePreferences({
        'home_barangay_id': _barangayId,
        'default_rainfall_intensity_id': _intensityId,
        'default_rainfall_duration_id': _durationId,
        'high_contrast': _highContrast,
        'reduce_motion': _reduceMotion,
      });
      _message = 'Preferences saved. No assessment was run.';
    } on ResidentAuthException catch (error) {
      _message = error.message;
    }
    if (mounted) setState(() {});
  }
}
