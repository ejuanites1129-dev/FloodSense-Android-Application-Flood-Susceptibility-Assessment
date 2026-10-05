import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/center_map_record.dart';
import 'package:floodsense/data/models/center_map_result.dart';
import 'package:floodsense/data/models/json_parsing.dart';
import 'package:floodsense/data/models/nearest_center_result.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/features/evacuation/evacuation_map_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/map/flood_map_presentation.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'location_day3_test.dart'
    show FakeBarangayResolver, FakeDay3LocationService;
import 'location_day4_centers_test.dart'
    show FakeNearestCenterProvider, sampleCenters;

Map<String, dynamic> _row({bool local = false}) => {
  'public_identifier': '00000000-0000-0000-0000-000000000001',
  'name': 'Synthetic test shelter',
  'address': 'Synthetic public address',
  'barangay': <String, dynamic>{'psgc_code': '0402103004', 'name': 'Bayanan'},
  'latitude': 14.406,
  'longitude': 120.966,
  'verified_on': local ? null : '2026-09-01',
  'source_attribution': 'Synthetic reviewed test source',
  'limitations': [
    local ? localCenterPreviewWarning : nearestCenterVerificationLimitation,
    nearestCenterReferenceWarning,
    nearestCenterBoundaryLimitation,
  ],
  if (local) 'data_status': 'DEMONSTRATION',
};

Map<String, dynamic> _envelope({bool local = false, bool empty = false}) => {
  'centers': [if (!empty) _row(local: local)],
  'warnings': [
    if (local) localCenterPreviewWarning,
    if (empty) local ? centerMapLocalEmptyWarning : centerMapEmptyWarning,
    centerMapWarning,
  ],
  'has_more': false,
  if (local) 'data_status': 'DEMONSTRATION',
};

http.Response _json(
  Object body, {
  int status = 200,
  String type = 'application/json; charset=utf-8',
}) => http.Response.bytes(
  utf8.encode(jsonEncode(body)),
  status,
  headers: {'content-type': type},
);

class _MapProvider implements EvacuationMapProvider {
  int calls = 0;
  final coordinates = <MapCoordinate?>[];
  Future<CenterMapResult> Function()? handler;
  @override
  Future<CenterMapResult> fetchMapCenters({MapCoordinate? coordinate}) async {
    calls++;
    coordinates.add(coordinate);
    return handler?.call() ?? CenterMapResult.fromJson(_envelope());
  }
}

void main() {
  test('nearby parser accepts exactly 25 and rejects 26 or inconsistent truncation', () {
    Map<String, dynamic> shortlist(int count, {bool more = false}) => {
      'centers': [
        for (var i = 1; i <= count; i++)
          {
            ..._row(),
            'public_identifier':
                '00000000-0000-0000-0000-${i.toRadixString(16).padLeft(12, '0')}',
          },
      ],
      'warnings': [centerMapWarning, if (more) centerMapNearbyLimitWarning],
      'has_more': more,
    };
    expect(
      CenterMapResult.fromJson(shortlist(25, more: true), nearby: true).centers,
      hasLength(25),
    );
    expect(
      () => CenterMapResult.fromJson(shortlist(26), nearby: true),
      throwsA(isA<ModelParsingException>()),
    );
    expect(
      () => CenterMapResult.fromJson(shortlist(24, more: true), nearby: true),
      throwsA(isA<ModelParsingException>()),
    );
  });

  test('pin-centered catalog sends only transient coordinate JSON, never a URL query', () async {
    late http.Request captured;
    final api = FloodSenseApiClient(
      baseUrl: 'http://example.test/api/v1',
      client: MockClient((request) async {
        captured = request;
        return _json(_envelope());
      }),
    );
    await api.fetchMapCenters(
      coordinate: const MapCoordinate(latitude: 14.406, longitude: 120.966),
    );
    expect(captured.method, 'POST');
    expect(captured.url.path, '/api/v1/evacuation-centers/map/');
    expect(captured.url.query, isEmpty);
    expect(jsonDecode(captured.body), {
      'latitude': 14.406,
      'longitude': 120.966,
    });
    expect(captured.headers['content-type'], 'application/json');
  });

  test(
    'pin changes supersede old requests; same pin and refresh retain origin',
    () async {
      final provider = _MapProvider();
      final first = Completer<CenterMapResult>();
      final second = Completer<CenterMapResult>();
      provider.handler = () =>
          provider.calls == 1 ? first.future : second.future;
      final controller = EvacuationMapController(provider);
      addTearDown(controller.dispose);
      const a = MapCoordinate(latitude: 14.406, longitude: 120.966);
      const b = MapCoordinate(latitude: 14.409, longitude: 120.964);
      final old = controller.load(coordinate: a);
      final current = controller.load(coordinate: b);
      await controller.load(coordinate: b);
      expect(provider.calls, 2);
      second.complete(CenterMapResult.fromJson(_envelope()));
      await current;
      first.complete(CenterMapResult.fromJson(_envelope(empty: true)));
      await old;
      expect(controller.centers, hasLength(1));
      expect(controller.origin, same(b));
      expect(controller.isLoading, isFalse);
      await controller.load(coordinate: b);
      expect(provider.calls, 2);
      provider.handler = null;
      await controller.load(refresh: true);
      expect(provider.calls, 3);
      expect(provider.coordinates.last, same(b));
    },
  );

  test(
    'nearest metadata cannot add hidden centers to an authoritative shortlist',
    () {
      final catalog = CenterMapResult.fromJson(_envelope()).centers;
      final presentation = FloodMapPresentation(
        referenceAreas: const [],
        scenarioAreas: const [],
        scenarioResults: const {},
        mapCenters: catalog,
        centers: sampleCenters(),
        mapCentersAreAuthoritative: true,
        onCoordinateTapped: (_) {},
      );
      expect(presentation.mapMarkers.map((center) => center.publicIdentifier), [
        catalog.single.publicIdentifier,
      ]);
    },
  );

  test('startup catalog has no invented distance or nearest ranking', () {
    final result = CenterMapResult.fromJson(_envelope());
    expect(result.centers.single.distanceLabel, isNull);
    expect(result.centers.single.verificationLabel, 'Verified on 2026-09-01');
    expect(result.hasMore, isFalse);
    expect(result.isDemonstration, isFalse);
    final presentation = FloodMapPresentation(
      referenceAreas: const [],
      scenarioAreas: const [],
      scenarioResults: const {},
      mapCenters: result.centers,
      onCoordinateTapped: (_) {},
    );
    final feature =
        (jsonDecode(presentation.pointGeoJson)['features'] as List).single;
    expect(feature['properties']['nearest'], isFalse);
    expect(feature['properties']['selected'], isFalse);
    expect(feature['properties']['is_demonstration'], isFalse);
    expect(presentation.coordinate, isNull);
  });

  for (final local in [false, true]) {
    for (final empty in [false, true]) {
      test('catalog exact envelope local=$local empty=$empty', () {
        final result = CenterMapResult.fromJson(
          _envelope(local: local, empty: empty),
          localTesting: local,
        );
        expect(result.centers, hasLength(empty ? 0 : 1));
        expect(result.isDemonstration, local);
      });
    }
  }

  final invalid = <String, void Function(Map<String, dynamic>)>{
    'unknown root field': (json) => json['private_note'] = 'secret',
    'unknown center field': (json) => json['centers'][0]['capacity'] = 100,
    'invented distance': (json) =>
        json['centers'][0]['approximate_distance'] = 0,
    'unknown barangay field': (json) =>
        json['centers'][0]['barangay']['id'] = 1,
    'duplicate identifiers': (json) => (json['centers'] as List).add(_row()),
    'noncanonical uuid': (json) =>
        json['centers'][0]['public_identifier'] = 'not-a-uuid',
    'too-long name': (json) => json['centers'][0]['name'] = 'x' * 181,
    'too-long barangay': (json) =>
        json['centers'][0]['barangay']['name'] = 'x' * 161,
    'too-long source': (json) =>
        json['centers'][0]['source_attribution'] = 'x' * 201,
    'invalid date': (json) => json['centers'][0]['verified_on'] = '2026-02-30',
    'year zero': (json) => json['centers'][0]['verified_on'] = '0000-01-01',
    'missing date': (json) => json['centers'][0]['verified_on'] = null,
    'infinite longitude': (json) =>
        json['centers'][0]['longitude'] = double.infinity,
    'latitude out of range': (json) => json['centers'][0]['latitude'] = 91,
    'untrimmed text': (json) => json['centers'][0]['name'] = ' name',
    'control text': (json) => json['centers'][0]['name'] = 'bad\u0000text',
    'nonboolean cap': (json) => json['has_more'] = 1,
    'inconsistent cap': (json) => json['has_more'] = true,
    'wrong warnings': (json) => json['warnings'] = ['Safe route'],
    'missing limitation': (json) => json['centers'][0]['limitations'] = [],
    'duplicate limitation': (json) =>
        (json['centers'][0]['limitations'] as List).add(
          nearestCenterReferenceWarning,
        ),
  };
  for (final entry in invalid.entries) {
    test('rejects ${entry.key} without partial map markers', () {
      final json = _envelope();
      entry.value(json);
      expect(
        () => CenterMapResult.fromJson(json),
        throwsA(isA<ModelParsingException>()),
      );
    });
  }
  test('temporary rows cannot enter the genuine envelope', () {
    expect(
      () => CenterMapResult.fromJson(_envelope(local: true)),
      throwsA(isA<ModelParsingException>()),
    );
    final json = _envelope(local: true);
    json['centers'][0]['verified_on'] = '2026-09-01';
    expect(
      () => CenterMapResult.fromJson(json, localTesting: true),
      throwsA(isA<ModelParsingException>()),
    );
  });

  test('map endpoint is a coordinate-free GET', () async {
    late http.Request captured;
    final api = FloodSenseApiClient(
      baseUrl: 'http://example.test/api/v1',
      client: MockClient((request) async {
        captured = request;
        return _json(_envelope());
      }),
    );
    expect((await api.fetchMapCenters()).centers, hasLength(1));
    expect(captured.method, 'GET');
    expect(captured.url.path, '/api/v1/evacuation-centers/map/');
    expect(captured.url.query, isEmpty);
    expect(captured.body, isEmpty);
  });

  for (final base in [
    'http://127.0.0.1:8000/api/v1',
    'http://example.test/api/v1',
  ]) {
    test('temporary catalog guarded by debug and loopback: $base', () async {
      final api = FloodSenseApiClient(
        baseUrl: base,
        client: MockClient((_) async => _json(_envelope(local: true))),
      );
      if (base.contains('127.0.0.1')) {
        expect((await api.fetchMapCenters()).isDemonstration, isTrue);
      } else {
        await expectLater(
          api.fetchMapCenters(),
          throwsA(
            isA<CenterLookupException>().having(
              (e) => e.kind,
              'kind',
              CenterLookupFailureKind.malformedResponse,
            ),
          ),
        );
      }
    });
  }

  for (final status in [429, 500, 503, 404]) {
    test(
      'map failure status $status is recoverable without leaking response',
      () async {
        final api = FloodSenseApiClient(
          baseUrl: 'http://example.test/api/v1',
          client: MockClient(
            (_) async => _json({'private': 'secret'}, status: status),
          ),
        );
        await expectLater(
          api.fetchMapCenters(),
          throwsA(isA<CenterLookupException>()),
        );
      },
    );
  }
  test('map rejects a JSON-lookalike media type', () async {
    final api = FloodSenseApiClient(
      baseUrl: 'http://example.test/api/v1',
      client: MockClient(
        (_) async => _json(_envelope(), type: 'application/jsonjunk'),
      ),
    );
    await expectLater(
      api.fetchMapCenters(),
      throwsA(
        isA<CenterLookupException>().having(
          (e) => e.kind,
          'kind',
          CenterLookupFailureKind.malformedResponse,
        ),
      ),
    );
  });
  test('map timeout and offline paths have safe failures', () async {
    final slow = FloodSenseApiClient(
      baseUrl: 'http://example.test/api/v1',
      timeout: const Duration(milliseconds: 1),
      client: MockClient((_) => Completer<http.Response>().future),
    );
    await expectLater(
      slow.fetchMapCenters(),
      throwsA(
        isA<CenterLookupException>().having(
          (e) => e.kind,
          'kind',
          CenterLookupFailureKind.timeout,
        ),
      ),
    );
    final offline = FloodSenseApiClient(
      baseUrl: 'http://example.test/api/v1',
      client: MockClient(
        (_) async => throw http.ClientException('private host'),
      ),
    );
    await expectLater(
      offline.fetchMapCenters(),
      throwsA(
        isA<CenterLookupException>().having(
          (e) => e.kind,
          'kind',
          CenterLookupFailureKind.offline,
        ),
      ),
    );
  });

  test(
    'catalog load once and explicit refresh only; selection has no GPS',
    () async {
      final provider = _MapProvider();
      final catalog = EvacuationMapController(provider);
      addTearDown(catalog.dispose);
      await catalog.load();
      await catalog.load();
      expect(provider.calls, 1);
      catalog.selectCenter(catalog.centers.single.publicIdentifier);
      expect(
        catalog.selectedCenterIdentifier,
        catalog.centers.single.publicIdentifier,
      );
      await catalog.load(refresh: true);
      expect(provider.calls, 2);
      expect(catalog.selectedCenterIdentifier, isNull);
    },
  );
  test(
    'failed catalog refresh removes stale eligibility and supports retry',
    () async {
      final provider = _MapProvider();
      final catalog = EvacuationMapController(provider);
      addTearDown(catalog.dispose);
      await catalog.load();
      provider.handler = () async =>
          throw const CenterLookupException(CenterLookupFailureKind.offline);
      await catalog.load(refresh: true);
      expect(catalog.centers, isEmpty);
      expect(catalog.failure, CenterLookupFailureKind.offline);
      provider.handler = null;
      await catalog.load(refresh: true);
      expect(catalog.centers, hasLength(1));
      expect(catalog.failure, isNull);
    },
  );
  test('late catalog response is ignored after disposal', () async {
    final pending = Completer<CenterMapResult>();
    final provider = _MapProvider()..handler = () => pending.future;
    final catalog = EvacuationMapController(provider);
    final loading = catalog.load();
    catalog.dispose();
    pending.complete(CenterMapResult.fromJson(_envelope()));
    await loading;
    expect(catalog.centers, isEmpty);
  });
  test(
    'nearest refresh also refreshes catalog without moving confirmed pin',
    () async {
      final provider = _MapProvider();
      final catalog = EvacuationMapController(provider);
      final location = LocationController(
        FakeDay3LocationService(),
        resolver: FakeBarangayResolver(),
      );
      final nearestProvider = FakeNearestCenterProvider();
      final nearest = NearestCenterController(
        location,
        provider: nearestProvider,
        mapController: catalog,
      );
      addTearDown(location.dispose);
      addTearDown(catalog.dispose);
      addTearDown(nearest.dispose);
      await catalog.load();
      const pin = MapCoordinate(latitude: 14.405, longitude: 120.965);
      await location.resolveManualPin(pin);
      location.confirmCandidate();
      await Future<void>.delayed(Duration.zero);
      expect(nearest.nearestCenterIdentifier, 'public-near');
      await nearest.refresh();
      expect(provider.calls, 2);
      expect(nearestProvider.calls, 2);
      expect(location.lookupCoordinate, same(pin));
    },
  );
  test(
    'nearest wins metadata and dedup, including centers beyond catalog cap',
    () {
      final near = sampleCenters().first;
      final map = CenterMapRecord.fromVerifiedCenter(near);
      final presentation = FloodMapPresentation(
        referenceAreas: const [],
        scenarioAreas: const [],
        scenarioResults: const {},
        onCoordinateTapped: (_) {},
        mapCenters: [map],
        centers: sampleCenters(),
        nearestCenterIdentifier: near.publicIdentifier,
      );
      expect(presentation.mapMarkers, hasLength(2));
      expect(presentation.mapMarkers.first.distanceLabel, near.distanceLabel);
      final features =
          jsonDecode(presentation.pointGeoJson)['features'] as List;
      expect(
        features.where((f) => f['properties']['nearest'] == true),
        hasLength(1),
      );
    },
  );
  test('genuine and temporary map markers never mix on mode switch', () {
    final temporary = CenterMapResult.fromJson(
      _envelope(local: true),
      localTesting: true,
    );
    final presentation = FloodMapPresentation(
      referenceAreas: const [],
      scenarioAreas: const [],
      scenarioResults: const {},
      onCoordinateTapped: (_) {},
      mapCenters: temporary.centers,
      centers: sampleCenters(),
      nearestIsDemonstration: false,
    );
    expect(presentation.mapMarkers, hasLength(2));
    expect(
      presentation.mapMarkers.every((center) => !center.isDemonstration),
      isTrue,
    );
  });
}
