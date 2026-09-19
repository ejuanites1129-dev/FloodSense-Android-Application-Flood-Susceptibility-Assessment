import 'location_copy.dart';
import 'location_service.dart';

enum LocationFlowPhase {
  initial,
  purposeExplanation,
  serviceDisabled,
  permissionDenied,
  permissionDeniedPermanently,
  acquiring,
  acquired,
  resolvingBarangay,
  resolvedCandidate,
  confirmed,
  rejected,
  outsideBacoor,
  ambiguousBoundary,
  resolverUnavailable,
  resolverTimeout,
  timeout,
  inaccurateOrUnavailable,
  platformError,
  cancelled,
  resolverFailure,
  malformedResponse,
  recoverableError,
  cleared,
}

enum LocationFlowAction {
  showPurpose,
  continueToPermission,
  cancel,
  retry,
  openAppSettings,
  openLocationSettings,
  resolveBarangay,
  clearLocation,
  placeManualPin,
  selectBarangay,
}

class LocationFlowState {
  LocationFlowState(this.phase, {this.temporaryLocation}) {
    if (temporaryLocation != null && !coordinateMayExist) {
      throw ArgumentError(
        'Phase $phase and temporaryLocation do not satisfy the location-state contract.',
      );
    }
    if (phase == LocationFlowPhase.acquired && temporaryLocation == null) {
      throw ArgumentError('The acquired phase requires a temporary location.');
    }
  }

  final LocationFlowPhase phase;
  final TemporaryLocation? temporaryLocation;

  String get message => switch (phase) {
    LocationFlowPhase.initial => 'Location has not been requested. Manual location selection is available.',
    LocationFlowPhase.purposeExplanation =>
      '${LocationCopy.purpose} ${LocationCopy.privacy}',
    LocationFlowPhase.serviceDisabled => LocationCopy.serviceDisabled,
    LocationFlowPhase.permissionDenied => LocationCopy.permissionDenied,
    LocationFlowPhase.permissionDeniedPermanently =>
      LocationCopy.permissionDeniedPermanently,
    LocationFlowPhase.acquiring => 'Getting one temporary foreground location. You can cancel and select manually.',
    LocationFlowPhase.acquired => 'A temporary location is ready for barangay lookup. It is not a susceptibility result.',
    LocationFlowPhase.resolvingBarangay => 'Checking the temporary point against the pending-validation Bacoor boundary reference.',
    LocationFlowPhase.resolvedCandidate => 'Review and confirm the proposed barangay. It is an administrative location, not a susceptibility result.',
    LocationFlowPhase.confirmed => 'The barangay was confirmed as the location input. The boundary remains pending validation.',
    LocationFlowPhase.rejected => 'The proposed barangay was not selected. Move the map pin or choose a barangay manually.',
    LocationFlowPhase.outsideBacoor => 'The temporary point did not match a Bacoor barangay. Move the pin or choose a barangay manually.',
    LocationFlowPhase.ambiguousBoundary => 'The temporary point is on or near a shared barangay boundary. Confirm the location manually.',
    LocationFlowPhase.resolverUnavailable => 'The controlled boundary layer cannot resolve this point right now. This does not mean the point is outside Bacoor.',
    LocationFlowPhase.resolverTimeout => 'The boundary lookup timed out. Retry this point or choose a barangay manually.',
    LocationFlowPhase.timeout => 'FloodSense stopped waiting for a location. Try again or choose a location manually.',
    LocationFlowPhase.inaccurateOrUnavailable =>
      LocationCopy.inaccurateOrUnavailable,
    LocationFlowPhase.platformError => 'Android could not provide a location. Try again or choose a location manually.',
    LocationFlowPhase.cancelled => 'The location request was cancelled. Manual location selection remains available.',
    LocationFlowPhase.resolverFailure => LocationCopy.resolverFailure,
    LocationFlowPhase.malformedResponse => LocationCopy.malformedResponse,
    LocationFlowPhase.recoverableError => 'The location step could not finish. Retry or choose a location manually.',
    LocationFlowPhase.cleared => LocationCopy.cleared,
  };

  Set<LocationFlowAction> get allowedActions => switch (phase) {
    LocationFlowPhase.initial ||
    LocationFlowPhase.cleared ||
    LocationFlowPhase.cancelled => const {
      LocationFlowAction.showPurpose,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.purposeExplanation => const {
      LocationFlowAction.continueToPermission,
      LocationFlowAction.cancel,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.serviceDisabled => const {
      LocationFlowAction.retry,
      LocationFlowAction.openLocationSettings,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.permissionDenied => const {
      LocationFlowAction.retry,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.permissionDeniedPermanently => const {
      LocationFlowAction.openAppSettings,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.acquiring => const {
      LocationFlowAction.cancel,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.acquired => const {
      LocationFlowAction.resolveBarangay,
      LocationFlowAction.clearLocation,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.resolvingBarangay => const {
      LocationFlowAction.cancel,
      LocationFlowAction.clearLocation,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.resolvedCandidate ||
    LocationFlowPhase.confirmed ||
    LocationFlowPhase.rejected ||
    LocationFlowPhase.outsideBacoor ||
    LocationFlowPhase.ambiguousBoundary => const {
      LocationFlowAction.clearLocation,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.resolverUnavailable ||
    LocationFlowPhase.resolverTimeout => const {
      LocationFlowAction.retry,
      LocationFlowAction.clearLocation,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.timeout ||
    LocationFlowPhase.inaccurateOrUnavailable ||
    LocationFlowPhase.platformError => const {
      LocationFlowAction.retry,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
    LocationFlowPhase.resolverFailure ||
    LocationFlowPhase.malformedResponse ||
    LocationFlowPhase.recoverableError => const {
      LocationFlowAction.retry,
      LocationFlowAction.clearLocation,
      LocationFlowAction.placeManualPin,
      LocationFlowAction.selectBarangay,
    },
  };

  bool get retryAllowed => allowedActions.contains(LocationFlowAction.retry);

  bool get manualSelectionAvailable =>
      allowedActions.contains(LocationFlowAction.placeManualPin) &&
      allowedActions.contains(LocationFlowAction.selectBarangay);

  bool get coordinateMayExist => switch (phase) {
    LocationFlowPhase.acquired ||
    LocationFlowPhase.resolvingBarangay ||
    LocationFlowPhase.resolvedCandidate ||
    LocationFlowPhase.confirmed ||
    LocationFlowPhase.rejected ||
    LocationFlowPhase.outsideBacoor ||
    LocationFlowPhase.ambiguousBoundary ||
    LocationFlowPhase.resolverUnavailable ||
    LocationFlowPhase.resolverTimeout ||
    LocationFlowPhase.resolverFailure ||
    LocationFlowPhase.malformedResponse ||
    LocationFlowPhase.recoverableError => true,
    _ => false,
  };

  /// Clears the coordinate after user action, assessment reset, or flow exit.
  LocationFlowState clear() => LocationFlowState(LocationFlowPhase.cleared);
}
