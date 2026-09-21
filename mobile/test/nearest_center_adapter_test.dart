import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/json_parsing.dart';
import 'package:floodsense/data/models/nearest_center_result.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

http.Response _jsonResponse(Object body, {int status = 200}) =>
    http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

Map<String, Object?> _center({
  String identifier = '1b7e659e-d095-4a8e-9bb2-90f7a9372fd9',
  String verifiedOn = '2026-09-01',
}) => {
  'public_identifier': identifier,
  'name': 'Authorized Test Center',
  'address': 'Authorized public address',
  'barangay': {'psgc_code': '0402103004', 'name': 'Bayanan'},
  'latitude': 14.406,
  'longitude': 120.966,
  'approximate_distance': 180.5,
  'distance_unit': 'meters',
  'verified_on': verifiedOn,
  'source_attribution': 'Authorized test source',
  'limitations': const [
    nearestCenterVerificationLimitation,
    nearestCenterReferenceWarning,
    nearestCenterBoundaryLimitation,
  ],
};

Map<String, Object?> _populatedEnvelope() => {
  'centers': [_center()],
  'distance_method': nearestCenterDistanceMethod,
  'warnings': const [nearestCenterDistanceWarning],
};

Map<String, Object?> _emptyEnvelope() => {
  'centers': <Object?>[],
  'distance_method': nearestCenterDistanceMethod,
  'warnings': const [
    nearestCenterEmptyWarning,
    nearestCenterEmptyDistanceWarning,
  ],
};

void main() {
  group('nearest-center response envelope', () {
    test('parses every frozen populated field and preserves service order', () {
      final second = _center(identifier: '1ea27816-0b3a-4ad7-a811-2ab28528505f')
        ..['approximate_distance'] = 450.0;
      final envelope = _populatedEnvelope();
      envelope['centers'] = [_center(), second];

      final result = NearestCenterResult.fromJson(envelope);

      expect(result.distanceMethod, nearestCenterDistanceMethod);
      expect(result.warnings, [nearestCenterDistanceWarning]);
      expect(result.centers.map((center) => center.publicIdentifier), [
        '1b7e659e-d095-4a8e-9bb2-90f7a9372fd9',
        '1ea27816-0b3a-4ad7-a811-2ab28528505f',
      ]);
      expect(result.centers.first.approximateDistance, 180.5);
      expect(result.centers.first.verifiedOn, DateTime.utc(2026, 9, 1));
    });

    test('accepts only the exact honest empty envelope', () {
      final result = NearestCenterResult.fromJson(_emptyEnvelope());

      expect(result.centers, isEmpty);
      expect(result.warnings, [
        nearestCenterEmptyWarning,
        nearestCenterEmptyDistanceWarning,
      ]);
    });

    test('rejects unknown fields, malformed IDs, and impossible dates', () {
      final extra = _emptyEnvelope()..['unexpected'] = true;
      expect(
        () => NearestCenterResult.fromJson(extra),
        throwsA(isA<ModelParsingException>()),
      );

      final badId = _populatedEnvelope();
      badId['centers'] = [_center(identifier: 'internal-id')];
      expect(
        () => NearestCenterResult.fromJson(badId),
        throwsA(isA<ModelParsingException>()),
      );

      final badDate = _populatedEnvelope();
      badDate['centers'] = [_center(verifiedOn: '2026-02-30')];
      expect(
        () => NearestCenterResult.fromJson(badDate),
        throwsA(isA<ModelParsingException>()),
      );
    });

    test('rejects altered safety vocabulary and limit violations', () {
      final warning = _populatedEnvelope();
      warning['warnings'] = ['Nearest means safest.'];
      expect(
        () => NearestCenterResult.fromJson(warning),
        throwsA(isA<ModelParsingException>()),
      );

      final limitations = _populatedEnvelope();
      final center = _center();
      center['limitations'] = [nearestCenterVerificationLimitation];
      limitations['centers'] = [center];
      expect(
        () => NearestCenterResult.fromJson(limitations),
        throwsA(isA<ModelParsingException>()),
      );

      final tooMany = _populatedEnvelope();
      tooMany['centers'] = [_center(), _center()];
      expect(
        () => NearestCenterResult.fromJson(tooMany, requestedLimit: 1),
        throwsA(isA<ModelParsingException>()),
      );
    });
  });

  group('nearest-center HTTP adapter', () {
    test(
      'posts coordinates in JSON and maps the honest empty response',
      () async {
        late http.Request captured;
        final api = FloodSenseApiClient(
          baseUrl: 'http://example.test/api/v1',
          client: MockClient((request) async {
            captured = request;
            return _jsonResponse(_emptyEnvelope());
          }),
        );

        final result = await api.findNearest(
          latitude: 14.405,
          longitude: 120.965,
        );

        expect(captured.method, 'POST');
        expect(captured.url.path, '/api/v1/evacuation-centers/nearest/');
        expect(captured.url.query, isEmpty);
        expect(jsonDecode(captured.body), {
          'latitude': 14.405,
          'longitude': 120.965,
          'limit': 3,
        });
        expect(result.centers, isEmpty);
        expect(result.warnings, hasLength(2));
      },
    );

    test(
      'maps malformed success, request rejection, and server failure',
      () async {
        Future<CenterLookupFailureKind> failureFor(
          http.Response Function() response,
        ) async {
          final api = FloodSenseApiClient(
            baseUrl: 'http://example.test/api/v1',
            client: MockClient((_) async => response()),
          );
          try {
            await api.findNearest(latitude: 14.405, longitude: 120.965);
            fail('Expected center lookup failure.');
          } on CenterLookupException catch (error) {
            return error.kind;
          }
        }

        expect(
          await failureFor(() => http.Response('{broken', 200)),
          CenterLookupFailureKind.malformedResponse,
        );
        expect(
          await failureFor(() => _jsonResponse({'detail': 'bad'}, status: 415)),
          CenterLookupFailureKind.requestRejected,
        );
        expect(
          await failureFor(
            () => _jsonResponse({'detail': 'hidden'}, status: 503),
          ),
          CenterLookupFailureKind.serverUnavailable,
        );
      },
    );

    test('429 retains Retry-After without retrying', () async {
      var calls = 0;
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient((_) async {
          calls++;
          return http.Response(
            '{}',
            429,
            headers: {'content-type': 'application/json', 'retry-after': '30'},
          );
        }),
      );

      await expectLater(
        api.findNearest(latitude: 14.405, longitude: 120.965),
        throwsA(
          isA<CenterLookupException>()
              .having(
                (error) => error.kind,
                'kind',
                CenterLookupFailureKind.rateLimited,
              )
              .having(
                (error) => error.retryAfter,
                'retryAfter',
                const Duration(seconds: 30),
              ),
        ),
      );
      expect(calls, 1);
    });

    test('timeout and connection failure are typed without retries', () async {
      var timeoutCalls = 0;
      final never = Completer<http.Response>();
      final timeoutApi = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        timeout: const Duration(milliseconds: 1),
        client: MockClient((_) {
          timeoutCalls++;
          return never.future;
        }),
      );
      await expectLater(
        timeoutApi.findNearest(latitude: 14.405, longitude: 120.965),
        throwsA(
          isA<CenterLookupException>().having(
            (error) => error.kind,
            'kind',
            CenterLookupFailureKind.timeout,
          ),
        ),
      );
      expect(timeoutCalls, 1);

      final offlineApi = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient(
          (_) async => throw http.ClientException('private network detail'),
        ),
      );
      await expectLater(
        offlineApi.findNearest(latitude: 14.405, longitude: 120.965),
        throwsA(
          isA<CenterLookupException>().having(
            (error) => error.kind,
            'kind',
            CenterLookupFailureKind.offline,
          ),
        ),
      );
    });
  });
}
