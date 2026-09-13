import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

import '../../../app/theme/app_colors.dart';
import '../../../data/models/assessment_result.dart';
import '../../../data/models/geojson_geometry.dart';
import '../../../data/models/geographic_area.dart';
import '../../../data/models/map_assessment_result.dart';
import '../../../data/models/point_resolution.dart';
import '../assessment_controller.dart';

class DynamicMapCard extends StatefulWidget {
  const DynamicMapCard({
    required this.controller,
    this.showBasemap = true,
    super.key,
  });

  final AssessmentController controller;
  final bool showBasemap;

  @override
  State<DynamicMapCard> createState() => _DynamicMapCardState();
}

class _DynamicMapCardState extends State<DynamicMapCard> {
  final MapController _mapController = MapController();
  bool _mapReady = false;
  int? _lastSelectedAreaId;

  @override
  void didUpdateWidget(covariant DynamicMapCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    final selected = widget.controller.selectedArea;
    if (selected?.id != _lastSelectedAreaId && selected != null) {
      _lastSelectedAreaId = selected.id;
      WidgetsBinding.instance.addPostFrameCallback((_) => _fitArea(selected));
    } else if (selected == null) {
      _lastSelectedAreaId = null;
    }
  }

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  void _fitAll() {
    if (!_mapReady) return;
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: GeoJsonGeometry.boundsFor(
          widget.controller.areas.map((area) => area.geometry),
        ),
        padding: const EdgeInsets.all(28),
        maxZoom: 16,
      ),
    );
  }

  void _fitArea(GeographicArea area) {
    if (!_mapReady) return;
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: area.geometry.bounds,
        padding: const EdgeInsets.all(52),
        maxZoom: 16,
      ),
    );
  }

  void _zoom(double change) {
    if (!_mapReady) return;
    final camera = _mapController.camera;
    _mapController.move(
      camera.center,
      (camera.zoom + change).clamp(2, 18).toDouble(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final bounds = GeoJsonGeometry.boundsFor(
      controller.areas.map((area) => area.geometry),
    );
    final polygons = _buildPolygons(controller);
    final pin = controller.pinCoordinate;

    return Card(
      key: const Key('dynamic-map-card'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.map_outlined, color: AppColors.primary),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Dynamic demonstration map',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 3),
                      Text(
                        'Pan, zoom, or tap to place a temporary pin.',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Semantics(
              container: true,
              label: 'Permanent map warning. DEMONSTRATION DATA—NOT OFFICIAL. Polygons are fictional and are not official Bacoor boundaries.',
              child: Container(
                key: const Key('map-demonstration-warning'),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.warningSurface,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'DEMONSTRATION DATA—NOT OFFICIAL\nFictional polygons—not official Bacoor boundaries or current conditions.',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
                ),
              ),
            ),
            const SizedBox(height: 10),
            LayoutBuilder(
              builder: (context, constraints) {
                final height = constraints.maxWidth < 360 ? 280.0 : 330.0;
                return Semantics(
                  container: true,
                  label: 'Interactive demonstration map. Drag to pan, pinch to zoom, or tap to place a temporary pin.',
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: SizedBox(
                      key: const Key('dynamic-map'),
                      height: height,
                      child: Stack(
                        children: [
                          FlutterMap(
                            mapController: _mapController,
                            options: MapOptions(
                              initialCameraFit: CameraFit.bounds(
                                bounds: bounds,
                                padding: const EdgeInsets.all(24),
                                maxZoom: 16,
                              ),
                              minZoom: 2,
                              maxZoom: 18,
                              keepAlive: true,
                              onMapReady: () => _mapReady = true,
                              onTap: (_, point) => controller.placePin(
                                MapCoordinate(
                                  latitude: point.latitude,
                                  longitude: point.longitude,
                                ),
                              ),
                            ),
                            children: [
                              if (widget.showBasemap)
                                TileLayer(
                                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                                  userAgentPackageName:
                                      'ph.edu.cvsu.bacoor.floodsense',
                                  maxNativeZoom: 19,
                                ),
                              PolygonLayer<int>(
                                key: const Key('demonstration-polygons'),
                                polygons: polygons,
                                drawLabelsLast: true,
                              ),
                              if (pin != null)
                                MarkerLayer(
                                  markers: [
                                    Marker(
                                      key: const Key('temporary-pin-marker'),
                                      point: pin.latLng,
                                      width: 48,
                                      height: 48,
                                      alignment: Alignment.topCenter,
                                      child: Semantics(
                                        label:
                                            'Temporary demonstration pin at latitude ${pin.latitude.toStringAsFixed(6)}, longitude ${pin.longitude.toStringAsFixed(6)}',
                                        child: const Icon(
                                          Icons.location_on,
                                          size: 44,
                                          color: AppColors.error,
                                          shadows: [
                                            Shadow(
                                              blurRadius: 4,
                                              color: Colors.white,
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              Align(
                                alignment: Alignment.bottomRight,
                                child: Semantics(
                                  label: 'Basemap attribution: OpenStreetMap contributors',
                                  child: const ColoredBox(
                                    color: Color(0xDDFFFFFF),
                                    child: Padding(
                                      padding: EdgeInsets.all(4),
                                      child: Text(
                                        '© OpenStreetMap contributors',
                                        key: Key('osm-attribution'),
                                        style: TextStyle(fontSize: 10),
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          Positioned(
                            left: 8,
                            top: 8,
                            child: Column(
                              children: [
                                _MapControl(
                                  key: const Key('map-zoom-in'),
                                  label: 'Zoom in',
                                  icon: Icons.add,
                                  onPressed: () => _zoom(1),
                                ),
                                const SizedBox(height: 6),
                                _MapControl(
                                  key: const Key('map-zoom-out'),
                                  label: 'Zoom out',
                                  icon: Icons.remove,
                                  onPressed: () => _zoom(-1),
                                ),
                                const SizedBox(height: 6),
                                _MapControl(
                                  key: const Key('map-fit-all'),
                                  label: 'Fit all demonstration areas',
                                  icon: Icons.fit_screen,
                                  onPressed: _fitAll,
                                ),
                              ],
                            ),
                          ),
                          if (controller.isMapAssessing)
                            const Positioned.fill(child: _MapLoadingOverlay()),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
            if (controller.mapError case final error?) ...[
              const SizedBox(height: 10),
              _MapError(
                message: error.message,
                onRetry: () => controller.refreshMapAssessment(force: true),
              ),
            ],
            const SizedBox(height: 12),
            MapLegend(results: controller.mapResultsByAreaId.values),
            const SizedBox(height: 12),
            _PointResolutionStatus(controller: controller),
          ],
        ),
      ),
    );
  }

  List<Polygon<int>> _buildPolygons(AssessmentController controller) {
    final result = <Polygon<int>>[];
    for (final area in controller.areas) {
      final assessment = controller.mapResultsByAreaId[area.id];
      final selected = controller.selectedArea?.id == area.id;
      final statusColor = assessment?.isClassified == true
          ? Color(assessment!.susceptibility!.colorValue)
          : AppColors.limitation;
      final statusLabel = _mapStateLabel(assessment);
      for (var index = 0; index < area.geometry.polygons.length; index++) {
        final polygon = area.geometry.polygons[index];
        result.add(
          Polygon<int>(
            points: polygon.exterior,
            holePointsList: polygon.holes.isEmpty ? null : polygon.holes,
            color: statusColor.withValues(alpha: selected ? 0.48 : 0.32),
            borderColor: selected ? AppColors.primary : statusColor,
            borderStrokeWidth: selected ? 4 : 2,
            label: index == 0 ? '${area.name}\n$statusLabel' : null,
            labelStyle: const TextStyle(
              color: AppColors.bodyText,
              fontSize: 11,
              fontWeight: FontWeight.w800,
              shadows: [Shadow(color: Colors.white, blurRadius: 4)],
            ),
            hitValue: area.id,
          ),
        );
      }
    }
    return result;
  }
}

String _mapStateLabel(MapAreaAssessment? assessment) {
  if (assessment == null) return 'No scenario result';
  return switch (assessment.state) {
    AssessmentState.classified => assessment.susceptibility!.label,
    AssessmentState.uncertain => 'Uncertain',
    AssessmentState.insufficientData => 'Insufficient Data',
    AssessmentState.unknown => 'Unavailable',
  };
}

class _MapControl extends StatelessWidget {
  const _MapControl({
    required this.label,
    required this.icon,
    required this.onPressed,
    super.key,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      child: Material(
        color: AppColors.surface,
        elevation: 2,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(8),
          child: SizedBox(
            width: 48,
            height: 48,
            child: Icon(icon, color: AppColors.primary),
          ),
        ),
      ),
    );
  }
}

class _MapLoadingOverlay extends StatelessWidget {
  const _MapLoadingOverlay();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      key: const Key('map-loading-overlay'),
      container: true,
      liveRegion: true,
      label: 'Updating polygon results for the selected scenario',
      child: ColoredBox(
        color: const Color(0x88FFFFFF),
        child: Center(
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                SizedBox(width: 10),
                Text('Updating map…'),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MapError extends StatelessWidget {
  const _MapError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      liveRegion: true,
      label: 'Map result error. $message',
      child: Container(
        key: const Key('map-assessment-error'),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFFFEEEE),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Map results could not be updated. Polygons remain neutral.',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(message),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('map-retry-button'),
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry map results'),
            ),
          ],
        ),
      ),
    );
  }
}

class MapLegend extends StatelessWidget {
  const MapLegend({required this.results, super.key});

  final Iterable<MapAreaAssessment> results;

  @override
  Widget build(BuildContext context) {
    final serverColors = <String, Color>{};
    for (final result in results) {
      final susceptibility = result.susceptibility;
      if (result.isClassified && susceptibility != null) {
        serverColors[susceptibility.code] = Color(susceptibility.colorValue);
      }
    }
    final entries = [
      ('LOW', 'Low', AppColors.low),
      ('MODERATE', 'Moderate', AppColors.moderate),
      ('HIGH', 'High', AppColors.high),
      ('VERY_HIGH', 'Very High', AppColors.veryHigh),
      ('LIMITATION', 'Uncertain / Insufficient Data', AppColors.limitation),
    ];
    return Semantics(
      container: true,
      label: 'Map legend. Colors represent the selected hypothetical scenario, not current conditions.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Map legend',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          ...entries.map(
            (entry) => Padding(
              padding: const EdgeInsets.only(bottom: 5),
              child: Semantics(
                label: '${entry.$2} legend entry',
                child: Row(
                  children: [
                    Container(
                      width: 14,
                      height: 14,
                      decoration: BoxDecoration(
                        color: serverColors[entry.$1] ?? entry.$3,
                        border: Border.all(color: AppColors.bodyText),
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                    const SizedBox(width: 5),
                    Expanded(
                      child: Text(
                        entry.$2,
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Colors describe the selected hypothetical scenario—not live rainfall, current conditions, or safety.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _PointResolutionStatus extends StatelessWidget {
  const _PointResolutionStatus({required this.controller});

  final AssessmentController controller;

  @override
  Widget build(BuildContext context) {
    if (controller.pinCoordinate == null) {
      return const Text(
        'Tap the map to place a temporary pin. Django and PostGIS—not the phone—will determine the containing zone.',
      );
    }
    if (controller.isResolvingPoint) {
      return Semantics(
        liveRegion: true,
        label: 'Resolving temporary pin with the FloodSense server',
        child: const Row(
          children: [
            SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            SizedBox(width: 8),
            Expanded(child: Text('Resolving the temporary pin…')),
          ],
        ),
      );
    }
    if (controller.pointError case final error?) {
      return Semantics(
        container: true,
        liveRegion: true,
        label: 'Temporary pin resolution failed. ${error.message}',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(error.message),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('point-retry-button'),
              onPressed: controller.retryPointResolution,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry pin resolution'),
            ),
          ],
        ),
      );
    }
    final resolution = controller.pointResolution;
    if (resolution == null) return const SizedBox.shrink();
    final (icon, title, message) = switch (resolution.state) {
      PointResolutionState.resolved => (
        Icons.check_circle_outline,
        'Demonstration zone resolved',
        '${resolution.area!.name} (${resolution.area!.code}) was confirmed by Django/PostGIS.',
      ),
      PointResolutionState.outsideSupportedArea => (
        Icons.info_outline,
        'Outside supported area',
        'Reposition the pin or choose a demonstration zone from the selector below.',
      ),
      PointResolutionState.ambiguousArea => (
        Icons.layers_outlined,
        'Point overlaps multiple zones',
        'Reposition the pin or use the demonstration-zone selector below.',
      ),
      PointResolutionState.unknown => (
        Icons.help_outline,
        'Point could not be resolved',
        'No zone was assumed. Reposition the pin or use the selector below.',
      ),
    };
    return Semantics(
      container: true,
      liveRegion: true,
      label: '$title. $message',
      child: Container(
        key: Key('point-state-${resolution.rawState}'),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.pageBackground,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.divider),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: AppColors.primary),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 3),
                  Text(message),
                  const SizedBox(height: 4),
                  const Text(
                    'The coordinate is temporary and is not saved.',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppColors.secondaryText,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class SelectedZonePreview extends StatelessWidget {
  const SelectedZonePreview({required this.controller, super.key});

  final AssessmentController controller;

  @override
  Widget build(BuildContext context) {
    final area = controller.selectedArea;
    if (area == null) {
      return Semantics(
        container: true,
        label: 'No demonstration zone selected',
        child: const Text(
          'Select a zone using the map pin or the selector to view its scenario result.',
        ),
      );
    }
    final mapResult = controller.mapResultsByAreaId[area.id];
    final intensity = controller.selectedIntensity?.label ?? 'Not selected';
    final duration = controller.selectedDuration?.label ?? 'Not selected';
    final stateLabel = _mapStateLabel(mapResult);
    return Semantics(
      container: true,
      label:
          'Selected zone ${area.name}, ${area.code}. Current map result: $stateLabel.',
      child: Container(
        key: const Key('selected-zone-preview'),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.activeBackground,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.primary),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Selected-zone preview',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 3),
            Text(
              '${area.name} (${area.code})',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            Text('Scenario: $intensity · $duration'),
            Text('Map result: $stateLabel'),
            if (mapResult != null && mapResult.matchedRuleCodes.isNotEmpty)
              Text('Matched rule: ${mapResult.matchedRuleCodes.join(', ')}'),
            if (mapResult != null && mapResult.ruleset != null)
              Text(
                'Rule set: ${mapResult.ruleset!.name} v${mapResult.ruleset!.version}',
              ),
            const SizedBox(height: 6),
            Text(
              mapResult?.summary ?? 'Choose both rainfall inputs to request this zone’s map result.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
