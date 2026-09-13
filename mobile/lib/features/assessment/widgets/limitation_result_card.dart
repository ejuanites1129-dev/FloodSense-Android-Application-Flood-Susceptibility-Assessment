import 'package:flutter/material.dart';

import '../../../app/theme/app_colors.dart';
import '../../../data/models/assessment_result.dart';

class LimitationResultCard extends StatelessWidget {
  const LimitationResultCard({required this.result, super.key});

  final AssessmentResult result;

  String get _title => switch (result.state) {
    AssessmentState.uncertain => 'Uncertain',
    AssessmentState.insufficientData => 'Insufficient Data',
    _ => 'Unable to Display Result',
  };

  String get _supportingText => switch (result.state) {
    AssessmentState.uncertain => 'Equally ranked stored rules conflict, so FloodSense did not assign a susceptibility class.',
    AssessmentState.insufficientData => 'The available stored facts or rules cannot support a susceptibility classification.',
    _ => 'The server returned an unsupported assessment state. No classification was assumed.',
  };

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Assessment limitation: $_title',
      child: Card(
        key: const Key('limitation-result'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(
                Icons.info_outline,
                color: AppColors.limitation,
                size: 36,
              ),
              const SizedBox(height: 8),
              Text(
                _title,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleLarge
                    ?.copyWith(color: AppColors.limitation),
              ),
              const SizedBox(height: 10),
              Text(_supportingText),
              const SizedBox(height: 8),
              Text(result.explanation.summary),
              if (result.matchedRuleCodes.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  'Matched rules: ${result.matchedRuleCodes.join(', ')}',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ],
              if (result.ruleset != null) ...[
                const SizedBox(height: 8),
                Text(
                  'Rule set: ${result.ruleset!.name} v${result.ruleset!.version}',
                ),
              ],
              if (result.warnings.isNotEmpty) ...[
                const Divider(height: 28),
                for (final warning in result.warnings) Text('• $warning'),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
