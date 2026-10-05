import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/data/auth/resident_auth_repository.dart';
import 'package:floodsense/data/dss/structured_dss_repository.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/center_map_record.dart';
import 'package:floodsense/data/models/center_map_result.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/geojson_geometry.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/models/verified_center.dart';
import 'package:floodsense/features/assessment/widgets/reference_boundary_map_card.dart';
import 'package:floodsense/features/assessment/widgets/zone_selector.dart';
import 'package:floodsense/features/evacuation/evacuation_center_marker.dart';
import 'package:floodsense/features/evacuation/evacuation_map_controller.dart';
import 'package:floodsense/features/home/hybrid_map_surface.dart';
import 'package:floodsense/features/location/barangay_reference_point.dart';
import 'package:floodsense/features/location/location_controller.dart';

import 'location_day3_test.dart' show FakeDay3LocationService;
import 'location_day4_centers_test.dart' show FakeNearestCenterProvider;
import 'resident_test_fakes.dart';
import 'test_data.dart';

const _catalogOnlyId = '11111111-1111-4111-8111-111111111111';
const _secondCatalogId = '22222222-2222-4222-8222-222222222222';

CenterMapRecord _catalogCenter(
  String identifier,
  String name,
  double latitude,
) => CenterMapRecord(
  publicIdentifier: identifier,
  name: name,
  address: 'Synthetic test address',
  barangay: CenterBarangayIdentity(psgcCode: '0402103004', name: 'Bayanan'),
  latitude: latitude,
  longitude: 120.964,
  verifiedOn: DateTime.utc(2026, 10, 5),
  sourceAttribution: 'Synthetic test source',
  limitations: const ['Synthetic automated test fixture, not a real facility.'],
);

final class _CatalogProvider implements EvacuationMapProvider {
  int calls = 0;
  final coordinates = <MapCoordinate?>[];

  @override
  Future<CenterMapResult> fetchMapCenters({MapCoordinate? coordinate}) async {
    calls++;
    coordinates.add(coordinate);
    return CenterMapResult(
      centers: [
        _catalogCenter(_catalogOnlyId, 'Synthetic catalog shelter A', 14.407),
        _catalogCenter(_secondCatalogId, 'Synthetic catalog shelter B', 14.409),
      ],
      warnings: const [centerMapWarning],
      hasMore: false,
    );
  }
}

final class _DssRepository implements StructuredDssRepository {
  int startCalls = 0;
  int answerCalls = 0;

  @override
  Future<DssStep> start(
    String susceptibilityCode, {
    required String operatingMode,
  }) async {
    startCalls++;
    throw StateError(
      'Tailored DSS must not start without a classified assessment.',
    );
  }

  @override
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String operatingMode,
    required String optionCode,
  }) async {
    answerCalls++;
    throw StateError('No tailored DSS answer is expected in these tests.');
  }
}

Future<void> _pumpApp(
  WidgetTester tester, {
  required FakeResidentAuthRepository auth,
  required _CatalogProvider catalog,
  required FakeDay3LocationService gps,
  required FakeNearestCenterProvider nearest,
  FakeFloodSenseApi? api,
  _DssRepository? dss,
}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    FloodSenseApp(
      api: api ?? FakeFloodSenseApi(),
      authRepository: auth,
      dssRepository: dss ?? _DssRepository(),
      locationService: gps,
      nearestCenterProvider: nearest,
      evacuationMapProvider: catalog,
      enableResidentAuthentication: true,
      showBasemap: false,
    ),
  );
  await tester.pumpAndSettle();
}

HybridMapSurface _surface(WidgetTester tester) =>
    tester.widget<HybridMapSurface>(
      find.byKey(const Key('resident-hybrid-map'), skipOffstage: false),
    );

MapController _mapController(WidgetTester tester) => tester
    .widget<FlutterMap>(find.byType(FlutterMap, skipOffstage: false))
    .mapController!;

Future<void> _scrollPrepareTo(WidgetTester tester, Finder finder) async {
  await tester.scrollUntilVisible(
    finder,
    220,
    scrollable: find.descendant(
      of: find.byKey(const Key('prepare-empty-state')),
      matching: find.byType(Scrollable),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'legacy barangay selector synchronizes its interior map pin without GPS',
    (tester) async {
      final first = sampleReferenceAreas().single;
      final second = GeographicArea(
        id: 102,
        code: 'PSGC_0402103007',
        name: 'Dulong Bayan',
        areaType: 'BARANGAY',
        dataStatus: 'PENDING_VALIDATION',
        geometry: GeoJsonGeometry.fromJson({
          'type': 'Polygon',
          'coordinates': [
            [
              [120.98, 14.42],
              [120.99, 14.42],
              [120.99, 14.43],
              [120.98, 14.43],
              [120.98, 14.42],
            ],
          ],
        }),
      );
      final gps = FakeDay3LocationService();
      final nearest = FakeNearestCenterProvider();
      final api = FakeFloodSenseApi(
        areas: [first, second],
        referenceAreas: [first, second],
      );
      await tester.pumpWidget(
        FloodSenseApp(
          api: api,
          locationService: gps,
          nearestCenterProvider: nearest,
          enableResidentAuthentication: false,
          showBasemap: false,
        ),
      );
      await tester.pumpAndSettle();
      final selector = find.descendant(
        of: find.byType(ZoneSelector),
        matching: find.byType(DropdownButtonFormField<GeographicArea>),
      );
      final scrollable = find.descendant(
        of: find.byKey(const Key('assessment-scroll-view')),
        matching: find.byType(Scrollable),
      );
      MapCoordinate? previous;
      for (final area in [first, second]) {
        await tester.scrollUntilVisible(selector, 300, scrollable: scrollable);
        await tester.pumpAndSettle();
        await tester.tap(selector);
        await tester.pumpAndSettle();
        await tester.tap(find.text('${area.name} (${area.code})').last);
        await tester.pumpAndSettle();
        final map = tester.widget<ReferenceBoundaryMapCard>(
          find.byType(ReferenceBoundaryMapCard),
        );
        final location = map.locationController!;
        final point = location.lookupCoordinate!;
        expect(
          BarangayReferencePoint.containsInterior(area.geometry, point),
          isTrue,
        );
        expect(
          location.coordinateOrigin,
          LocationCoordinateOrigin.barangayReference,
        );
        expect(location.confirmedBarangay!.geographicAreaCode, area.code);
        expect(map.controller.selectedArea!.code, area.code);
        expect(
          map.nearestCenterController!.distanceOriginLabel,
          contains('approximate point inside'),
        );
        expect(nearest.latitude, point.latitude);
        expect(nearest.longitude, point.longitude);
        final renderedPin = tester
            .widgetList<MarkerLayer>(find.byType(MarkerLayer))
            .expand((layer) => layer.markers)
            .singleWhere(
              (marker) =>
                  marker.key == const Key('temporary-location-map-marker'),
            );
        expect(renderedPin.point.latitude, point.latitude);
        expect(renderedPin.point.longitude, point.longitude);
        if (previous != null) {
          expect(point.latitude, isNot(previous.latitude));
          expect(point.longitude, isNot(previous.longitude));
        }
        previous = point;
      }
      expect(nearest.calls, 2);
      expect(gps.permissionRequests, 0);
      expect(gps.acquisitions, 0);
      expect(api.barangayCalls, 0);
      expect(api.pointCalls, 0);
      expect(api.evaluateCalls, 0);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'signed-in onboarding still withholds catalog until setup is ready',
    (tester) async {
      final auth = FakeResidentAuthRepository()
        ..restoration = testSession(SetupStage.awaitingOnboarding);
      final catalog = _CatalogProvider();
      final gps = FakeDay3LocationService();
      final nearest = FakeNearestCenterProvider();
      await _pumpApp(
        tester,
        auth: auth,
        catalog: catalog,
        gps: gps,
        nearest: nearest,
      );
      expect(find.byKey(const Key('onboarding-continue')), findsOneWidget);
      expect(find.byKey(const Key('resident-hybrid-map')), findsNothing);
      expect(catalog.calls, 0);
      expect(nearest.calls, 0);
      expect(gps.permissionRequests, 0);
      expect(gps.acquisitions, 0);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'catalog loads only after authenticatedReady and shows icons without GPS',
    (tester) async {
      final auth = FakeResidentAuthRepository();
      final catalog = _CatalogProvider();
      final gps = FakeDay3LocationService();
      final nearest = FakeNearestCenterProvider();
      final api = FakeFloodSenseApi();
      await _pumpApp(
        tester,
        auth: auth,
        catalog: catalog,
        gps: gps,
        nearest: nearest,
        api: api,
      );
      expect(find.text('Resident sign in'), findsOneWidget);
      expect(catalog.calls, 0);
      expect(find.byType(EvacuationCenterMarker), findsNothing);

      await tester.enterText(
        find.byKey(const Key('login-identifier')),
        'resident',
      );
      await tester.enterText(
        find.byKey(const Key('login-password')),
        'SyntheticTestPassword1!',
      );
      await tester.ensureVisible(find.byKey(const Key('sign-in-button')));
      await tester.tap(find.byKey(const Key('sign-in-button')));
      await tester.pumpAndSettle();

      expect(catalog.calls, 1);
      expect(find.byType(EvacuationCenterMarker), findsNWidgets(2));
      expect(catalog.coordinates.single, isNotNull);
      final bounds = _surface(tester)
          .controller
          .referenceAreas
          .single
          .geometry
          .allPoints;
      final latitude = bounds
          .map((point) => point.latitude)
          .reduce((a, b) => a < b ? a : b);
      final north = bounds
          .map((point) => point.latitude)
          .reduce((a, b) => a > b ? a : b);
      expect(catalog.coordinates.single!.latitude, (latitude + north) / 2);
      expect(
        find.byKey(const Key('evacuation-shelter-icon')),
        findsNWidgets(2),
      );
      expect(_surface(tester).locationController!.lookupCoordinate, isNull);
      expect(nearest.calls, 0);
      expect(gps.permissionRequests, 0);
      expect(gps.acquisitions, 0);
      expect(api.barangayCalls, 0);
      expect(api.pointCalls, 0);
      expect(api.evaluateCalls, 0);
      for (final marker in tester.widgetList<EvacuationCenterMarker>(
        find.byType(EvacuationCenterMarker),
      )) {
        expect(marker.isNearest, isFalse);
      }
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'navigation and sheet interactions retain catalog and exact camera',
    (tester) async {
      final auth = FakeResidentAuthRepository()
        ..restoration = testSession(SetupStage.authenticatedReady);
      final catalog = _CatalogProvider();
      final gps = FakeDay3LocationService();
      final nearest = FakeNearestCenterProvider();
      await _pumpApp(
        tester,
        auth: auth,
        catalog: catalog,
        gps: gps,
        nearest: nearest,
      );
      final retainedMap = find.byKey(
        const Key('resident-hybrid-map'),
        skipOffstage: false,
      );
      final originalState = tester.state(retainedMap);
      await tester.tap(find.byTooltip('Zoom in'));
      await tester.pumpAndSettle();
      final camera = _mapController(tester).camera;
      final latitude = camera.center.latitude;
      final longitude = camera.center.longitude;
      final zoom = camera.zoom;

      await tester.tap(find.byTooltip('Map legend'));
      await tester.pumpAndSettle();
      expect(
        find.text('Unclassified / insufficient data\nOutside Bacoor coverage'),
        findsOneWidget,
      );
      expect(find.text('Moderate'), findsOneWidget);
      await tester.tapAt(const Offset(300, 750));
      await tester.pumpAndSettle();
      expect(_mapController(tester).camera.zoom, zoom);
      expect(catalog.calls, 1);

      for (final destination in ['prepare', 'assess', 'profile', 'assess']) {
        await tester.tap(find.byKey(Key('resident-nav-$destination')));
        await tester.pumpAndSettle();
        expect(tester.state(retainedMap), same(originalState));
        expect(
          TickerMode.valuesOf(tester.element(retainedMap)).enabled,
          destination != 'profile',
        );
        expect(_mapController(tester).camera.center.latitude, latitude);
        expect(_mapController(tester).camera.center.longitude, longitude);
        expect(_mapController(tester).camera.zoom, zoom);
      }
      await tester.tap(find.byKey(const Key('resident-sheet-collapse-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('resident-sheet-expand-tab')));
      await tester.pumpAndSettle();
      await tester.drag(
        find.byKey(const Key('resident-sheet-handle')),
        const Offset(0, -120),
      );
      await tester.pumpAndSettle();
      expect(_mapController(tester).camera.center.latitude, latitude);
      expect(_mapController(tester).camera.center.longitude, longitude);
      expect(_mapController(tester).camera.zoom, zoom);
      expect(catalog.calls, 1);
      expect(nearest.calls, 0);
      expect(gps.acquisitions, 0);
      expect(gps.permissionRequests, 0);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'catalog-only icon selection never moves user pin or starts a lookup',
    (tester) async {
      final auth = FakeResidentAuthRepository()
        ..restoration = testSession(SetupStage.authenticatedReady);
      final catalog = _CatalogProvider();
      final gps = FakeDay3LocationService();
      final nearest = FakeNearestCenterProvider();
      final api = FakeFloodSenseApi();
      await _pumpApp(
        tester,
        auth: auth,
        catalog: catalog,
        gps: gps,
        nearest: nearest,
        api: api,
      );
      final surface = _surface(tester);
      final location = surface.locationController!;
      const pin = MapCoordinate(latitude: 14.405, longitude: 120.965);
      await location.resolveManualPin(pin);
      location.confirmCandidate();
      await tester.pumpAndSettle();
      expect(nearest.calls, 1);
      final nearestCalls = nearest.calls;
      final catalogCalls = catalog.calls;
      expect(catalogCalls, 2); // Startup midpoint, then the chosen map pin.
      expect(catalog.coordinates.last, same(pin));
      final barangayCalls = api.barangayCalls;
      final pointCalls = api.pointCalls;
      final markerFinder = find.byKey(const ValueKey(_catalogOnlyId));
      expect(markerFinder, findsOneWidget);
      await tester.tap(markerFinder);
      await tester.pumpAndSettle();

      expect(
        surface.evacuationMapController!.selectedCenterIdentifier,
        _catalogOnlyId,
      );
      expect(location.lookupCoordinate, same(pin));
      expect(location.confirmedBarangay!.psgcCode, '0402103004');
      expect(nearest.calls, nearestCalls);
      expect(api.barangayCalls, barangayCalls);
      expect(api.pointCalls, pointCalls);
      expect(gps.acquisitions, 0);
      expect(gps.permissionRequests, 0);
      expect(catalog.calls, catalogCalls);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Prepare exposes nearest distance before classification without opening DSS',
    (tester) async {
      final auth = FakeResidentAuthRepository()
        ..restoration = testSession(SetupStage.authenticatedReady);
      final catalog = _CatalogProvider();
      final gps = FakeDay3LocationService();
      final nearest = FakeNearestCenterProvider();
      final api = FakeFloodSenseApi();
      final dss = _DssRepository();
      await _pumpApp(
        tester,
        auth: auth,
        catalog: catalog,
        gps: gps,
        nearest: nearest,
        api: api,
        dss: dss,
      );
      final location = _surface(tester).locationController!;
      await location.selectManualBarangay(
        BarangayIdentity(psgcCode: '0402103004', name: 'Bayanan'),
        geometry: _surface(tester).controller.referenceAreas.single.geometry,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('resident-nav-prepare')));
      await tester.pumpAndSettle();
      expect(find.text('Assessment required'), findsOneWidget);
      expect(api.evaluateCalls, 0);
      expect(_surface(tester).controller.result, isNull);
      final summary = find.byKey(const Key('nearest-center-distance-summary'));
      await _scrollPrepareTo(tester, summary);
      expect(summary, findsOneWidget);
      expect(find.text('Nearest: Synthetic Near Center'), findsOneWidget);
      expect(
        find.text('Distance: 180 m approximate straight-line distance'),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('nearest-center-distance-origin')),
        findsOneWidget,
      );
      expect(
        find.textContaining('approximate point inside the selected barangay'),
        findsOneWidget,
      );
      expect(nearest.calls, 1);
      expect(gps.acquisitions, 0);
      expect(gps.permissionRequests, 0);
      expect(dss.startCalls, 0);
      expect(dss.answerCalls, 0);
      expect(find.byKey(const Key('dss-flow-view')), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}
