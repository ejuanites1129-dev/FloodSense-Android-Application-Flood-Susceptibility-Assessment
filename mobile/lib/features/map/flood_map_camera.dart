import 'dart:math' as math;

const double selectedLocationCameraHeightMeters = 70;

const double _earthCircumferenceMeters = 40075016.686;
const double _mapboxTileSizePixels = 512;
const double _mapboxVerticalFieldOfViewRadians = 0.6435011087932844;

double approximateCameraHeightMeters({
  required double zoom,
  required double latitude,
  required double pitchDegrees,
  required double viewportHeightPixels,
}) {
  if (!zoom.isFinite ||
      !latitude.isFinite ||
      !pitchDegrees.isFinite ||
      !viewportHeightPixels.isFinite ||
      viewportHeightPixels <= 0) {
    return double.nan;
  }
  final latitudeRadians = latitude.clamp(-85.0, 85.0) * math.pi / 180;
  final pitchRadians = pitchDegrees.clamp(0.0, 89.0) * math.pi / 180;
  final metersPerPixel =
      _earthCircumferenceMeters *
      math.cos(latitudeRadians) /
      (_mapboxTileSizePixels * math.pow(2, zoom));
  final cameraToCenterPixels =
      viewportHeightPixels /
      (2 * math.tan(_mapboxVerticalFieldOfViewRadians / 2));
  return metersPerPixel * cameraToCenterPixels * math.cos(pitchRadians);
}

double zoomForCameraHeightMeters({
  required double cameraHeightMeters,
  required double latitude,
  required double pitchDegrees,
  required double viewportHeightPixels,
}) {
  if (!cameraHeightMeters.isFinite || cameraHeightMeters <= 0) {
    throw ArgumentError.value(
      cameraHeightMeters,
      'cameraHeightMeters',
      'must be finite and greater than zero',
    );
  }
  final heightAtZoomZero = approximateCameraHeightMeters(
    zoom: 0,
    latitude: latitude,
    pitchDegrees: pitchDegrees,
    viewportHeightPixels: viewportHeightPixels,
  );
  if (!heightAtZoomZero.isFinite || heightAtZoomZero <= 0) return 15.5;
  return math.log(heightAtZoomZero / cameraHeightMeters) / math.ln2;
}

String formatCameraHeight(double meters) {
  if (!meters.isFinite || meters <= 0) return '—';
  if (meters < 1000) return '${meters.round()} m';
  final kilometers = meters / 1000;
  return '${kilometers.toStringAsFixed(kilometers < 10 ? 1 : 0)} km';
}
