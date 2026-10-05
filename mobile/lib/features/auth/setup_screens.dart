import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/theme/app_colors.dart';
import '../../data/auth/resident_auth_repository.dart';
import 'session_controller.dart';

class MandatoryLegalScreen extends StatefulWidget {
  const MandatoryLegalScreen({required this.controller, super.key});
  final SessionController controller;
  @override
  State<MandatoryLegalScreen> createState() => _MandatoryLegalScreenState();
}

class _MandatoryLegalScreenState extends State<MandatoryLegalScreen> {
  late Future<List<LegalDocument>> _documents;
  bool _acceptedAll = false;

  @override
  void initState() {
    super.initState();
    _documents = widget.controller.repository.requiredLegalDocuments();
  }

  @override
  Widget build(BuildContext context) => _SetupBackdrop(
    child: Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('Terms & Privacy'),
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        systemOverlayStyle: _setupOverlayStyle,
      ),
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
              const _LegalReviewHero(),
              const SizedBox(height: 22),
              for (final document in documents)
                _RequiredDocument(document: document),
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
            final ready = documents.isNotEmpty && _acceptedAll;
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CheckboxListTile(
                    key: const Key('accept-all-legal'),
                    contentPadding: EdgeInsets.zero,
                    value: _acceptedAll,
                    controlAffinity: ListTileControlAffinity.leading,
                    title: const Text(
                      'I have read and accept the Terms of Use and Privacy Policy.',
                    ),
                    onChanged: documents.isEmpty
                        ? null
                        : (value) =>
                              setState(() => _acceptedAll = value ?? false),
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      key: const Key('accept-legal-button'),
                      onPressed: ready && !widget.controller.busy
                          ? () => widget.controller.acceptLegal(
                              documents.map((document) => document.id).toList(),
                            )
                          : null,
                      child: const Text('Accept and Continue'),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    ),
  );
}

final _setupOverlayStyle = SystemUiOverlayStyle.dark.copyWith(
  statusBarColor: Colors.transparent,
  systemNavigationBarColor: const Color(0xFFE1F4FC),
  systemNavigationBarIconBrightness: Brightness.dark,
);

// Paint behind the entire scaffold so the header and bottom controls share
// the same blue glow as the content, rather than separate white surfaces.
class _SetupBackdrop extends StatelessWidget {
  const _SetupBackdrop({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    key: const Key('setup-blue-background'),
    decoration: const BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xFFF0FAFF), Color(0xFFDCF3FD), Color(0xFFE6F9FA)],
      ),
    ),
    child: DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(-0.8, 0.3),
          radius: 1.2,
          colors: [Color(0x5579D3FF), Color(0x0079D3FF)],
        ),
      ),
      child: child,
    ),
  );
}

class _LegalReviewHero extends StatelessWidget {
  const _LegalReviewHero();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 8, 4, 0),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: const BoxDecoration(
            color: Color(0xFFD2EFFB),
            shape: BoxShape.circle,
          ),
          child: const Icon(
            Icons.policy_outlined,
            color: AppColors.primary,
            size: 34,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          'Know what you’re agreeing to',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        const Text('Review both documents below before continuing.'),
      ],
    ),
  );
}

class _RequiredDocument extends StatelessWidget {
  const _RequiredDocument({required this.document});
  final LegalDocument document;
  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 14),
    clipBehavior: Clip.antiAlias,
    child: ExpansionTile(
      leading: Icon(
        document.type.toUpperCase() == 'PRIVACY'
            ? Icons.privacy_tip_outlined
            : Icons.gavel_outlined,
        color: AppColors.primary,
      ),
      title: Text(
        document.title,
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
      subtitle: Text(
        '${document.prototypeDraft ? 'Prototype draft • ' : ''}'
        'Version ${document.version} • ${document.summary}',
      ),
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

  @override
  Widget build(BuildContext context) => AnnotatedRegion<SystemUiOverlayStyle>(
    value: _setupOverlayStyle,
    child: _SetupBackdrop(
      child: Scaffold(
        backgroundColor: Colors.transparent,
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
                    key: const Key('onboarding-progress'),
                    backgroundColor: AppColors.primary.withValues(alpha: 0.12),
                    value: (_index + 1) / content.steps.length,
                    semanticsLabel:
                        'Onboarding step ${_index + 1} of ${content.steps.length}',
                  ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: LayoutBuilder(
                        key: const Key('onboarding-content-viewport'),
                        builder: (context, constraints) =>
                            SingleChildScrollView(
                              child: ConstrainedBox(
                                constraints: BoxConstraints(
                                  minHeight: constraints.maxHeight,
                                ),
                                child: Center(
                                  child: ConstrainedBox(
                                    constraints: const BoxConstraints(
                                      maxWidth: 620,
                                    ),
                                    child: AnimatedSwitcher(
                                      duration: const Duration(
                                        milliseconds: 320,
                                      ),
                                      transitionBuilder: (child, animation) =>
                                          FadeTransition(
                                            opacity: animation,
                                            child: SlideTransition(
                                              position: Tween<Offset>(
                                                begin: const Offset(0.08, 0),
                                                end: Offset.zero,
                                              ).animate(animation),
                                              child: child,
                                            ),
                                          ),
                                      child: _OnboardingStep(
                                        key: ValueKey(_index),
                                        stepNumber: _index + 1,
                                        stepCount: content.steps.length,
                                        title: step.title,
                                        body: step.body,
                                        icon: _iconFor(_index),
                                        warning: warning,
                                        message: widget.controller.message,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: IntrinsicHeight(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              key: const Key('onboarding-back'),
                              onPressed:
                                  _index == 0 && !Navigator.canPop(context)
                                  ? null
                                  : () {
                                      if (_index > 0) {
                                        setState(() => _index--);
                                      } else {
                                        Navigator.pop(context);
                                      }
                                    },
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
                  ),
                ],
              ),
            );
          },
        ),
      ),
    ),
  );
}

class _OnboardingStep extends StatelessWidget {
  const _OnboardingStep({
    required this.stepNumber,
    required this.stepCount,
    required this.title,
    required this.body,
    required this.icon,
    required this.warning,
    required this.message,
    super.key,
  });

  final int stepNumber;
  final int stepCount;
  final String title;
  final String body;
  final IconData icon;
  final bool warning;
  final String? message;

  @override
  Widget build(BuildContext context) => Padding(
    key: const Key('onboarding-step-content'),
    padding: const EdgeInsets.fromLTRB(22, 24, 22, 22),
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'STEP $stepNumber OF $stepCount',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: AppColors.secondaryText,
            fontWeight: FontWeight.w800,
            letterSpacing: 0.7,
          ),
        ),
        const SizedBox(height: 20),
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0.82, end: 1),
          duration: const Duration(milliseconds: 450),
          curve: Curves.easeOutBack,
          builder: (context, scale, child) =>
              Transform.scale(scale: scale, child: child),
          child: Center(
            child: Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: 104,
                  height: 104,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppColors.primary.withValues(alpha: 0.10),
                  ),
                ),
                Container(
                  width: 76,
                  height: 76,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppColors.primary,
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x26005B88),
                        blurRadius: 18,
                        offset: Offset(0, 7),
                      ),
                    ],
                  ),
                  child: Icon(icon, size: 40, color: Colors.white),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 22),
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 12),
        Text(
          body,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.45),
        ),
        if (warning) ...[
          const SizedBox(height: 20),
          const DecoratedBox(
            decoration: BoxDecoration(
              color: Color(0xFFCEEAF8),
              borderRadius: BorderRadius.all(Radius.circular(14)),
            ),
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text(
                'Official authorities and emergency services take priority over this research prototype.',
                textAlign: TextAlign.center,
              ),
            ),
          ),
        ],
        if (message != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Text(
              message!,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.error),
            ),
          ),
      ],
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
