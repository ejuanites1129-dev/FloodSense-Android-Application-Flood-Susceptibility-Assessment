import 'dart:async';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:mapbox_maps_flutter/mapbox_maps_flutter.dart';

import '../../app/theme/app_colors.dart';
import '../../data/models/geojson_geometry.dart';
import '../../data/models/point_resolution.dart';
import '../evacuation/evacuation_center_marker.dart';
import 'flood_map_camera.dart';
import 'flood_map_palette.dart';
import 'flood_map_presentation.dart';
import 'map_provider_config.dart';
import 'mapbox_shelter_image.dart';

Widget buildFloodMapboxSurface(
  FloodMapPresentation presentation,
  FloodMapProviderConfig config,
  VoidCallback onUnavailable,
) => _FloodMapboxSurface(
  presentation: presentation,
  config: config,
  onUnavailable: onUnavailable,
);

class _FloodMapboxSurface extends StatefulWidget {
  const _FloodMapboxSurface({
    required this.presentation,
    required this.config,
    required this.onUnavailable,
  });

  final FloodMapPresentation presentation;
  final FloodMapProviderConfig config;
  final VoidCallback onUnavailable;

  @override
  State<_FloodMapboxSurface> createState() => _FloodMapboxSurfaceState();
}

class _FloodMapboxSurfaceState extends State<_FloodMapboxSurface>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  static const _maskSourceId = 'floodsense-coverage-mask-source';
  static const _boundarySourceId = 'floodsense-boundary-source';
  static const _scenarioSourceId = 'floodsense-scenario-source';
  static const _accuracySourceId = 'floodsense-accuracy-source';
  static const _pointSourceId = 'floodsense-point-source';
  static const _scenarioFillLayerId = 'floodsense-scenario-fill';
  static const _centerLayerId = 'floodsense-center-points';
  static const _nearestHaloLayerId = 'floodsense-nearest-center-halo';
  static const _shelterImageId = 'floodsense-shelter-icon';

  late final AnimationController _nearestPulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 3600),
  )..addListener(_updateNearestHalo);
  bool _haloUpdating = false;
  double _haloStrength = 0;
  int _lastHaloStep = -1;

  MapboxMap? _map;
  PointAnnotationManager? _pinManager;
  PointAnnotation? _pinAnnotation;
  Cancelable? _pinDragEvents;
  Uint8List? _pinImage;
  GeoJsonSource? _maskSource;
  GeoJsonSource? _boundarySource;
  GeoJsonSource? _scenarioSource;
  GeoJsonSource? _accuracySource;
  GeoJsonSource? _pointSource;
  bool _styleReady = false;
  bool _perspective = false;
  bool _reportedUnavailable = false;
  String _startupStage = 'loading basemap';
  late final CameraViewportState _initialViewport;
  double _mapViewportHeight = 600;
  String _cameraHeightLabel = '—';
  Timer? _loadGuard;
  int? _lastSelectedAreaId;
  String? _lastSelectedCenterIdentifier;
  String? _lastMaskGeoJson;
  String? _lastBoundaryGeoJson;
  String? _lastScenarioGeoJson;
  String? _lastAccuracyGeoJson;
  String? _lastPointGeoJson;
  Future<void> _sourceRefresh = Future.value();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Configuration guarantees this is a public `pk.` token. It is set only
    // when the optional native renderer is actually selected.
    MapboxOptions.setAccessToken(widget.config.mapboxPublicToken);
    final bounds = widget.presentation.bounds;
    _initialViewport = CameraViewportState(
      center: Point(
        coordinates: Position(bounds.centerLongitude, bounds.centerLatitude),
      ),
      zoom: 12.5,
      pitch: 0,
      bearing: 0,
    );
    _loadGuard = Timer(
      const Duration(seconds: 12),
      () => _reportUnavailable(reason: 'startup timeout at $_startupStage'),
    );
  }

  @override
  void dispose() {
    _loadGuard?.cancel();
    _pinDragEvents?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    _nearestPulse.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_decorativeMotionEnabled) {
      _nearestPulse.stop();
      _nearestPulse.value = 1;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      _nearestPulse.stop();
      _nearestPulse.value = 1;
    }
  }

  bool get _decorativeMotionEnabled {
    final lifecycle = WidgetsBinding.instance.lifecycleState;
    return mounted &&
        TickerMode.valuesOf(context).enabled &&
        !MediaQuery.disableAnimationsOf(context) &&
        (lifecycle == null || lifecycle == AppLifecycleState.resumed);
  }

  void _highlightNearestCenter() {
    _nearestPulse.stop();
    _lastHaloStep = -1;
    if (widget.presentation.nearestCenterIdentifier != null &&
        _decorativeMotionEnabled) {
      _nearestPulse.forward(from: 0);
    } else {
      _nearestPulse.value = 1;
      _updateNearestHalo();
    }
  }

  void _updateNearestHalo() {
    if (!_styleReady || !mounted) return;
    final strength = evacuationPulseStrength(_nearestPulse.value);
    final step = (strength * 12).round();
    if (step == _lastHaloStep) return;
    _lastHaloStep = step;
    _haloStrength = step / 12;
    if (!_haloUpdating) unawaited(_flushNearestHalo());
  }

  Future<void> _flushNearestHalo() async {
    final map = _map;
    if (map == null) return;
    _haloUpdating = true;
    try {
      // Coalesce in-flight style updates. No source reload, camera move,
      // location request, polling, or repeating background animation.
      double strength;
      do {
        strength = _haloStrength;
        await map.style.setStyleLayerProperty(
          _nearestHaloLayerId,
          'circle-radius',
          23 + 6 * strength,
        );
        if (!mounted) return;
        await map.style.setStyleLayerProperty(
          _nearestHaloLayerId,
          'circle-opacity',
          0.20 + 0.12 * strength,
        );
      } while (mounted && strength != _haloStrength);
    } catch (_) {
      // Decorative emphasis failure must not discard a usable map.
    } finally {
      _haloUpdating = false;
    }
  }

  @override
  void didUpdateWidget(covariant _FloodMapboxSurface oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_styleReady) return;
    final currentPresentation = widget.presentation;
    final coordinateChanged = !_sameCoordinate(
      oldWidget.presentation.coordinate,
      currentPresentation.coordinate,
    );
    _sourceRefresh = _sourceRefresh
        .then((_) async {
          await _refreshSources(oldWidget.presentation, currentPresentation);
          if (oldWidget.presentation.nearestCenterIdentifier !=
              currentPresentation.nearestCenterIdentifier) {
            _highlightNearestCenter();
          }
          if (!mounted ||
              !coordinateChanged ||
              !_sameCoordinate(
                currentPresentation.coordinate,
                widget.presentation.coordinate,
              )) {
            return;
          }
          await _syncPinAnnotation();
          // Source/annotation work is asynchronous. A newer pin must not be
          // interrupted by a queued focus for the previous location.
          if (!mounted ||
              !_sameCoordinate(
                currentPresentation.coordinate,
                widget.presentation.coordinate,
              )) {
            return;
          }
          final coordinate = currentPresentation.coordinate;
          if (coordinate == null) {
            await _fitAll();
          } else {
            await _focusCoordinateAtHeight(coordinate);
          }
        })
        .catchError((_) => _reportUnavailable());
    if (widget.presentation.selectedAreaId != _lastSelectedAreaId) {
      _lastSelectedAreaId = widget.presentation.selectedAreaId;
      final selected = widget.presentation.scenarioAreas.where(
        (area) => area.id == _lastSelectedAreaId,
      );
      if (selected.length == 1 && widget.presentation.coordinate == null) {
        unawaited(_fitGeometry(selected.single.geometry));
      }
    }
    if (widget.presentation.selectedCenterIdentifier !=
        _lastSelectedCenterIdentifier) {
      _lastSelectedCenterIdentifier =
          widget.presentation.selectedCenterIdentifier;
      final selected = widget.presentation.mapMarkers.where(
        (center) => center.publicIdentifier == _lastSelectedCenterIdentifier,
      );
      if (selected.length == 1) {
        unawaited(
          _recenter(
            selected.single.latitude,
            selected.single.longitude,
            minimumZoom: 15,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final pinDescription = widget.presentation.coordinate == null
        ? 'Unconfirmed starting map pin—not your actual location'
        : widget.presentation.coordinateDescription ?? 'Temporary map pin';
    final controls = Positioned(
      top: 8,
      left: widget.presentation.controlsOnRight ? null : 8,
      right: widget.presentation.controlsOnRight ? 8 : null,
      child: Column(
        crossAxisAlignment: widget.presentation.controlsOnRight
            ? CrossAxisAlignment.end
            : CrossAxisAlignment.start,
        children: [
          _MapboxControl(
            label: 'Zoom in',
            icon: Icons.add,
            onPressed: () => _zoom(0.5),
          ),
          const SizedBox(height: 6),
          _MapboxControl(
            label: 'Zoom out',
            icon: Icons.remove,
            onPressed: () => _zoom(-0.5),
          ),
          const SizedBox(height: 6),
          _MapboxControl(
            label: 'Fit all Bacoor areas',
            icon: Icons.fit_screen,
            onPressed: _fitAll,
          ),
          if (widget.presentation.coordinate != null) ...[
            const SizedBox(height: 6),
            _MapboxControl(
              label: 'Recenter on $pinDescription',
              icon: Icons.my_location,
              onPressed: _recenterOnTemporaryPoint,
            ),
          ],
          if (widget.config.showsThreeDimensionalControl()) ...[
            const SizedBox(height: 6),
            _MapboxControl(
              key: const Key('mapbox-perspective-toggle'),
              label: _perspective
                  ? 'Switch to overhead map view'
                  : 'Switch to perspective map view',
              icon: _perspective ? Icons.map_outlined : Icons.view_in_ar,
              onPressed: _togglePerspective,
            ),
          ],
          if (widget.presentation.controlsOnRight) ...[
            const SizedBox(height: 6),
            _CameraHeightBadge(label: _cameraHeightLabel),
          ],
        ],
      ),
    );
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxHeight.isFinite && constraints.maxHeight > 0) {
          _mapViewportHeight = constraints.maxHeight;
        }
        return Stack(
          key: const Key('mapbox-flood-map'),
          fit: StackFit.expand,
          children: [
            Semantics(
              container: true,
              label:
                  'Map. $pinDescription. This coordinate is temporary and is '
                  'not saved. Drag the pin to choose a new map location. '
                  'Evacuation-center icons are reference information; nearest '
                  'means approximate straight-line distance, not safety or '
                  'current availability.',
              child: MapWidget(
                key: const ValueKey('floodsense-mapbox-widget'),
                styleUri: MapboxStyles.STANDARD,
                viewport: _initialViewport,
                onMapCreated: (map) {
                  _map = map;
                  map.addInteraction(
                    TapInteraction.onMap(
                      (gesture) => unawaited(_handleTap(gesture)),
                    ),
                  );
                },
                onCameraChangeListener: _handleCameraChanged,
                onStyleLoadedListener: (_) => unawaited(_onStyleLoaded()),
                onMapLoadErrorListener: (event) => _reportUnavailable(
                  reason: 'basemap load error ${event.type.name}',
                ),
              ),
            ),
            controls,
            if (!widget.presentation.controlsOnRight)
              Positioned(
                top: 8,
                right: 8,
                child: _CameraHeightBadge(label: _cameraHeightLabel),
              ),
          ],
        );
      },
    );
  }

  Future<void> _onStyleLoaded() async {
    final map = _map;
    if (map == null) return _reportUnavailable();
    try {
      _startupStage = 'basemap configuration';
      // The native north-reset compass occupies the same upper-right space as
      // our zoom controls. Keep only the visible app controls in that position.
      await map.compass.updateSettings(CompassSettings(enabled: false));
      await map.style.setStyleImportConfigProperty(
        'basemap',
        'theme',
        'monochrome',
      );
      await map.style.setStyleImportConfigProperty(
        'basemap',
        'lightPreset',
        'day',
      );
      await map.style.setStyleImportConfigProperty(
        'basemap',
        'show3dObjects',
        widget.config.showsThreeDimensionalControl(),
      );

      _startupStage = 'assessment sources and layers';
      final sourcePresentation = widget.presentation;
      _lastMaskGeoJson = sourcePresentation.coverageMaskGeoJson;
      _lastBoundaryGeoJson = sourcePresentation.boundaryGeoJson;
      _lastScenarioGeoJson = sourcePresentation.scenarioGeoJson;
      _lastAccuracyGeoJson = sourcePresentation.accuracyGeoJson;
      _lastPointGeoJson = sourcePresentation.pointGeoJson;
      _maskSource = GeoJsonSource(id: _maskSourceId, data: _lastMaskGeoJson);
      _boundarySource = GeoJsonSource(
        id: _boundarySourceId,
        data: _lastBoundaryGeoJson,
      );
      _scenarioSource = GeoJsonSource(
        id: _scenarioSourceId,
        data: _lastScenarioGeoJson,
      );
      _accuracySource = GeoJsonSource(
        id: _accuracySourceId,
        data: _lastAccuracyGeoJson,
      );
      _pointSource = GeoJsonSource(id: _pointSourceId, data: _lastPointGeoJson);
      for (final source in [
        _maskSource!,
        _boundarySource!,
        _scenarioSource!,
        _accuracySource!,
        _pointSource!,
      ]) {
        await map.style.addSource(source);
      }

      await map.style.addLayer(
        FillLayer(
          id: 'floodsense-coverage-mask',
          sourceId: _maskSourceId,
          slot: 'middle',
          fillColor: FloodMapPalette.outsideCoverage.toARGB32(),
          fillOpacity: 0.55,
        ),
      );
      await map.style.addLayer(
        FillLayer(
          id: _scenarioFillLayerId,
          sourceId: _scenarioSourceId,
          slot: 'middle',
          fillColorExpression: [
            'to-color',
            ['get', 'color'],
          ],
          fillOpacityExpression: [
            'case',
            [
              '==',
              true,
              ['get', 'selected'],
            ],
            0.50,
            0.32,
          ],
        ),
      );
      await map.style.addLayer(
        LineLayer(
          id: 'floodsense-scenario-line',
          sourceId: _scenarioSourceId,
          slot: 'middle',
          lineColorExpression: [
            'case',
            [
              '==',
              true,
              ['get', 'selected'],
            ],
            FloodMapPalette.cssHex(FloodMapPalette.selection),
            [
              'to-color',
              ['get', 'color'],
            ],
          ],
          lineWidthExpression: [
            'case',
            [
              '==',
              true,
              ['get', 'selected'],
            ],
            4.0,
            2.0,
          ],
        ),
      );
      await map.style.addLayer(
        FillLayer(
          id: 'floodsense-confirmed-area-fill',
          sourceId: _boundarySourceId,
          slot: 'middle',
          fillColor: FloodMapPalette.selection.toARGB32(),
          fillOpacityExpression: [
            'case',
            [
              '==',
              true,
              ['get', 'confirmed'],
            ],
            0.17,
            0.025,
          ],
        ),
      );
      await map.style.addLayer(
        LineLayer(
          id: 'floodsense-boundary-line',
          sourceId: _boundarySourceId,
          slot: 'middle',
          lineColorExpression: [
            'case',
            [
              '==',
              true,
              ['get', 'confirmed'],
            ],
            FloodMapPalette.cssHex(FloodMapPalette.selection),
            FloodMapPalette.cssHex(FloodMapPalette.boundary),
          ],
          lineOpacityExpression: [
            'case',
            [
              '==',
              true,
              ['get', 'confirmed'],
            ],
            1.0,
            0.7,
          ],
          lineWidthExpression: [
            'case',
            [
              '==',
              true,
              ['get', 'confirmed'],
            ],
            3.0,
            1.2,
          ],
        ),
      );
      await map.style.addLayer(
        LineLayer(
          id: 'floodsense-selection-line',
          sourceId: _scenarioSourceId,
          slot: 'top',
          filter: [
            '==',
            true,
            ['get', 'selected'],
          ],
          lineColor: FloodMapPalette.selection.toARGB32(),
          lineWidth: 4.5,
        ),
      );
      await map.style.addLayer(
        FillLayer(
          id: 'floodsense-accuracy-fill',
          sourceId: _accuracySourceId,
          slot: 'top',
          fillColor: FloodMapPalette.selection.toARGB32(),
          fillOpacity: 0.14,
          fillOutlineColor: FloodMapPalette.selection.toARGB32(),
        ),
      );
      _startupStage = 'shelter PNG image';
      final shelter = await createEvacuationShelterStyleImage();
      await map.style.addStyleImage(
        _shelterImageId,
        2,
        shelter,
        false,
        [],
        [],
        null,
      );
      _startupStage = 'nearest shelter halo';
      await map.style.addLayer(
        CircleLayer(
          id: _nearestHaloLayerId,
          sourceId: _pointSourceId,
          slot: 'top',
          filter: [
            '==',
            true,
            ['get', 'nearest'],
          ],
          circleColor: FloodMapPalette.center.toARGB32(),
          circleStrokeColor: FloodMapPalette.center.toARGB32(),
          circleStrokeWidth: 2,
          circleOpacity: 0.20,
          circleRadius: 23,
        ),
      );
      _startupStage = 'shelter symbol layer';
      await map.style.addLayer(
        createEvacuationShelterSymbolLayer(
          id: _centerLayerId,
          sourceId: _pointSourceId,
          imageId: _shelterImageId,
        ),
      );
      _startupStage = 'draggable location pin';
      await _createDraggablePin();
      _styleReady = true;
      // Catalog/location responses can arrive while native layers are being
      // created. didUpdateWidget cannot update unregistered sources yet; replay
      // the newest presentation now instead of losing those shelter icons.
      _sourceRefresh = _sourceRefresh.then(
        (_) => _refreshSources(sourcePresentation, widget.presentation),
      );
      await _sourceRefresh;
      _highlightNearestCenter();
      _loadGuard?.cancel();
      _lastSelectedAreaId = widget.presentation.selectedAreaId;
      _lastSelectedCenterIdentifier =
          widget.presentation.selectedCenterIdentifier;
      _startupStage = 'initial camera';
      final coordinate = widget.presentation.coordinate;
      if (coordinate == null) {
        await _fitAll();
      } else {
        await _focusCoordinateAtHeight(coordinate);
      }
      if (kDebugMode) debugPrint('FloodSense Mapbox: startup complete.');
    } catch (error) {
      // Log only the stage and error category, never a token, URL, coordinate,
      // GeoJSON payload or arbitrary native error message.
      final category = error is PlatformException
          ? 'PlatformException'
          : error.runtimeType.toString();
      _reportUnavailable(reason: '$_startupStage failed ($category)');
    }
  }

  Future<void> _refreshSources(
    FloodMapPresentation previous,
    FloodMapPresentation current,
  ) async {
    try {
      if (!identical(previous.referenceAreas, current.referenceAreas)) {
        final value = current.coverageMaskGeoJson;
        if (value != _lastMaskGeoJson) {
          await _maskSource?.updateGeoJSON(value);
          _lastMaskGeoJson = value;
        }
      }
      if (!identical(previous.referenceAreas, current.referenceAreas) ||
          previous.confirmedAreaCode != current.confirmedAreaCode) {
        final value = current.boundaryGeoJson;
        if (value != _lastBoundaryGeoJson) {
          await _boundarySource?.updateGeoJSON(value);
          _lastBoundaryGeoJson = value;
        }
      }
      if (!identical(previous.scenarioAreas, current.scenarioAreas) ||
          !identical(previous.scenarioResults, current.scenarioResults) ||
          previous.selectedAreaId != current.selectedAreaId) {
        final value = current.scenarioGeoJson;
        if (value != _lastScenarioGeoJson) {
          await _scenarioSource?.updateGeoJSON(value);
          _lastScenarioGeoJson = value;
        }
      }
      if (!_sameCoordinate(previous.coordinate, current.coordinate) ||
          previous.accuracyMeters != current.accuracyMeters) {
        final value = current.accuracyGeoJson;
        if (value != _lastAccuracyGeoJson) {
          await _accuracySource?.updateGeoJSON(value);
          _lastAccuracyGeoJson = value;
        }
      }
      if (!_sameCoordinate(previous.coordinate, current.coordinate) ||
          !identical(previous.centers, current.centers) ||
          !identical(previous.mapCenters, current.mapCenters) ||
          previous.mapCentersAreAuthoritative !=
              current.mapCentersAreAuthoritative ||
          previous.nearestIsDemonstration != current.nearestIsDemonstration ||
          previous.nearestCenterIdentifier != current.nearestCenterIdentifier ||
          previous.selectedCenterIdentifier !=
              current.selectedCenterIdentifier) {
        final value = current.pointGeoJson;
        if (value != _lastPointGeoJson) {
          await _pointSource?.updateGeoJSON(value);
          _lastPointGeoJson = value;
        }
      }
    } catch (_) {
      _reportUnavailable();
    }
  }

  bool _sameCoordinate(MapCoordinate? first, MapCoordinate? second) =>
      first?.latitude == second?.latitude &&
      first?.longitude == second?.longitude;

  Future<void> _handleTap(MapContentGestureContext gesture) async {
    final map = _map;
    if (map == null) return;
    try {
      final features = await map.queryRenderedFeatures(
        RenderedQueryGeometry.fromScreenCoordinate(gesture.touchPosition),
        RenderedQueryOptions(layerIds: [_centerLayerId, _scenarioFillLayerId]),
      );
      for (final result in features.whereType<QueriedRenderedFeature>()) {
        final rawProperties = result.queriedFeature.feature['properties'];
        if (rawProperties is! Map) continue;
        final properties = rawProperties.cast<Object?, Object?>();
        final centerIdentifier = properties['public_identifier'];
        if (centerIdentifier is String &&
            widget.presentation.onCenterTapped != null) {
          widget.presentation.onCenterTapped!(centerIdentifier);
          return;
        }
        final areaId = properties['area_id'];
        if (areaId is num && widget.presentation.onAreaTapped != null) {
          widget.presentation.onAreaTapped!(areaId.toInt());
          return;
        }
      }
    } catch (_) {
      // A feature-query failure must not move the temporary location pin.
    }
  }

  Future<void> _fitAll() =>
      _fitBounds(widget.presentation.bounds, closerOverview: true);

  Future<void> _fitGeometry(GeoJsonGeometry geometry) =>
      _fitBounds(FloodMapBounds.fromGeometries([geometry]), maximumZoom: 16);

  Future<void> _fitBounds(
    FloodMapBounds bounds, {
    double maximumZoom = 14,
    bool closerOverview = false,
  }) async {
    final map = _map;
    if (map == null) return;
    final padding = widget.presentation.fitPadding;
    final camera = await map.cameraForCoordinateBounds(
      CoordinateBounds(
        southwest: Point(coordinates: Position(bounds.west, bounds.south)),
        northeast: Point(coordinates: Position(bounds.east, bounds.north)),
        infiniteBounds: false,
      ),
      MbxEdgeInsets(
        top: padding.top,
        left: padding.left,
        bottom: padding.bottom,
        right: padding.right,
      ),
      _perspective ? -18 : 0,
      _perspective ? 45 : 0,
      maximumZoom,
      null,
    );
    final fittedZoom = camera.zoom;
    if (closerOverview && fittedZoom != null) {
      camera.zoom = closerBacoorOverviewZoom(
        fittedZoom,
        maximumZoom: maximumZoom,
      );
    }
    await map.easeTo(camera, _cameraAnimationOptions(mapFitAnimationDuration));
  }

  Future<void> _zoom(double change) async {
    final map = _map;
    if (map == null) return;
    final camera = await map.getCameraState();
    final pin = _displayPinCoordinate;
    await map.easeTo(
      CameraOptions(
        center: Point(coordinates: Position(pin.longitude, pin.latitude)),
        zoom: (camera.zoom + change).clamp(2, 22).toDouble(),
      ),
      _cameraAnimationOptions(mapZoomAnimationDuration),
    );
  }

  Future<void> _recenterOnTemporaryPoint() async {
    final point = widget.presentation.coordinate;
    if (point == null) return;
    await _focusCoordinateAtHeight(point);
  }

  MapCoordinate get _displayPinCoordinate {
    final coordinate = widget.presentation.coordinate;
    if (coordinate != null) return coordinate;
    final bounds = widget.presentation.bounds;
    return MapCoordinate(
      latitude: bounds.centerLatitude,
      longitude: bounds.centerLongitude,
    );
  }

  Future<void> _createDraggablePin() async {
    final map = _map;
    if (map == null) return;
    _pinDragEvents?.cancel();
    final manager = _pinManager ??= await map.annotations
        .createPointAnnotationManager();
    await manager.setIconAllowOverlap(true);
    _pinImage ??= await _drawPinImage();
    final coordinate = _displayPinCoordinate;
    _pinAnnotation = await manager.create(
      PointAnnotationOptions(
        geometry: Point(
          coordinates: Position(coordinate.longitude, coordinate.latitude),
        ),
        image: _pinImage,
        iconAnchor: IconAnchor.BOTTOM,
        iconSize: 0.62,
        isDraggable: true,
      ),
    );
    _pinDragEvents = manager.dragEvents(
      onChanged: (annotation) => _pinAnnotation = annotation,
      onEnd: _handlePinDragEnd,
    );
  }

  Future<void> _syncPinAnnotation() async {
    final manager = _pinManager;
    final annotation = _pinAnnotation;
    if (manager == null || annotation == null) return;
    final coordinate = _displayPinCoordinate;
    final current = annotation.geometry.coordinates;
    if (current.lat == coordinate.latitude &&
        current.lng == coordinate.longitude) {
      return;
    }
    annotation.geometry = Point(
      coordinates: Position(coordinate.longitude, coordinate.latitude),
    );
    await manager.update(annotation);
  }

  void _handlePinDragEnd(PointAnnotation annotation) {
    _pinAnnotation = annotation;
    final coordinates = annotation.geometry.coordinates;
    final coordinate = MapCoordinate(
      latitude: coordinates.lat.toDouble(),
      longitude: coordinates.lng.toDouble(),
    );
    widget.presentation.onCoordinateTapped(coordinate);
    // didUpdateWidget owns focusing after the coordinate changes. Starting it
    // here as well restarts the same native animation after sources refresh.
  }

  Future<void> _focusCoordinateAtHeight(MapCoordinate coordinate) async {
    final map = _map;
    if (map == null) return;
    final camera = await map.getCameraState();
    final zoom = zoomForCameraHeightMeters(
      cameraHeightMeters: selectedLocationCameraHeightMeters,
      latitude: coordinate.latitude,
      pitchDegrees: camera.pitch,
      viewportHeightPixels: _mapViewportHeight,
    ).clamp(2, 22).toDouble();
    await map.easeTo(
      CameraOptions(
        center: Point(
          coordinates: Position(coordinate.longitude, coordinate.latitude),
        ),
        zoom: zoom,
      ),
      _cameraAnimationOptions(selectedLocationAnimationDuration),
    );
  }

  void _handleCameraChanged(CameraChangedEventData data) {
    final camera = data.cameraState;
    final coordinates = camera.center.coordinates;
    final label = formatCameraHeight(
      approximateCameraHeightMeters(
        zoom: camera.zoom,
        latitude: coordinates.lat.toDouble(),
        pitchDegrees: camera.pitch,
        viewportHeightPixels: _mapViewportHeight,
      ),
    );
    if (!mounted || label == _cameraHeightLabel) return;
    setState(() => _cameraHeightLabel = label);
  }

  Future<Uint8List> _drawPinImage() async {
    const width = 80.0;
    const height = 104.0;
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final path = Path()
      ..moveTo(width / 2, height - 5)
      ..cubicTo(34, 88, 8, 62, 8, 38)
      ..cubicTo(8, 18, 21, 5, width / 2, 5)
      ..cubicTo(59, 5, 72, 18, 72, 38)
      ..cubicTo(72, 62, 46, 88, width / 2, height - 5)
      ..close();
    canvas.drawShadow(path, const Color(0x66000000), 5, true);
    canvas.drawPath(
      path,
      Paint()
        ..color = AppColors.primary
        ..style = PaintingStyle.fill,
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = Colors.white
        ..style = PaintingStyle.stroke
        ..strokeWidth = 4,
    );
    canvas.drawCircle(
      const Offset(width / 2, 37),
      13,
      Paint()..color = Colors.white,
    );
    canvas.drawCircle(
      const Offset(width / 2, 37),
      6,
      Paint()..color = AppColors.primary,
    );
    final image = await recorder.endRecording().toImage(
      width.toInt(),
      height.toInt(),
    );
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    if (bytes == null) throw StateError('Unable to render map pin image.');
    return bytes.buffer.asUint8List();
  }

  Future<void> _recenter(
    double latitude,
    double longitude, {
    required double minimumZoom,
  }) async {
    final map = _map;
    if (map == null) return;
    final camera = await map.getCameraState();
    await map.easeTo(
      CameraOptions(
        center: Point(coordinates: Position(longitude, latitude)),
        zoom: camera.zoom < minimumZoom ? minimumZoom : camera.zoom,
      ),
      _cameraAnimationOptions(mapRecenterAnimationDuration),
    );
  }

  Future<void> _togglePerspective() async {
    final map = _map;
    if (map == null) return;
    setState(() => _perspective = !_perspective);
    await map.easeTo(
      CameraOptions(
        pitch: _perspective ? 45 : 0,
        bearing: _perspective ? -18 : 0,
      ),
      _cameraAnimationOptions(const Duration(milliseconds: 450)),
    );
  }

  MapAnimationOptions _cameraAnimationOptions(Duration duration) =>
      MapAnimationOptions(
        duration: MediaQuery.disableAnimationsOf(context)
            ? 0
            : duration.inMilliseconds,
      );

  void _reportUnavailable({String reason = 'map update failed'}) {
    if (_reportedUnavailable) return;
    _reportedUnavailable = true;
    if (kDebugMode) {
      debugPrint('FloodSense Mapbox: $reason; using standard map.');
    }
    widget.onUnavailable();
  }
}

class _MapboxControl extends StatelessWidget {
  const _MapboxControl({
    required this.label,
    required this.icon,
    required this.onPressed,
    super.key,
  });

  final String label;
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) => Tooltip(
    message: label,
    excludeFromSemantics: true,
    child: Semantics(
      button: true,
      label: label,
      child: Material(
        color: AppColors.surface,
        elevation: 3,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(10),
          child: SizedBox(
            width: 48,
            height: 48,
            child: Icon(icon, color: AppColors.primary),
          ),
        ),
      ),
    ),
  );
}

class _CameraHeightBadge extends StatelessWidget {
  const _CameraHeightBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Approximate camera height $label',
    child: Material(
      key: const Key('mapbox-camera-height'),
      color: const Color(0xEFFFFFFF),
      elevation: 2,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
        child: Text(
          'Height ≈ $label',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
        ),
      ),
    ),
  );
}
