import 'package:flutter/material.dart';

import '../../../data/models/geographic_area.dart';

class ZoneSelector extends StatelessWidget {
  const ZoneSelector({
    required this.areas,
    required this.selected,
    required this.onChanged,
    this.title = 'Demonstration zone',
    this.description =
        'Choose a fictional zone supplied by the FloodSense API.',
    this.hintText = 'Select a demonstration zone',
    this.semanticLabel = 'Demonstration zone selector',
    super.key,
  });

  final List<GeographicArea> areas;
  final GeographicArea? selected;
  final ValueChanged<GeographicArea?> onChanged;
  final String title;
  final String description;
  final String hintText;
  final String semanticLabel;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: semanticLabel,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(description, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 10),
          DropdownButtonFormField<GeographicArea>(
            key: ValueKey('zone-${selected?.id ?? 'none'}'),
            initialValue: selected,
            isExpanded: true,
            decoration: InputDecoration(
              hintText: hintText,
              prefixIcon: const Icon(Icons.place_outlined),
            ),
            items: areas
                .map(
                  (area) => DropdownMenuItem(
                    value: area,
                    child: Text('${area.name} (${area.code})'),
                  ),
                )
                .toList(),
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}
