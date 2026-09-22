import 'package:floodsense/data/auth/resident_auth_repository.dart';

const testUser = ResidentUser(
  id: 1,
  username: 'resident',
  email: 'resident@example.com',
  emailVerified: true,
  passwordLoginAvailable: true,
  linkedProviders: [],
);

AuthSession testSession(SetupStage stage) => AuthSession(
  user: testUser,
  stage: stage,
  accessToken: 'access-token-for-test',
  refreshToken: 'refresh-token-for-test',
);

class FakeResidentAuthRepository implements ResidentAuthRepository {
  AuthSession? restoration;
  AuthSession loginSession = testSession(SetupStage.authenticatedReady);
  AuthSession? googleSession = testSession(SetupStage.authenticatedReady);
  ResidentAuthException? googleError;
  bool requireGoogleUsername = false;
  String? googleUsername;
  bool loginRememberMe = false;
  bool logoutCalled = false;
  bool registerCalled = false;
  bool resetRequested = false;
  bool preferencesSaved = false;
  String? lastUsername;

  final documents = const [
    LegalDocument(
      id: 11,
      type: 'TERMS',
      version: '1',
      title: 'Terms of Use',
      summary: 'Current terms.',
      prototypeDraft: false,
      reviewNotice: '',
      sections: [
        LegalSection(
          title: 'Scenario limitations',
          summary: 'Not live weather.',
          body: 'FloodSense is scenario-based and is not an official warning.',
        ),
      ],
    ),
    LegalDocument(
      id: 12,
      type: 'PRIVACY',
      version: '1',
      title: 'Privacy Policy',
      summary: 'Current privacy policy.',
      prototypeDraft: false,
      reviewNotice: '',
      sections: [
        LegalSection(
          title: 'Foreground GPS',
          summary: 'Temporary location only.',
          body: 'Precise coordinates are not account preferences.',
        ),
      ],
    ),
  ];

  @override
  String? get accessToken => 'access-token-for-test';

  @override
  Future<AuthSession?> restore() async => restoration;

  @override
  Future<AuthSession> login({
    required String identifier,
    required String password,
    required bool rememberMe,
  }) async {
    loginRememberMe = rememberMe;
    return loginSession;
  }

  @override
  Future<void> register({
    required String username,
    required String email,
    required String password,
  }) async {
    registerCalled = true;
  }

  @override
  Future<AuthSession?> googleSignIn({String? username}) async {
    googleUsername = username;
    if (requireGoogleUsername && (username == null || username.isEmpty)) {
      throw const ResidentAuthException(
        'Choose a resident username to finish setup.',
        code: 'username_required',
      );
    }
    if (googleError case final error?) throw error;
    return googleSession;
  }

  @override
  Future<void> requestPasswordReset(String email) async {
    resetRequested = true;
  }

  @override
  Future<void> confirmPasswordReset({
    required String uid,
    required String token,
    required String password,
  }) async {}

  @override
  Future<void> verifyEmail(String token) async {}

  @override
  Future<void> resendVerification(String email) async {}

  @override
  Future<List<LegalDocument>> requiredLegalDocuments() async => documents;

  @override
  Future<SetupStage> setupStatus() async => SetupStage.authenticatedReady;

  @override
  Future<LegalDocument> publicLegalDocument(String type) async =>
      documents.firstWhere(
        (document) => document.type.toLowerCase() == type.toLowerCase(),
      );

  @override
  Future<SetupStage> acceptLegal(List<int> ids) async =>
      SetupStage.awaitingOnboarding;

  @override
  Future<OnboardingContent> onboarding() async => const OnboardingContent(
    version: '1',
    steps: [
      (title: 'What FloodSense does', body: 'Scenario-based support.'),
      (title: 'Hypothetical rainfall scenario', body: 'Not live weather.'),
      (title: 'Location', body: 'Foreground only.'),
      (title: 'Map and susceptibility', body: 'Source limitations.'),
      (title: 'Decision support', body: 'Does not change classification.'),
      (title: 'Evacuation centers', body: 'Nearest does not prove safety.'),
      (title: 'Official information', body: 'Follow official authorities.'),
    ],
  );

  @override
  Future<SetupStage> acknowledgeOnboarding(String version) async =>
      SetupStage.authenticatedReady;

  @override
  Future<ResidentUser> account() async => testUser;

  @override
  Future<ResidentUser> updateUsername(String username) async {
    lastUsername = username;
    return ResidentUser(
      id: testUser.id,
      username: username,
      email: testUser.email,
      emailVerified: true,
      passwordLoginAvailable: true,
      linkedProviders: const [],
    );
  }

  @override
  Future<Map<String, dynamic>> preferences() async => {
    'home_barangay': null,
    'default_rainfall_intensity': null,
    'default_rainfall_duration': null,
    'high_contrast': false,
    'reduce_motion': false,
  };

  @override
  Future<Map<String, dynamic>> updatePreferences(
    Map<String, dynamic> values,
  ) async {
    preferencesSaved = true;
    return values;
  }

  @override
  Future<void> changePassword(
    String currentPassword,
    String newPassword,
  ) async {}

  @override
  Future<ResidentUser> linkGoogle(String password) async => testUser;

  @override
  Future<ResidentUser> unlinkGoogle(String password) async => testUser;

  @override
  Future<void> requestDeletion() async {}

  @override
  Future<void> logout() async {
    logoutCalled = true;
  }
}

class MemoryRefreshTokenStore implements RefreshTokenStore {
  String? value;
  int writes = 0;
  int clears = 0;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String token) async {
    value = token;
    writes++;
  }

  @override
  Future<void> clear() async {
    value = null;
    clears++;
  }
}
