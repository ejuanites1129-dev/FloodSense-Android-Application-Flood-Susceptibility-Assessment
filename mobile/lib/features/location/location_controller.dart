import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/api/api_exception.dart';
import '../../data/api/floodsense_api_client.dart';
import '../../data/models/barangay_resolution.dart';
import '../../data/models/point_resolution.dart';
import 'location_flow_state.dart';
import 'location_service.dart';

/// Coordinates one explicit, foreground-only location request.
///
/// The controller owns no persistence, timer, background task, or analytics.
/// Its coordinate exists only in [TemporaryLocationSession].
class LocationController extends ChangeNotifier {
  LocationController(
    this._service, {
    this.resolver,
    this.policy = const LocationAcquisitionPolicy(),
  });

  final LocationService _service;
  final BarangayResolver? resolver;
  final LocationAcquisitionPolicy policy;
  final TemporaryLocationSession _session = TemporaryLocationSession();

  LocationFlowState _state = LocationFlowState(LocationFlowPhase.initial);
  int _generation = 0;
  bool _disposed = false;
  MapCoordinate? _lookupCoordinate;
  BarangayResolution? _resolution;
  BarangayIdentity? _confirmedBarangay;

  LocationFlowState get state => _state;
  TemporaryLocation? get temporaryLocation => _session.location;
  bool get hasTemporaryLocation => _session.hasLocation;
  MapCoordinate? get lookupCoordinate => _lookupCoordinate;
  BarangayResolution? get resolution => _resolution;
  BarangayIdentity? get candidateBarangay =>
      _state.phase == LocationFlowPhase.resolvedCandidate
      ? _resolution?.barangay
      : null;
  BarangayIdentity? get confirmedBarangay => _confirmedBarangay;
  bool get isBusy =>
      _state.phase == LocationFlowPhase.acquiring ||
      _state.phase == LocationFlowPhase.resolvingBarangay;

  /// Called only by the visible "Use my location" action.
  void showPurposeExplanation() {
    if (_disposed || isBusy) return;
    _setState(LocationFlowState(LocationFlowPhase.purposeExplanation));
  }

  /// Called only after the purpose dialog's explicit Continue action.
  Future<void> continueAfterPurposeExplanation() async {
    if (_disposed || _state.phase != LocationFlowPhase.purposeExplanation) {
      return;
    }
    await _attemptAcquisition(mayRequestPermission: true);
  }

  Future<void> retry() async {
    if (_disposed || !_state.retryAllowed) return;
    if (_lookupCoordinate case final coordinate?) {
      await _resolveCoordinate(coordinate);
      return;
    }
    await _attemptAcquisition(mayRequestPermission: true);
  }

  Future<void> _attemptAcquisition({required bool mayRequestPermission}) async {
    if (_disposed || isBusy) return;
    final generation = ++_generation;
    _session.clear();
    _lookupCoordinate = null;
    _resolution = null;
    _confirmedBarangay = null;
    _setIfCurrent(generation, LocationFlowState(LocationFlowPhase.acquiring));
    try {
      final serviceEnabled = await _service.isLocationServiceEnabled();
      if (!_isCurrent(generation)) return;
      if (!serviceEnabled) {
        _setIfCurrent(
          generation,
          LocationFlowState(LocationFlowPhase.serviceDisabled),
        );
        return;
      }

      var permission = await _service.checkPermission();
      if (!_isCurrent(generation)) return;
      if (permission == LocationPermissionState.deniedPermanently) {
        _setIfCurrent(
          generation,
          LocationFlowState(LocationFlowPhase.permissionDeniedPermanently),
        );
        return;
      }
      if (permission != LocationPermissionState.foregroundGranted) {
        if (!mayRequestPermission) {
          _setIfCurrent(
            generation,
            LocationFlowState(LocationFlowPhase.permissionDenied),
          );
          return;
        }
        permission = await _service.requestForegroundPermission();
        if (!_isCurrent(generation)) return;
        if (permission == LocationPermissionState.deniedPermanently) {
          _setIfCurrent(
            generation,
            LocationFlowState(LocationFlowPhase.permissionDeniedPermanently),
          );
          return;
        }
        if (permission != LocationPermissionState.foregroundGranted) {
          _setIfCurrent(
            generation,
            LocationFlowState(LocationFlowPhase.permissionDenied),
          );
          return;
        }
      }

      final location = await _service.acquireCurrentPosition(policy: policy);
      if (!_isCurrent(generation)) return;
      if (!policy.accepts(location)) {
        await _service.clearTemporaryState();
        _setIfCurrent(
          generation,
          LocationFlowState(LocationFlowPhase.inaccurateOrUnavailable),
        );
        return;
      }
      _session.retain(location);
      _lookupCoordinate = MapCoordinate(
        latitude: location.latitude,
        longitude: location.longitude,
      );
      _setIfCurrent(
        generation,
        LocationFlowState(
          LocationFlowPhase.acquired,
          temporaryLocation: location,
        ),
      );
      if (resolver != null && _isCurrent(generation)) {
        await _resolveCoordinate(_lookupCoordinate!, generation: generation);
      }
    } on LocationFailure catch (error) {
      if (!_isCurrent(generation)) return;
      _session.clear();
      _setIfCurrent(generation, LocationFlowState(_phaseFor(error.kind)));
    } on TimeoutException {
      if (!_isCurrent(generation)) return;
      _session.clear();
      _setIfCurrent(generation, LocationFlowState(LocationFlowPhase.timeout));
    } catch (_) {
      if (!_isCurrent(generation)) return;
      _session.clear();
      _setIfCurrent(
        generation,
        LocationFlowState(LocationFlowPhase.platformError),
      );
    }
  }

  Future<void> cancel() async {
    if (_disposed) return;
    final generation = ++_generation;
    _session.clear();
    _lookupCoordinate = null;
    _resolution = null;
    _confirmedBarangay = null;
    await _clearAdapterState();
    _setIfCurrent(generation, LocationFlowState(LocationFlowPhase.cancelled));
  }

  Future<void> clearLocation() async {
    if (_disposed) return;
    final generation = ++_generation;
    _session.clear();
    _lookupCoordinate = null;
    _resolution = null;
    _confirmedBarangay = null;
    await _clearAdapterState();
    _setIfCurrent(generation, LocationFlowState(LocationFlowPhase.cleared));
  }

  Future<void> reset() async {
    if (_disposed) return;
    final generation = ++_generation;
    _session.reset();
    _lookupCoordinate = null;
    _resolution = null;
    _confirmedBarangay = null;
    await _clearAdapterState();
    _setIfCurrent(generation, LocationFlowState(LocationFlowPhase.initial));
  }

  Future<bool> openAppSettings() async {
    if (_disposed ||
        _state.phase != LocationFlowPhase.permissionDeniedPermanently) {
      return false;
    }
    try {
      return await _service.openAppSettings();
    } catch (_) {
      return false;
    }
  }

  Future<bool> openLocationSettings() async {
    if (_disposed || _state.phase != LocationFlowPhase.serviceDisabled) {
      return false;
    }
    try {
      return await _service.openLocationSettings();
    } catch (_) {
      return false;
    }
  }

  Future<void> _clearAdapterState() async {
    try {
      await _service.clearTemporaryState();
    } catch (_) {
      // Cleanup is best-effort; there is no persisted coordinate to recover.
    }
  }

  Future<void> resolveManualPin(MapCoordinate coordinate) async {
    if (_disposed || isBusy) return;
    final generation = ++_generation;
    _session.clear();
    _lookupCoordinate = coordinate;
    _resolution = null;
    _confirmedBarangay = null;
    await _clearAdapterState();
    if (!_isCurrent(generation)) return;
    await _resolveCoordinate(coordinate, generation: generation);
  }

  Future<void> _resolveCoordinate(
    MapCoordinate coordinate, {
    int? generation,
  }) async {
    final activeResolver = resolver;
    if (activeResolver == null || _disposed) return;
    final requestGeneration = generation ?? ++_generation;
    _resolution = null;
    _confirmedBarangay = null;
    _setIfCurrent(
      requestGeneration,
      LocationFlowState(
        LocationFlowPhase.resolvingBarangay,
        temporaryLocation: _session.location,
      ),
    );
    try {
      final response = await activeResolver.resolveBarangay(
        latitude: coordinate.latitude,
        longitude: coordinate.longitude,
      );
      if (!_isCurrent(requestGeneration)) return;
      _resolution = response;
      final phase = switch (response.state) {
        BarangayResolutionState.resolved => LocationFlowPhase.resolvedCandidate,
        BarangayResolutionState.outsideBacoor =>
          LocationFlowPhase.outsideBacoor,
        BarangayResolutionState.ambiguousBoundary =>
          LocationFlowPhase.ambiguousBoundary,
        BarangayResolutionState.unavailable =>
          LocationFlowPhase.resolverUnavailable,
      };
      _setIfCurrent(
        requestGeneration,
        LocationFlowState(phase, temporaryLocation: _session.location),
      );
    } on ApiException catch (error) {
      if (!_isCurrent(requestGeneration)) return;
      final phase = switch (error.kind) {
        ApiFailureKind.timeout => LocationFlowPhase.resolverTimeout,
        ApiFailureKind.malformedResponse => LocationFlowPhase.malformedResponse,
        ApiFailureKind.service => LocationFlowPhase.resolverUnavailable,
        ApiFailureKind.validation ||
        ApiFailureKind.connectivity => LocationFlowPhase.resolverFailure,
      };
      _setIfCurrent(
        requestGeneration,
        LocationFlowState(phase, temporaryLocation: _session.location),
      );
    } catch (_) {
      if (!_isCurrent(requestGeneration)) return;
      _setIfCurrent(
        requestGeneration,
        LocationFlowState(
          LocationFlowPhase.resolverFailure,
          temporaryLocation: _session.location,
        ),
      );
    }
  }

  void confirmCandidate() {
    if (_disposed || _state.phase != LocationFlowPhase.resolvedCandidate) {
      return;
    }
    final candidate = _resolution?.barangay;
    if (candidate == null) return;
    _confirmedBarangay = candidate;
    _setState(
      LocationFlowState(
        LocationFlowPhase.confirmed,
        temporaryLocation: _session.location,
      ),
    );
  }

  void rejectCandidate() {
    if (_disposed || _state.phase != LocationFlowPhase.resolvedCandidate) {
      return;
    }
    _generation++;
    _resolution = null;
    _confirmedBarangay = null;
    _setState(
      LocationFlowState(
        LocationFlowPhase.rejected,
        temporaryLocation: _session.location,
      ),
    );
  }

  Future<void> selectManualBarangay(BarangayIdentity barangay) async {
    if (_disposed) return;
    final generation = ++_generation;
    _session.clear();
    _lookupCoordinate = null;
    _resolution = null;
    _confirmedBarangay = barangay;
    await _clearAdapterState();
    _setIfCurrent(generation, LocationFlowState(LocationFlowPhase.confirmed));
  }

  bool _isCurrent(int generation) => !_disposed && generation == _generation;

  void _setIfCurrent(int generation, LocationFlowState state) {
    if (_isCurrent(generation)) _setState(state);
  }

  void _setState(LocationFlowState state) {
    if (_disposed) return;
    _state = state;
    notifyListeners();
  }

  LocationFlowPhase _phaseFor(LocationFailureKind kind) => switch (kind) {
    LocationFailureKind.serviceDisabled => LocationFlowPhase.serviceDisabled,
    LocationFailureKind.permissionDenied => LocationFlowPhase.permissionDenied,
    LocationFailureKind.permissionDeniedPermanently =>
      LocationFlowPhase.permissionDeniedPermanently,
    LocationFailureKind.timeout => LocationFlowPhase.timeout,
    LocationFailureKind.inaccurate || LocationFailureKind.unavailable =>
      LocationFlowPhase.inaccurateOrUnavailable,
    LocationFailureKind.unexpected => LocationFlowPhase.platformError,
  };

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _generation++;
    _session.dispose();
    _lookupCoordinate = null;
    _resolution = null;
    _confirmedBarangay = null;
    unawaited(_service.clearTemporaryState().catchError((_) {}));
    _service.dispose();
    super.dispose();
  }
}
