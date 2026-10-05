import 'dart:ui' as ui;

import 'package:mapbox_maps_flutter/mapbox_maps_flutter.dart';

import '../evacuation/evacuation_center_marker.dart';
import 'flood_map_palette.dart';

/// Keep every selected shelter visible even when its text collides with nearby
/// labels or a 3D building covers the geographic point. Labels may be omitted;
/// the actual icon must not disappear during camera movement.
SymbolLayer createEvacuationShelterSymbolLayer({
  required String id,
  required String sourceId,
  required String imageId,
}) => SymbolLayer(
  id: id,
  sourceId: sourceId,
  slot: 'top',
  filter: [
    '==',
    'verified-center',
    ['get', 'kind'],
  ],
  iconImage: imageId,
  iconAllowOverlap: true,
  iconIgnorePlacement: true,
  textOptional: true,
  textIgnorePlacement: true,
  iconOcclusionOpacity: 1,
  iconAnchor: IconAnchor.CENTER,
  iconPitchAlignment: IconPitchAlignment.VIEWPORT,
  iconSizeExpression: [
    'case',
    [
      '==',
      true,
      ['get', 'selected'],
    ],
    1.15,
    0.90,
  ],
  textFieldExpression: [
    'case',
    [
      '==',
      true,
      ['get', 'nearest'],
    ],
    [
      'case',
      [
        '==',
        true,
        ['get', 'is_demonstration'],
      ],
      'Nearest · TEST',
      'Nearest',
    ],
    [
      '==',
      true,
      ['get', 'is_demonstration'],
    ],
    'TEST',
    '',
  ],
  textAnchor: TextAnchor.TOP,
  textOffset: [0, 2],
  textSize: 12,
  textColor: FloodMapPalette.center.toARGB32(),
  textHaloColor: 0xFFFFFFFF,
  textHaloWidth: 2,
);

/// Render the shared shelter badge in the format the native bridge accepts.
///
/// Although MbxImage's Dart documentation describes raw RGBA, the installed
/// Mapbox Flutter 2.31 native addStyleImage bridges decode encoded image bytes
/// with BitmapFactory (Android) and UIImage (iOS). PNG preserves transparency
/// and avoids rejecting a raw pixel buffer during map-style initialization.
Future<MbxImage> createEvacuationShelterStyleImage() async {
  const size = 96;
  final recorder = ui.PictureRecorder();
  paintEvacuationShelter(
    ui.Canvas(recorder),
    const ui.Rect.fromLTWH(0, 0, 96, 96),
    FloodMapPalette.center,
  );
  final picture = recorder.endRecording();
  ui.Image? image;
  try {
    image = await picture.toImage(size, size);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    if (bytes == null) {
      throw StateError('Unable to encode the evacuation shelter icon.');
    }
    return MbxImage(
      width: size,
      height: size,
      data: bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes),
    );
  } finally {
    image?.dispose();
    picture.dispose();
  }
}
