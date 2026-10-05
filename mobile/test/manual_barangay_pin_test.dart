import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/geojson_geometry.dart';
import 'package:floodsense/data/models/nearest_center_result.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';
import 'package:floodsense/features/location/barangay_reference_point.dart';
import 'package:floodsense/features/location/location_card.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/location/location_flow_state.dart';
import 'package:floodsense/features/location/location_service.dart';

import 'test_data.dart';

class FakeDay3LocationService implements LocationService {
  int acquisitions = 0;
  int permissionRequests = 0;
  Completer<TemporaryLocation>? completer;
  TemporaryLocation location = TemporaryLocation(
    latitude: 14.405,
    longitude: 120.965,
    accuracyMeters: 12,
    acquiredAt: DateTime.utc(2026, 10, 5),
  );

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) {
    acquisitions++;
    return completer?.future ?? Future.value(location);
  }

  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.foregroundGranted;

  @override
  Future<void> clearTemporaryState() async {}

  @override
  void dispose() {}

  @override
  Future<bool> isLocationServiceEnabled() async => true;

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;

  @override
  Future<LocationPermissionState> requestForegroundPermission() async {
    permissionRequests++;
    return LocationPermissionState.foregroundGranted;
  }
}

class FakeBarangayResolver implements BarangayResolver {
  int calls = 0;
  double? latitude;
  double? longitude;
  Future<BarangayResolution> Function(double, double)? handler;

  @override
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  }) {
    calls++;
    this.latitude = latitude;
    this.longitude = longitude;
    return handler?.call(latitude, longitude) ??
        Future.value(sampleBarangayResolution());
  }
}

class FakeNearestCenterProvider implements NearestCenterProvider {
  int calls = 0;
  double? latitude;
  double? longitude;

  @override
  Future<NearestCenterResult> findNearest({
    required double latitude,
    required double longitude,
  }) async {
    calls++;
    this.latitude = latitude;
    this.longitude = longitude;
    return NearestCenterResult(
      centers: [],
      distanceMethod: nearestCenterDistanceMethod,
      warnings: [nearestCenterEmptyWarning, nearestCenterEmptyDistanceWarning],
    );
  }
}

Future<void> acquire(LocationController controller) async {
  controller.showPurposeExplanation();
  await controller.continueAfterPurposeExplanation();
}

BarangayIdentity _barangay() =>
    BarangayIdentity(psgcCode: '0402103004', name: 'Bayanan');

GeographicArea _area() =>
    GeographicArea.listFromFeatureCollection(referenceBoundaryCollectionJson())
        .single;

void main() {
  test(
    'manual selection gives a labeled interior pin without accessing GPS',
    () async {
      final service = FakeDay3LocationService();
      final resolver = FakeBarangayResolver();
      final location = LocationController(service, resolver: resolver);
      final provider = FakeNearestCenterProvider();
      final centers = NearestCenterController(location, provider: provider);
      addTearDown(location.dispose);
      addTearDown(centers.dispose);

      await location.selectManualBarangay(
        _barangay(),
        geometry: _area().geometry,
      );
      await Future<void>.delayed(Duration.zero);

      expect(location.state.phase, LocationFlowPhase.confirmed);
      expect(location.confirmedBarangay?.psgcCode, '0402103004');
      expect(
        location.coordinateOrigin,
        LocationCoordinateOrigin.barangayReference,
      );
      expect(location.isApproximateCoordinate, isTrue);
      expect(
        location.coordinateDescription,
        contains('not your actual location'),
      );
      expect(
        BarangayReferencePoint.containsInterior(
          _area().geometry,
          location.lookupCoordinate!,
        ),
        isTrue,
      );
      expect(location.temporaryLocation, isNull);
      expect(service.permissionRequests, 0);
      expect(service.acquisitions, 0);
      expect(resolver.calls, 0);
      expect(provider.calls, 1);
      expect(provider.latitude, location.lookupCoordinate!.latitude);
      expect(provider.longitude, location.lookupCoordinate!.longitude);
      expect(centers.phase, NearestCenterPhase.empty);
    },
  );

  test(
    'GPS follows exact acquired coordinates rather than rounded resolver echo',
    () async {
      final service = FakeDay3LocationService()
        ..location = TemporaryLocation(
          latitude: 14.405123456,
          longitude: 120.965987654,
          accuracyMeters: 12,
          acquiredAt: DateTime.utc(2026, 10, 5),
        );
      final resolver = FakeBarangayResolver();
      final location = LocationController(service, resolver: resolver);
      addTearDown(location.dispose);

      await acquire(location);
      final point = location.lookupCoordinate!;
      location.confirmCandidate();
      expect(point.latitude, service.location.latitude);
      expect(point.longitude, service.location.longitude);
      expect(location.lookupCoordinate, same(point));
      expect(location.coordinateOrigin, LocationCoordinateOrigin.deviceGps);
      expect(location.isApproximateCoordinate, isFalse);
      expect(resolver.latitude, service.location.latitude);
      expect(resolver.longitude, service.location.longitude);
    },
  );

  test(
    'manual reselection keeps confirmed precise GPS and manual pins',
    () async {
      for (final useGps in [true, false]) {
        final service = FakeDay3LocationService();
        final location = LocationController(
          service,
          resolver: FakeBarangayResolver(),
        );
        addTearDown(location.dispose);
        if (useGps) {
          await acquire(location);
        } else {
          await location.resolveManualPin(
            const MapCoordinate(latitude: 14.4042, longitude: 120.9668),
          );
        }
        location.confirmCandidate();
        final point = location.lookupCoordinate;
        final origin = location.coordinateOrigin;
        await location.selectManualBarangay(
          _barangay(),
          geometry: _area().geometry,
        );
        expect(location.lookupCoordinate, same(point));
        expect(location.coordinateOrigin, origin);
        expect(location.isApproximateCoordinate, isFalse);
      }
    },
  );

  test(
    'switching a manual reference to GPS stays explicit and confirmable',
    () async {
      final service = FakeDay3LocationService();
      final location = LocationController(
        service,
        resolver: FakeBarangayResolver(),
      );
      addTearDown(location.dispose);
      await location.selectManualBarangay(
        _barangay(),
        geometry: _area().geometry,
      );
      expect(location.isApproximateCoordinate, isTrue);
      expect(service.acquisitions, 0);

      location.showPurposeExplanation();
      expect(service.acquisitions, 0);
      await location.continueAfterPurposeExplanation();
      expect(service.acquisitions, 1);
      expect(location.lookupCoordinate!.latitude, service.location.latitude);
      expect(location.lookupCoordinate!.longitude, service.location.longitude);
      expect(location.coordinateOrigin, LocationCoordinateOrigin.deviceGps);
      expect(location.isApproximateCoordinate, isFalse);
      expect(location.state.phase, LocationFlowPhase.resolvedCandidate);
      expect(location.confirmedBarangay, isNull);
      location.confirmCandidate();
      expect(location.state.phase, LocationFlowPhase.confirmed);
      expect(service.acquisitions, 1);

      await location.selectManualBarangay(
        BarangayIdentity(psgcCode: '0402103007', name: 'Dulong Bayan'),
        geometry: _area().geometry,
      );
      expect(location.temporaryLocation, isNull);
      expect(location.isApproximateCoordinate, isTrue);
      expect(service.acquisitions, 1);
    },
  );

  test('missing or degenerate geometry never invents a coordinate', () async {
    final location = LocationController(FakeDay3LocationService());
    addTearDown(location.dispose);
    await location.selectManualBarangay(_barangay());
    expect(location.lookupCoordinate, isNull);
    expect(location.coordinateOrigin, isNull);
    await location.selectManualBarangay(
      _barangay(),
      geometry: GeoJsonGeometry.fromJson({
        'type': 'Polygon',
        'coordinates': [
          [
            [0, 0],
            [1, 0],
            [2, 0],
            [0, 0],
          ],
        ],
      }),
    );
    expect(location.lookupCoordinate, isNull);
    expect(location.confirmedBarangay?.psgcCode, '0402103004');
  });

  test(
    'drag refinement replaces approximate origin and resolves the new point',
    () async {
      final resolver = FakeBarangayResolver();
      final location = LocationController(
        FakeDay3LocationService(),
        resolver: resolver,
      );
      addTearDown(location.dispose);
      await location.selectManualBarangay(
        _barangay(),
        geometry: _area().geometry,
      );
      const refined = MapCoordinate(latitude: 14.4042, longitude: 120.9668);
      await location.resolveManualPin(refined);
      expect(location.lookupCoordinate, same(refined));
      expect(location.coordinateOrigin, LocationCoordinateOrigin.manualPin);
      expect(location.isApproximateCoordinate, isFalse);
      expect(location.confirmedBarangay, isNull);
      expect(location.state.phase, LocationFlowPhase.resolvedCandidate);
      location.confirmCandidate();
      expect(location.lookupCoordinate, same(refined));
    },
  );

  test(
    'late GPS and resolution responses cannot overwrite manual reference pin',
    () async {
      final service = FakeDay3LocationService()
        ..completer = Completer<TemporaryLocation>();
      final location = LocationController(
        service,
        resolver: FakeBarangayResolver(),
      );
      addTearDown(location.dispose);
      final acquiring = acquire(location);
      await Future<void>.delayed(Duration.zero);
      await location.selectManualBarangay(
        _barangay(),
        geometry: _area().geometry,
      );
      final reference = location.lookupCoordinate;
      service.completer!.complete(service.location);
      await acquiring;
      expect(location.lookupCoordinate, same(reference));
      expect(
        location.coordinateOrigin,
        LocationCoordinateOrigin.barangayReference,
      );

      final pending = Completer<BarangayResolution>();
      final resolver = FakeBarangayResolver()
        ..handler = (_, _) => pending.future;
      final second = LocationController(
        FakeDay3LocationService(),
        resolver: resolver,
      );
      addTearDown(second.dispose);
      final resolving = second.resolveManualPin(
        const MapCoordinate(latitude: 14.4042, longitude: 120.9668),
      );
      await Future<void>.delayed(Duration.zero);
      await second.selectManualBarangay(
        _barangay(),
        geometry: _area().geometry,
      );
      final selected = second.lookupCoordinate;
      pending.complete(sampleBarangayResolution());
      await resolving;
      expect(second.lookupCoordinate, same(selected));
      expect(second.resolution, isNull);
      expect(second.state.phase, LocationFlowPhase.confirmed);
      expect(second.isApproximateCoordinate, isTrue);
    },
  );

  test('clear cancel reset and dispose remove coordinate origin', () async {
    for (final action in ['clear', 'cancel', 'reset', 'dispose']) {
      final location = LocationController(FakeDay3LocationService());
      await location.selectManualBarangay(
        _barangay(),
        geometry: _area().geometry,
      );
      switch (action) {
        case 'clear':
          await location.clearLocation();
        case 'cancel':
          await location.cancel();
        case 'reset':
          await location.reset();
        case 'dispose':
          location.dispose();
      }
      expect(location.lookupCoordinate, isNull);
      expect(location.coordinateOrigin, isNull);
      expect(location.isApproximateCoordinate, isFalse);
      if (action != 'dispose') location.dispose();
    }
  });

  testWidgets(
    'manual selector passes geometry and labels reference point visibly',
    (tester) async {
      final location = LocationController(FakeDay3LocationService());
      addTearDown(location.dispose);
      final area = _area();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: LocationCard(controller: location, barangays: [area]),
            ),
          ),
        ),
      );
      tester
          .widget<DropdownButtonFormField<GeographicArea>>(
            find.byType(DropdownButtonFormField<GeographicArea>),
          )
          .onChanged!(area);
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('approximate-barangay-reference-point')),
        findsOneWidget,
      );
      expect(find.text('Approximate barangay reference point'), findsOneWidget);
      expect(
        find.bySemanticsLabel(RegExp('not your actual location')),
        findsOneWidget,
      );
      expect(location.lookupCoordinate, isNotNull);
      expect(find.byKey(const Key('use-my-location-button')), findsOneWidget);
      expect(find.byKey(const Key('clear-location-button')), findsOneWidget);
    },
  );
}
