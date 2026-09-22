import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/auth/resident_auth_repository.dart';
import 'session_controller.dart';

class AuthenticationScreen extends StatefulWidget {
  const AuthenticationScreen({required this.controller, super.key});
  final SessionController controller;

  @override
  State<AuthenticationScreen> createState() => _AuthenticationScreenState();
}

class _AuthenticationScreenState extends State<AuthenticationScreen> {
  bool _registration = false;

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 180),
              child: _registration
                  ? RegistrationForm(
                      key: const ValueKey('registration'),
                      controller: widget.controller,
                      onShowLogin: () => setState(() => _registration = false),
                    )
                  : LoginForm(
                      key: const ValueKey('login'),
                      controller: widget.controller,
                      onCreateAccount: () =>
                          setState(() => _registration = true),
                    ),
            ),
          ),
        ),
      ),
    ),
  );
}

class _BrandHeader extends StatelessWidget {
  const _BrandHeader({required this.title, required this.subtitle});
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      const Icon(Icons.water_drop_outlined, size: 54, color: AppColors.primary),
      const SizedBox(height: 10),
      Text(
        'FloodSense',
        style: Theme.of(context).textTheme.headlineMedium
            ?.copyWith(color: AppColors.primary, fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 18),
      Text(title, style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 6),
      Text(subtitle, textAlign: TextAlign.center),
    ],
  );
}

class LoginForm extends StatefulWidget {
  const LoginForm({
    required this.controller,
    required this.onCreateAccount,
    super.key,
  });
  final SessionController controller;
  final VoidCallback onCreateAccount;

  @override
  State<LoginForm> createState() => _LoginFormState();
}

class _LoginFormState extends State<LoginForm> {
  final _form = GlobalKey<FormState>();
  final _identifier = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;
  bool _remember = false;

  @override
  void dispose() {
    _identifier.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _google() async {
    final succeeded = await widget.controller.googleSignIn();
    if (!mounted || succeeded) return;
    if (widget.controller.errorCode == 'username_required') {
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GoogleUsernameScreen(controller: widget.controller),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Form(
    key: _form,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _BrandHeader(
          title: 'Resident sign in',
          subtitle: 'Explore hypothetical flood susceptibility scenarios.',
        ),
        const SizedBox(height: 24),
        TextFormField(
          key: const Key('login-identifier'),
          controller: _identifier,
          textInputAction: TextInputAction.next,
          autofillHints: const [AutofillHints.username, AutofillHints.email],
          decoration: const InputDecoration(
            labelText: 'Username or email',
            border: OutlineInputBorder(),
          ),
          validator: (value) => value == null || value.trim().isEmpty
              ? 'Enter your username or email.'
              : null,
        ),
        const SizedBox(height: 14),
        TextFormField(
          key: const Key('login-password'),
          controller: _password,
          obscureText: _obscure,
          autofillHints: const [AutofillHints.password],
          decoration: InputDecoration(
            labelText: 'Password',
            border: const OutlineInputBorder(),
            suffixIcon: IconButton(
              key: const Key('login-password-visibility'),
              tooltip: _obscure ? 'Show password' : 'Hide password',
              onPressed: () => setState(() => _obscure = !_obscure),
              icon: Icon(
                _obscure
                    ? Icons.visibility_outlined
                    : Icons.visibility_off_outlined,
              ),
            ),
          ),
          validator: (value) =>
              value == null || value.isEmpty ? 'Enter your password.' : null,
        ),
        Row(
          children: [
            Checkbox(
              key: const Key('remember-me'),
              value: _remember,
              onChanged: (value) => setState(() => _remember = value ?? false),
            ),
            const Expanded(child: Text('Remember Me on this device')),
            TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => ForgotPasswordScreen(
                    repository: widget.controller.repository,
                  ),
                ),
              ),
              child: const Text('Forgot Password?'),
            ),
          ],
        ),
        _SessionMessage(controller: widget.controller),
        const SizedBox(height: 10),
        FilledButton(
          key: const Key('sign-in-button'),
          onPressed: widget.controller.busy
              ? null
              : () {
                  if (_form.currentState!.validate()) {
                    widget.controller.login(
                      identifier: _identifier.text,
                      password: _password.text,
                      rememberMe: _remember,
                    );
                  }
                },
          child: Text(widget.controller.busy ? 'Signing in…' : 'Sign In'),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 16),
          child: Row(
            children: [
              Expanded(child: Divider()),
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 12),
                child: Text('or'),
              ),
              Expanded(child: Divider()),
            ],
          ),
        ),
        OutlinedButton.icon(
          key: const Key('google-sign-in'),
          onPressed: widget.controller.busy ? null : _google,
          icon: const Icon(Icons.account_circle_outlined),
          label: const Text('Continue with Google'),
        ),
        TextButton(
          onPressed: widget.onCreateAccount,
          child: const Text('Create Account'),
        ),
        LegalFooter(
          repository: widget.controller.repository,
          originLabel: 'Login',
        ),
      ],
    ),
  );
}

class RegistrationForm extends StatefulWidget {
  const RegistrationForm({
    required this.controller,
    required this.onShowLogin,
    super.key,
  });
  final SessionController controller;
  final VoidCallback onShowLogin;

  @override
  State<RegistrationForm> createState() => _RegistrationFormState();
}

class _RegistrationFormState extends State<RegistrationForm> {
  final _form = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _username.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _google() async {
    final succeeded = await widget.controller.googleSignIn();
    if (!mounted || succeeded) return;
    if (widget.controller.errorCode == 'username_required') {
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => GoogleUsernameScreen(controller: widget.controller),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Form(
    key: _form,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _BrandHeader(
          title: 'Create resident account',
          subtitle:
              'Only a username, email address, and password are required.',
        ),
        const SizedBox(height: 24),
        TextFormField(
          key: const Key('register-username'),
          controller: _username,
          decoration: const InputDecoration(
            labelText: 'Username',
            border: OutlineInputBorder(),
          ),
          validator: (value) =>
              RegExp(r'^[A-Za-z][A-Za-z0-9_.-]{2,29}$')
                  .hasMatch(value?.trim() ?? '')
              ? null
              : 'Use 3–30 allowed characters, beginning with a letter.',
        ),
        const SizedBox(height: 14),
        TextFormField(
          key: const Key('register-email'),
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          autofillHints: const [AutofillHints.email],
          decoration: const InputDecoration(
            labelText: 'Email address',
            border: OutlineInputBorder(),
          ),
          validator: (value) =>
              RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
                  .hasMatch(value?.trim() ?? '')
              ? null
              : 'Enter a valid email address.',
        ),
        const SizedBox(height: 14),
        TextFormField(
          key: const Key('register-password'),
          controller: _password,
          obscureText: _obscure,
          autofillHints: const [AutofillHints.newPassword],
          decoration: InputDecoration(
            labelText: 'Password',
            border: const OutlineInputBorder(),
            suffixIcon: IconButton(
              key: const Key('register-password-visibility'),
              tooltip: _obscure ? 'Show password' : 'Hide password',
              onPressed: () => setState(() => _obscure = !_obscure),
              icon: Icon(
                _obscure
                    ? Icons.visibility_outlined
                    : Icons.visibility_off_outlined,
              ),
            ),
          ),
          validator: (value) =>
              (value?.length ?? 0) < 8 ? 'Use at least 8 characters.' : null,
        ),
        const SizedBox(height: 8),
        const Text(
          'Use a long, unique password. Avoid common, all-numeric, or account-similar passwords.',
        ),
        _SessionMessage(controller: widget.controller),
        const SizedBox(height: 14),
        FilledButton(
          key: const Key('create-account-button'),
          onPressed: widget.controller.busy
              ? null
              : () {
                  if (_form.currentState!.validate()) {
                    widget.controller.register(
                      username: _username.text,
                      email: _email.text,
                      password: _password.text,
                    );
                  }
                },
          child: Text(
            widget.controller.busy ? 'Creating account…' : 'Create Account',
          ),
        ),
        OutlinedButton.icon(
          onPressed: widget.controller.busy ? null : _google,
          icon: const Icon(Icons.account_circle_outlined),
          label: const Text('Continue with Google'),
        ),
        TextButton(
          onPressed: widget.onShowLogin,
          child: const Text('Back to Login'),
        ),
        LegalFooter(
          repository: widget.controller.repository,
          originLabel: 'Registration',
        ),
      ],
    ),
  );
}

class _SessionMessage extends StatelessWidget {
  const _SessionMessage({required this.controller});
  final SessionController controller;
  @override
  Widget build(BuildContext context) => controller.message == null
      ? const SizedBox.shrink()
      : Semantics(
          liveRegion: true,
          child: Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text(
              controller.message!,
              key: const Key('auth-message'),
              style: const TextStyle(color: AppColors.error),
            ),
          ),
        );
}

class LegalFooter extends StatelessWidget {
  const LegalFooter({
    required this.repository,
    required this.originLabel,
    super.key,
  });
  final ResidentAuthRepository repository;
  final String originLabel;

  void _open(BuildContext context, String type) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => LegalDocumentScreen(
          repository: repository,
          type: type,
          originLabel: originLabel,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Wrap(
    alignment: WrapAlignment.center,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      const Text('By creating an account, you agree to the '),
      TextButton(
        onPressed: () => _open(context, 'terms'),
        child: const Text('Terms of Use'),
      ),
      const Text(' and acknowledge the '),
      TextButton(
        onPressed: () => _open(context, 'privacy'),
        child: const Text('Privacy Policy'),
      ),
      const Text('.'),
    ],
  );
}

class LegalDocumentScreen extends StatefulWidget {
  const LegalDocumentScreen({
    required this.repository,
    required this.type,
    required this.originLabel,
    super.key,
  });
  final ResidentAuthRepository repository;
  final String type;
  final String originLabel;

  @override
  State<LegalDocumentScreen> createState() => _LegalDocumentScreenState();
}

class _LegalDocumentScreenState extends State<LegalDocumentScreen> {
  late Future<LegalDocument> _document;
  @override
  void initState() {
    super.initState();
    _document = widget.repository.publicLegalDocument(widget.type);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.type == 'terms' ? 'Terms of Use' : 'Privacy Policy'),
    ),
    body: FutureBuilder<LegalDocument>(
      future: _document,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return _LoadFailure(
            onRetry: () => setState(
              () => _document = widget.repository.publicLegalDocument(
                widget.type,
              ),
            ),
          );
        }
        return LegalDocumentView(document: snapshot.requireData);
      },
    ),
    bottomNavigationBar: SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: OutlinedButton.icon(
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.arrow_back),
          label: Text('Back to ${widget.originLabel}'),
        ),
      ),
    ),
  );
}

class LegalDocumentView extends StatefulWidget {
  const LegalDocumentView({required this.document, super.key});
  final LegalDocument document;
  @override
  State<LegalDocumentView> createState() => _LegalDocumentViewState();
}

class _LegalDocumentViewState extends State<LegalDocumentView> {
  late List<bool> _expanded;
  @override
  void initState() {
    super.initState();
    _expanded = List.filled(widget.document.sections.length, false);
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
    children: [
      Text(
        widget.document.title,
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 8),
      Text('Version ${widget.document.version}'),
      const SizedBox(height: 12),
      if (widget.document.prototypeDraft)
        MaterialBanner(
          content: Text(widget.document.reviewNotice),
          actions: const [SizedBox.shrink()],
        ),
      const SizedBox(height: 12),
      Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          TextButton(
            onPressed: () =>
                setState(() => _expanded = List.filled(_expanded.length, true)),
            child: const Text('Expand All'),
          ),
          TextButton(
            onPressed: () => setState(
              () => _expanded = List.filled(_expanded.length, false),
            ),
            child: const Text('Collapse All'),
          ),
        ],
      ),
      for (var index = 0; index < widget.document.sections.length; index++)
        Card(
          child: Semantics(
            button: true,
            expanded: _expanded[index],
            child: ExpansionTile(
              key: Key('legal-section-$index'),
              initiallyExpanded: _expanded[index],
              onExpansionChanged: (value) =>
                  setState(() => _expanded[index] = value),
              title: Text(widget.document.sections[index].title),
              subtitle: Text(widget.document.sections[index].summary),
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: SelectableText(widget.document.sections[index].body),
                ),
              ],
            ),
          ),
        ),
    ],
  );
}

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({required this.repository, super.key});
  final ResidentAuthRepository repository;
  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _email = TextEditingController();
  String? _message;
  bool _busy = false;
  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Reset password')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Enter your email address. The response is the same whether or not an eligible account exists.',
        ),
        const SizedBox(height: 16),
        TextField(
          key: const Key('forgot-email'),
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(
            labelText: 'Email address',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: _busy
              ? null
              : () async {
                  setState(() => _busy = true);
                  try {
                    await widget.repository.requestPasswordReset(_email.text);
                    _message =
                        'If eligible, reset instructions have been sent.';
                  } on ResidentAuthException catch (error) {
                    _message = error.message;
                  }
                  if (mounted) setState(() => _busy = false);
                },
          child: const Text('Send reset instructions'),
        ),
        if (_message != null)
          Semantics(liveRegion: true, child: Text(_message!)),
        TextButton(
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) =>
                  ResetPasswordScreen(repository: widget.repository),
            ),
          ),
          child: const Text('I already have a reset link'),
        ),
      ],
    ),
  );
}

class ResetPasswordScreen extends StatefulWidget {
  const ResetPasswordScreen({
    required this.repository,
    this.initialUid = '',
    this.initialToken = '',
    super.key,
  });
  final ResidentAuthRepository repository;
  final String initialUid;
  final String initialToken;
  @override
  State<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends State<ResetPasswordScreen> {
  late final TextEditingController _uid = TextEditingController(
    text: widget.initialUid,
  );
  late final TextEditingController _token = TextEditingController(
    text: widget.initialToken,
  );
  final _password = TextEditingController();
  bool _obscure = true;
  String? _message;
  @override
  void dispose() {
    _uid.dispose();
    _token.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Choose a new password')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        TextField(
          controller: _uid,
          decoration: const InputDecoration(
            labelText: 'Link user code',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _token,
          decoration: const InputDecoration(
            labelText: 'One-time reset token',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _password,
          obscureText: _obscure,
          decoration: InputDecoration(
            labelText: 'New password',
            border: const OutlineInputBorder(),
            suffixIcon: IconButton(
              onPressed: () => setState(() => _obscure = !_obscure),
              icon: const Icon(Icons.visibility_outlined),
            ),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: () async {
            try {
              await widget.repository.confirmPasswordReset(
                uid: _uid.text,
                token: _token.text,
                password: _password.text,
              );
              _message = 'Password changed. Return to Login.';
            } on ResidentAuthException catch (error) {
              _message = error.message;
            }
            if (mounted) setState(() {});
          },
          child: const Text('Change password'),
        ),
        if (_message != null)
          Semantics(liveRegion: true, child: Text(_message!)),
      ],
    ),
  );
}

class EmailVerificationScreen extends StatefulWidget {
  const EmailVerificationScreen({required this.controller, super.key});
  final SessionController controller;
  @override
  State<EmailVerificationScreen> createState() =>
      _EmailVerificationScreenState();
}

class _EmailVerificationScreenState extends State<EmailVerificationScreen> {
  final _token = TextEditingController();
  final _email = TextEditingController();
  @override
  void initState() {
    super.initState();
    _email.text = widget.controller.pendingVerificationEmail ?? '';
  }

  @override
  void dispose() {
    _token.dispose();
    _email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Verify email address')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Open the one-time link from your email, or paste its token below. Tokens expire and work only once.',
        ),
        const SizedBox(height: 16),
        TextField(
          key: const Key('verification-token'),
          controller: _token,
          decoration: const InputDecoration(
            labelText: 'Verification token',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: widget.controller.busy
              ? null
              : () => widget.controller.verifyEmail(_token.text),
          child: const Text('Verify email'),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _email,
          decoration: const InputDecoration(
            labelText: 'Email address',
            border: OutlineInputBorder(),
          ),
        ),
        OutlinedButton(
          onPressed: widget.controller.busy
              ? null
              : () => widget.controller.resendVerification(_email.text),
          child: const Text('Resend verification'),
        ),
        _SessionMessage(controller: widget.controller),
        TextButton(
          onPressed: widget.controller.showLogin,
          child: const Text('Back to Login'),
        ),
      ],
    ),
  );
}

class GoogleUsernameScreen extends StatefulWidget {
  const GoogleUsernameScreen({required this.controller, super.key});
  final SessionController controller;
  @override
  State<GoogleUsernameScreen> createState() => _GoogleUsernameScreenState();
}

class _GoogleUsernameScreenState extends State<GoogleUsernameScreen> {
  final _username = TextEditingController();
  @override
  void dispose() {
    _username.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Choose a resident username')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Text(
          'Google verified your identity. Choose the FloodSense username shown on your account.',
        ),
        const SizedBox(height: 16),
        TextField(
          key: const Key('google-resident-username'),
          controller: _username,
          decoration: const InputDecoration(
            labelText: 'Username',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: widget.controller.busy
              ? null
              : () async {
                  final succeeded = await widget.controller.googleSignIn(
                    username: _username.text,
                  );
                  if (!context.mounted) return;
                  if (succeeded) {
                    Navigator.pop(context);
                  }
                },
          child: const Text('Continue with Google'),
        ),
        _SessionMessage(controller: widget.controller),
      ],
    ),
  );
}

class _LoadFailure extends StatelessWidget {
  const _LoadFailure({required this.onRetry});
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text('This content could not be loaded.'),
        TextButton(onPressed: onRetry, child: const Text('Try again')),
      ],
    ),
  );
}
