import 'package:flutter/foundation.dart';

enum FloodMapProvider { auto, mapbox, osm }

enum FloodMapRenderer { mapbox, osm }

/// Compile-time map presentation configuration.
///
/// The Mapbox public token is supplied with `--dart-define` and is never
/// written to source control. Stable Mapbox Flutter releases currently target
/// Android and iOS, so web and desktop builds deliberately keep the OSM map.
final class FloodMapProviderConfig {
  const FloodMapProviderConfig({
    required this.requestedProvider,
    required this.mapboxPublicToken,
    required this.allowThreeDimensionalView,
  });

  factory FloodMapProviderConfig.fromEnvironment() =>
      FloodMapProviderConfig.fromValues(
        provider: const String.fromEnvironment(
          'FLOODSENSE_MAP_PROVIDER',
          defaultValue: 'mapbox',
        ),
        mapboxPublicToken: const String.fromEnvironment('MAPBOX_ACCESS_TOKEN'),
        allowThreeDimensionalView: const bool.fromEnvironment(
          'FLOODSENSE_MAP_3D',
          defaultValue: false,
        ),
      );

  factory FloodMapProviderConfig.fromValues({
    String provider = 'mapbox',
    String mapboxPublicToken = '',
    bool allowThreeDimensionalView = false,
  }) {
    final normalizedProvider = provider.trim().toLowerCase();
    return FloodMapProviderConfig(
      requestedProvider: switch (normalizedProvider) {
        'mapbox' => FloodMapProvider.mapbox,
        'osm' => FloodMapProvider.osm,
        _ => FloodMapProvider.auto,
      },
      mapboxPublicToken: mapboxPublicToken.trim(),
      allowThreeDimensionalView: allowThreeDimensionalView,
    );
  }

  final FloodMapProvider requestedProvider;
  final String mapboxPublicToken;
  final bool allowThreeDimensionalView;

  bool get hasValidPublicToken => mapboxPublicToken.startsWith('pk.');

  FloodMapRenderer rendererFor({TargetPlatform? platform, bool? isWeb}) {
    if (requestedProvider == FloodMapProvider.osm ||
        (isWeb ?? kIsWeb) ||
        !hasValidPublicToken) {
      return FloodMapRenderer.osm;
    }
    final target = platform ?? defaultTargetPlatform;
    final supportsStableMapbox =
        target == TargetPlatform.android || target == TargetPlatform.iOS;
    return supportsStableMapbox
        ? FloodMapRenderer.mapbox
        : FloodMapRenderer.osm;
  }

  /// The perspective control is present only for an opted-in, capable
  /// renderer. This keeps the visibility rule independently testable without
  /// constructing the native platform view in a widget test.
  bool showsThreeDimensionalControl({TargetPlatform? platform, bool? isWeb}) =>
      allowThreeDimensionalView &&
      rendererFor(platform: platform, isWeb: isWeb) == FloodMapRenderer.mapbox;
}

final floodMapProviderConfig = FloodMapProviderConfig.fromEnvironment();
