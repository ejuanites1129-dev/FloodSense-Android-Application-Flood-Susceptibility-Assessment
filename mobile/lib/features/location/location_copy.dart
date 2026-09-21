/// Draft product copy for the future foreground-only location flow.
///
/// This copy is a Day 1 implementation draft, not a legal approval.
abstract final class LocationCopy {
  static const purposeTitle = 'Use your location for this assessment?';
  static const purpose =
      'FloodSense can use one temporary location to look up a likely Bacoor '
      'barangay and request nearby verified center information with approximate '
      'straight-line distances. This lookup does not determine flood '
      'susceptibility, route safety, accessibility, availability, or an '
      'evacuation recommendation.';
  static const privacy =
      'Your coordinate is used only during this flow and is not retained. '
      'You can use the map pin or barangay selector instead.';
  static const permissionDenied =
      'Location permission was not granted. You can try again or choose a '
      'location manually.';
  static const permissionDeniedPermanently =
      'Location permission is blocked for FloodSense. You may enable it in '
      'Android app settings, or choose a location manually.';
  static const serviceDisabled =
      'Device location is turned off. Tap Try again to open Android Location '
      'Settings. FloodSense will retry once when you return, or you can choose '
      'a location manually.';
  static const inaccurateOrUnavailable =
      'FloodSense could not get a reliable location. Try again, place a '
      'temporary map pin, or select a barangay.';
  static const resolverFailure =
      'FloodSense could not check the temporary location with the boundary '
      'service. Your scenario choices are unchanged; retry or select manually.';
  static const malformedResponse =
      'FloodSense received an unexpected boundary response. No barangay or '
      'susceptibility result was assumed.';
  static const cleared =
      'The temporary location was cleared. Choose a map pin or barangay, or '
      'start the location request again.';
}
