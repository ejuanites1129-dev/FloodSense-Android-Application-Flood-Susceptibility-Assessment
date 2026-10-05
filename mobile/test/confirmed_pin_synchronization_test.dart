import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/models/verified_center.dart';
import 'package:floodsense/features/assessment/assessment_controller.dart';
import 'package:floodsense/features/assessment/widgets/reference_boundary_map_card.dart';
import 'package:floodsense/features/evacuation/nearest_center_controller.dart';
import 'package:floodsense/features/home/hybrid_map_surface.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/location/location_flow_state.dart';
import 'package:floodsense/features/map/provider_aware_flood_map.dart';

import 'location_day3_test.dart'
    show FakeBarangayResolver, FakeDay3LocationService;
import 'location_day4_centers_test.dart'
    show FakeNearestCenterProvider, sampleCenters;
import 'test_data.dart';

const _pin = MapCoordinate(latitude: 14.405, longitude: 120.965);

BarangayIdentity _sameBarangay() =>
    BarangayIdentity(psgcCode: '0402103004', name: 'Bayanan');

BarangayIdentity _differentBarangay() =>
    BarangayIdentity(psgcCode: '0402103007', name: 'Dulong Bayan');

Future<void> _confirmPin(LocationController location) async {
  await location.resolveManualPin(_pin);
  location.confirmCandidate();
  await Future<void>.delayed(Duration.zero);
}

void main() {
  test('same confirmed barangay retains pin, centers and selection without a request', () async {
    final service = FakeDay3LocationService();
    final resolver = FakeBarangayResolver();
    final location = LocationController(service, resolver: resolver);
    final provider = FakeNearestCenterProvider();
    final centers = NearestCenterController(location, provider: provider);
    addTearDown(location.dispose);
    addTearDown(centers.dispose);

    await _confirmPin(location);
    centers.selectCenter('public-near');
    final clearCalls = service.clearCalls;
    final resolution = location.resolution;

    await location.selectManualBarangay(_sameBarangay());
    await Future<void>.delayed(Duration.zero);

    expect(location.state.phase, LocationFlowPhase.confirmed);
    expect(location.lookupCoordinate, same(_pin));
    expect(location.resolution, same(resolution));
    expect(centers.phase, NearestCenterPhase.resultsAvailable);
    expect(centers.centers, hasLength(2));
    expect(centers.selectedCenterIdentifier, 'public-near');
    expect(provider.calls, 1);
    expect(resolver.calls, 1);
    expect(service.clearCalls, clearCalls);
    expect(service.permissionRequests, 0);
    expect(service.acquisitions, 0);
  });

  test('same confirmed GPS barangay retains temporary accuracy without reacquiring', () async {
    final service = FakeDay3LocationService();
    final resolver = FakeBarangayResolver();
    final location = LocationController(service, resolver: resolver);
    final provider = FakeNearestCenterProvider();
    final centers = NearestCenterController(location, provider: provider);
    addTearDown(location.dispose);
    addTearDown(centers.dispose);

    location.showPurposeExplanation();
    await location.continueAfterPurposeExplanation();
    location.confirmCandidate();
    await Future<void>.delayed(Duration.zero);
    final coordinate = location.lookupCoordinate;
    final temporary = location.temporaryLocation;

    await location.selectManualBarangay(_sameBarangay());

    expect(location.lookupCoordinate, same(coordinate));
    expect(location.temporaryLocation, same(temporary));
    expect(location.temporaryLocation?.accuracyMeters, 18);
    expect(centers.phase, NearestCenterPhase.resultsAvailable);
    expect(provider.calls, 1);
    expect(resolver.calls, 1);
    expect(service.permissionRequests, 1);
    expect(service.acquisitions, 1);
    expect(service.clearCalls, 0);
  });

  test(
    'manual choice cannot silently confirm an unconfirmed candidate pin',
    () async {
      final location = LocationController(
        FakeDay3LocationService(),
        resolver: FakeBarangayResolver(),
      );
      final provider = FakeNearestCenterProvider();
      final centers = NearestCenterController(location, provider: provider);
      addTearDown(location.dispose);
      addTearDown(centers.dispose);

      await location.resolveManualPin(_pin);
      expect(location.state.phase, LocationFlowPhase.resolvedCandidate);
      await location.selectManualBarangay(_sameBarangay());

      expect(location.lookupCoordinate, isNull);
      expect(location.resolution, isNull);
      expect(centers.phase, NearestCenterPhase.coordinateRequired);
      expect(provider.calls, 0);
    },
  );

  test('different barangay clears the coordinate and discards an outstanding center response', () async {
    final location = LocationController(
      FakeDay3LocationService(),
      resolver: FakeBarangayResolver(),
    );
    final response = Completer<List<VerifiedCenter>>();
    final provider = FakeNearestCenterProvider()
      ..handler = (_, _) => response.future;
    final centers = NearestCenterController(location, provider: provider);
    addTearDown(location.dispose);
    addTearDown(centers.dispose);

    await _confirmPin(location);
    expect(centers.phase, NearestCenterPhase.loading);
    await location.selectManualBarangay(_differentBarangay());
    response.complete(sampleCenters());
    await Future<void>.delayed(Duration.zero);

    expect(location.confirmedBarangay?.psgcCode, '0402103007');
    expect(location.lookupCoordinate, isNull);
    expect(location.temporaryLocation, isNull);
    expect(location.resolution, isNull);
    expect(centers.phase, NearestCenterPhase.coordinateRequired);
    expect(centers.centers, isEmpty);
    expect(centers.selectedCenterIdentifier, isNull);
    expect(provider.calls, 1);
  });

  test(
    'same confirmed barangay keeps an outstanding center request valid',
    () async {
      final location = LocationController(
        FakeDay3LocationService(),
        resolver: FakeBarangayResolver(),
      );
      final response = Completer<List<VerifiedCenter>>();
      final provider = FakeNearestCenterProvider()
        ..handler = (_, _) => response.future;
      final centers = NearestCenterController(location, provider: provider);
      addTearDown(location.dispose);
      addTearDown(centers.dispose);

      await _confirmPin(location);
      expect(centers.phase, NearestCenterPhase.loading);
      await location.selectManualBarangay(_sameBarangay());
      expect(centers.phase, NearestCenterPhase.loading);
      response.complete(sampleCenters());
      await Future<void>.delayed(Duration.zero);

      expect(location.lookupCoordinate, same(_pin));
      expect(centers.phase, NearestCenterPhase.resultsAvailable);
      expect(centers.centers, hasLength(2));
      expect(provider.calls, 1);
    },
  );

  test(
    'reselecting the same barangay does not manufacture a coordinate',
    () async {
      final location = LocationController(
        FakeDay3LocationService(),
        resolver: FakeBarangayResolver(),
      );
      final provider = FakeNearestCenterProvider();
      final centers = NearestCenterController(location, provider: provider);
      addTearDown(location.dispose);
      addTearDown(centers.dispose);

      await location.selectManualBarangay(_sameBarangay());
      await location.selectManualBarangay(_sameBarangay());

      expect(location.lookupCoordinate, isNull);
      expect(centers.phase, NearestCenterPhase.coordinateRequired);
      expect(provider.calls, 0);
    },
  );

  for (final hybrid in [true, false]) {
    final surfaceName = hybrid
        ? 'shared resident map'
        : 'reference boundary map';

    Widget mapSurface(
      AssessmentController assessment, {
      LocationController? location,
      NearestCenterController? centers,
    }) => MaterialApp(
      home: Scaffold(
        body: hybrid
            ? HybridMapSurface(
                controller: assessment,
                locationController: location,
                nearestCenterController: centers,
                showBasemap: false,
              )
            : SingleChildScrollView(
                child: ReferenceBoundaryMapCard(
                  controller: assessment,
                  locationController: location,
                  nearestCenterController: centers,
                  showBasemap: false,
                ),
              ),
      ),
    );

    testWidgets('$surfaceName uses the same coordinate as the center lookup', (
      tester,
    ) async {
      final assessment = AssessmentController(FakeFloodSenseApi());
      final location = LocationController(
        FakeDay3LocationService(),
        resolver: FakeBarangayResolver(),
      );
      final provider = FakeNearestCenterProvider();
      final centers = NearestCenterController(location, provider: provider);
      addTearDown(assessment.dispose);
      addTearDown(location.dispose);
      addTearDown(centers.dispose);

      await assessment.load();
      await assessment.loadReferenceBoundaries();
      await assessment.placePin(_pin);
      await tester.pumpWidget(
        mapSurface(assessment, location: location, centers: centers),
      );
      await location.resolveManualPin(_pin);
      location.confirmCandidate();
      await tester.pumpAndSettle();

      ProviderAwareFloodMap map() => tester.widget<ProviderAwareFloodMap>(
        find.byType(ProviderAwareFloodMap),
      );
      expect(map().presentation.coordinate, same(_pin));
      expect(map().presentation.centers, hasLength(2));

      await location.selectManualBarangay(_sameBarangay());
      await tester.pumpAndSettle();
      expect(map().presentation.coordinate, same(_pin));
      expect(map().presentation.centers, hasLength(2));
      expect(provider.calls, 1);

      await location.selectManualBarangay(_differentBarangay());
      await tester.pumpAndSettle();
      // The legacy assessment cache must not resurrect a managed location.
      expect(assessment.pinCoordinate, same(_pin));
      expect(map().presentation.coordinate, isNull);
      expect(map().presentation.centers, isEmpty);
      expect(jsonDecode(map().presentation.pointGeoJson)['features'], isEmpty);
      final markers = tester
          .widgetList<MarkerLayer>(find.byType(MarkerLayer))
          .expand((layer) => layer.markers);
      expect(markers, isEmpty);
      expect(find.byTooltip('Recenter on temporary point'), findsNothing);
      expect(centers.phase, NearestCenterPhase.coordinateRequired);

      await location.resolveManualPin(_pin);
      location.confirmCandidate();
      await tester.pumpAndSettle();
      expect(map().presentation.coordinate, same(_pin));
      expect(map().presentation.centers, hasLength(2));
      expect(provider.calls, 2);

      await location.clearLocation();
      await tester.pumpAndSettle();
      expect(map().presentation.coordinate, isNull);
      expect(map().presentation.centers, isEmpty);
      expect(jsonDecode(map().presentation.pointGeoJson)['features'], isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
    });

    testWidgets(
      '$surfaceName retains the pin fallback when no location controller exists',
      (tester) async {
        final assessment = AssessmentController(FakeFloodSenseApi());
        addTearDown(assessment.dispose);
        await assessment.load();
        await assessment.loadReferenceBoundaries();
        await assessment.placePin(_pin);

        await tester.pumpWidget(mapSurface(assessment));
        await tester.pumpAndSettle();

        final map = tester.widget<ProviderAwareFloodMap>(
          find.byType(ProviderAwareFloodMap),
        );
        expect(map.presentation.coordinate, same(_pin));
        await tester.pumpWidget(const SizedBox.shrink());
      },
    );
  }
}
