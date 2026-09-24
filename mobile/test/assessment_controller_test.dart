import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/api/api_exception.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/map_assessment_result.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/models/scenario_option.dart';
import 'package:floodsense/features/assessment/assessment_controller.dart';

import 'test_data.dart';

void main() {
  group('AssessmentController', () {
    test('22 loads independent initial resources concurrently', () async {
      final optionsCompleter = Completer<AssessmentOptions>();
      final areasCompleter = Completer<List<GeographicArea>>();
      final api = FakeFloodSenseApi(
        optionsCompleter: optionsCompleter,
        areasCompleter: areasCompleter,
      );
      final controller = AssessmentController(api);

      final loading = controller.load();
      expect(api.optionsCalls, 1);
      expect(api.areasCalls, 1);
      expect(controller.isLoading, isTrue);
      optionsCompleter.complete(sampleOptions());
      areasCompleter.complete(sampleAreas());
      await loading;
      expect(controller.isLoading, isFalse);
      expect(controller.areas, hasLength(1));
    });

    test('23 requires all three explicit selections before submit', () async {
      final api = FakeFloodSenseApi();
      final controller = AssessmentController(api);
      await controller.load();
      expect(controller.canSubmit, isFalse);
      controller.selectIntensity(controller.intensities.first);
      controller.selectDuration(controller.durations.first);
      expect(controller.canSubmit, isFalse);
      controller.selectArea(controller.areas.first);
      expect(controller.canSubmit, isTrue);
    });

    test(
      'confirmed location can select one assessment area by stable code',
      () async {
        final controller = AssessmentController(FakeFloodSenseApi());
        await controller.load();

        controller.selectAreaByCode('DEMO_ZONE_A');
        expect(controller.selectedArea?.id, 7);

        controller.selectAreaByCode('UNKNOWN_AREA');
        expect(controller.selectedArea, isNull);
      },
    );

    test('24 submit forwards selected IDs and codes', () async {
      final api = FakeFloodSenseApi();
      final controller = AssessmentController(api);
      await controller.load();
      controller.selectIntensity(controller.intensities.last);
      controller.selectDuration(controller.durations.last);
      controller.selectArea(controller.areas.first);
      await controller.submit();
      expect(api.lastRequest?.geographicAreaId, 7);
      expect(api.lastRequest?.rainfallIntensityCode, 'DEMO_HEAVY');
      expect(api.lastRequest?.rainfallDurationCode, 'DEMO_6_HOURS');
    });

    test('25 selection change immediately clears stale result', () async {
      final api = FakeFloodSenseApi();
      final controller = AssessmentController(api);
      await controller.load();
      controller.selectIntensity(controller.intensities.last);
      controller.selectDuration(controller.durations.last);
      controller.selectArea(controller.areas.first);
      await controller.submit();
      expect(controller.result, isNotNull);
      controller.selectIntensity(controller.intensities.first);
      expect(controller.result, isNull);
    });

    test('26 duplicate submissions are ignored while pending', () async {
      final completer = Completer<AssessmentResult>();
      final api = FakeFloodSenseApi(evaluateCompleter: completer);
      final controller = AssessmentController(api);
      await controller.load();
      controller.selectIntensity(controller.intensities.first);
      controller.selectDuration(controller.durations.first);
      controller.selectArea(controller.areas.first);
      final first = controller.submit();
      final second = controller.submit();
      expect(api.evaluateCalls, 1);
      completer.complete(sampleResult());
      await Future.wait([first, second]);
    });

    test('27 API errors preserve selections', () async {
      final api = FakeFloodSenseApi(
        evaluateError: const ApiException(
          'Network unavailable.',
          kind: ApiFailureKind.connectivity,
        ),
      );
      final controller = AssessmentController(api);
      await controller.load();
      controller.selectIntensity(controller.intensities.first);
      controller.selectDuration(controller.durations.first);
      controller.selectArea(controller.areas.first);
      await controller.submit();
      expect(controller.submissionError?.kind, ApiFailureKind.connectivity);
      expect(controller.selectedArea?.code, 'DEMO_ZONE_A');
      expect(controller.selectedIntensity?.code, 'DEMO_LIGHT');
    });

    test('28 missing any resource is an empty-data state', () async {
      final controller = AssessmentController(
        FakeFloodSenseApi(areas: const []),
      );
      await controller.load();
      expect(controller.hasEmptyData, isTrue);
      expect(controller.canSubmit, isFalse);
    });

    test(
      'complete scenario triggers map evaluation; incomplete stays neutral',
      () async {
        final api = FakeFloodSenseApi();
        final controller = AssessmentController(api);
        await controller.load();

        controller.selectIntensity(controller.intensities.last);
        await Future<void>.delayed(Duration.zero);
        expect(api.mapCalls, 0);
        expect(controller.mapAssessment, isNull);

        controller.selectDuration(controller.durations.last);
        await Future<void>.delayed(Duration.zero);
        expect(api.mapCalls, 1);
        expect(controller.mapAssessment?.results.single.area.id, 7);
      },
    );

    test(
      'changing scenario clears colors and rejects older slow response',
      () async {
        final heavyCompleter = Completer<MapAssessmentResult>();
        final lightCompleter = Completer<MapAssessmentResult>();
        final api = FakeFloodSenseApi(
          mapHandler: (intensity, duration) {
            if (intensity == 'DEMO_HEAVY') {
              return heavyCompleter.future;
            }
            return lightCompleter.future;
          },
        );
        final controller = AssessmentController(api);
        await controller.load();
        controller.selectIntensity(controller.intensities.last);
        controller.selectDuration(controller.durations.last);
        await Future<void>.delayed(Duration.zero);
        expect(controller.mapAssessment, isNull);

        controller.selectIntensity(controller.intensities.first);
        expect(controller.mapAssessment, isNull);
        lightCompleter.complete(
          sampleMapAssessment(
            intensityCode: 'DEMO_LIGHT',
            durationCode: 'DEMO_6_HOURS',
          ),
        );
        await Future<void>.delayed(Duration.zero);
        heavyCompleter.complete(sampleMapAssessment());
        await Future<void>.delayed(Duration.zero);

        expect(
          controller.mapAssessment?.scenario.rainfallIntensityCode,
          'DEMO_LIGHT',
        );
      },
    );

    test('duplicate identical map requests are avoided', () async {
      final api = FakeFloodSenseApi();
      final controller = AssessmentController(api);
      await controller.load();
      controller.selectIntensity(controller.intensities.last);
      controller.selectDuration(controller.durations.last);
      await Future<void>.delayed(Duration.zero);

      await controller.refreshMapAssessment();

      expect(api.mapCalls, 1);
    });

    test(
      'map failure clears colors and Retry requests current scenario',
      () async {
        final api = FakeFloodSenseApi(
          mapError: const ApiException(
            'Map unavailable.',
            kind: ApiFailureKind.connectivity,
          ),
        );
        final controller = AssessmentController(api);
        await controller.load();
        controller.selectIntensity(controller.intensities.last);
        controller.selectDuration(controller.durations.last);
        await Future<void>.delayed(Duration.zero);
        expect(controller.mapAssessment, isNull);
        expect(controller.mapError, isNotNull);

        api.mapError = null;
        await controller.refreshMapAssessment(force: true);

        expect(api.mapCalls, 2);
        expect(controller.mapAssessment, isNotNull);
      },
    );

    test('pin selects an area only after backend confirmation', () async {
      final completer = Completer<PointResolution>();
      final api = FakeFloodSenseApi(pointHandler: (_, _) => completer.future);
      final controller = AssessmentController(api);
      await controller.load();

      final resolving = controller.placePin(
        const MapCoordinate(latitude: 14.005, longitude: 120.005),
      );
      expect(controller.selectedArea, isNull);
      expect(controller.isResolvingPoint, isTrue);
      completer.complete(samplePointResolution());
      await resolving;

      expect(controller.selectedArea?.code, 'DEMO_ZONE_A');
      expect(api.lastLatitude, 14.005);
      expect(api.lastLongitude, 120.005);
    });

    test(
      'outside and ambiguous pin outcomes clear the selected area',
      () async {
        for (final state in ['OUTSIDE_SUPPORTED_AREA', 'AMBIGUOUS_AREA']) {
          final api = FakeFloodSenseApi(
            pointResult: samplePointResolution(state: state),
          );
          final controller = AssessmentController(api);
          await controller.load();
          controller.selectArea(controller.areas.first);

          await controller.placePin(
            const MapCoordinate(latitude: 13, longitude: 119),
          );

          expect(controller.selectedArea, isNull);
          expect(controller.pointResolution?.rawState, state);
        }
      },
    );

    test('moving the pin invalidates a previous detailed result', () async {
      final controller = AssessmentController(FakeFloodSenseApi());
      await controller.load();
      controller.selectIntensity(controller.intensities.last);
      controller.selectDuration(controller.durations.last);
      controller.selectArea(controller.areas.first);
      await controller.submit();
      expect(controller.result, isNotNull);

      await controller.placePin(
        const MapCoordinate(latitude: 14.005, longitude: 120.005),
      );

      expect(controller.result, isNull);
    });
  });
}
