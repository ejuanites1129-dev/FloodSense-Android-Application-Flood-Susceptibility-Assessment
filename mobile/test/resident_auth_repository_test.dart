import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/auth/resident_auth_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'resident_test_fakes.dart';

Map<String, dynamic> sessionJson({String refresh = 'refresh-1'}) => {
  'access': 'access-1',
  'refresh': refresh,
  'user': {
    'id': 1,
    'username': 'resident',
    'email': 'resident@example.com',
    'email_verified': true,
    'password_login_available': true,
    'linked_providers': <String>[],
  },
  'setup': {'stage': 'authenticated_ready'},
};

class FakeGoogleProvider implements GoogleIdentityProvider {
  String? token = 'google-id-token';
  bool signedOut = false;
  @override
  Future<String?> authenticate() async => token;
  @override
  Future<void> signOut() async {
    signedOut = true;
  }
}

void main() {
  test('unknown setup stages fail closed', () {
    expect(
      setupStageFromWire('unexpected_server_stage'),
      SetupStage.configurationRequired,
    );
  });

  test(
    'Remember Me off clears storage and on stores only refresh token',
    () async {
      final store = MemoryRefreshTokenStore();
      final client = MockClient(
        (_) async => http.Response(jsonEncode(sessionJson()), 200),
      );
      final repository = HttpResidentAuthRepository(
        client: client,
        tokenStore: store,
        googleProvider: FakeGoogleProvider(),
        baseUrl: 'http://example.test/api/v1',
      );
      await repository.login(
        identifier: 'resident',
        password: 'secret',
        rememberMe: false,
      );
      expect(store.value, isNull);
      expect(store.clears, 1);
      await repository.login(
        identifier: 'resident',
        password: 'secret',
        rememberMe: true,
      );
      expect(store.value, 'refresh-1');
      expect(repository.accessToken, 'access-1');
    },
  );

  test('restoration exchanges and rotates stored refresh token', () async {
    final store = MemoryRefreshTokenStore()..value = 'stored-refresh';
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/auth/token/refresh/')) {
        expect(jsonDecode(request.body)['refresh'], 'stored-refresh');
        return http.Response(
          jsonEncode({'access': 'new-access', 'refresh': 'rotated-refresh'}),
          200,
        );
      }
      if (request.url.path.endsWith('/account/me/')) {
        return http.Response(jsonEncode(sessionJson()['user']), 200);
      }
      return http.Response(jsonEncode({'stage': 'authenticated_ready'}), 200);
    });
    final repository = HttpResidentAuthRepository(
      client: client,
      tokenStore: store,
      googleProvider: FakeGoogleProvider(),
      baseUrl: 'http://example.test/api/v1',
    );
    final session = await repository.restore();
    expect(session, isNotNull);
    expect(store.value, 'rotated-refresh');
    expect(repository.accessToken, 'new-access');
  });

  test(
    'failed restoration and logout clear all local authentication material',
    () async {
      final failedStore = MemoryRefreshTokenStore()..value = 'revoked';
      final failed = HttpResidentAuthRepository(
        client: MockClient((_) async => http.Response('{}', 401)),
        tokenStore: failedStore,
        googleProvider: FakeGoogleProvider(),
        baseUrl: 'http://example.test/api/v1',
      );
      expect(await failed.restore(), isNull);
      expect(failedStore.value, isNull);

      final store = MemoryRefreshTokenStore();
      final google = FakeGoogleProvider();
      final repository = HttpResidentAuthRepository(
        client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/login/')) {
            return http.Response(jsonEncode(sessionJson()), 200);
          }
          return http.Response('', 204);
        }),
        tokenStore: store,
        googleProvider: google,
        baseUrl: 'http://example.test/api/v1',
      );
      await repository.login(
        identifier: 'resident',
        password: 'secret',
        rememberMe: true,
      );
      await repository.logout();
      expect(store.value, isNull);
      expect(repository.accessToken, isNull);
      expect(google.signedOut, isTrue);
    },
  );
}
