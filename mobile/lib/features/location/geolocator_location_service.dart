import 'dart:async';

import 'package:geolocator/geolocator.dart';

import 'location_service.dart';

/// Narrow gateway around the package's static API.
///
/// It exists so the production adapter can be tested without requesting a
/// device permission or reading a real coordinate.
abstract interface class GeolocatorGateway {
  Future<bool> isLocationServiceEnabled();

  Future<LocationPermission> checkPermission();

  Future<LocationPermission> requestPermission();

  Future<Position> getCurrentPosition({
    required LocationSettings locationSettings,
  });

  Future<bool> openAppSettings();

  Future<bool> openLocationSettings();
}

class SystemGeolocatorGateway implements GeolocatorGateway {
  const SystemGeolocatorGateway();

  @override
  Future<LocationPermission> checkPermission() => Geolocator.checkPermission();

  @override
  Future<Position> getCurrentPosition({
    required LocationSettings locationSettings,
  }) => Geolocator.getCurrentPosition(locationSettings: locationSettings);

  @override
  Future<bool> isLocationServiceEnabled() =>
      Geolocator.isLocationServiceEnabled();

  @override
  Future<bool> openAppSettings() => Geolocator.openAppSettings();

  @override
  Future<bool> openLocationSettings() => Geolocator.openLocationSettings();

  @override
  Future<LocationPermission> requestPermission() =>
      Geolocator.requestPermission();
}

/// Production, foreground-only implementation of [LocationService].
///
/// This adapter requests one fresh position. It never reads the last known
/// position, starts a position stream, persists a coordinate, or logs one.
class GeolocatorLocationService implements LocationService {
  GeolocatorLocationService({GeolocatorGateway? gateway})
    : _gateway = gateway ?? const SystemGeolocatorGateway();

  final GeolocatorGateway _gateway;
  bool _hasRequestedPermission = false;

  @override
  Future<bool> isLocationServiceEnabled() async {
    try {
      return await _gateway.isLocationServiceEnabled();
    } on LocationServiceDisabledException {
      return false;
    } catch (_) {
      throw const LocationFailure(
        LocationFailureKind.unexpected,
        'Location service status could not be checked.',
      );
    }
  }

  @override
  Future<LocationPermissionState> checkPermission() async {
    try {
      return _mapPermission(
        await _gateway.checkPermission(),
        requestedThisSession: _hasRequestedPermission,
      );
    } on PermissionDeniedException {
      return _hasRequestedPermission
          ? LocationPermissionState.denied
          : LocationPermissionState.notRequested;
    } catch (_) {
      throw const LocationFailure(
        LocationFailureKind.unexpected,
        'Location permission status could not be checked.',
      );
    }
  }

  @override
  Future<LocationPermissionState> requestForegroundPermission() async {
    _hasRequestedPermission = true;
    try {
      return _mapPermission(
        await _gateway.requestPermission(),
        requestedThisSession: true,
      );
    } on PermissionDeniedException {
      return LocationPermissionState.denied;
    } catch (_) {
      throw const LocationFailure(
        LocationFailureKind.unexpected,
        'Foreground location permission could not be requested.',
      );
    }
  }

  @override
  Future<TemporaryLocation> acquireCurrentPosition({
    required LocationAcquisitionPolicy policy,
  }) async {
    if (policy.timeout <= Duration.zero ||
        !policy.maximumAcceptedAccuracyMeters.isFinite ||
        policy.maximumAcceptedAccuracyMeters <= 0) {
      throw const LocationFailure(
        LocationFailureKind.unexpected,
        'The location request policy is invalid.',
      );
    }

    try {
      final position = await _gateway.getCurrentPosition(
        locationSettings: AndroidSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: policy.timeout,
        ),
      );
      // geolocator_android 5.0.3 currently preserves the numeric accuracy but
      // loses Position.hasAccuracy while wrapping Position as AndroidPosition.
      // Validate the usable measurement itself so valid Android fixes are not
      // rejected; a missing Android accuracy is represented as 0.0.
      if (!position.accuracy.isFinite ||
          position.accuracy <= 0 ||
          position.accuracy > policy.maximumAcceptedAccuracyMeters) {
        throw const LocationFailure(
          LocationFailureKind.inaccurate,
          'The current location is not accurate enough to use.',
        );
      }
      if (!position.latitude.isFinite ||
          position.latitude < -90 ||
          position.latitude > 90 ||
          !position.longitude.isFinite ||
          position.longitude < -180 ||
          position.longitude > 180) {
        throw const LocationFailure(
          LocationFailureKind.unavailable,
          'A usable current location was not available.',
        );
      }
      return TemporaryLocation(
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyMeters: position.accuracy,
        acquiredAt: position.timestamp,
      );
    } on TimeoutException {
      throw const LocationFailure(
        LocationFailureKind.timeout,
        'The current location request timed out.',
      );
    } on LocationServiceDisabledException {
      throw const LocationFailure(
        LocationFailureKind.serviceDisabled,
        'Device location services are turned off.',
      );
    } on PermissionDeniedException {
      throw const LocationFailure(
        LocationFailureKind.permissionDenied,
        'Foreground location permission is not available.',
      );
    } on LocationFailure {
      rethrow;
    } on Exception {
      throw const LocationFailure(
        LocationFailureKind.unavailable,
        'A usable current location was not available.',
      );
    } catch (_) {
      throw const LocationFailure(
        LocationFailureKind.unexpected,
        'The device could not complete the location request.',
      );
    }
  }

  @override
  Future<bool> openAppSettings() async {
    try {
      return await _gateway.openAppSettings();
    } catch (_) {
      return false;
    }
  }

  @override
  Future<bool> openLocationSettings() async {
    try {
      return await _gateway.openLocationSettings();
    } catch (_) {
      return false;
    }
  }

  @override
  Future<void> clearTemporaryState() async {
    // The adapter stores no position; the controller owns the temporary copy.
  }

  @override
  void dispose() {
    // There is no stream, listener, timer, or platform request to dispose.
  }

  LocationPermissionState _mapPermission(
    LocationPermission permission, {
    required bool requestedThisSession,
  }) => switch (permission) {
    LocationPermission.denied =>
      requestedThisSession
          ? LocationPermissionState.denied
          : LocationPermissionState.notRequested,
    LocationPermission.deniedForever =>
      LocationPermissionState.deniedPermanently,
    LocationPermission.whileInUse ||
    LocationPermission.always => LocationPermissionState.foregroundGranted,
    LocationPermission.unableToDetermine => LocationPermissionState.denied,
  };
}
