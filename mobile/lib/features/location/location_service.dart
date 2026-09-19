/// Platform-neutral contract for one user-triggered foreground location read.
///
/// Day 1 deliberately provides no production adapter. A later adapter may wrap
/// a platform package, while tests can implement this interface without device
/// services or permission dialogs.
abstract interface class LocationService {
  Future<bool> isLocationServiceEnabled();

  Future<LocationPermissionState> checkPermission();

  /// Must only be called after the user has seen the purpose explanation and
  /// explicitly chosen to continue.
  Future<LocationPermissionState> requestForegroundPermission();

  Future<bool> openAppSettings();

  Future<bool> openLocationSettings();

  /// Acquires one position. Implementations must not start a position stream.
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  });

  /// Releases package/plugin state without persisting the last coordinate.
  Future<void> clearTemporaryState();

  void dispose();
}

enum LocationPermissionState {
  notRequested,
  denied,
  deniedPermanently,
  foregroundGranted,
}

enum LocationFailureKind {
  serviceDisabled,
  permissionDenied,
  permissionDeniedPermanently,
  timeout,
  inaccurate,
  unavailable,
  unexpected,
}

class LocationFailure implements Exception {
  const LocationFailure(this.kind, this.message);

  final LocationFailureKind kind;
  final String message;

  @override
  String toString() => message;
}

class TemporaryLocation {
  TemporaryLocation({
    required this.latitude,
    required this.longitude,
    required this.accuracyMeters,
    required this.acquiredAt,
  }) {
    if (!latitude.isFinite || latitude < -90 || latitude > 90) {
      throw ArgumentError.value(
        latitude,
        'latitude',
        'Must be finite and in -90..90.',
      );
    }
    if (!longitude.isFinite || longitude < -180 || longitude > 180) {
      throw ArgumentError.value(
        longitude,
        'longitude',
        'Must be finite and in -180..180.',
      );
    }
    if (!accuracyMeters.isFinite || accuracyMeters < 0) {
      throw ArgumentError.value(
        accuracyMeters,
        'accuracyMeters',
        'Must be a finite non-negative value.',
      );
    }
  }

  final double latitude;
  final double longitude;
  final double accuracyMeters;
  final DateTime acquiredAt;
}

class LocationAcquisitionPolicy {
  const LocationAcquisitionPolicy({
    this.timeout = const Duration(seconds: 15),
    this.maximumAcceptedAccuracyMeters = 50,
  });

  final Duration timeout;
  final double maximumAcceptedAccuracyMeters;

  bool accepts(TemporaryLocation location) =>
      timeout > Duration.zero &&
      maximumAcceptedAccuracyMeters.isFinite &&
      maximumAcceptedAccuracyMeters > 0 &&
      location.accuracyMeters <= maximumAcceptedAccuracyMeters;
}

/// Owns the only in-memory coordinate intended for the future GPS flow.
///
/// It has no serialization API and no dependency on preferences, databases,
/// analytics, auditing, or logging. The owner must call [clear] on assessment
/// reset/user clear and [dispose] when the flow ends.
class TemporaryLocationSession {
  TemporaryLocation? _location;
  bool _isDisposed = false;

  TemporaryLocation? get location => _location;
  bool get hasLocation => _location != null;
  bool get isDisposed => _isDisposed;

  void retain(TemporaryLocation location) {
    if (_isDisposed) {
      throw StateError(
        'Cannot retain a location after the session is disposed.',
      );
    }
    _location = location;
  }

  void clear() {
    _location = null;
  }

  void reset() => clear();

  void dispose() {
    clear();
    _isDisposed = true;
  }
}
