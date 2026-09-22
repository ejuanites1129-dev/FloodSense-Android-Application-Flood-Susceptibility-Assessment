import 'package:flutter/foundation.dart';

import '../../data/auth/resident_auth_repository.dart';

enum ResidentSessionState {
  initializing,
  unauthenticated,
  configurationRequired,
  awaitingEmailVerification,
  awaitingLegalAcceptance,
  awaitingOnboarding,
  authenticatedReady,
  refreshFailed,
}

class SessionController extends ChangeNotifier {
  SessionController(this.repository);

  final ResidentAuthRepository repository;
  ResidentSessionState state = ResidentSessionState.initializing;
  ResidentUser? user;
  String? message;
  String? errorCode;
  String? pendingVerificationEmail;
  bool busy = false;
  bool _disposed = false;

  Future<void> initialize() async {
    try {
      final session = await repository.restore();
      if (_disposed) return;
      if (session == null) {
        state = ResidentSessionState.unauthenticated;
      } else {
        user = session.user;
        _setStage(session.stage);
      }
    } catch (_) {
      if (_disposed) return;
      state = ResidentSessionState.refreshFailed;
      message = 'Your remembered session expired. Please sign in again.';
    }
    _notify();
  }

  Future<bool> login({
    required String identifier,
    required String password,
    required bool rememberMe,
  }) async {
    return _run(() async {
      final session = await repository.login(
        identifier: identifier,
        password: password,
        rememberMe: rememberMe,
      );
      user = session.user;
      _setStage(session.stage);
    });
  }

  Future<bool> register({
    required String username,
    required String email,
    required String password,
  }) async {
    return _run(() async {
      await repository.register(
        username: username,
        email: email,
        password: password,
      );
      pendingVerificationEmail = email;
      state = ResidentSessionState.awaitingEmailVerification;
      message = 'Check your email for the one-time verification link.';
    });
  }

  Future<bool> googleSignIn({String? username}) async {
    return _run(() async {
      final session = await repository.googleSignIn(username: username);
      if (session == null) {
        message = 'Google sign-in was cancelled.';
        return;
      }
      user = session.user;
      _setStage(session.stage);
    });
  }

  Future<bool> verifyEmail(String token) async => _run(() async {
    await repository.verifyEmail(token);
    state = ResidentSessionState.unauthenticated;
    message = 'Email verified. Sign in to continue.';
  });

  Future<bool> resendVerification(String email) async => _run(() async {
    await repository.resendVerification(email);
    message =
        'If the account is eligible, a new verification message was sent.';
  });

  Future<bool> acceptLegal(List<int> ids) async => _run(() async {
    _setStage(await repository.acceptLegal(ids));
  });

  Future<bool> refreshSetup() async => _run(() async {
    _setStage(await repository.setupStatus());
  });

  Future<bool> acknowledgeOnboarding(String version) async => _run(() async {
    _setStage(await repository.acknowledgeOnboarding(version));
  });

  Future<bool> updateUsername(String username) async => _run(() async {
    user = await repository.updateUsername(username);
  });

  Future<bool> linkGoogle(String password) async => _run(() async {
    user = await repository.linkGoogle(password);
  });

  Future<bool> unlinkGoogle(String password) async => _run(() async {
    user = await repository.unlinkGoogle(password);
  });

  Future<void> logout() async {
    busy = true;
    _notify();
    try {
      await repository.logout();
    } finally {
      user = null;
      pendingVerificationEmail = null;
      state = ResidentSessionState.unauthenticated;
      busy = false;
      message = null;
      _notify();
    }
  }

  Future<bool> _run(Future<void> Function() action) async {
    if (busy) return false;
    busy = true;
    message = null;
    errorCode = null;
    _notify();
    try {
      await action();
      return true;
    } on ResidentAuthException catch (error) {
      message = error.message;
      errorCode = error.code;
      return false;
    } catch (_) {
      message = 'FloodSense could not complete the request. Please try again.';
      return false;
    } finally {
      busy = false;
      _notify();
    }
  }

  void _setStage(SetupStage stage) {
    state = switch (stage) {
      SetupStage.configurationRequired =>
        ResidentSessionState.configurationRequired,
      SetupStage.awaitingEmailVerification =>
        ResidentSessionState.awaitingEmailVerification,
      SetupStage.awaitingLegalAcceptance =>
        ResidentSessionState.awaitingLegalAcceptance,
      SetupStage.awaitingOnboarding => ResidentSessionState.awaitingOnboarding,
      SetupStage.authenticatedReady => ResidentSessionState.authenticatedReady,
    };
  }

  void showLogin() {
    state = ResidentSessionState.unauthenticated;
    message = null;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
