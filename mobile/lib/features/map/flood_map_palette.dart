import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/models/map_assessment_result.dart';

/// One presentation palette shared by the OSM and Mapbox renderers.
abstract final class FloodMapPalette {
  static const low = AppColors.low;
  static const moderate = AppColors.moderate;
  static const high = AppColors.high;
  static const veryHigh = AppColors.veryHigh;
  static const limitation = AppColors.limitation;
  static const selection = AppColors.primary;
  static const boundary = AppColors.primary;
  static const center = Color(0xFF6A1B9A);
  // Coverage masking is a separate neutral cue, not a susceptibility class.
  static const outsideCoverage = Color(0xA6677280);

  static Color forAssessment(MapAreaAssessment? assessment) =>
      assessment?.isClassified == true
      // The versioned backend result remains authoritative when it supplies a
      // valid map color. Susceptibility meaning is not inferred in the client.
      ? Color(assessment!.susceptibility!.colorValue)
      : limitation;

  static String cssHex(Color color) =>
      '#${color.toARGB32().toRadixString(16).padLeft(8, '0').substring(2).toUpperCase()}';
}
