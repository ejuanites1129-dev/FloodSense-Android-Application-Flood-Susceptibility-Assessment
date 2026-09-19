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
  inaccurateOrUnavailable,
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
    LocationFlowPhase.inaccurateOrUnavailable =>
      LocationCopy.inaccurateOrUnavailable,
    LocationFlowPhase.resolverFailure => LocationCopy.resolverFailure,
    LocationFlowPhase.malformedResponse => LocationCopy.malformedResponse,
    LocationFlowPhase.recoverableError => 'The location step could not finish. Retry or choose a location manually.',
    LocationFlowPhase.cleared => LocationCopy.cleared,
  };

  Set<LocationFlowAction> get allowedActions => switch (phase) {
    LocationFlowPhase.initial || LocationFlowPhase.cleared => const {
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
    LocationFlowPhase.inaccurateOrUnavailable => const {
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
    LocationFlowPhase.resolverFailure ||
    LocationFlowPhase.malformedResponse ||
    LocationFlowPhase.recoverableError => true,
    _ => false,
  };

  /// Clears the coordinate after user action, assessment reset, or flow exit.
  LocationFlowState clear() => LocationFlowState(LocationFlowPhase.cleared);
}
