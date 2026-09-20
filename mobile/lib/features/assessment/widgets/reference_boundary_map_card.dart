import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/theme/app_colors.dart';
import '../../../data/models/geojson_geometry.dart';
import '../../../data/models/geographic_area.dart';
import '../../../data/models/point_resolution.dart';
import '../../../data/models/verified_center.dart';
import '../../evacuation/nearest_center_controller.dart';
import '../../location/location_controller.dart';
import '../assessment_controller.dart';

class ReferenceBoundaryMapCard extends StatefulWidget {
  const ReferenceBoundaryMapCard({
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
  State<ReferenceBoundaryMapCard> createState() =>
      _ReferenceBoundaryMapCardState();
}

class _ReferenceBoundaryMapCardState extends State<ReferenceBoundaryMapCard> {
  final MapController _mapController = MapController();
  bool _mapReady = false;
  double? _lastCenteredLatitude;
  double? _lastCenteredLongitude;
  String? _lastCenteredCenterIdentifier;
  List<GeographicArea>? _cachedPolygonAreas;
  String? _cachedConfirmedAreaCode;
  List<Polygon<int>> _cachedPolygons = const [];

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
        padding: const EdgeInsets.all(22),
        maxZoom: 14,
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

  void _centerOnTemporaryPoint() {
    final coordinate = widget.locationController?.lookupCoordinate;
    if (!_mapReady || coordinate == null) return;
    if (_lastCenteredLatitude == coordinate.latitude &&
        _lastCenteredLongitude == coordinate.longitude) {
      return;
    }
    _lastCenteredLatitude = coordinate.latitude;
    _lastCenteredLongitude = coordinate.longitude;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_mapReady) return;
      _mapController.move(coordinate.latLng, 16);
    });
  }

  void _centerOnSelectedCenter() {
    final centers = widget.nearestCenterController;
    final selectedIdentifier = centers?.selectedCenterIdentifier;
    if (!_mapReady ||
        centers == null ||
        selectedIdentifier == null ||
        _lastCenteredCenterIdentifier == selectedIdentifier) {
      return;
    }
    final matches = centers.centers.where(
      (center) => center.publicIdentifier == selectedIdentifier,
    );
    if (matches.length != 1) return;
    final center = matches.single;
    _lastCenteredCenterIdentifier = selectedIdentifier;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_mapReady) return;
      _mapController.move(
        LatLng(center.latitude, center.longitude),
        _mapController.camera.zoom < 15 ? 15 : _mapController.camera.zoom,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final locationController = widget.locationController;
    final centerController = widget.nearestCenterController;
    if (locationController == null && centerController == null) {
      return _buildCard(context);
    }
    return AnimatedBuilder(
      animation: Listenable.merge([?locationController, ?centerController]),
      builder: (context, _) => _buildCard(context),
    );
  }

  Widget _buildCard(BuildContext context) {
    final controller = widget.controller;
    final centerController = widget.nearestCenterController;
    final centers = centerController?.centers ?? const <VerifiedCenter>[];
    _centerOnTemporaryPoint();
    _centerOnSelectedCenter();
    return Card(
      key: const Key('reference-boundary-card'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.location_city_outlined,
                  color: AppColors.primary,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Bacoor administrative reference',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 3),
                      Text(
                        'Current 47-barangay reference layer for map and data integration.',
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
              label: 'Derived administrative reference, not City-verified. Administrative boundaries only and no flood susceptibility.',
              child: Container(
                key: const Key('reference-boundary-warning'),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.warningSurface,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED\n'
                  'Boundary locations only. These colors do not indicate flood susceptibility or current conditions.',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
                ),
              ),
            ),
            const SizedBox(height: 10),
            if (controller.isReferenceLoading)
              const _ReferenceLoading()
            else if (controller.referenceError case final error?)
              _ReferenceError(
                message: error.message,
                onRetry: controller.loadReferenceBoundaries,
              )
            else if (controller.referenceAreas.isEmpty)
              const _ReferenceEmpty()
            else ...[
              LayoutBuilder(
                builder: (context, constraints) {
                  final height = constraints.maxWidth < 360 ? 280.0 : 330.0;
                  final bounds = GeoJsonGeometry.boundsFor(
                    controller.referenceAreas.map((area) => area.geometry),
                  );
                  return ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: SizedBox(
                      key: const Key('reference-boundary-map'),
                      height: height,
                      child: Stack(
                        children: [
                          FlutterMap(
                            mapController: _mapController,
                            options: MapOptions(
                              initialCameraFit: CameraFit.bounds(
                                bounds: bounds,
                                padding: const EdgeInsets.all(20),
                                maxZoom: 14,
                              ),
                              minZoom: 2,
                              maxZoom: 18,
                              keepAlive: true,
                              onMapReady: () {
                                _mapReady = true;
                                _centerOnTemporaryPoint();
                              },
                              onTap: widget.locationController == null
                                  ? null
                                  : (_, point) => widget.locationController!
                                        .resolveManualPin(
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
                                key: const Key('reference-boundary-polygons'),
                                polygons: _polygons(controller.referenceAreas),
                              ),
                              if (centerController
                                  case final activeCenterController?
                                  when centers.isNotEmpty)
                                MarkerLayer(
                                  key: const Key('nearest-center-markers'),
                                  markers: [
                                    for (final center in centers)
                                      Marker(
                                        key: Key(
                                          'nearest-center-marker-${center.publicIdentifier}',
                                        ),
                                        point: LatLng(
                                          center.latitude,
                                          center.longitude,
                                        ),
                                        width: 52,
                                        height: 52,
                                        alignment: Alignment.topCenter,
                                        child: Semantics(
                                          button: true,
                                          selected:
                                              activeCenterController
                                                  .selectedCenterIdentifier ==
                                              center.publicIdentifier,
                                          label:
                                              'Center marker for ${center.name}. ${center.distanceLabel}.',
                                          child: GestureDetector(
                                            behavior: HitTestBehavior.opaque,
                                            onTap: () => activeCenterController
                                                .selectCenter(
                                                  center.publicIdentifier,
                                                ),
                                            child: Icon(
                                              Icons.home_work,
                                              size:
                                                  activeCenterController
                                                          .selectedCenterIdentifier ==
                                                      center.publicIdentifier
                                                  ? 46
                                                  : 38,
                                              color: const Color(0xFF6A1B9A),
                                              shadows: const [
                                                Shadow(
                                                  blurRadius: 4,
                                                  color: Colors.white,
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                              if (widget.locationController?.temporaryLocation
                                  case final temporary?)
                                CircleLayer<String>(
                                  key: const Key(
                                    'temporary-location-accuracy-circle',
                                  ),
                                  circles: [
                                    CircleMarker<String>(
                                      key: const Key(
                                        'temporary-location-accuracy-circle',
                                      ),
                                      point: widget
                                          .locationController!
                                          .lookupCoordinate!
                                          .latLng,
                                      radius: temporary.accuracyMeters,
                                      useRadiusInMeter: true,
                                      color: AppColors.primary.withValues(
                                        alpha: 0.14,
                                      ),
                                      borderColor: AppColors.primary,
                                      borderStrokeWidth: 1.5,
                                    ),
                                  ],
                                ),
                              if (widget.locationController?.lookupCoordinate
                                  case final coordinate?)
                                MarkerLayer(
                                  markers: [
                                    Marker(
                                      key: const Key(
                                        'temporary-location-map-marker',
                                      ),
                                      point: coordinate.latLng,
                                      width: 48,
                                      height: 48,
                                      alignment: Alignment.topCenter,
                                      child: Semantics(
                                        label: 'Temporary location marker. Accuracy is approximate.',
                                        child: const Icon(
                                          Icons.my_location,
                                          size: 40,
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
                              const Align(
                                alignment: Alignment.bottomRight,
                                child: ColoredBox(
                                  color: Color(0xDDFFFFFF),
                                  child: Padding(
                                    padding: EdgeInsets.all(4),
                                    child: Text(
                                      '© OpenStreetMap contributors',
                                      key: Key('reference-osm-attribution'),
                                      style: TextStyle(fontSize: 10),
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
                                _ReferenceMapControl(
                                  label: 'Zoom in reference map',
                                  icon: Icons.add,
                                  onPressed: () => _zoom(1),
                                ),
                                const SizedBox(height: 6),
                                _ReferenceMapControl(
                                  label: 'Zoom out reference map',
                                  icon: Icons.remove,
                                  onPressed: () => _zoom(-1),
                                ),
                                const SizedBox(height: 6),
                                _ReferenceMapControl(
                                  label: 'Fit all Bacoor barangays',
                                  icon: Icons.fit_screen,
                                  onPressed: _fitAll,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 10),
              Text(
                '${controller.referenceAreas.length} barangay boundaries loaded from Django/PostGIS.',
                key: const Key('reference-boundary-count'),
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
          ],
        ),
      ),
    );
  }

  List<Polygon<int>> _polygons(List<GeographicArea> areas) {
    final confirmedCode =
        widget.locationController?.confirmedBarangay?.geographicAreaCode;
    if (identical(areas, _cachedPolygonAreas) &&
        confirmedCode == _cachedConfirmedAreaCode) {
      return _cachedPolygons;
    }
    final polygons = <Polygon<int>>[];
    for (final area in areas) {
      final isConfirmed = area.code == confirmedCode;
      for (final polygon in area.geometry.polygons) {
        polygons.add(
          Polygon<int>(
            points: polygon.exterior,
            holePointsList: polygon.holes.isEmpty ? null : polygon.holes,
            color: AppColors.primary.withValues(
              alpha: isConfirmed ? 0.3 : 0.12,
            ),
            borderColor: isConfirmed ? AppColors.error : AppColors.primary,
            borderStrokeWidth: isConfirmed ? 3 : 1.4,
            hitValue: area.id,
          ),
        );
      }
    }
    _cachedPolygonAreas = areas;
    _cachedConfirmedAreaCode = confirmedCode;
    return _cachedPolygons = List.unmodifiable(polygons);
  }
}

class _ReferenceLoading extends StatelessWidget {
  const _ReferenceLoading();

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.all(20),
    child: Center(child: CircularProgressIndicator()),
  );
}

class _ReferenceEmpty extends StatelessWidget {
  const _ReferenceEmpty();

  @override
  Widget build(BuildContext context) => const Text(
    'No reference boundaries are loaded yet. An administrator can run the reviewed Bacoor boundary import command.',
    key: Key('reference-boundary-empty'),
  );
}

class _ReferenceError extends StatelessWidget {
  const _ReferenceError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(message),
      const SizedBox(height: 8),
      OutlinedButton.icon(
        key: const Key('reference-boundary-retry'),
        onPressed: onRetry,
        icon: const Icon(Icons.refresh),
        label: const Text('Retry boundary layer'),
      ),
    ],
  );
}

class _ReferenceMapControl extends StatelessWidget {
  const _ReferenceMapControl({
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
