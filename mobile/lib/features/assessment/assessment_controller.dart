import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/api/api_exception.dart';
import '../../data/api/floodsense_api_client.dart';
import '../../data/models/assessment_request.dart';
import '../../data/models/assessment_result.dart';
import '../../data/models/geographic_area.dart';
import '../../data/models/map_assessment_result.dart';
import '../../data/models/point_resolution.dart';
import '../../data/models/scenario_option.dart';

class AssessmentController extends ChangeNotifier {
  AssessmentController(this._api);

  final FloodSenseApi _api;

  bool isLoading = false;
  bool isSubmitting = false;
  bool isMapAssessing = false;
  bool isResolvingPoint = false;
  AssessmentOptions? options;
  List<GeographicArea> areas = const [];
  ScenarioOption? selectedIntensity;
  ScenarioOption? selectedDuration;
  GeographicArea? selectedArea;
  AssessmentResult? result;
  MapAssessmentResult? mapAssessment;
  PointResolution? pointResolution;
  MapCoordinate? pinCoordinate;
  ApiException? loadError;
  ApiException? submissionError;
  ApiException? mapError;
  ApiException? pointError;

  int _mapGeneration = 0;
  int _pointGeneration = 0;
  int _detailGeneration = 0;
  String? _activeMapIdentity;
  String? _completedMapIdentity;

  List<ScenarioOption> get intensities => options?.intensityOptions ?? const [];
  List<ScenarioOption> get durations => options?.durationOptions ?? const [];
  Map<int, MapAreaAssessment> get mapResultsByAreaId =>
      mapAssessment?.resultsByAreaId ?? const {};
  bool get hasCompleteScenario =>
      selectedIntensity != null && selectedDuration != null;

  bool get hasEmptyData =>
      !isLoading &&
      loadError == null &&
      (intensities.isEmpty || durations.isEmpty || areas.isEmpty);

  bool get canSubmit =>
      !isLoading &&
      !isSubmitting &&
      !hasEmptyData &&
      selectedIntensity != null &&
      selectedDuration != null &&
      selectedArea != null;

  Future<void> load() async {
    if (isLoading) return;
    isLoading = true;
    loadError = null;
    notifyListeners();
    try {
      final resources = await Future.wait<Object>([
        _api.fetchAssessmentOptions(),
        _api.fetchDemonstrationAreas(),
      ]);
      options = resources[0] as AssessmentOptions;
      areas = List.unmodifiable(resources[1] as List<GeographicArea>);
      _removeInvalidSelections();
      if (hasCompleteScenario) unawaited(refreshMapAssessment());
    } on ApiException catch (error) {
      loadError = error;
    } catch (_) {
      loadError = const ApiException(
        'FloodSense could not load the demonstration data. Please try again.',
        kind: ApiFailureKind.service,
      );
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  void selectIntensity(ScenarioOption option) {
    if (selectedIntensity?.code == option.code) return;
    selectedIntensity = option;
    _scenarioChanged();
  }

  void selectDuration(ScenarioOption option) {
    if (selectedDuration?.code == option.code) return;
    selectedDuration = option;
    _scenarioChanged();
  }

  void selectArea(GeographicArea? area) {
    if (selectedArea?.id == area?.id) return;
    _pointGeneration++;
    isResolvingPoint = false;
    pointResolution = null;
    pointError = null;
    selectedArea = area;
    _invalidateDetailedResult();
    notifyListeners();
  }

  Future<void> refreshMapAssessment({bool force = false}) async {
    if (!hasCompleteScenario) return;
    final intensity = selectedIntensity!;
    final duration = selectedDuration!;
    final identity = '${intensity.code}|${duration.code}';
    if (!force &&
        ((_activeMapIdentity == identity && isMapAssessing) ||
            (_completedMapIdentity == identity && mapAssessment != null))) {
      return;
    }

    final generation = ++_mapGeneration;
    _activeMapIdentity = identity;
    isMapAssessing = true;
    mapAssessment = null;
    mapError = null;
    notifyListeners();
    try {
      final response = await _api.evaluateMapScenario(
        intensityCode: intensity.code,
        durationCode: duration.code,
      );
      if (generation != _mapGeneration) return;
      if (response.scenario.rainfallIntensityCode != intensity.code ||
          response.scenario.rainfallDurationCode != duration.code) {
        throw const ApiException(
          'FloodSense returned map colors for a different scenario.',
          kind: ApiFailureKind.malformedResponse,
        );
      }
      mapAssessment = response;
      _completedMapIdentity = identity;
    } on ApiException catch (error) {
      if (generation != _mapGeneration) return;
      mapError = error;
      mapAssessment = null;
      _completedMapIdentity = null;
    } catch (_) {
      if (generation != _mapGeneration) return;
      mapError = const ApiException(
        'FloodSense could not update the demonstration map. Please try again.',
        kind: ApiFailureKind.service,
      );
      mapAssessment = null;
      _completedMapIdentity = null;
    } finally {
      if (generation == _mapGeneration) {
        isMapAssessing = false;
        _activeMapIdentity = null;
        notifyListeners();
      }
    }
  }

  Future<void> placePin(MapCoordinate coordinate) async {
    final generation = ++_pointGeneration;
    pinCoordinate = coordinate;
    pointResolution = null;
    pointError = null;
    selectedArea = null;
    isResolvingPoint = true;
    _invalidateDetailedResult();
    notifyListeners();
    try {
      final response = await _api.resolvePoint(
        latitude: coordinate.latitude,
        longitude: coordinate.longitude,
      );
      if (generation != _pointGeneration) return;
      pointResolution = response;
      if (response.state == PointResolutionState.resolved) {
        final matchingAreas = areas.where(
          (candidate) => candidate.id == response.area!.id,
        );
        if (matchingAreas.length != 1) {
          throw const ApiException(
            'The resolved demonstration zone is unavailable on this map.',
            kind: ApiFailureKind.malformedResponse,
          );
        }
        selectedArea = matchingAreas.single;
      } else {
        selectedArea = null;
      }
    } on ApiException catch (error) {
      if (generation != _pointGeneration) return;
      pointError = error;
      pointResolution = null;
      selectedArea = null;
    } catch (_) {
      if (generation != _pointGeneration) return;
      pointError = const ApiException(
        'FloodSense could not resolve this temporary pin. Please try again.',
        kind: ApiFailureKind.service,
      );
      pointResolution = null;
      selectedArea = null;
    } finally {
      if (generation == _pointGeneration) {
        isResolvingPoint = false;
        notifyListeners();
      }
    }
  }

  Future<void> retryPointResolution() async {
    final coordinate = pinCoordinate;
    if (coordinate != null) await placePin(coordinate);
  }

  Future<void> submit() async {
    if (!canSubmit) return;
    final intensity = selectedIntensity!;
    final duration = selectedDuration!;
    final area = selectedArea!;
    final generation = ++_detailGeneration;
    isSubmitting = true;
    submissionError = null;
    result = null;
    notifyListeners();
    try {
      final response = await _api.evaluateAssessment(
        AssessmentRequest(
          geographicAreaId: area.id,
          rainfallIntensityCode: intensity.code,
          rainfallDurationCode: duration.code,
        ),
      );
      if (generation != _detailGeneration) return;
      result = response;
    } on ApiException catch (error) {
      if (generation != _detailGeneration) return;
      submissionError = error;
    } catch (_) {
      if (generation != _detailGeneration) return;
      submissionError = const ApiException(
        'FloodSense could not complete the assessment. Please try again.',
        kind: ApiFailureKind.service,
      );
    } finally {
      if (generation == _detailGeneration) {
        isSubmitting = false;
        notifyListeners();
      }
    }
  }

  void _scenarioChanged() {
    _mapGeneration++;
    isMapAssessing = false;
    _activeMapIdentity = null;
    _completedMapIdentity = null;
    mapAssessment = null;
    mapError = null;
    _invalidateDetailedResult();
    notifyListeners();
    if (hasCompleteScenario) unawaited(refreshMapAssessment());
  }

  void _invalidateDetailedResult() {
    _detailGeneration++;
    isSubmitting = false;
    result = null;
    submissionError = null;
  }

  void _removeInvalidSelections() {
    if (!intensities.any((item) => item.code == selectedIntensity?.code)) {
      selectedIntensity = null;
    }
    if (!durations.any((item) => item.code == selectedDuration?.code)) {
      selectedDuration = null;
    }
    if (!areas.any((item) => item.id == selectedArea?.id)) {
      selectedArea = null;
    }
    _mapGeneration++;
    _pointGeneration++;
    mapAssessment = null;
    pointResolution = null;
    pinCoordinate = null;
    mapError = null;
    pointError = null;
    _completedMapIdentity = null;
    _invalidateDetailedResult();
  }

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }
}
