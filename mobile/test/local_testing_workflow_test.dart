import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';
import 'package:floodsense/features/evacuation/nearest_centers_section.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:http/testing.dart';

import 'local_center_preview_test.dart' show preview, response;
import 'location_day4_centers_test.dart';

void main() {
  test(
    'normal debug loopback endpoint reads labeled tests without a preview flag',
    () async {
      final body = preview();
      (body['centers'] as List).first['name'] = 'Temporary training location';
      final api = FloodSenseApiClient(
        baseUrl: 'http://127.0.0.1:8000/api/v1',
        client: MockClient((request) async {
          expect(request.url.path, '/api/v1/evacuation-centers/nearest/');
          return response(body);
        }),
      );
      final result = await api.findNearest(
        latitude: 14.405,
        longitude: 120.965,
      );
      expect(result.isDemonstration, isTrue);
      expect(result.centers.single.name, 'Temporary training location');
      expect(result.centers.single.verifiedOn, isNull);
      api.close();
    },
  );

  test(
    'nonlocal endpoint cannot supply temporary records to the ordinary app',
    () async {
      final api = FloodSenseApiClient(
        baseUrl: 'https://example.test/api/v1',
        client: MockClient((_) async => response(preview())),
      );
      await expectLater(
        api.findNearest(latitude: 14.405, longitude: 120.965),
        throwsA(
          isA<CenterLookupException>().having(
            (error) => error.kind,
            'failure kind',
            CenterLookupFailureKind.malformedResponse,
          ),
        ),
      );
      api.close();
    },
  );

  test(
    'manual refresh preserves pin and prevents duplicate requests',
    () async {
      final location = LocationController(
        Day4LocationService(),
        resolver: Day4Resolver(),
      );
      final provider = FakeNearestCenterProvider()
        ..handler = (_, _) async => [];
      final centers = NearestCenterController(location, provider: provider);
      await acquireAndConfirm(location);
      expect(centers.phase, NearestCenterPhase.empty);
      final coordinate = location.lookupCoordinate;
      final barangay = location.confirmedBarangay;
      final state = location.state;
      final pending = Completer<List<Never>>();
      provider.handler = (_, _) => pending.future;
      final refresh = centers.refresh();
      expect(centers.phase, NearestCenterPhase.loading);
      expect(centers.canRefresh, isFalse);
      await centers.refresh();
      expect(provider.calls, 2);
      pending.complete([]);
      await refresh;
      provider.handler = (_, _) async => sampleCenters();
      await centers.refresh();
      expect(centers.centers.length, 2);
      expect(location.lookupCoordinate, same(coordinate));
      expect(location.confirmedBarangay, same(barangay));
      expect(location.state, same(state));
      expect(provider.latitude, coordinate!.latitude);
      expect(provider.longitude, coordinate.longitude);
      centers.dispose();
      location.dispose();
    },
  );

  test(
    'late refresh cannot restore old results after location changes',
    () async {
      final location = LocationController(
        Day4LocationService(),
        resolver: Day4Resolver(),
      );
      final provider = FakeNearestCenterProvider();
      final centers = NearestCenterController(location, provider: provider);
      await acquireAndConfirm(location);
      final pending = Completer<List<Never>>();
      provider.handler = (_, _) => pending.future;
      final refresh = centers.refresh();
      await location.resolveManualPin(
        const MapCoordinate(latitude: 14.408, longitude: 120.968),
      );
      pending.complete([]);
      await refresh;
      expect(centers.centers, isEmpty);
      expect(centers.canRefresh, isFalse);
      expect(centers.phase, NearestCenterPhase.waitingForLocationConfirmation);
      centers.dispose();
      location.dispose();
    },
  );

  testWidgets('ordinary center section exposes an explicit refresh button', (
    tester,
  ) async {
    final location = LocationController(
      Day4LocationService(),
      resolver: Day4Resolver(),
    );
    final provider = FakeNearestCenterProvider()..handler = (_, _) async => [];
    final centers = NearestCenterController(location, provider: provider);
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
    final button = find.byKey(const Key('nearest-centers-refresh'));
    expect(button, findsOneWidget);
    provider.handler = (_, _) async => sampleCenters();
    await tester.ensureVisible(button);
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(provider.calls, 2);
    expect(centers.centers.length, 2);
    await tester.pumpWidget(const SizedBox());
    centers.dispose();
    location.dispose();
  });
}
