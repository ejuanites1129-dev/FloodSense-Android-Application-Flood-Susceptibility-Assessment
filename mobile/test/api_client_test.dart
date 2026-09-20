import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/config/api_config.dart';
import 'package:floodsense/data/api/api_exception.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/assessment_request.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'test_data.dart';

http.Response jsonResponse(Object body, {int status = 200}) =>
    http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

void main() {
  group('FloodSense API client', () {
    test(
      '12 options request uses correct endpoint and demonstration mode',
      () async {
        late Uri requested;
        final api = FloodSenseApiClient(
          baseUrl: 'http://example.test/api/v1/',
          client: MockClient((request) async {
            requested = request.url;
            return jsonResponse(optionsJson());
          }),
        );

        final result = await api.fetchAssessmentOptions();

        expect(requested.path, '/api/v1/assessment-options/');
        expect(requested.queryParameters, {'mode': 'demonstration'});
        expect(result.warnings.first, 'DEMONSTRATION DATA—NOT OFFICIAL');
      },
    );

    test(
      '13 areas request uses correct endpoint and demonstration mode',
      () async {
        late Uri requested;
        final api = FloodSenseApiClient(
          baseUrl: 'http://example.test/api/v1',
          client: MockClient((request) async {
            requested = request.url;
            return jsonResponse(areaCollectionJson());
          }),
        );

        final result = await api.fetchDemonstrationAreas();

        expect(requested.path, '/api/v1/geography/areas/');
        expect(requested.queryParameters['mode'], 'demonstration');
        expect(result.single.name, 'Demo Zone A');
      },
    );

    test('reference boundaries use the dedicated neutral endpoint', () async {
      late Uri requested;
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient((request) async {
          requested = request.url;
          return jsonResponse(referenceBoundaryCollectionJson());
        }),
      );

      final result = await api.fetchReferenceBoundaries();

      expect(requested.path, '/api/v1/geography/reference-boundaries/');
      expect(requested.queryParameters, isEmpty);
      expect(result.single.name, 'Bayanan');
      expect(result.single.dataStatus, 'PENDING_VALIDATION');
    });

    test('14 assessment POST sends exact expected JSON fields', () async {
      late http.Request captured;
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient((request) async {
          captured = request;
          return jsonResponse(assessmentJson());
        }),
      );

      await api.evaluateAssessment(
        const AssessmentRequest(
          geographicAreaId: 7,
          rainfallIntensityCode: 'DEMO_HEAVY',
          rainfallDurationCode: 'DEMO_6_HOURS',
        ),
      );

      expect(captured.method, 'POST');
      expect(captured.url.path, '/api/v1/assessments/evaluate/');
      expect(jsonDecode(captured.body), {
        'mode': 'demonstration',
        'geographic_area_id': 7,
        'rainfall_intensity_code': 'DEMO_HEAVY',
        'rainfall_duration_code': 'DEMO_6_HOURS',
      });
      expect(captured.headers['content-type'], contains('application/json'));
    });

    test('15 HTTP 400 becomes field-aware validation exception', () async {
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient(
          (_) async => jsonResponse({
            'intensity_code': ['The selected option is unavailable.'],
          }, status: 400),
        ),
      );

      expect(
        api.fetchAssessmentOptions(),
        throwsA(
          isA<ApiException>()
              .having((error) => error.kind, 'kind', ApiFailureKind.validation)
              .having(
                (error) => error.fieldErrors['intensity_code'],
                'field error',
                ['The selected option is unavailable.'],
              ),
        ),
      );
    });

    test('16 HTTP 500 becomes a user-safe service exception', () async {
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient(
          (_) async => jsonResponse({'detail': 'internal'}, status: 500),
        ),
      );

      expect(
        api.fetchAssessmentOptions(),
        throwsA(
          isA<ApiException>()
              .having((error) => error.kind, 'kind', ApiFailureKind.service)
              .having(
                (error) => error.message,
                'message',
                isNot(contains('internal')),
              ),
        ),
      );
    });

    test('17 request timeout becomes connectivity exception', () async {
      final never = Completer<http.Response>();
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        timeout: const Duration(milliseconds: 1),
        client: MockClient((_) => never.future),
      );

      expect(
        api.fetchAssessmentOptions(),
        throwsA(
          isA<ApiException>().having(
            (error) => error.kind,
            'kind',
            ApiFailureKind.timeout,
          ),
        ),
      );
    });

    test('18 connection failure becomes connectivity exception', () async {
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient((_) async => throw http.ClientException('refused')),
      );

      expect(
        api.fetchAssessmentOptions(),
        throwsA(
          isA<ApiException>().having(
            (error) => error.kind,
            'kind',
            ApiFailureKind.connectivity,
          ),
        ),
      );
    });

    test('19 invalid JSON becomes malformed-response exception', () async {
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient((_) async => http.Response('{broken', 200)),
      );

      expect(
        api.fetchAssessmentOptions(),
        throwsA(
          isA<ApiException>().having(
            (error) => error.kind,
            'kind',
            ApiFailureKind.malformedResponse,
          ),
        ),
      );
    });

    test('20 structurally incomplete JSON is handled safely', () async {
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient(
          (_) async => jsonResponse({'warnings': <dynamic>[]}),
        ),
      );

      expect(
        api.fetchAssessmentOptions(),
        throwsA(
          isA<ApiException>().having(
            (error) => error.kind,
            'kind',
            ApiFailureKind.malformedResponse,
          ),
        ),
      );
    });

    test('21 base URL normalization removes all trailing slashes', () {
      expect(
        ApiConfig.normalizeBaseUrl(' http://10.0.2.2:8000/api/v1/// '),
        'http://10.0.2.2:8000/api/v1',
      );
    });

    test(
      'point resolution sends exact latitude and longitude fields',
      () async {
        late http.Request captured;
        final api = FloodSenseApiClient(
          baseUrl: 'http://example.test/api/v1',
          client: MockClient((request) async {
            captured = request;
            return jsonResponse(pointResolutionJson());
          }),
        );

        final result = await api.resolvePoint(
          latitude: 14.005,
          longitude: 120.005,
        );

        expect(captured.url.path, '/api/v1/geography/resolve-point/');
        expect(jsonDecode(captured.body), {
          'mode': 'demonstration',
          'latitude': 14.005,
          'longitude': 120.005,
        });
        expect(result.area?.code, 'DEMO_ZONE_A');
      },
    );

    test('map assessment sends exact scenario fields', () async {
      late http.Request captured;
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient((request) async {
          captured = request;
          return jsonResponse(mapAssessmentJson());
        }),
      );

      final result = await api.evaluateMapScenario(
        intensityCode: 'DEMO_HEAVY',
        durationCode: 'DEMO_6_HOURS',
      );

      expect(captured.url.path, '/api/v1/assessments/evaluate-map/');
      expect(jsonDecode(captured.body), {
        'mode': 'demonstration',
        'rainfall_intensity_code': 'DEMO_HEAVY',
        'rainfall_duration_code': 'DEMO_6_HOURS',
      });
      expect(result.results.single.susceptibility?.code, 'HIGH');
    });

    test('point and map HTTP errors use existing typed behavior', () async {
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient(
          (_) async => jsonResponse({
            'latitude': ['Ensure this value is valid.'],
          }, status: 400),
        ),
      );

      expect(
        api.resolvePoint(latitude: 91, longitude: 120),
        throwsA(
          isA<ApiException>().having(
            (error) => error.kind,
            'kind',
            ApiFailureKind.validation,
          ),
        ),
      );
      expect(
        api.evaluateMapScenario(
          intensityCode: 'UNKNOWN',
          durationCode: 'DEMO_1_HOUR',
        ),
        throwsA(isA<ApiException>()),
      );
    });

    test(
      'barangay resolver uses POST body without coordinate query parameters',
      () async {
        late http.Request captured;
        final api = FloodSenseApiClient(
          baseUrl: 'http://example.test/api/v1',
          client: MockClient((request) async {
            captured = request;
            return jsonResponse(barangayResolutionJson());
          }),
        );

        final result = await api.resolveBarangay(
          latitude: 14.405,
          longitude: 120.965,
        );

        expect(captured.method, 'POST');
        expect(captured.url.path, '/api/v1/geography/resolve-barangay/');
        expect(captured.url.query, isEmpty);
        expect(jsonDecode(captured.body), {
          'latitude': 14.405,
          'longitude': 120.965,
        });
        expect(result.barangay?.psgcCode, '0402103004');
      },
    );

    test('unknown barangay resolver state is a typed malformed response', () {
      final api = FloodSenseApiClient(
        baseUrl: 'http://example.test/api/v1',
        client: MockClient(
          (_) async =>
              jsonResponse(barangayResolutionJson(state: 'UNSUPPORTED_STATE')),
        ),
      );

      expect(
        api.resolveBarangay(latitude: 14.4, longitude: 120.9),
        throwsA(
          isA<ApiException>().having(
            (error) => error.kind,
            'kind',
            ApiFailureKind.malformedResponse,
          ),
        ),
      );
    });

    test(
      'barangay validation failure does not retain raw server details',
      () async {
        final api = FloodSenseApiClient(
          baseUrl: 'http://example.test/api/v1',
          client: MockClient(
            (_) async => jsonResponse({
              'latitude': ['Rejected 14.412345 at /private/server/path.'],
              'longitude': ['Rejected 120.976543.'],
            }, status: 400),
          ),
        );

        try {
          await api.resolveBarangay(latitude: 14.412345, longitude: 120.976543);
          fail('Expected a typed validation failure.');
        } on ApiException catch (error) {
          expect(error.kind, ApiFailureKind.validation);
          expect(
            error.message,
            'The location lookup request was not accepted.',
          );
          expect(error.message, isNot(contains('14.412345')));
          expect(error.message, isNot(contains('120.976543')));
          expect(error.message, isNot(contains('/private/server/path')));
          expect(error.fieldErrors, isEmpty);
        }
      },
    );
  });
}
