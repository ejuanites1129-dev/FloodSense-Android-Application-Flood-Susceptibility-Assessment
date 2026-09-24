import 'package:flutter/material.dart';

import '../../../app/theme/app_colors.dart';
import '../../../data/models/assessment_result.dart';
import '../../../data/models/scenario_option.dart';
import 'guidance_section.dart';

class AssessmentResultCard extends StatelessWidget {
  const AssessmentResultCard({
    required this.result,
    required this.intensity,
    required this.duration,
    super.key,
  });

  final AssessmentResult result;
  final ScenarioOption intensity;
  final ScenarioOption duration;

  @override
  Widget build(BuildContext context) {
    final susceptibility = result.susceptibility!;
    final severityColor = Color(susceptibility.colorValue);
    final foreground = _foregroundFor(severityColor);
    return Semantics(
      container: true,
      label: 'Classified result: ${susceptibility.label} susceptibility',
      child: Column(
        key: const Key('classified-result'),
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: severityColor,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(11),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.shield_outlined, color: foreground),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          '${susceptibility.label} susceptibility',
                          style: TextStyle(
                            color: foreground,
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      Text(
                        susceptibility.code,
                        style: TextStyle(
                          color: foreground,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _LabelValue(
                        label: 'Area',
                        value: '${result.area.name} (${result.area.code})',
                      ),
                      _LabelValue(
                        label: 'Rainfall intensity',
                        value: intensity.label,
                      ),
                      _LabelValue(
                        label: 'Rainfall duration',
                        value: duration.label,
                      ),
                      const Divider(height: 28),
                      Text(
                        'Why this result?',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      Text(result.explanation.summary),
                      if (result.matchedRuleCodes.isNotEmpty) ...[
                        const SizedBox(height: 14),
                        _LabelValue(
                          label:
                              'Matched rule${result.matchedRuleCodes.length == 1 ? '' : 's'}',
                          value: result.matchedRuleCodes.join(', '),
                        ),
                      ],
                      if (result.facts.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Facts used',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 6),
                        for (final fact in result.facts.entries)
                          Text(
                            '• ${_factLabel(fact.key)}: ${fact.value ?? 'Not available'}',
                          ),
                      ],
                      const Divider(height: 28),
                      _LabelValue(
                        label: 'Rule set',
                        value: result.ruleset == null
                            ? 'Not available'
                            : '${result.ruleset!.name} v${result.ruleset!.version}',
                      ),
                      _LabelValue(
                        label: 'Data status',
                        value: result.dataStatus,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          _Warnings(warnings: result.warnings),
          const SizedBox(height: 12),
          GuidanceSection(items: result.guidance),
        ],
      ),
    );
  }

  Color _foregroundFor(Color background) {
    return ThemeData.estimateBrightnessForColor(background) == Brightness.dark
        ? Colors.white
        : Colors.black;
  }

  String _factLabel(String key) => switch (key) {
    'zone_code' => 'Assessment area code',
    'zone_baseline_rank' => 'Provisional area baseline rank',
    'mgb_dominant_mapped_class' => 'MGB dominant mapped class',
    'mgb_dominant_mapped_percent' => 'Dominant class share (%)',
    'mgb_mapped_percent' => 'Mapped LF/MF/HF/VHF coverage (%)',
    'mgb_unmapped_percent' => 'Unmapped area (%)',
    'mgb_conflict_percent' => 'Conflicting class area (%)',
    'mgb_dataset_version' => 'MGB-derived dataset version',
    'rainfall_intensity_code' => 'Rainfall intensity code',
    'rainfall_intensity_rank' => 'Demonstration rainfall intensity rank',
    'rainfall_duration_code' => 'Rainfall duration code',
    'rainfall_duration_hours' => 'Rainfall duration hours',
    _ => key.replaceAll('_', ' '),
  };
}

class _LabelValue extends StatelessWidget {
  const _LabelValue({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text.rich(
        TextSpan(
          children: [
            TextSpan(
              text: '$label: ',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            TextSpan(text: value),
          ],
        ),
      ),
    );
  }
}

class _Warnings extends StatelessWidget {
  const _Warnings({required this.warnings});

  final List<String> warnings;

  @override
  Widget build(BuildContext context) {
    if (warnings.isEmpty) return const SizedBox.shrink();
    return Semantics(
      container: true,
      label: 'Assessment warnings',
      child: Container(
        key: const Key('result-warnings'),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.warningSurface,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Important limitations',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 6),
            for (final warning in warnings) Text('• $warning'),
          ],
        ),
      ),
    );
  }
}
