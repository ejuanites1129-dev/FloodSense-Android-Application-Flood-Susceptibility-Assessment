import 'package:flutter/material.dart';

import '../../../data/models/geographic_area.dart';

class ZoneSelector extends StatelessWidget {
  const ZoneSelector({
    required this.areas,
    required this.selected,
    required this.onChanged,
    super.key,
  });

  final List<GeographicArea> areas;
  final GeographicArea? selected;
  final ValueChanged<GeographicArea?> onChanged;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Demonstration zone selector',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Demonstration zone',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          Text(
            'Choose a fictional zone supplied by the FloodSense API.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<GeographicArea>(
            key: ValueKey('zone-${selected?.id ?? 'none'}'),
            initialValue: selected,
            isExpanded: true,
            decoration: const InputDecoration(
              hintText: 'Select a demonstration zone',
              prefixIcon: Icon(Icons.place_outlined),
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
