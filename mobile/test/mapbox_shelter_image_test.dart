import 'dart:ui' as ui;

import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/map/mapbox_shelter_image.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('native shelter placement cannot be hidden by text collision or 3D buildings', () {
    final layer = createEvacuationShelterSymbolLayer(
      id: 'shelters',
      sourceId: 'points',
      imageId: 'shelter-image',
    );
    expect(layer.iconAllowOverlap, isTrue);
    expect(layer.iconIgnorePlacement, isTrue);
    expect(layer.textOptional, isTrue);
    expect(layer.textIgnorePlacement, isTrue);
    expect(layer.iconOcclusionOpacity, 1);
    expect(layer.minZoom, isNull);
    expect(layer.maxZoom, isNull);
    expect(layer.slot, 'top');
  });

  test(
    'native shelter style image supplies encoded PNG, not raw pixels',
    () async {
      final shelter = await createEvacuationShelterStyleImage();

      expect(shelter.width, 96);
      expect(shelter.height, 96);
      expect(shelter.data.take(8), [137, 80, 78, 71, 13, 10, 26, 10]);
      expect(shelter.data.length, lessThan(96 * 96 * 4));
    },
  );

  test(
    'native shelter PNG decodes with the transparent, visible badge',
    () async {
      final shelter = await createEvacuationShelterStyleImage();
      final codec = await ui.instantiateImageCodec(shelter.data);
      ui.Image? image;
      try {
        image = (await codec.getNextFrame()).image;
        expect(image.width, shelter.width);
        expect(image.height, shelter.height);
        final pixels = await image.toByteData(
          format: ui.ImageByteFormat.rawRgba,
        );
        expect(pixels, isNotNull);
        expect(pixels!.lengthInBytes, 96 * 96 * 4);

        List<int> rgbaAt(int x, int y) => [
          for (var channel = 0; channel < 4; channel++)
            pixels.getUint8((y * 96 + x) * 4 + channel),
        ];

        // Transparent corner, opaque purple building, and a white doorway.
        expect(rgbaAt(0, 0), [0, 0, 0, 0]);
        expect(rgbaAt(40, 52), [106, 27, 154, 255]);
        expect(rgbaAt(48, 65), [255, 255, 255, 255]);
      } finally {
        image?.dispose();
        codec.dispose();
      }
    },
  );
}
