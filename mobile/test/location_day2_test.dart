import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/app/floodsense_app.dart';
import 'package:floodsense/features/location/location_card.dart';
import 'package:floodsense/features/location/location_controller.dart';
import 'package:floodsense/features/location/location_flow_state.dart';
import 'package:floodsense/features/location/location_service.dart';

import 'test_data.dart';

class FakeDay2LocationService implements LocationService {
  bool serviceEnabled = true;
  LocationPermissionState checkedPermission =
      LocationPermissionState.notRequested;
  LocationPermissionState requestedPermission =
      LocationPermissionState.foregroundGranted;
  TemporaryLocation location = TemporaryLocation(
    latitude: 14.41,
    longitude: 120.97,
    accuracyMeters: 12,
    acquiredAt: DateTime.utc(2026, 9, 19),
  );
  Object? acquisitionError;
  Completer<TemporaryLocation>? acquisitionCompleter;
  int serviceChecks = 0;
  int permissionChecks = 0;
  int permissionRequests = 0;
  int acquisitions = 0;
  int clearCalls = 0;
  int appSettingsCalls = 0;
  int locationSettingsCalls = 0;
  bool locationSettingsOpened = true;
  bool disposed = false;

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) async {
    acquisitions++;
    if (acquisitionError case final error?) throw error;
    if (acquisitionCompleter case final completer?) return completer.future;
    return location;
  }

  @override
  Future<LocationPermissionState> checkPermission() async {
    permissionChecks++;
    return checkedPermission;
  }

  @override
  Future<void> clearTemporaryState() async {
    clearCalls++;
  }

  @override
  void dispose() {
    disposed = true;
  }

  @override
  Future<bool> isLocationServiceEnabled() async {
    serviceChecks++;
    return serviceEnabled;
  }

  @override
  Future<bool> openAppSettings() async {
    appSettingsCalls++;
    return true;
  }

  @override
  Future<bool> openLocationSettings() async {
    locationSettingsCalls++;
    return locationSettingsOpened;
  }

  @override
  Future<LocationPermissionState> requestForegroundPermission() async {
    permissionRequests++;
    return requestedPermission;
  }
}

Future<void> pumpLocationCard(
  WidgetTester tester,
  LocationController controller,
) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(body: LocationCard(controller: controller)),
    ),
  );
  await tester.pump();
}

Future<void> beginAndContinue(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('use-my-location-button')));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('location-purpose-continue')));
  await tester.pumpAndSettle();
}

void main() {
  group('Day 2 location controller', () {
    test('does not inspect or request permission during construction', () {
      final service = FakeDay2LocationService();
      final controller = LocationController(service);

      expect(controller.state.phase, LocationFlowPhase.initial);
      expect(service.serviceChecks, 0);
      expect(service.permissionChecks, 0);
      expect(service.permissionRequests, 0);
      expect(service.acquisitions, 0);
      controller.dispose();
    });

    test(
      'granted permission retains exactly one acceptable coordinate',
      () async {
        final service = FakeDay2LocationService();
        final controller = LocationController(service);

        controller.showPurposeExplanation();
        await controller.continueAfterPurposeExplanation();

        expect(service.permissionRequests, 1);
        expect(service.acquisitions, 1);
        expect(controller.state.phase, LocationFlowPhase.acquired);
        expect(controller.hasTemporaryLocation, isTrue);
        controller.dispose();
      },
    );

    test('already granted permission does not prompt again', () async {
      final service = FakeDay2LocationService()
        ..checkedPermission = LocationPermissionState.foregroundGranted;
      final controller = LocationController(service);

      controller.showPurposeExplanation();
      await controller.continueAfterPurposeExplanation();

      expect(service.permissionRequests, 0);
      expect(service.acquisitions, 1);
      controller.dispose();
    });

    test(
      'denied, permanent denial, and disabled service stay recoverable',
      () async {
        final cases = <(FakeDay2LocationService, LocationFlowPhase, int)>[
          (
            FakeDay2LocationService()
              ..requestedPermission = LocationPermissionState.denied,
            LocationFlowPhase.permissionDenied,
            1,
          ),
          (
            FakeDay2LocationService()
              ..requestedPermission = LocationPermissionState.deniedPermanently,
            LocationFlowPhase.permissionDeniedPermanently,
            1,
          ),
          (
            FakeDay2LocationService()..serviceEnabled = false,
            LocationFlowPhase.serviceDisabled,
            0,
          ),
        ];
        for (final (service, expected, requestCount) in cases) {
          final controller = LocationController(service);
          controller.showPurposeExplanation();
          await controller.continueAfterPurposeExplanation();

          expect(controller.state.phase, expected);
          expect(controller.state.manualSelectionAvailable, isTrue);
          expect(service.permissionRequests, requestCount);
          expect(service.acquisitions, 0);
          controller.dispose();
        }
      },
    );

    test(
      'disabled-service retry opens settings and retries once on return',
      () async {
        final service = FakeDay2LocationService()..serviceEnabled = false;
        final controller = LocationController(service);
        controller.showPurposeExplanation();
        await controller.continueAfterPurposeExplanation();

        expect(controller.state.phase, LocationFlowPhase.serviceDisabled);
        expect(service.serviceChecks, 1);

        await controller.retry();
        await controller.retry();
        expect(service.locationSettingsCalls, 1);
        expect(service.serviceChecks, 1);

        service
          ..serviceEnabled = true
          ..checkedPermission = LocationPermissionState.foregroundGranted;
        await controller.resumeAfterLocationSettings();

        expect(service.serviceChecks, 2);
        expect(service.acquisitions, 1);
        expect(controller.state.phase, LocationFlowPhase.acquired);

        await controller.resumeAfterLocationSettings();
        expect(service.serviceChecks, 2);
        expect(service.acquisitions, 1);
        controller.dispose();
      },
    );

    test('failed settings launch does not arm a later retry', () async {
      final service = FakeDay2LocationService()
        ..serviceEnabled = false
        ..locationSettingsOpened = false;
      final controller = LocationController(service);
      controller.showPurposeExplanation();
      await controller.continueAfterPurposeExplanation();

      await controller.retry();
      service.serviceEnabled = true;
      await controller.resumeAfterLocationSettings();

      expect(service.locationSettingsCalls, 1);
      expect(service.serviceChecks, 1);
      expect(service.acquisitions, 0);
      expect(controller.state.phase, LocationFlowPhase.serviceDisabled);
      controller.dispose();
    });

    test('typed acquisition failures map to safe states', () async {
      final cases = <(LocationFailureKind, LocationFlowPhase)>[
        (LocationFailureKind.timeout, LocationFlowPhase.timeout),
        (
          LocationFailureKind.inaccurate,
          LocationFlowPhase.inaccurateOrUnavailable,
        ),
        (
          LocationFailureKind.unavailable,
          LocationFlowPhase.inaccurateOrUnavailable,
        ),
        (LocationFailureKind.unexpected, LocationFlowPhase.platformError),
      ];
      for (final (kind, expected) in cases) {
        final service = FakeDay2LocationService()
          ..checkedPermission = LocationPermissionState.foregroundGranted
          ..acquisitionError = LocationFailure(kind, 'Synthetic failure');
        final controller = LocationController(service);
        controller.showPurposeExplanation();
        await controller.continueAfterPurposeExplanation();

        expect(controller.state.phase, expected);
        expect(controller.hasTemporaryLocation, isFalse);
        controller.dispose();
      }
    });

    test('policy rejects an inaccurate reading without retaining it', () async {
      final service = FakeDay2LocationService()
        ..checkedPermission = LocationPermissionState.foregroundGranted
        ..location = TemporaryLocation(
          latitude: 14.41,
          longitude: 120.97,
          accuracyMeters: 80,
          acquiredAt: DateTime.utc(2026, 9, 19),
        );
      final controller = LocationController(service);
      controller.showPurposeExplanation();

      await controller.continueAfterPurposeExplanation();

      expect(controller.state.phase, LocationFlowPhase.inaccurateOrUnavailable);
      expect(controller.temporaryLocation, isNull);
      expect(service.clearCalls, 1);
      controller.dispose();
    });

    test('clear, reset, cancellation, and disposal remove location', () async {
      final service = FakeDay2LocationService()
        ..checkedPermission = LocationPermissionState.foregroundGranted;
      final controller = LocationController(service);
      controller.showPurposeExplanation();
      await controller.continueAfterPurposeExplanation();
      await controller.clearLocation();
      expect(controller.temporaryLocation, isNull);
      expect(controller.state.phase, LocationFlowPhase.cleared);

      controller.showPurposeExplanation();
      await controller.continueAfterPurposeExplanation();
      await controller.reset();
      expect(controller.temporaryLocation, isNull);
      expect(controller.state.phase, LocationFlowPhase.initial);

      controller.showPurposeExplanation();
      await controller.cancel();
      expect(controller.state.phase, LocationFlowPhase.cancelled);
      controller.dispose();
      expect(service.disposed, isTrue);
      expect(controller.temporaryLocation, isNull);
    });

    test('late position after cancellation is ignored', () async {
      final pending = Completer<TemporaryLocation>();
      final service = FakeDay2LocationService()
        ..checkedPermission = LocationPermissionState.foregroundGranted
        ..acquisitionCompleter = pending;
      final controller = LocationController(service);
      controller.showPurposeExplanation();
      final acquisition = controller.continueAfterPurposeExplanation();
      await Future<void>.delayed(Duration.zero);
      await controller.cancel();
      pending.complete(service.location);
      await acquisition;

      expect(controller.temporaryLocation, isNull);
      expect(controller.state.phase, LocationFlowPhase.cancelled);
      controller.dispose();
    });

    test('a new controller cannot restore a previous coordinate', () async {
      final firstService = FakeDay2LocationService()
        ..checkedPermission = LocationPermissionState.foregroundGranted;
      final first = LocationController(firstService);
      first.showPurposeExplanation();
      await first.continueAfterPurposeExplanation();
      expect(first.hasTemporaryLocation, isTrue);
      first.dispose();

      final second = LocationController(FakeDay2LocationService());
      expect(second.hasTemporaryLocation, isFalse);
      expect(second.state.phase, LocationFlowPhase.initial);
      second.dispose();
    });
  });

  group('Day 2 location widgets', () {
    testWidgets('purpose appears before any permission request', (
      tester,
    ) async {
      final service = FakeDay2LocationService();
      final controller = LocationController(service);
      await pumpLocationCard(tester, controller);

      expect(service.permissionRequests, 0);
      await tester.tap(find.byKey(const Key('use-my-location-button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('location-purpose-dialog')), findsOneWidget);
      expect(find.textContaining('one temporary location'), findsWidgets);
      expect(service.serviceChecks, 0);
      expect(service.permissionRequests, 0);

      await tester.tap(find.byKey(const Key('location-purpose-cancel')));
      await tester.pumpAndSettle();
      expect(controller.state.phase, LocationFlowPhase.cancelled);
      controller.dispose();
    });

    testWidgets('explicit continue acquires and clear removes indicator', (
      tester,
    ) async {
      final service = FakeDay2LocationService();
      final controller = LocationController(service);
      await pumpLocationCard(tester, controller);

      await beginAndContinue(tester);

      expect(service.permissionRequests, 1);
      expect(
        find.byKey(const Key('temporary-location-indicator')),
        findsOneWidget,
      );
      expect(find.textContaining('14.41'), findsNothing);

      await tester.tap(find.byKey(const Key('clear-location-button')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('temporary-location-indicator')),
        findsNothing,
      );
      expect(find.byKey(const Key('use-my-location-button')), findsOneWidget);
      controller.dispose();
    });

    testWidgets('settings open only after an explicit settings tap', (
      tester,
    ) async {
      final service = FakeDay2LocationService()
        ..requestedPermission = LocationPermissionState.deniedPermanently;
      final controller = LocationController(service);
      await pumpLocationCard(tester, controller);
      await beginAndContinue(tester);

      expect(service.appSettingsCalls, 0);
      expect(find.byKey(const Key('open-app-settings-button')), findsOneWidget);
      await tester.tap(find.byKey(const Key('open-app-settings-button')));
      await tester.pump();
      expect(service.appSettingsCalls, 1);
      controller.dispose();
    });

    testWidgets(
      'disabled-service Try again opens settings and resumes one retry',
      (tester) async {
        final service = FakeDay2LocationService()..serviceEnabled = false;
        final controller = LocationController(service);
        await pumpLocationCard(tester, controller);
        await beginAndContinue(tester);

        expect(find.byKey(const Key('location-retry-button')), findsOneWidget);
        expect(
          find.byKey(const Key('open-location-settings-button')),
          findsNothing,
        );
        expect(find.text('Open location settings'), findsNothing);

        await tester.tap(find.byKey(const Key('location-retry-button')));
        await tester.pumpAndSettle();
        expect(service.locationSettingsCalls, 1);
        expect(service.serviceChecks, 1);

        service
          ..serviceEnabled = true
          ..checkedPermission = LocationPermissionState.foregroundGranted;
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pumpAndSettle();

        expect(service.serviceChecks, 2);
        expect(service.acquisitions, 1);
        expect(controller.state.phase, LocationFlowPhase.acquired);
        controller.dispose();
      },
    );

    testWidgets('manual controls and rainfall selection survive denied GPS', (
      tester,
    ) async {
      final service = FakeDay2LocationService()
        ..requestedPermission = LocationPermissionState.denied;
      await tester.pumpWidget(
        FloodSenseApp(
          api: FakeFloodSenseApi(),
          locationService: service,
          showBasemap: false,
        ),
      );
      await tester.pumpAndSettle();

      final intensity = find.byKey(const Key('option-DEMO_LIGHT'));
      await tester.ensureVisible(intensity);
      await tester.tap(intensity);
      await tester.pump();
      final useLocation = find.byKey(const Key('use-my-location-button'));
      await tester.ensureVisible(useLocation);
      await tester.tap(useLocation);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('location-purpose-continue')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('reference-boundary-map')), findsOneWidget);
      expect(find.byKey(const Key('manual-barangay-selector')), findsOneWidget);
      expect(find.byKey(const Key('zone-none')), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp('Light, selected')), findsOneWidget);
      expect(find.textContaining('choose a location manually'), findsWidgets);
    });

    testWidgets('removing the flow disposes adapter state', (tester) async {
      final service = FakeDay2LocationService();
      final controller = LocationController(service);
      await pumpLocationCard(tester, controller);

      controller.dispose();
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();

      expect(service.disposed, isTrue);
      expect(controller.temporaryLocation, isNull);
    });
  });
}
