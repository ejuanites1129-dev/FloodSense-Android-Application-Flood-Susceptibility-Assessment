import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/map/map_provider_config.dart';

void main() {
  group('FloodMapProviderConfig', () {
    test('requests Mapbox by default but requires a public token', () {
      final withoutToken = FloodMapProviderConfig.fromValues();
      expect(withoutToken.requestedProvider, FloodMapProvider.mapbox);
      expect(
        withoutToken.rendererFor(
          platform: TargetPlatform.android,
          isWeb: false,
        ),
        FloodMapRenderer.osm,
      );

      final configured = FloodMapProviderConfig.fromValues(
        mapboxPublicToken: 'pk.public-test-token',
      );
      expect(
        configured.rendererFor(
          platform: TargetPlatform.android,
          isWeb: false,
        ),
        FloodMapRenderer.mapbox,
      );
    });

    test('uses OSM when a public token is absent or invalid', () {
      for (final token in ['', 'sk.secret', 'not-a-token']) {
        final config = FloodMapProviderConfig.fromValues(
          provider: 'mapbox',
          mapboxPublicToken: token,
        );
        expect(
          config.rendererFor(platform: TargetPlatform.android, isWeb: false),
          FloodMapRenderer.osm,
        );
      }
    });

    test('uses Mapbox on supported mobile platforms with a public token', () {
      for (final provider in ['auto', 'mapbox']) {
        final config = FloodMapProviderConfig.fromValues(
          provider: provider,
          mapboxPublicToken: 'pk.public-test-token',
        );
        expect(
          config.rendererFor(platform: TargetPlatform.android, isWeb: false),
          FloodMapRenderer.mapbox,
        );
        expect(
          config.rendererFor(platform: TargetPlatform.iOS, isWeb: false),
          FloodMapRenderer.mapbox,
        );
      }
    });

    test('keeps OSM for web, desktop, and explicit OSM configuration', () {
      final automatic = FloodMapProviderConfig.fromValues(
        mapboxPublicToken: 'pk.public-test-token',
      );
      expect(
        automatic.rendererFor(platform: TargetPlatform.android, isWeb: true),
        FloodMapRenderer.osm,
      );
      expect(
        automatic.rendererFor(platform: TargetPlatform.windows, isWeb: false),
        FloodMapRenderer.osm,
      );

      final osm = FloodMapProviderConfig.fromValues(
        provider: 'osm',
        mapboxPublicToken: 'pk.public-test-token',
      );
      expect(
        osm.rendererFor(platform: TargetPlatform.android, isWeb: false),
        FloodMapRenderer.osm,
      );
    });

    test('defaults unknown provider values safely to automatic selection', () {
      final config = FloodMapProviderConfig.fromValues(
        provider: 'unexpected',
        mapboxPublicToken: 'pk.public-test-token',
        allowThreeDimensionalView: true,
      );
      expect(config.requestedProvider, FloodMapProvider.auto);
      expect(config.allowThreeDimensionalView, isTrue);
    });

    test('shows perspective only when opted in on a capable renderer', () {
      final enabled = FloodMapProviderConfig.fromValues(
        provider: 'mapbox',
        mapboxPublicToken: 'pk.public-test-token',
        allowThreeDimensionalView: true,
      );
      expect(
        enabled.showsThreeDimensionalControl(
          platform: TargetPlatform.android,
          isWeb: false,
        ),
        isTrue,
      );
      expect(
        enabled.showsThreeDimensionalControl(
          platform: TargetPlatform.android,
          isWeb: true,
        ),
        isFalse,
      );

      final disabled = FloodMapProviderConfig.fromValues(
        provider: 'mapbox',
        mapboxPublicToken: 'pk.public-test-token',
      );
      expect(
        disabled.showsThreeDimensionalControl(
          platform: TargetPlatform.android,
          isWeb: false,
        ),
        isFalse,
      );
    });
  });
}
