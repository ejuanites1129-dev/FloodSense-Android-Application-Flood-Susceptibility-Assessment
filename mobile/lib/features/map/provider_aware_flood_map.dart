import 'package:flutter/material.dart';

import 'flood_map_presentation.dart';
import 'flood_mapbox_surface.dart';
import 'map_provider_config.dart';

typedef FloodMapboxBuilder = Widget Function(
  FloodMapPresentation presentation,
  FloodMapProviderConfig config,
  VoidCallback onUnavailable,
);

/// Chooses the optional Mapbox renderer and reversibly falls back to OSM.
class ProviderAwareFloodMap extends StatefulWidget {
  const ProviderAwareFloodMap({
    required this.presentation,
    required this.osmMap,
    this.foreground,
    this.config,
    this.mapboxBuilder = buildFloodMapboxSurface,
    super.key,
  });

  final FloodMapPresentation presentation;
  final Widget osmMap;
  final Widget? foreground;
  final FloodMapProviderConfig? config;
  final FloodMapboxBuilder mapboxBuilder;

  @override
  State<ProviderAwareFloodMap> createState() => _ProviderAwareFloodMapState();
}

class _ProviderAwareFloodMapState extends State<ProviderAwareFloodMap> {
  bool _mapboxUnavailable = false;

  @override
  void didUpdateWidget(covariant ProviderAwareFloodMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.config != widget.config) _mapboxUnavailable = false;
  }

  @override
  Widget build(BuildContext context) {
    final config = widget.config ?? floodMapProviderConfig;
    final useMapbox =
        !_mapboxUnavailable && config.rendererFor() == FloodMapRenderer.mapbox;
    final surface = useMapbox
        ? widget.mapboxBuilder(widget.presentation, config, () {
            if (!mounted || _mapboxUnavailable) return;
            setState(() => _mapboxUnavailable = true);
          })
        : _osmSurface();
    return Stack(
      fit: StackFit.expand,
      children: [
        Positioned.fill(child: surface),
        ?widget.foreground,
      ],
    );
  }

  Widget _osmSurface() => Stack(
    fit: StackFit.expand,
    children: [
      widget.osmMap,
      if (_mapboxUnavailable)
        const Positioned(
          left: 8,
          right: 8,
          bottom: 28,
          child: _FallbackStatus(),
        ),
    ],
  );
}

class _FallbackStatus extends StatelessWidget {
  const _FallbackStatus();

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Material(
      key: const Key('map-provider-fallback-status'),
      color: const Color(0xEFFFFFFF),
      borderRadius: BorderRadius.circular(8),
      elevation: 2,
      child: const Padding(
        padding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Text(
          'Enhanced map unavailable. Standard map is active.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
        ),
      ),
    ),
  );
}
