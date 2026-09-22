import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

import '../../config/api_config.dart';

class ResidentAuthException implements Exception {
  const ResidentAuthException(
    this.message, {
    this.code,
    this.fieldErrors = const {},
  });

  final String message;
  final String? code;
  final Map<String, List<String>> fieldErrors;

  @override
  String toString() => message;
}

enum SetupStage {
  configurationRequired,
  awaitingEmailVerification,
  awaitingLegalAcceptance,
  awaitingOnboarding,
  authenticatedReady,
}

SetupStage setupStageFromWire(String value) => switch (value) {
  'configuration_required' => SetupStage.configurationRequired,
  'awaiting_email_verification' => SetupStage.awaitingEmailVerification,
  'awaiting_legal_acceptance' => SetupStage.awaitingLegalAcceptance,
  'awaiting_onboarding' => SetupStage.awaitingOnboarding,
  'authenticated_ready' => SetupStage.authenticatedReady,
  _ => SetupStage.configurationRequired,
};

class ResidentUser {
  const ResidentUser({
    required this.id,
    required this.username,
    required this.email,
    required this.emailVerified,
    required this.passwordLoginAvailable,
    required this.linkedProviders,
  });

  final int id;
  final String? username;
  final String email;
  final bool emailVerified;
  final bool passwordLoginAvailable;
  final List<String> linkedProviders;

  factory ResidentUser.fromJson(Map<String, dynamic> json) => ResidentUser(
    id: json['id'] as int,
    username: json['username'] as String?,
    email: json['email'] as String,
    emailVerified: json['email_verified'] as bool? ?? false,
    passwordLoginAvailable: json['password_login_available'] as bool? ?? false,
    linkedProviders: List<String>.unmodifiable(
      (json['linked_providers'] as List? ?? const []).map((item) => '$item'),
    ),
  );
}

class AuthSession {
  const AuthSession({
    required this.user,
    required this.stage,
    required this.accessToken,
    required this.refreshToken,
  });

  final ResidentUser user;
  final SetupStage stage;
  final String accessToken;
  final String refreshToken;
}

class LegalSection {
  const LegalSection({
    required this.title,
    required this.summary,
    required this.body,
  });
  final String title;
  final String summary;
  final String body;
}

class LegalDocument {
  const LegalDocument({
    required this.id,
    required this.type,
    required this.version,
    required this.title,
    required this.summary,
    required this.prototypeDraft,
    required this.reviewNotice,
    required this.sections,
  });
  final int id;
  final String type;
  final String version;
  final String title;
  final String summary;
  final bool prototypeDraft;
  final String reviewNotice;
  final List<LegalSection> sections;

  factory LegalDocument.fromJson(Map<String, dynamic> json) => LegalDocument(
    id: json['id'] as int,
    type: json['document_type'] as String,
    version: json['version'] as String,
    title: json['title'] as String,
    summary: json['summary'] as String,
    prototypeDraft: json['prototype_draft'] as bool? ?? false,
    reviewNotice: json['review_notice'] as String? ?? '',
    sections: List<LegalSection>.unmodifiable(
      (json['sections'] as List).map((raw) {
        final section = Map<String, dynamic>.from(raw as Map);
        return LegalSection(
          title: section['title'] as String,
          summary: section['summary'] as String,
          body: section['body'] as String,
        );
      }),
    ),
  );
}

class OnboardingContent {
  const OnboardingContent({required this.version, required this.steps});
  final String version;
  final List<({String title, String body})> steps;

  factory OnboardingContent.fromJson(Map<String, dynamic> json) =>
      OnboardingContent(
        version: json['version'] as String,
        steps: List.unmodifiable(
          (json['steps'] as List).map((raw) {
            final step = Map<String, dynamic>.from(raw as Map);
            return (
              title: step['title'] as String,
              body: step['body'] as String,
            );
          }),
        ),
      );
}

abstract interface class RefreshTokenStore {
  Future<String?> read();
  Future<void> write(String token);
  Future<void> clear();
}

class SecureRefreshTokenStore implements RefreshTokenStore {
  SecureRefreshTokenStore({FlutterSecureStorage? storage})
    : _storage =
          storage ?? const FlutterSecureStorage(aOptions: AndroidOptions());

  static const _key = 'floodsense_resident_refresh_token';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> read() => _storage.read(key: _key);
  @override
  Future<void> write(String token) => _storage.write(key: _key, value: token);
  @override
  Future<void> clear() => _storage.delete(key: _key);
}

abstract interface class GoogleIdentityProvider {
  Future<String?> authenticate();
  Future<void> signOut();
}

class OfficialGoogleIdentityProvider implements GoogleIdentityProvider {
  OfficialGoogleIdentityProvider({
    this.serverClientId = const String.fromEnvironment(
      'GOOGLE_SERVER_CLIENT_ID',
    ),
  });

  final String serverClientId;
  bool _initialized = false;

  Future<void> _initialize() async {
    if (serverClientId.trim().isEmpty) {
      throw const ResidentAuthException(
        'Google sign-in is not configured for this build.',
        code: 'google_not_configured',
      );
    }
    if (_initialized) return;
    await GoogleSignIn.instance.initialize(serverClientId: serverClientId);
    _initialized = true;
  }

  @override
  Future<String?> authenticate() async {
    await _initialize();
    try {
      final account = await GoogleSignIn.instance.authenticate();
      final token = account.authentication.idToken;
      if (token == null || token.isEmpty) {
        throw const ResidentAuthException(
          'Google did not return a verifiable identity token.',
        );
      }
      return token;
    } on GoogleSignInException catch (error) {
      if (error.code == GoogleSignInExceptionCode.canceled ||
          error.code == GoogleSignInExceptionCode.interrupted) {
        return null;
      }
      throw const ResidentAuthException(
        'Google sign-in could not be completed.',
      );
    }
  }

  @override
  Future<void> signOut() async {
    if (_initialized) await GoogleSignIn.instance.signOut();
  }
}

abstract interface class ResidentAuthRepository {
  Future<AuthSession?> restore();
  Future<AuthSession> login({
    required String identifier,
    required String password,
    required bool rememberMe,
  });
  Future<void> register({
    required String username,
    required String email,
    required String password,
  });
  Future<AuthSession?> googleSignIn({String? username});
  Future<void> requestPasswordReset(String email);
  Future<void> confirmPasswordReset({
    required String uid,
    required String token,
    required String password,
  });
  Future<void> verifyEmail(String token);
  Future<void> resendVerification(String email);
  Future<List<LegalDocument>> requiredLegalDocuments();
  Future<SetupStage> setupStatus();
  Future<LegalDocument> publicLegalDocument(String type);
  Future<SetupStage> acceptLegal(List<int> ids);
  Future<OnboardingContent> onboarding();
  Future<SetupStage> acknowledgeOnboarding(String version);
  Future<ResidentUser> account();
  Future<ResidentUser> updateUsername(String username);
  Future<Map<String, dynamic>> preferences();
  Future<Map<String, dynamic>> updatePreferences(Map<String, dynamic> values);
  Future<void> changePassword(String currentPassword, String newPassword);
  Future<ResidentUser> linkGoogle(String password);
  Future<ResidentUser> unlinkGoogle(String password);
  Future<void> requestDeletion();
  Future<void> logout();
  String? get accessToken;
}

class HttpResidentAuthRepository implements ResidentAuthRepository {
  HttpResidentAuthRepository({
    http.Client? client,
    RefreshTokenStore? tokenStore,
    GoogleIdentityProvider? googleProvider,
    String? baseUrl,
    this.timeout = const Duration(seconds: 15),
  }) : _client = client ?? http.Client(),
       _store = tokenStore ?? SecureRefreshTokenStore(),
       _google = googleProvider ?? OfficialGoogleIdentityProvider(),
       _baseUrl = ApiConfig.normalizeBaseUrl(baseUrl ?? ApiConfig.baseUrl);

  final http.Client _client;
  final RefreshTokenStore _store;
  final GoogleIdentityProvider _google;
  final String _baseUrl;
  final Duration timeout;
  String? _accessToken;
  String? _activeRefreshToken;

  @override
  String? get accessToken => _accessToken;

  Uri _uri(String path) =>
      Uri.parse('$_baseUrl/${path.replaceFirst(RegExp(r'^/+'), '')}');

  Map<String, String> _headers({bool authenticated = false}) => {
    HttpHeaders.acceptHeader: 'application/json',
    HttpHeaders.contentTypeHeader: 'application/json; charset=utf-8',
    if (authenticated && _accessToken != null)
      HttpHeaders.authorizationHeader: 'Bearer $_accessToken',
  };

  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = false,
  }) async {
    try {
      final request = http.Request(method, _uri(path))
        ..headers.addAll(_headers(authenticated: authenticated));
      if (body != null) request.body = jsonEncode(body);
      final streamed = await _client.send(request).timeout(timeout);
      final response = await http.Response.fromStream(streamed);
      final decoded = response.bodyBytes.isEmpty
          ? <String, dynamic>{}
          : Map<String, dynamic>.from(
              jsonDecode(utf8.decode(response.bodyBytes)) as Map,
            );
      if (response.statusCode >= 200 && response.statusCode < 300) {
        return decoded;
      }
      final fields = <String, List<String>>{};
      for (final entry in decoded.entries) {
        if (entry.value is List) {
          fields[entry.key] = (entry.value as List)
              .map((item) => '$item')
              .toList();
        }
      }
      throw ResidentAuthException(
        decoded['detail']?.toString() ??
            fields.values.expand((value) => value).join(' '),
        code: decoded['code']?.toString(),
        fieldErrors: fields,
      );
    } on ResidentAuthException {
      rethrow;
    } on TimeoutException {
      throw const ResidentAuthException(
        'The request timed out. Check your connection and try again.',
      );
    } on SocketException {
      throw const ResidentAuthException(
        'FloodSense is offline or unavailable. Check your connection.',
      );
    } on FormatException {
      throw const ResidentAuthException(
        'FloodSense returned an unreadable response.',
      );
    } on http.ClientException {
      throw const ResidentAuthException(
        'FloodSense is offline or unavailable. Check your connection.',
      );
    }
  }

  AuthSession _session(Map<String, dynamic> json) => AuthSession(
    user: ResidentUser.fromJson(Map<String, dynamic>.from(json['user'] as Map)),
    stage: setupStageFromWire(
      (Map<String, dynamic>.from(json['setup'] as Map))['stage'] as String,
    ),
    accessToken: json['access'] as String,
    refreshToken: json['refresh'] as String,
  );

  Future<void> _apply(AuthSession session, {required bool remember}) async {
    _accessToken = session.accessToken;
    _activeRefreshToken = session.refreshToken;
    if (remember) {
      await _store.write(session.refreshToken);
    } else {
      await _store.clear();
    }
  }

  @override
  Future<AuthSession?> restore() async {
    final stored = await _store.read();
    if (stored == null || stored.isEmpty) return null;
    try {
      final refreshed = await _request(
        'POST',
        'auth/token/refresh/',
        body: {'refresh': stored},
      );
      _accessToken = refreshed['access'] as String;
      _activeRefreshToken = refreshed['refresh'] as String? ?? stored;
      await _store.write(_activeRefreshToken!);
      final user = await account();
      final setup = await _request(
        'GET',
        'auth/setup-status/',
        authenticated: true,
      );
      return AuthSession(
        user: user,
        stage: setupStageFromWire(setup['stage'] as String),
        accessToken: _accessToken!,
        refreshToken: _activeRefreshToken!,
      );
    } catch (_) {
      await _store.clear();
      _accessToken = null;
      _activeRefreshToken = null;
      return null;
    }
  }

  @override
  Future<AuthSession> login({
    required String identifier,
    required String password,
    required bool rememberMe,
  }) async {
    final json = await _request(
      'POST',
      'auth/login/',
      body: {
        'identifier': identifier,
        'password': password,
        'remember_me': rememberMe,
      },
    );
    final session = _session(json);
    await _apply(session, remember: rememberMe);
    return session;
  }

  @override
  Future<void> register({
    required String username,
    required String email,
    required String password,
  }) async {
    await _request(
      'POST',
      'auth/register/',
      body: {'username': username, 'email': email, 'password': password},
    );
  }

  @override
  Future<AuthSession?> googleSignIn({String? username}) async {
    final token = await _google.authenticate();
    if (token == null) return null;
    final json = await _request(
      'POST',
      'auth/google/',
      body: {
        'id_token': token,
        if (username != null && username.isNotEmpty) 'username': username,
      },
    );
    final session = _session(json);
    await _apply(session, remember: true);
    return session;
  }

  @override
  Future<void> requestPasswordReset(String email) =>
      _request('POST', 'auth/password-reset/request/', body: {'email': email});
  @override
  Future<void> confirmPasswordReset({
    required String uid,
    required String token,
    required String password,
  }) => _request(
    'POST',
    'auth/password-reset/confirm/',
    body: {'uid': uid, 'token': token, 'new_password': password},
  );
  @override
  Future<void> verifyEmail(String token) =>
      _request('POST', 'auth/email/verify/', body: {'token': token});
  @override
  Future<void> resendVerification(String email) =>
      _request('POST', 'auth/email/resend/', body: {'email': email});

  @override
  Future<List<LegalDocument>> requiredLegalDocuments() async {
    final json = await _request(
      'GET',
      'auth/legal/required/',
      authenticated: true,
    );
    return List.unmodifiable(
      (json['documents'] as List).map(
        (item) =>
            LegalDocument.fromJson(Map<String, dynamic>.from(item as Map)),
      ),
    );
  }

  @override
  Future<SetupStage> setupStatus() async {
    final json = await _request(
      'GET',
      'auth/setup-status/',
      authenticated: true,
    );
    return setupStageFromWire(json['stage'] as String);
  }

  @override
  Future<LegalDocument> publicLegalDocument(String type) async {
    final json = await _request('GET', 'legal/${type.toLowerCase()}/current/');
    return LegalDocument.fromJson(json);
  }

  @override
  Future<SetupStage> acceptLegal(List<int> ids) async {
    final json = await _request(
      'POST',
      'auth/legal/accept/',
      body: {'document_version_ids': ids, 'application_version': '1.0.0'},
      authenticated: true,
    );
    return setupStageFromWire(json['stage'] as String);
  }

  @override
  Future<OnboardingContent> onboarding() async => OnboardingContent.fromJson(
    await _request('GET', 'auth/onboarding/current/', authenticated: true),
  );
  @override
  Future<SetupStage> acknowledgeOnboarding(String version) async {
    final json = await _request(
      'POST',
      'auth/onboarding/acknowledge/',
      body: {'version': version},
      authenticated: true,
    );
    return setupStageFromWire(json['stage'] as String);
  }

  @override
  Future<ResidentUser> account() async => ResidentUser.fromJson(
    await _request('GET', 'account/me/', authenticated: true),
  );
  @override
  Future<ResidentUser> updateUsername(String username) async =>
      ResidentUser.fromJson(
        await _request(
          'PATCH',
          'account/me/',
          body: {'username': username},
          authenticated: true,
        ),
      );
  @override
  Future<Map<String, dynamic>> preferences() =>
      _request('GET', 'account/preferences/', authenticated: true);
  @override
  Future<Map<String, dynamic>> updatePreferences(Map<String, dynamic> values) =>
      _request(
        'PATCH',
        'account/preferences/',
        body: values,
        authenticated: true,
      );
  @override
  Future<void> changePassword(String currentPassword, String newPassword) =>
      _request(
        'POST',
        'account/change-password/',
        body: {
          'current_password': currentPassword,
          'new_password': newPassword,
        },
        authenticated: true,
      );
  @override
  Future<ResidentUser> linkGoogle(String password) async {
    final token = await _google.authenticate();
    if (token == null) {
      throw const ResidentAuthException('Google sign-in was cancelled.');
    }
    return ResidentUser.fromJson(
      await _request(
        'POST',
        'account/google/link/',
        body: {'password': password, 'id_token': token},
        authenticated: true,
      ),
    );
  }

  @override
  Future<ResidentUser> unlinkGoogle(String password) async {
    await _request(
      'POST',
      'account/google/unlink/',
      body: {'password': password},
      authenticated: true,
    );
    return account();
  }

  @override
  Future<void> requestDeletion() => _request(
    'POST',
    'account/request-deletion/',
    body: const {},
    authenticated: true,
  );

  @override
  Future<void> logout() async {
    final refresh = _activeRefreshToken ?? await _store.read();
    try {
      if (refresh != null && _accessToken != null) {
        await _request(
          'POST',
          'auth/logout/',
          body: {'refresh': refresh},
          authenticated: true,
        );
      }
    } finally {
      _accessToken = null;
      _activeRefreshToken = null;
      await _store.clear();
      await _google.signOut();
    }
  }
}
