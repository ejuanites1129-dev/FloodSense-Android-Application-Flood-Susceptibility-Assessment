import 'package:flutter/material.dart';

import '../../../app/theme/app_colors.dart';
import '../../../data/models/scenario_option.dart';

class DurationSelector extends StatelessWidget {
  const DurationSelector({
    required this.options,
    required this.selected,
    required this.onSelected,
    super.key,
  });

  final List<ScenarioOption> options;
  final ScenarioOption? selected;
  final ValueChanged<ScenarioOption> onSelected;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Rainfall duration selector',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Rainfall duration',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: options.map((option) {
              final isSelected = selected?.code == option.code;
              return Semantics(
                selected: isSelected,
                button: true,
                label:
                    '${option.label}, ${isSelected ? 'selected' : 'not selected'}',
                child: ChoiceChip(
                  key: Key('duration-${option.code}'),
                  label: Text(option.label),
                  selected: isSelected,
                  showCheckmark: true,
                  selectedColor: const Color(0xFFEAF6FC),
                  side: BorderSide(
                    color: isSelected ? AppColors.primary : AppColors.divider,
                    width: isSelected ? 2 : 1,
                  ),
                  labelStyle: TextStyle(
                    color: AppColors.bodyText,
                    fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                  ),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                  onSelected: (_) => onSelected(option),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
