import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/map/flood_map_camera.dart';

void main() {
  test('Bacoor overview is a modest half-step closer to the fitted city', () {
    expect(bacoorOverviewZoomBoost, 0.5);
    expect(closerBacoorOverviewZoom(10), 10.5);
  });

  test('closer overview retains the bounds-fit zoom limits', () {
    expect(closerBacoorOverviewZoom(13.8), 14);
    expect(closerBacoorOverviewZoom(14), 14);
    expect(closerBacoorOverviewZoom(15.8, maximumZoom: 16), 16);
    expect(closerBacoorOverviewZoom(1), 2);
  });

  for (final view in [
    (pitch: 0.0, height: 47000.0),
    (pitch: 45.0, height: 34000.0),
  ]) {
    test(
      'overview brings the ${view.pitch} degree view proportionally closer',
      () {
        final fittedZoom = zoomForCameraHeightMeters(
          cameraHeightMeters: view.height,
          latitude: 14.46,
          pitchDegrees: view.pitch,
          viewportHeightPixels: 700,
        );
        final closerHeight = approximateCameraHeightMeters(
          zoom: closerBacoorOverviewZoom(fittedZoom),
          latitude: 14.46,
          pitchDegrees: view.pitch,
          viewportHeightPixels: 700,
        );
        expect(closerHeight, closeTo(view.height / math.sqrt(2), 0.01));
        expect(closerHeight, lessThan(view.height));
      },
    );
  }

  test('zoom steps are smoother without a long control delay', () {
    expect(mapZoomAnimationDuration.inMilliseconds, 650);
    expect(mapZoomAnimationDuration.inMilliseconds, inInclusiveRange(500, 800));
  });

  test(
    'location focus is slower than a step but settles within 1.5 seconds',
    () {
      expect(selectedLocationAnimationDuration.inMilliseconds, 1400);
      expect(
        selectedLocationAnimationDuration,
        greaterThan(mapZoomAnimationDuration),
      );
      expect(
        selectedLocationAnimationDuration.inMilliseconds,
        lessThanOrEqualTo(1500),
      );
    },
  );

  test('fit and shelter recenter stay between step and location timings', () {
    for (final duration in [
      mapFitAnimationDuration,
      mapRecenterAnimationDuration,
    ]) {
      expect(duration, greaterThan(mapZoomAnimationDuration));
      expect(duration, lessThan(selectedLocationAnimationDuration));
    }
  });

  test('70 meter camera target round-trips through the zoom conversion', () {
    final zoom = zoomForCameraHeightMeters(
      cameraHeightMeters: 70,
      latitude: 14.46,
      pitchDegrees: 0,
      viewportHeightPixels: 700,
    );

    expect(zoom, inInclusiveRange(19, 21));
    expect(
      approximateCameraHeightMeters(
        zoom: zoom,
        latitude: 14.46,
        pitchDegrees: 0,
        viewportHeightPixels: 700,
      ),
      closeTo(70, 0.01),
    );
  });

  test('editable selected-location target round-trips without a fixed zoom assumption', () {
    final zoom = zoomForCameraHeightMeters(
      cameraHeightMeters: selectedLocationCameraHeightMeters,
      latitude: 14.46,
      pitchDegrees: 0,
      viewportHeightPixels: 700,
    );
    expect(zoom.isFinite, isTrue);
    expect(
      approximateCameraHeightMeters(
        zoom: zoom,
        latitude: 14.46,
        pitchDegrees: 0,
        viewportHeightPixels: 700,
      ),
      closeTo(selectedLocationCameraHeightMeters, 0.01),
    );
  });

  test(
    'camera height display uses meters nearby and kilometers farther out',
    () {
      expect(formatCameraHeight(69.6), '70 m');
      expect(formatCameraHeight(1530), '1.5 km');
      expect(formatCameraHeight(double.nan), '—');
    },
  );

  test('invalid target height is rejected', () {
    expect(
      () => zoomForCameraHeightMeters(
        cameraHeightMeters: 0,
        latitude: 14.46,
        pitchDegrees: 0,
        viewportHeightPixels: 700,
      ),
      throwsArgumentError,
    );
  });
}
