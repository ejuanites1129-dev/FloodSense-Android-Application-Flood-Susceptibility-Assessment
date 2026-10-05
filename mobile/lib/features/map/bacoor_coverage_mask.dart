import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

import '../../data/models/geographic_area.dart';
import '../../data/models/map_assessment_result.dart';
import 'flood_map_palette.dart';

/// Neutral presentation color for places outside FloodSense's Bacoor coverage.
///
/// This is a coverage cue only. It must not be reused as a susceptibility,
/// hazard, warning, or safety classification.
const bacoorOutsideCoverageColor = FloodMapPalette.outsideCoverage;

List<Polygon<int>> buildBacoorCoveragePolygons(
  List<GeographicArea> barangays,
) => List.unmodifiable([
  for (final area in barangays)
    for (final polygon in area.geometry.polygons)
      Polygon<int>(
        points: polygon.exterior,
        holePointsList: polygon.holes.isEmpty ? null : polygon.holes,
        disableHolesBorder: true,
      ),
]);

class BacoorCoverageLegend extends StatelessWidget {
  const BacoorCoverageLegend({
    this.compact = false,
    this.results = const {},
    this.isDemonstration = false,
    super.key,
  });

  final bool compact;
  final Map<int, MapAreaAssessment> results;
  final bool isDemonstration;

  @override
  Widget build(BuildContext context) {
    if (compact) return _legendButton(context);
    return _coverageNotice();
  }

  Widget _legendButton(BuildContext context) {
    // Use the same backend colors as the polygons when results are available.
    // Defaults describe the existing presentation palette, not new risk rules.
    final classes = <String, (String, Color)>{
      'LOW': ('Low', FloodMapPalette.low),
      'MODERATE': ('Moderate', FloodMapPalette.moderate),
      'HIGH': ('High', FloodMapPalette.high),
      'VERY_HIGH': ('Very high', FloodMapPalette.veryHigh),
    };
    for (final result in results.values) {
      final susceptibility = result.susceptibility;
      if (result.isClassified && susceptibility != null) {
        classes[susceptibility.code] = (
          susceptibility.label,
          Color(susceptibility.colorValue),
        );
      }
    }
    final size = MediaQuery.sizeOf(context);
    return PopupMenuButton<void>(
      key: const Key('bacoor-coverage-legend'),
      tooltip: 'Map legend',
      position: PopupMenuPosition.under,
      constraints: BoxConstraints.tightFor(
        width: (size.width - 32).clamp(180, 260),
      ),
      itemBuilder: (_) => [
        PopupMenuItem<void>(
          enabled: false,
          padding: EdgeInsets.zero,
          child: ConstrainedBox(
            constraints: BoxConstraints(maxHeight: size.height * 0.62),
            child: SingleChildScrollView(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: DefaultTextStyle(
                  style: const TextStyle(
                    color: Color(0xFF344054),
                    fontSize: 12,
                  ),
                  child: Column(
                    key: const Key('map-legend-content'),
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Map legend',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 8),
                      if (isDemonstration) ...[
                        const Text(
                          'Demonstration susceptibility—not official data.',
                        ),
                        const SizedBox(height: 8),
                      ],
                      for (final entry in classes.values)
                        _legendRow(entry.$1, entry.$2),
                      Semantics(
                        label:
                            'Gray means unclassified or insufficient data inside Bacoor, '
                            'or outside Bacoor assessment coverage. '
                            'Gray is not a susceptibility class.',
                        excludeSemantics: true,
                        child: _legendRow(
                          'Unclassified / insufficient data\nOutside Bacoor coverage',
                          FloodMapPalette.limitation,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
      child: Material(
        color: const Color(0xEFFFFFFF),
        elevation: 2,
        borderRadius: BorderRadius.circular(8),
        child: const Padding(
          padding: EdgeInsets.symmetric(horizontal: 10, vertical: 14),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.legend_toggle, size: 18, color: Color(0xFF344054)),
              SizedBox(width: 5),
              Text(
                'Legend',
                style: TextStyle(
                  color: Color(0xFF344054),
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _legendRow(String label, Color color) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(
      children: [
        Container(
          key: ValueKey('legend-swatch-$label'),
          width: 18,
          height: 14,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(child: Text(label)),
      ],
    ),
  );

  Widget _coverageNotice() => Semantics(
    container: true,
    label: 'Gray map areas are outside FloodSense assessment coverage. Gray does not indicate flood susceptibility or danger.',
    child: Material(
      key: const Key('bacoor-coverage-legend'),
      color: compact ? const Color(0xEFFFFFFF) : Colors.transparent,
      elevation: compact ? 2 : 0,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: compact
            ? const EdgeInsets.symmetric(horizontal: 8, vertical: 6)
            : EdgeInsets.zero,
        child: Row(
          mainAxisSize: compact ? MainAxisSize.min : MainAxisSize.max,
          children: [
            Container(
              key: const Key('bacoor-coverage-swatch'),
              width: 18,
              height: 14,
              decoration: BoxDecoration(
                color: bacoorOutsideCoverageColor,
                border: Border.all(color: const Color(0xFF475467)),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 7),
            Flexible(
              child: Text(
                'Outside Bacoor assessment coverage',
                maxLines: compact ? 2 : null,
                overflow: compact ? TextOverflow.ellipsis : null,
                style: const TextStyle(
                  color: Color(0xFF344054),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
