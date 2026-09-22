import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/auth/resident_auth_repository.dart';
import 'auth_screens.dart';
import 'session_controller.dart';

class MandatoryLegalScreen extends StatefulWidget {
  const MandatoryLegalScreen({required this.controller, super.key});
  final SessionController controller;
  @override
  State<MandatoryLegalScreen> createState() => _MandatoryLegalScreenState();
}

class _MandatoryLegalScreenState extends State<MandatoryLegalScreen> {
  late Future<List<LegalDocument>> _documents;
  final Set<int> _accepted = {};

  @override
  void initState() {
    super.initState();
    _documents = widget.controller.repository.requiredLegalDocuments();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Review Terms and Privacy')),
    body: FutureBuilder<List<LegalDocument>>(
      future: _documents,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(
            child: CircularProgressIndicator(
              semanticsLabel: 'Loading required legal documents',
            ),
          );
        }
        if (snapshot.hasError) {
          return Center(
            child: FilledButton(
              onPressed: () => setState(
                () => _documents = widget.controller.repository
                    .requiredLegalDocuments(),
              ),
              child: const Text('Retry'),
            ),
          );
        }
        final documents = snapshot.requireData;
        return ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 120),
          children: [
            Text(
              'Required before continuing',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            const Text(
              'Read each current version. FloodSense records the exact version and acceptance time.',
            ),
            const SizedBox(height: 16),
            for (final document in documents) ...[
              _RequiredDocument(document: document),
              CheckboxListTile(
                key: Key('accept-${document.id}'),
                value: _accepted.contains(document.id),
                controlAffinity: ListTileControlAffinity.leading,
                title: Text(
                  'I have reviewed and accept ${document.title} (v${document.version}).',
                ),
                onChanged: (value) => setState(() {
                  if (value ?? false) {
                    _accepted.add(document.id);
                  } else {
                    _accepted.remove(document.id);
                  }
                }),
              ),
            ],
            if (widget.controller.message != null)
              Semantics(
                liveRegion: true,
                child: Text(
                  widget.controller.message!,
                  style: const TextStyle(color: AppColors.error),
                ),
              ),
          ],
        );
      },
    ),
    bottomNavigationBar: SafeArea(
      child: FutureBuilder<List<LegalDocument>>(
        future: _documents,
        builder: (context, snapshot) {
          final documents = snapshot.data ?? const <LegalDocument>[];
          final ready =
              documents.isNotEmpty && _accepted.length == documents.length;
          return Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton(
              key: const Key('accept-legal-button'),
              onPressed: ready && !widget.controller.busy
                  ? () => widget.controller.acceptLegal(
                      documents.map((document) => document.id).toList(),
                    )
                  : null,
              child: const Text('Accept and Continue'),
            ),
          );
        },
      ),
    ),
  );
}

class _RequiredDocument extends StatelessWidget {
  const _RequiredDocument({required this.document});
  final LegalDocument document;
  @override
  Widget build(BuildContext context) => Card(
    child: ExpansionTile(
      title: Text(document.title),
      subtitle: Text('Version ${document.version} • ${document.summary}'),
      children: [
        for (final section in document.sections)
          Semantics(
            button: true,
            child: ExpansionTile(
              title: Text(section.title),
              subtitle: Text(section.summary),
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: SelectableText(section.body),
                ),
              ],
            ),
          ),
      ],
    ),
  );
}

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({required this.controller, super.key});
  final SessionController controller;
  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  late Future<OnboardingContent> _content;
  int _index = 0;

  @override
  void initState() {
    super.initState();
    _content = widget.controller.repository.onboarding();
  }

  void _legal(String type) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => LegalDocumentScreen(
          repository: widget.controller.repository,
          type: type,
          originLabel: 'Onboarding',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Welcome to FloodSense'),
      actions: [
        PopupMenuButton<String>(
          tooltip: 'Open legal documents',
          onSelected: _legal,
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'terms', child: Text('Terms of Use')),
            PopupMenuItem(value: 'privacy', child: Text('Privacy Policy')),
          ],
        ),
      ],
    ),
    body: FutureBuilder<OnboardingContent>(
      future: _content,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(
            child: FilledButton(
              onPressed: () => setState(
                () => _content = widget.controller.repository.onboarding(),
              ),
              child: const Text('Retry'),
            ),
          );
        }
        final content = snapshot.requireData;
        final step = content.steps[_index];
        final warning = _index >= 4;
        return SafeArea(
          child: Column(
            children: [
              LinearProgressIndicator(
                value: (_index + 1) / content.steps.length,
                semanticsLabel:
                    'Onboarding step ${_index + 1} of ${content.steps.length}',
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 620),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Step ${_index + 1} of ${content.steps.length}',
                            style: Theme.of(context).textTheme.labelLarge,
                          ),
                          const SizedBox(height: 20),
                          Icon(
                            _iconFor(_index),
                            size: 72,
                            color: warning ? AppColors.high : AppColors.primary,
                          ),
                          const SizedBox(height: 20),
                          Text(
                            step.title,
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.headlineSmall,
                          ),
                          const SizedBox(height: 14),
                          Text(
                            step.body,
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                          if (warning) ...[
                            const SizedBox(height: 20),
                            const Card(
                              color: AppColors.warningSurface,
                              child: Padding(
                                padding: EdgeInsets.all(16),
                                child: Text(
                                  'Official authorities and emergency services take priority over this research prototype.',
                                ),
                              ),
                            ),
                          ],
                          if (widget.controller.message != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 16),
                              child: Text(
                                widget.controller.message!,
                                style: const TextStyle(color: AppColors.error),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _index == 0
                            ? null
                            : () => setState(() => _index--),
                        child: const Text('Back'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        key: const Key('onboarding-continue'),
                        onPressed: widget.controller.busy
                            ? null
                            : () {
                                if (_index < content.steps.length - 1) {
                                  setState(() => _index++);
                                } else {
                                  widget.controller.acknowledgeOnboarding(
                                    content.version,
                                  );
                                }
                              },
                        child: Text(
                          _index == content.steps.length - 1
                              ? 'Finish'
                              : 'Continue',
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    ),
  );
}

IconData _iconFor(int index) => switch (index) {
  0 => Icons.water_drop_outlined,
  1 => Icons.cloud_outlined,
  2 => Icons.location_on_outlined,
  3 => Icons.map_outlined,
  4 => Icons.alt_route,
  5 => Icons.apartment_outlined,
  _ => Icons.warning_amber_outlined,
};
