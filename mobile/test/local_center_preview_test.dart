import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/json_parsing.dart';
import 'package:floodsense/data/models/nearest_center_result.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_centers_section.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'location_day4_centers_test.dart' show Day4LocationService, Day4Resolver;

Map<String, dynamic> preview({bool empty = false}) => {
  'data_status': 'DEMONSTRATION',
  'centers': empty
      ? <Object?>[]
      : [
          {
            'data_status': 'DEMONSTRATION',
            'public_identifier': '1b7e659e-d095-4a8e-9bb2-90f7a9372fd9',
            'name': 'LOCAL TEST - NOT A REAL FACILITY',
            'address': 'Fictional display-test address',
            'barangay': {'psgc_code': '0402103004', 'name': 'Bayanan'},
            'latitude': 14.406,
            'longitude': 120.966,
            'approximate_distance': 180.5,
            'distance_unit': 'meters',
            'verified_on': null,
            'source_attribution': 'Synthetic test source',
            'limitations': [
              localCenterPreviewWarning,
              nearestCenterReferenceWarning,
              nearestCenterBoundaryLimitation,
            ],
          },
        ],
  'distance_method': nearestCenterDistanceMethod,
  'warnings': [
    localCenterPreviewWarning,
    empty ? nearestCenterEmptyDistanceWarning : nearestCenterDistanceWarning,
  ],
};

http.Response response(Map<String, dynamic> body) => http.Response(
  jsonEncode(body),
  200,
  headers: {'content-type': 'application/json'},
);

void main() {
  test('ordinary parser rejects synthetic envelopes', () {
    expect(
      () => NearestCenterResult.fromJson(preview()),
      throwsA(isA<ModelParsingException>()),
    );
  });

  test(
    'preview preserves null verification and explicit synthetic warnings',
    () {
      final result = NearestCenterResult.fromJson(
        preview(),
        localPreview: true,
      );
      expect(result.isDemonstration, isTrue);
      expect(result.centers.single.isDemonstration, isTrue);
      expect(result.centers.single.verifiedOn, isNull);
      expect(result.centers.single.verificationLabel, contains('not verified'));
      expect(result.warnings.first, localCenterPreviewWarning);
      expect(
        NearestCenterResult.fromJson(
          preview(empty: true),
          localPreview: true,
        ).centers,
        isEmpty,
      );
    },
  );

  for (final defect in ['status', 'date', 'title', 'warning', 'extra']) {
    test('preview rejects unsafe $defect', () {
      final body = preview();
      final center = (body['centers'] as List).single as Map<String, dynamic>;
      switch (defect) {
        case 'status':
          center['data_status'] = 'APPROVED';
        case 'date':
          center['verified_on'] = '2026-10-04';
        case 'title':
          center['name'] = 'Imaginary center';
        case 'warning':
          body['warnings'] = [nearestCenterDistanceWarning];
        case 'extra':
          center['contact_information'] = 'private';
      }
      expect(
        () => NearestCenterResult.fromJson(body, localPreview: true),
        throwsA(isA<ModelParsingException>()),
      );
    });
  }

  test(
    'explicit debug opt-in uses the separate loopback preview endpoint',
    () async {
      late http.Request captured;
      final client = FloodSenseApiClient(
        baseUrl: 'http://127.0.0.1:8000/api/v1',
        localCenterPreview: true,
        client: MockClient((request) async {
          captured = request;
          return response(preview());
        }),
      );
      final result = await client.findNearest(
        latitude: 14.405,
        longitude: 120.965,
      );
      expect(
        captured.url.path,
        '/api/v1/evacuation-centers/local-preview/nearest/',
      );
      expect(result.isDemonstration, isTrue);
      client.close();
    },
  );

  test(
    'preview opt-in cannot send a preview request to a nonlocal backend',
    () async {
      late http.Request captured;
      final client = FloodSenseApiClient(
        baseUrl: 'https://example.test/api/v1',
        localCenterPreview: true,
        client: MockClient((request) async {
          captured = request;
          return response({
            'centers': [],
            'distance_method': nearestCenterDistanceMethod,
            'warnings': [
              nearestCenterEmptyWarning,
              nearestCenterEmptyDistanceWarning,
            ],
          });
        }),
      );
      await client.findNearest(latitude: 14.405, longitude: 120.965);
      expect(captured.url.path, '/api/v1/evacuation-centers/nearest/');
      client.close();
    },
  );

  testWidgets('synthetic center card never claims facility verification', (
    tester,
  ) async {
    final api = FloodSenseApiClient(
      baseUrl: 'http://127.0.0.1:8000/api/v1',
      localCenterPreview: true,
      client: MockClient((_) async => response(preview())),
    );
    final location = LocationController(
      Day4LocationService(),
      resolver: Day4Resolver(),
    );
    final centers = NearestCenterController(location, provider: api);
    await location.resolveManualPin(
      const MapCoordinate(latitude: 14.405, longitude: 120.965),
    );
    location.confirmCandidate();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: NearestCentersSection(controller: centers),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Local test center preview'), findsOneWidget);
    expect(find.text('LOCAL TEST - NOT A REAL FACILITY'), findsOneWidget);
    expect(
      find.text('LOCAL TEST - not verified; not a real facility'),
      findsOneWidget,
    );
    expect(find.textContaining('Verified on'), findsNothing);
    expect(centers.message, contains('not real facilities'));
    await tester.pumpWidget(const SizedBox());
    centers.dispose();
    location.dispose();
    api.close();
  });
}
