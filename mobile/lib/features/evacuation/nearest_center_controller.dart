import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../data/models/point_resolution.dart';
import '../../data/models/verified_center.dart';
import '../location/location_controller.dart';
import '../location/location_flow_state.dart';
import 'nearest_center_provider.dart';
import 'evacuation_map_controller.dart';

enum NearestCenterPhase {
  initial,
  notRequested,
  waitingForLocationConfirmation,
  loading,
  resultsAvailable,
  empty,
  offline,
  timeout,
  serverUnavailable,
  malformedResponse,
  requestRejected,
  rateLimited,
  locationCleared,
  locationChanged,
  recoverableError,
  coordinateRequired,
  contractUnavailable,
}

/// Coordinates center presentation without owning or persisting a coordinate.
final class NearestCenterController extends ChangeNotifier {
  NearestCenterController(
    this._locationController, {
    this.provider,
    this.mapController,
  }) {
    _locationController.addListener(_onLocationChanged);
    _synchronizeWithLocation();
  }

  final LocationController _locationController;
  final NearestCenterProvider? provider;
  final EvacuationMapController? mapController;

  NearestCenterPhase _phase = NearestCenterPhase.initial;
  List<VerifiedCenter> _centers = const [];
  List<String> _warnings = const [];
  String? _distanceMethod;
  String? _selectedCenterIdentifier;
  _ConfirmedLocationKey? _activeLocation;
  int _generation = 0;
  bool _disposed = false;
  bool _isDemonstration = false;

  NearestCenterPhase get phase => _phase;
  List<VerifiedCenter> get centers => _centers;
  List<String> get warnings => _warnings;
  String? get distanceMethod => _distanceMethod;
  String? get selectedCenterIdentifier => _selectedCenterIdentifier;
  bool get isDemonstration => _isDemonstration;
  String? get nearestCenterIdentifier =>
      _phase == NearestCenterPhase.resultsAvailable && _centers.isNotEmpty
      ? _centers.first.publicIdentifier
      : null;
  String get distanceOriginLabel => _locationController.isApproximateCoordinate
      ? 'From an approximate point inside the selected barangay—not your exact location'
      : _locationController.coordinateOrigin ==
            LocationCoordinateOrigin.deviceGps
      ? 'From your confirmed GPS location'
      : 'From your confirmed map pin';
  bool get canRetry => switch (_phase) {
    NearestCenterPhase.offline ||
    NearestCenterPhase.timeout ||
    NearestCenterPhase.serverUnavailable ||
    NearestCenterPhase.malformedResponse ||
    NearestCenterPhase.recoverableError => true,
    _ => false,
  };

  bool get canRefresh =>
      _activeLocation != null &&
      provider != null &&
      (_phase == NearestCenterPhase.resultsAvailable ||
          _phase == NearestCenterPhase.empty);

  /// Explicit user refresh only; preserves the confirmed location and scenario.
  Future<void> refresh() async {
    if (_disposed || !canRefresh) return;
    await Future.wait([
      _request(_activeLocation!),
      if (mapController != null) mapController!.load(refresh: true),
    ]);
  }

  String get message => switch (_phase) {
    NearestCenterPhase.initial ||
    NearestCenterPhase.notRequested ||
    NearestCenterPhase.waitingForLocationConfirmation => 'Confirm a GPS or map-pin location to request nearby verified center information.',
    NearestCenterPhase.loading =>
      'Requesting nearby verified center information...',
    NearestCenterPhase.resultsAvailable =>
      _isDemonstration
          ? '${_centers.length} local test center${_centers.length == 1 ? '' : 's'} - not real facilities.'
          : '${_centers.length} verified center${_centers.length == 1 ? '' : 's'} returned in the service order.',
    NearestCenterPhase.empty =>
      _isDemonstration ? 'No local demonstration centers match this request.' : 'No verified eligible center information is currently available for this request. This does not mean that no evacuation centers exist in Bacoor.',
    NearestCenterPhase.offline => 'Center information could not be requested while offline. Your confirmed location and assessment choices are unchanged.',
    NearestCenterPhase.timeout => 'The center request timed out. Your confirmed location and assessment choices are unchanged.',
    NearestCenterPhase.serverUnavailable => 'Verified center information is temporarily unavailable. Your confirmed location and assessment choices are unchanged.',
    NearestCenterPhase.malformedResponse => 'Center information could not be safely read. No partial center records are shown.',
    NearestCenterPhase.requestRejected => 'The center request was not accepted. Confirm a valid location before trying again.',
    NearestCenterPhase.rateLimited => 'Too many center requests were made. Please wait before confirming a location again.',
    NearestCenterPhase.locationCleared =>
      'Center results were cleared with the temporary location.',
    NearestCenterPhase.locationChanged =>
      'The location changed, so earlier center results were cleared.',
    NearestCenterPhase.recoverableError => 'Center information could not be requested. Your confirmed location and assessment choices are unchanged.',
    NearestCenterPhase.coordinateRequired => 'A barangay is confirmed, but nearest centers require a coordinate. Place and confirm a map pin to continue.',
    NearestCenterPhase.contractUnavailable =>
      'Verified center information is not available in this app build yet.',
  };

  Future<void> retry() async {
    if (_disposed || !canRetry || _activeLocation == null) return;
    await _request(_activeLocation!);
  }

  void selectCenter(String publicIdentifier) {
    if (_disposed ||
        !_centers.any(
          (center) => center.publicIdentifier == publicIdentifier,
        )) {
      return;
    }
    if (_selectedCenterIdentifier == publicIdentifier) return;
    _selectedCenterIdentifier = publicIdentifier;
    notifyListeners();
  }

  void clearSelection() {
    if (_disposed || _selectedCenterIdentifier == null) return;
    _selectedCenterIdentifier = null;
    notifyListeners();
  }

  void _onLocationChanged() => _synchronizeWithLocation();

  void _synchronizeWithLocation() {
    if (_disposed) return;
    final locationState = _locationController.state.phase;
    final isConfirmed = locationState == LocationFlowPhase.confirmed;
    final coordinate = _locationController.lookupCoordinate;
    final barangay = _locationController.confirmedBarangay;

    if (!isConfirmed || barangay == null) {
      final hadLocation = _activeLocation != null || _centers.isNotEmpty;
      _invalidate();
      _setPhase(
        hadLocation
            ? (coordinate == null
                  ? NearestCenterPhase.locationCleared
                  : NearestCenterPhase.locationChanged)
            : locationState == LocationFlowPhase.initial
            ? NearestCenterPhase.notRequested
            : NearestCenterPhase.waitingForLocationConfirmation,
      );
      return;
    }

    if (coordinate == null) {
      _invalidate();
      _setPhase(NearestCenterPhase.coordinateRequired);
      return;
    }

    final location = _ConfirmedLocationKey(
      coordinate: coordinate,
      barangayPsgcCode: barangay.psgcCode,
    );
    if (location == _activeLocation) return;

    _invalidate();
    _activeLocation = location;
    if (provider == null) {
      _setPhase(NearestCenterPhase.contractUnavailable);
      return;
    }
    unawaited(_request(location));
  }

  Future<void> _request(_ConfirmedLocationKey location) async {
    final activeProvider = provider;
    if (_disposed || activeProvider == null || location != _activeLocation) {
      return;
    }
    if (_phase == NearestCenterPhase.loading) return;
    final generation = ++_generation;
    _centers = const [];
    _warnings = const [];
    _distanceMethod = null;
    _selectedCenterIdentifier = null;
    _setPhase(NearestCenterPhase.loading);
    try {
      final result = await activeProvider.findNearest(
        latitude: location.coordinate.latitude,
        longitude: location.coordinate.longitude,
      );
      if (!_isCurrent(generation, location)) return;
      final centers = result.centers;
      final identifiers = centers
          .map((center) => center.publicIdentifier)
          .toSet();
      if (identifiers.length != centers.length) {
        _centers = const [];
        _setPhase(NearestCenterPhase.malformedResponse);
        return;
      }
      _centers = List.unmodifiable(centers);
      _isDemonstration = result.isDemonstration;
      _warnings = List.unmodifiable(result.warnings);
      _distanceMethod = result.distanceMethod;
      _setPhase(
        centers.isEmpty
            ? NearestCenterPhase.empty
            : NearestCenterPhase.resultsAvailable,
      );
    } on CenterLookupException catch (error) {
      if (!_isCurrent(generation, location)) return;
      _centers = const [];
      _warnings = const [];
      _distanceMethod = null;
      _setPhase(switch (error.kind) {
        CenterLookupFailureKind.offline => NearestCenterPhase.offline,
        CenterLookupFailureKind.timeout => NearestCenterPhase.timeout,
        CenterLookupFailureKind.serverUnavailable =>
          NearestCenterPhase.serverUnavailable,
        CenterLookupFailureKind.malformedResponse =>
          NearestCenterPhase.malformedResponse,
        CenterLookupFailureKind.requestRejected =>
          NearestCenterPhase.requestRejected,
        CenterLookupFailureKind.rateLimited => NearestCenterPhase.rateLimited,
        CenterLookupFailureKind.recoverable =>
          NearestCenterPhase.recoverableError,
      });
    } catch (_) {
      if (!_isCurrent(generation, location)) return;
      _centers = const [];
      _warnings = const [];
      _distanceMethod = null;
      _setPhase(NearestCenterPhase.recoverableError);
    }
  }

  bool _isCurrent(int generation, _ConfirmedLocationKey location) =>
      !_disposed && generation == _generation && location == _activeLocation;

  void _invalidate() {
    _isDemonstration = false;
    _generation++;
    _activeLocation = null;
    _centers = const [];
    _warnings = const [];
    _distanceMethod = null;
    _selectedCenterIdentifier = null;
  }

  void _setPhase(NearestCenterPhase phase) {
    if (_disposed) return;
    _phase = phase;
    notifyListeners();
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _generation++;
    _locationController.removeListener(_onLocationChanged);
    _activeLocation = null;
    _centers = const [];
    _warnings = const [];
    _distanceMethod = null;
    _selectedCenterIdentifier = null;
    super.dispose();
  }
}

final class _ConfirmedLocationKey {
  const _ConfirmedLocationKey({
    required this.coordinate,
    required this.barangayPsgcCode,
  });

  final MapCoordinate coordinate;
  final String barangayPsgcCode;

  @override
  bool operator ==(Object other) =>
      other is _ConfirmedLocationKey &&
      other.coordinate.latitude == coordinate.latitude &&
      other.coordinate.longitude == coordinate.longitude &&
      other.barangayPsgcCode == barangayPsgcCode;

  @override
  int get hashCode =>
      Object.hash(coordinate.latitude, coordinate.longitude, barangayPsgcCode);
}
