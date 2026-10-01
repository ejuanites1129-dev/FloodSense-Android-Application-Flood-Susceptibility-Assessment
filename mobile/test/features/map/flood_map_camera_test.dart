import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/map/flood_map_camera.dart';

void main() {
  test('70 meter camera target round-trips through the zoom conversion', () {
    final zoom = zoomForCameraHeightMeters(
      cameraHeightMeters: selectedLocationCameraHeightMeters,
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
