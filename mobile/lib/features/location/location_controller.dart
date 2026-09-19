import 'dart:async';

import 'package:flutter/foundation.dart';

import 'location_flow_state.dart';
import 'location_service.dart';

/// Coordinates one explicit, foreground-only location request.
///
/// The controller owns no persistence, timer, background task, analytics, or
/// resolver call. Its coordinate exists only in [TemporaryLocationSession].
class LocationController extends ChangeNotifier {
  LocationController(
    this._service, {
    this.policy = const LocationAcquisitionPolicy(),
  });

  final LocationService _service;
  final LocationAcquisitionPolicy policy;
  final TemporaryLocationSession _session = TemporaryLocationSession();

  LocationFlowState _state = LocationFlowState(LocationFlowPhase.initial);
  int _generation = 0;
  bool _disposed = false;

  LocationFlowState get state => _state;
  TemporaryLocation? get temporaryLocation => _session.location;
  bool get hasTemporaryLocation => _session.hasLocation;

  /// Called only by the visible "Use my location" action.
  void showPurposeExplanation() {
    if (_disposed || _state.phase == LocationFlowPhase.acquiring) return;
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
    await _attemptAcquisition(mayRequestPermission: true);
  }

  Future<void> _attemptAcquisition({required bool mayRequestPermission}) async {
    final generation = ++_generation;
    _session.clear();
    try {
      if (!await _service.isLocationServiceEnabled()) {
        _setIfCurrent(
          generation,
          LocationFlowState(LocationFlowPhase.serviceDisabled),
        );
        return;
      }

      var permission = await _service.checkPermission();
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

      _setIfCurrent(generation, LocationFlowState(LocationFlowPhase.acquiring));
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
      _setIfCurrent(
        generation,
        LocationFlowState(
          LocationFlowPhase.acquired,
          temporaryLocation: location,
        ),
      );
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
    _generation++;
    _session.clear();
    await _clearAdapterState();
    _setState(LocationFlowState(LocationFlowPhase.cancelled));
  }

  Future<void> clearLocation() async {
    if (_disposed) return;
    _generation++;
    _session.clear();
    await _clearAdapterState();
    _setState(LocationFlowState(LocationFlowPhase.cleared));
  }

  Future<void> reset() async {
    if (_disposed) return;
    _generation++;
    _session.reset();
    await _clearAdapterState();
    _setState(LocationFlowState(LocationFlowPhase.initial));
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
    unawaited(_service.clearTemporaryState().catchError((_) {}));
    _service.dispose();
    super.dispose();
  }
}
