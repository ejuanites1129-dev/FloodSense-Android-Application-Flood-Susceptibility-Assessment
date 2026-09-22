import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';

import '../../data/models/geographic_area.dart';

/// Neutral presentation color for places outside FloodSense's Bacoor coverage.
///
/// This is a coverage cue only. It must not be reused as a susceptibility,
/// hazard, warning, or safety classification.
const bacoorOutsideCoverageColor = Color(0xA6677280);

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
  const BacoorCoverageLegend({this.compact = false, super.key});

  final bool compact;

  @override
  Widget build(BuildContext context) => Semantics(
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
