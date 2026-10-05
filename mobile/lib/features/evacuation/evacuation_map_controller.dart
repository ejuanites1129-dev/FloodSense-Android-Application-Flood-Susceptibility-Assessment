import 'package:flutter/foundation.dart';

import '../../data/models/center_map_record.dart';
import '../../data/models/center_map_result.dart';
import '../../data/models/geographic_area.dart';
import '../../data/models/point_resolution.dart';
import '../map/flood_map_presentation.dart';
import 'nearest_center_provider.dart';

abstract interface class EvacuationMapProvider {
  Future<CenterMapResult> fetchMapCenters({MapCoordinate? coordinate});
}

/// Pin-centered foreground discovery. Camera changes never trigger a request.
final class EvacuationMapController extends ChangeNotifier {
  EvacuationMapController(this.provider);
  final EvacuationMapProvider provider;
  List<CenterMapRecord> _centers = const [];
  List<String> _warnings = const [];
  bool _loading = false;
  bool _loaded = false;
  bool _disposed = false;
  bool _isDemonstration = false;
  String? _selectedCenterIdentifier;
  CenterLookupFailureKind? _failure;
  int _generation = 0;
  MapCoordinate? _origin;

  MapCoordinate? get origin => _origin;

  List<CenterMapRecord> get centers => _centers;
  List<String> get warnings => _warnings;
  bool get isLoading => _loading;
  bool get isDemonstration => _isDemonstration;
  String? get selectedCenterIdentifier => _selectedCenterIdentifier;
  CenterLookupFailureKind? get failure => _failure;
  String get message => _loading
      ? 'Loading evacuation-center map icons…'
      : _failure != null
      ? 'Evacuation-center map information could not be loaded. Retry when connected.'
      : !_loaded
      ? ''
      : _centers.isEmpty
      ? (_isDemonstration ? centerMapLocalEmptyWarning : centerMapEmptyWarning)
      : _isDemonstration
      ? 'Local test shelter icons — not real facilities.'
      : '${_centers.length} nearest evacuation-center references around the map pin. Confirm a location for distance details.';

  /// The initial pin uses the same boundary-bounds midpoint as the native map.
  /// This is a map reference, never an automatically acquired device location.
  void synchronizePin({
    required List<GeographicArea> referenceAreas,
    MapCoordinate? coordinate,
  }) {
    if (_disposed) return;
    if (coordinate == null && referenceAreas.isEmpty) return;
    final bounds = FloodMapBounds.fromGeometries(
      referenceAreas.map((area) => area.geometry),
    );
    load(
      coordinate:
          coordinate ??
          MapCoordinate(
            latitude: bounds.centerLatitude,
            longitude: bounds.centerLongitude,
          ),
    );
  }

  Future<void> load({MapCoordinate? coordinate, bool refresh = false}) async {
    if (_disposed) return;
    final nextOrigin = coordinate ?? _origin;
    final changed =
        nextOrigin?.latitude != _origin?.latitude ||
        nextOrigin?.longitude != _origin?.longitude;
    if (!changed && !refresh && (_loading || _loaded || _failure != null)) {
      return;
    }
    // A new pin supersedes in-flight work; its late response cannot restore
    // the previous pin's shortlist. Refresh keeps the existing origin.
    _origin = nextOrigin;
    _loading = true;
    _failure = null;
    _loaded = false;
    // Do not retain stale eligibility after an explicit refresh.
    _centers = const [];
    _warnings = const [];
    _selectedCenterIdentifier = null;
    final generation = ++_generation;
    notifyListeners();
    try {
      final result = await provider.fetchMapCenters(coordinate: nextOrigin);
      if (_disposed || generation != _generation) return;
      _centers = result.centers;
      _warnings = result.warnings;
      _isDemonstration = result.isDemonstration;
      _loaded = true;
    } on CenterLookupException catch (error) {
      if (_disposed || generation != _generation) return;
      _failure = error.kind;
    } catch (_) {
      if (_disposed || generation != _generation) return;
      _failure = CenterLookupFailureKind.recoverable;
    }
    _loading = false;
    notifyListeners();
  }

  void selectCenter(String identifier) {
    if (_disposed ||
        !_centers.any((center) => center.publicIdentifier == identifier)) {
      return;
    }
    if (_selectedCenterIdentifier == identifier) return;
    _selectedCenterIdentifier = identifier;
    notifyListeners();
  }

  void clearSelection() {
    if (_disposed || _selectedCenterIdentifier == null) return;
    _selectedCenterIdentifier = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    super.dispose();
  }
}
