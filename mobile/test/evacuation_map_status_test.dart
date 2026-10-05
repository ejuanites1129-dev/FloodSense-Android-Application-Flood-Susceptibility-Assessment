import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/center_map_record.dart';
import 'package:floodsense/data/models/center_map_result.dart';
import 'package:floodsense/data/models/nearest_center_result.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/models/verified_center.dart';
import 'package:floodsense/features/evacuation/evacuation_map_controller.dart';
import 'package:floodsense/features/evacuation/evacuation_map_status.dart';
import 'package:floodsense/features/evacuation/nearest_center_provider.dart';

class _Provider implements EvacuationMapProvider {
  int calls = 0;
  Future<CenterMapResult> Function()? handler;

  @override
  Future<CenterMapResult> fetchMapCenters({MapCoordinate? coordinate}) async {
    calls++;
    return handler?.call() ?? _result();
  }
}

CenterMapResult _result({bool empty = false}) => CenterMapResult(
  centers: empty
      ? []
      : [
          CenterMapRecord(
            publicIdentifier: '00000000-0000-4000-8000-000000000001',
            name: 'Synthetic test shelter',
            address: 'Synthetic address',
            barangay: CenterBarangayIdentity(
              psgcCode: '0402103004',
              name: 'Bayanan',
            ),
            latitude: 14.405,
            longitude: 120.965,
            verifiedOn: null,
            sourceAttribution: 'Synthetic test source',
            limitations: [localCenterPreviewWarning],
            isDemonstration: true,
          ),
        ],
  warnings: [
    localCenterPreviewWarning,
    if (empty) centerMapLocalEmptyWarning,
    centerMapWarning,
  ],
  hasMore: false,
  isDemonstration: true,
);

void main() {
  testWidgets(
    'compact map status keeps limitation, refresh and record labels',
    (tester) async {
      final provider = _Provider();
      final controller = EvacuationMapController(provider);
      addTearDown(controller.dispose);
      await controller.load(
        coordinate: const MapCoordinate(latitude: 14.405, longitude: 120.965),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: EvacuationMapStatus(controller: controller)),
        ),
      );
      expect(find.textContaining('Local test shelter icons'), findsNothing);
      expect(find.text(localCenterPreviewWarning), findsNothing);
      expect(
        find.text(
          'This map does not confirm that a center is open, available, reachable, or safe.',
        ),
        findsOneWidget,
      );
      expect(controller.centers.single.isDemonstration, isTrue);
      expect(
        controller.centers.single.limitations,
        contains(localCenterPreviewWarning),
      );
      expect(controller.warnings, contains(localCenterPreviewWarning));
      await tester.tap(find.byKey(const Key('refresh-evacuation-map')));
      await tester.pumpAndSettle();
      expect(provider.calls, 2);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('map status still shows loading, failure and empty recovery', (
    tester,
  ) async {
    final provider = _Provider();
    final controller = EvacuationMapController(provider);
    addTearDown(controller.dispose);
    await controller.load(
      coordinate: const MapCoordinate(latitude: 14.405, longitude: 120.965),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: EvacuationMapStatus(controller: controller)),
      ),
    );
    final pending = Completer<CenterMapResult>();
    provider.handler = () => pending.future;
    final request = controller.load(refresh: true);
    await tester.pump();
    expect(find.text('Loading evacuation-center map icons…'), findsOneWidget);
    expect(find.byKey(const Key('refresh-evacuation-map')), findsNothing);
    pending.completeError(
      const CenterLookupException(CenterLookupFailureKind.recoverable),
    );
    await request;
    await tester.pump();
    expect(find.textContaining('could not be loaded'), findsOneWidget);
    expect(find.text('Retry map centers'), findsOneWidget);
    provider.handler = () async => _result(empty: true);
    await tester.tap(find.byKey(const Key('refresh-evacuation-map')));
    await tester.pumpAndSettle();
    expect(find.text(centerMapLocalEmptyWarning), findsWidgets);
    expect(find.textContaining('This map does not confirm'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
