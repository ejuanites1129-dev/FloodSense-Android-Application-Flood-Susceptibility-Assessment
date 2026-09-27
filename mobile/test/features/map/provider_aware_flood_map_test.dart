import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/features/map/flood_map_presentation.dart';
import 'package:floodsense/features/map/map_provider_config.dart';
import 'package:floodsense/features/map/provider_aware_flood_map.dart';

void main() {
  const presentation = FloodMapPresentation(
    referenceAreas: [],
    scenarioAreas: [],
    scenarioResults: {},
    onCoordinateTapped: _ignoreCoordinate,
  );

  testWidgets('keeps the OSM surface when Mapbox is not configured', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: SizedBox(
          width: 300,
          height: 300,
          child: ProviderAwareFloodMap(
            config: FloodMapProviderConfig(
              requestedProvider: FloodMapProvider.auto,
              mapboxPublicToken: '',
              allowThreeDimensionalView: false,
            ),
            presentation: presentation,
            osmMap: ColoredBox(
              key: Key('osm-test-surface'),
              color: Colors.blue,
            ),
          ),
        ),
      ),
    );

    expect(find.byKey(const Key('osm-test-surface')), findsOneWidget);
    expect(find.byKey(const Key('map-provider-fallback-status')), findsNothing);
  });

  testWidgets('switches to OSM with a generic status after renderer failure', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 300,
          height: 300,
          child: ProviderAwareFloodMap(
            config: const FloodMapProviderConfig(
              requestedProvider: FloodMapProvider.mapbox,
              mapboxPublicToken: 'pk.public-token-must-not-appear',
              allowThreeDimensionalView: false,
            ),
            presentation: presentation,
            osmMap: const ColoredBox(
              key: Key('osm-test-surface'),
              color: Colors.blue,
            ),
            mapboxBuilder: (presentation, config, onUnavailable) {
              WidgetsBinding.instance.addPostFrameCallback(
                (_) => onUnavailable(),
              );
              return const ColoredBox(
                key: Key('mapbox-test-surface'),
                color: Colors.green,
              );
            },
          ),
        ),
      ),
    );
    expect(find.byKey(const Key('mapbox-test-surface')), findsOneWidget);

    await tester.pump();

    expect(find.byKey(const Key('osm-test-surface')), findsOneWidget);
    expect(
      find.text('Enhanced map unavailable. Standard map is active.'),
      findsOneWidget,
    );
    expect(
      find.textContaining('pk.public-token-must-not-appear'),
      findsNothing,
    );
  });
}

void _ignoreCoordinate(dynamic _) {}
