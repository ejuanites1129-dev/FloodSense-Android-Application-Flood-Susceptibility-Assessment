import 'package:flutter/widgets.dart';

import 'flood_map_presentation.dart';
import 'map_provider_config.dart';

Widget buildFloodMapboxSurface(
  FloodMapPresentation presentation,
  FloodMapProviderConfig config,
  VoidCallback onUnavailable,
) {
  WidgetsBinding.instance.addPostFrameCallback((_) => onUnavailable());
  return const SizedBox.expand();
}
