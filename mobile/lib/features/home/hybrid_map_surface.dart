import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../app/theme/app_colors.dart';
import '../../data/models/assessment_result.dart';
import '../../data/models/geojson_geometry.dart';
import '../../data/models/geographic_area.dart';
import '../../data/models/map_assessment_result.dart';
import '../../data/models/point_resolution.dart';
import '../../data/models/verified_center.dart';
import '../assessment/assessment_controller.dart';
import '../assessment/widgets/dynamic_map_card.dart';
import '../evacuation/nearest_center_controller.dart';
import '../location/location_controller.dart';

/// The shared map canvas behind Map, Assess, and Prepare.
///
/// It deliberately owns only presentation state. Scenario, location, result,
/// and DSS state remain in the resident shell controllers.
class HybridMapSurface extends StatefulWidget {
  const HybridMapSurface({
    required this.controller,
    this.locationController,
    this.nearestCenterController,
    this.showBasemap = true,
    super.key,
  });

  final AssessmentController controller;
  final LocationController? locationController;
  final NearestCenterController? nearestCenterController;
  final bool showBasemap;

  @override
  State<HybridMapSurface> createState() => _HybridMapSurfaceState();
}

class _HybridMapSurfaceState extends State<HybridMapSurface> {
  final MapController _mapController = MapController();
  bool _mapReady = false;
  int? _lastSelectedAreaId;
  String? _lastSelectedCenter;

  @override
  void didUpdateWidget(covariant HybridMapSurface oldWidget) {
    super.didUpdateWidget(oldWidget);
    _centerSelectionWhenNeeded();
  }

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  void _fitAll() {
    if (!_mapReady || widget.controller.referenceAreas.isEmpty) return;
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: GeoJsonGeometry.boundsFor(
          widget.controller.referenceAreas.map((area) => area.geometry),
        ),
        padding: const EdgeInsets.fromLTRB(24, 132, 24, 170),
        maxZoom: 14,
      ),
    );
  }

  void _zoom(double delta) {
    if (!_mapReady) return;
    final camera = _mapController.camera;
    _mapController.move(
      camera.center,
      (camera.zoom + delta).clamp(2, 18).toDouble(),
    );
  }

  void _centerSelectionWhenNeeded() {
    if (!_mapReady) return;
    final coordinate =
        widget.locationController?.lookupCoordinate ??
        widget.controller.pinCoordinate;
    if (coordinate != null &&
        widget.controller.selectedArea?.id != _lastSelectedAreaId) {
      _lastSelectedAreaId = widget.controller.selectedArea?.id;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _mapReady) {
          _mapController.move(coordinate.latLng, 15.5);
        }
      });
    }

    final centers = widget.nearestCenterController;
    final selected = centers?.selectedCenterIdentifier;
    if (centers != null &&
        selected != null &&
        selected != _lastSelectedCenter) {
      final matches = centers.centers.where(
        (center) => center.publicIdentifier == selected,
      );
      if (matches.length == 1) {
        _lastSelectedCenter = selected;
        final center = matches.single;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && _mapReady) {
            _mapController.move(
              LatLng(center.latitude, center.longitude),
              15.5,
            );
          }
        });
      }
    }
  }

  void _placeTemporaryPin(LatLng point) {
    final coordinate = MapCoordinate(
      latitude: point.latitude,
      longitude: point.longitude,
    );
    unawaited(widget.controller.placePin(coordinate));
    final location = widget.locationController;
    if (location != null) unawaited(location.resolveManualPin(coordinate));
  }

  @override
  Widget build(BuildContext context) {
    final listenables = <Listenable>[
      widget.controller,
      ?widget.locationController,
      ?widget.nearestCenterController,
    ];
    return AnimatedBuilder(
      animation: Listenable.merge(listenables),
      builder: (context, _) {
        _centerSelectionWhenNeeded();
        if (widget.controller.isReferenceLoading) {
          return const ColoredBox(
            color: Color(0xFFEAF4F7),
            child: Center(
              child: CircularProgressIndicator(
                semanticsLabel: 'Loading the Bacoor map',
              ),
            ),
          );
        }
        if (widget.controller.referenceError case final error?) {
          return _MapUnavailable(
            message: error.message,
            onRetry: widget.controller.loadReferenceBoundaries,
          );
        }
        if (widget.controller.referenceAreas.isEmpty) {
          return const _MapUnavailable(
            message: 'No supported Bacoor boundary layer is available. Ask an administrator to review the map data setup.',
          );
        }
        return _map(context);
      },
    );
  }

  Widget _map(BuildContext context) {
    final controller = widget.controller;
    final bounds = GeoJsonGeometry.boundsFor(
      controller.referenceAreas.map((area) => area.geometry),
    );
    final coordinate =
        widget.locationController?.lookupCoordinate ?? controller.pinCoordinate;
    final centers =
        widget.nearestCenterController?.centers ?? const <VerifiedCenter>[];

    return Semantics(
      container: true,
      label: 'Interactive Bacoor scenario map. Drag to pan, pinch to zoom, or tap to place a temporary pin.',
      child: Stack(
        fit: StackFit.expand,
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCameraFit: CameraFit.bounds(
                bounds: bounds,
                padding: const EdgeInsets.fromLTRB(22, 118, 22, 150),
                maxZoom: 14,
              ),
              minZoom: 2,
              maxZoom: 18,
              keepAlive: true,
              onMapReady: () {
                _mapReady = true;
                _centerSelectionWhenNeeded();
              },
              onTap: (_, point) => _placeTemporaryPin(point),
            ),
            children: [
              if (widget.showBasemap)
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'ph.edu.cvsu.bacoor.floodsense',
                  maxNativeZoom: 19,
                ),
              PolygonLayer<int>(
                key: const Key('hybrid-scenario-polygons'),
                polygons: _scenarioPolygons(controller),
                drawLabelsLast: true,
              ),
              PolygonLayer<int>(
                key: const Key('hybrid-boundary-polygons'),
                polygons: _boundaryPolygons(controller.referenceAreas),
              ),
              if (centers.isNotEmpty)
                MarkerLayer(
                  markers: [
                    for (final center in centers) _centerMarker(center),
                  ],
                ),
              if (widget.locationController?.temporaryLocation
                  case final temporary?)
                CircleLayer<String>(
                  circles: [
                    CircleMarker<String>(
                      point:
                          widget.locationController!.lookupCoordinate!.latLng,
                      radius: temporary.accuracyMeters,
                      useRadiusInMeter: true,
                      color: AppColors.primary.withValues(alpha: 0.12),
                      borderColor: AppColors.primary,
                      borderStrokeWidth: 1.5,
                    ),
                  ],
                ),
              if (coordinate != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      key: const Key('hybrid-temporary-pin'),
                      point: coordinate.latLng,
                      width: 52,
                      height: 52,
                      alignment: Alignment.topCenter,
                      child: Semantics(
                        label:
                            'Temporary map pin. This coordinate is not saved.',
                        child: const Icon(
                          Icons.location_on,
                          color: AppColors.error,
                          size: 46,
                          shadows: [Shadow(color: Colors.white, blurRadius: 5)],
                        ),
                      ),
                    ),
                  ],
                ),
              const Align(
                alignment: Alignment.bottomRight,
                child: ColoredBox(
                  color: Color(0xDDFFFFFF),
                  child: Padding(
                    padding: EdgeInsets.all(4),
                    child: Text(
                      '© OpenStreetMap contributors',
                      key: Key('hybrid-osm-attribution'),
                      style: TextStyle(fontSize: 10),
                    ),
                  ),
                ),
              ),
            ],
          ),
          Positioned(
            right: 14,
            top: 116,
            child: Column(
              children: [
                _MapButton(
                  label: 'Zoom in',
                  icon: Icons.add,
                  onPressed: () => _zoom(1),
                ),
                const SizedBox(height: 8),
                _MapButton(
                  label: 'Zoom out',
                  icon: Icons.remove,
                  onPressed: () => _zoom(-1),
                ),
                const SizedBox(height: 8),
                _MapButton(
                  label: 'Fit all Bacoor barangays',
                  icon: Icons.center_focus_strong,
                  onPressed: _fitAll,
                ),
              ],
            ),
          ),
          if (controller.isMapAssessing)
            const Positioned.fill(child: MapLoadingOverlay()),
          if (controller.mapError case final error?)
            Positioned(
              left: 14,
              right: 76,
              top: 116,
              child: Material(
                elevation: 2,
                borderRadius: BorderRadius.circular(12),
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Row(
                    children: [
                      const Icon(Icons.cloud_off, color: AppColors.error),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          error.message,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Retry map scenario',
                        onPressed: () =>
                            controller.refreshMapAssessment(force: true),
                        icon: const Icon(Icons.refresh),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  List<Polygon<int>> _scenarioPolygons(AssessmentController controller) {
    final polygons = <Polygon<int>>[];
    for (final area in controller.areas) {
      final assessment = controller.mapResultsByAreaId[area.id];
      final selected = controller.selectedArea?.id == area.id;
      final color = assessment?.isClassified == true
          ? Color(assessment!.susceptibility!.colorValue)
          : AppColors.limitation;
      for (var index = 0; index < area.geometry.polygons.length; index++) {
        final polygon = area.geometry.polygons[index];
        polygons.add(
          Polygon<int>(
            points: polygon.exterior,
            holePointsList: polygon.holes.isEmpty ? null : polygon.holes,
            color: color.withValues(alpha: selected ? 0.5 : 0.32),
            borderColor: selected ? AppColors.primary : color,
            borderStrokeWidth: selected ? 4 : 2,
            label: selected && index == 0
                ? '${area.name}\n${_scenarioLabel(assessment)}'
                : null,
            labelStyle: const TextStyle(
              color: AppColors.bodyText,
              fontSize: 10,
              fontWeight: FontWeight.w800,
              shadows: [Shadow(color: Colors.white, blurRadius: 4)],
            ),
            hitValue: area.id,
          ),
        );
      }
    }
    return polygons;
  }

  List<Polygon<int>> _boundaryPolygons(List<GeographicArea> areas) {
    final confirmedCode =
        widget.locationController?.confirmedBarangay?.geographicAreaCode;
    return [
      for (final area in areas)
        for (final polygon in area.geometry.polygons)
          Polygon<int>(
            points: polygon.exterior,
            holePointsList: polygon.holes.isEmpty ? null : polygon.holes,
            color: AppColors.primary.withValues(
              alpha: area.code == confirmedCode ? 0.17 : 0.025,
            ),
            borderColor: area.code == confirmedCode
                ? AppColors.primary
                : AppColors.primary.withValues(alpha: 0.7),
            borderStrokeWidth: area.code == confirmedCode ? 3 : 1.2,
            hitValue: area.id,
          ),
    ];
  }

  Marker _centerMarker(VerifiedCenter center) {
    final active =
        widget.nearestCenterController?.selectedCenterIdentifier ==
        center.publicIdentifier;
    return Marker(
      point: LatLng(center.latitude, center.longitude),
      width: 48,
      height: 48,
      alignment: Alignment.topCenter,
      child: Semantics(
        button: true,
        selected: active,
        label: 'Verified center ${center.name}. ${center.distanceLabel}.',
        child: GestureDetector(
          onTap: () => widget.nearestCenterController?.selectCenter(
            center.publicIdentifier,
          ),
          child: Icon(
            Icons.home_work,
            size: active ? 44 : 36,
            color: const Color(0xFF6A1B9A),
            shadows: const [Shadow(color: Colors.white, blurRadius: 5)],
          ),
        ),
      ),
    );
  }
}

String _scenarioLabel(MapAreaAssessment? result) {
  if (result == null) return 'Choose a scenario';
  return switch (result.state) {
    AssessmentState.classified => result.susceptibility!.label,
    AssessmentState.uncertain => 'Uncertain',
    AssessmentState.insufficientData => 'Insufficient data',
    AssessmentState.unknown => 'Unavailable',
  };
}

class _MapButton extends StatelessWidget {
  const _MapButton({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    label: label,
    child: Material(
      color: AppColors.surface,
      elevation: 3,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
          width: 48,
          height: 48,
          child: Icon(icon, color: AppColors.primary),
        ),
      ),
    ),
  );
}

class _MapUnavailable extends StatelessWidget {
  const _MapUnavailable({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: const Color(0xFFEAF4F7),
    child: Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.map_outlined, size: 52, color: AppColors.primary),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 14),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry map'),
              ),
            ],
          ],
        ),
      ),
    ),
  );
}
