import 'package:flutter/material.dart';

import '../../../app/theme/app_colors.dart';
import '../../../data/models/scenario_option.dart';

class ScenarioSelector extends StatelessWidget {
  const ScenarioSelector({
    required this.title,
    required this.semanticLabel,
    required this.options,
    required this.selected,
    required this.onSelected,
    super.key,
  });

  final String title;
  final String semanticLabel;
  final List<ScenarioOption> options;
  final ScenarioOption? selected;
  final ValueChanged<ScenarioOption> onSelected;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: semanticLabel,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          for (final option in options) ...[
            _OptionTile(
              key: Key('option-${option.code}'),
              option: option,
              selected: selected?.code == option.code,
              onTap: () => onSelected(option),
            ),
            if (option != options.last) const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  const _OptionTile({
    required this.option,
    required this.selected,
    required this.onTap,
    super.key,
  });

  final ScenarioOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      label: '${option.label}, ${selected ? 'selected' : 'not selected'}',
      child: Material(
        color: selected ? const Color(0xFFEAF6FC) : AppColors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: selected ? AppColors.primary : AppColors.divider,
            width: selected ? 2 : 1,
          ),
        ),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 56),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      option.label,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                  Icon(
                    selected
                        ? Icons.check_circle
                        : Icons.radio_button_unchecked,
                    color: selected
                        ? AppColors.primary
                        : AppColors.secondaryText,
                  ),
                  if (selected) ...[
                    const SizedBox(width: 6),
                    const Text(
                      'Selected',
                      style: TextStyle(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
