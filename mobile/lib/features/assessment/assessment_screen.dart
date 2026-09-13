import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/api/api_exception.dart';
import '../../data/api/floodsense_api_client.dart';
import '../../data/models/assessment_result.dart';
import 'assessment_controller.dart';
import 'widgets/assessment_result_card.dart';
import 'widgets/demonstration_warning.dart';
import 'widgets/dynamic_map_card.dart';
import 'widgets/duration_selector.dart';
import 'widgets/limitation_result_card.dart';
import 'widgets/scenario_selector.dart';
import 'widgets/zone_selector.dart';

class AssessmentScreen extends StatefulWidget {
  const AssessmentScreen({
    required this.api,
    this.showBasemap = true,
    super.key,
  });

  final FloodSenseApi api;
  final bool showBasemap;

  @override
  State<AssessmentScreen> createState() => _AssessmentScreenState();
}

class _AssessmentScreenState extends State<AssessmentScreen> {
  late final AssessmentController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AssessmentController(widget.api);
    _controller.load();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FloodSense'),
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.primary,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
      ),
      body: SafeArea(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            return SingleChildScrollView(
              key: const Key('assessment-scroll-view'),
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 720),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'Scenario-based flood susceptibility assessment.',
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Choose a hypothetical rainfall scenario and a fictional demonstration zone.',
                        style: Theme.of(context).textTheme.bodyLarge
                            ?.copyWith(color: AppColors.secondaryText),
                      ),
                      const SizedBox(height: 16),
                      const DemonstrationWarning(),
                      const SizedBox(height: 20),
                      if (_controller.isLoading)
                        const _InitialLoading()
                      else if (_controller.loadError case final error?)
                        _ErrorCard(
                          key: const Key('initial-load-error'),
                          error: error,
                          onRetry: _controller.load,
                        )
                      else if (_controller.hasEmptyData)
                        const _EmptyState()
                      else
                        _buildAssessmentForm(context),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildAssessmentForm(BuildContext context) {
    final result = _controller.result;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Plan a scenario',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 6),
                Text(
                  'All choices below are loaded from the current Django demonstration database.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 18),
                ScenarioSelector(
                  title: 'Rainfall intensity',
                  semanticLabel: 'Rainfall intensity selector',
                  options: _controller.intensities,
                  selected: _controller.selectedIntensity,
                  onSelected: _controller.selectIntensity,
                ),
                const SizedBox(height: 20),
                DurationSelector(
                  options: _controller.durations,
                  selected: _controller.selectedDuration,
                  onSelected: _controller.selectDuration,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 14),
        DynamicMapCard(
          controller: _controller,
          showBasemap: widget.showBasemap,
        ),
        const SizedBox(height: 14),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Choose the assessment zone',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 6),
                Text(
                  'The selector remains available if placing a map pin is difficult.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 14),
                ZoneSelector(
                  areas: _controller.areas,
                  selected: _controller.selectedArea,
                  onChanged: _controller.selectArea,
                ),
                const SizedBox(height: 14),
                SelectedZonePreview(controller: _controller),
                const SizedBox(height: 16),
                Semantics(
                  button: true,
                  enabled: _controller.canSubmit,
                  label: _controller.isSubmitting
                      ? 'Assessing susceptibility'
                      : 'Run full susceptibility assessment',
                  child: FilledButton(
                    key: const Key('assess-button'),
                    onPressed: _controller.canSubmit
                        ? _controller.submit
                        : null,
                    child: _controller.isSubmitting
                        ? const Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                  semanticsLabel: 'Assessment in progress',
                                ),
                              ),
                              SizedBox(width: 10),
                              Text('Assessing…'),
                            ],
                          )
                        : const Text('Assess Susceptibility'),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (_controller.submissionError case final error?) ...[
          const SizedBox(height: 12),
          _ErrorCard(
            key: const Key('submission-error'),
            error: error,
            onRetry: error.canRetry ? _controller.submit : null,
          ),
        ],
        if (result != null) ...[
          const SizedBox(height: 20),
          if (result.state == AssessmentState.classified)
            AssessmentResultCard(
              result: result,
              intensity: _controller.selectedIntensity!,
              duration: _controller.selectedDuration!,
            )
          else
            LimitationResultCard(result: result),
        ],
      ],
    );
  }
}

class _InitialLoading extends StatelessWidget {
  const _InitialLoading();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Loading demonstration options and zones',
      child: const Card(
        key: Key('initial-loading'),
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            children: [
              CircularProgressIndicator(
                semanticsLabel: 'Loading demonstration data',
              ),
              SizedBox(height: 14),
              Text('Loading demonstration options and zones…'),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'No demonstration data available',
      child: const Card(
        key: Key('empty-state'),
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Column(
            children: [
              Icon(
                Icons.inventory_2_outlined,
                color: AppColors.limitation,
                size: 36,
              ),
              SizedBox(height: 10),
              Text(
                'No demonstration data is currently available. Ask an administrator to configure and enable the demonstration records.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.error, required this.onRetry, super.key});

  final ApiException error;
  final VoidCallback? onRetry;

  String get _title => switch (error.kind) {
    ApiFailureKind.validation => 'Check your selections',
    ApiFailureKind.connectivity => 'Cannot connect to FloodSense',
    ApiFailureKind.service => 'FloodSense is unavailable',
    ApiFailureKind.malformedResponse => 'Unexpected server response',
  };

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      liveRegion: true,
      label: 'Error: $_title. ${error.message}',
      child: Card(
        color: const Color(0xFFFFEEEE),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Icon(Icons.error_outline, color: AppColors.error),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _title,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(error.message),
              if (onRetry != null) ...[
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  key: const Key('retry-button'),
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
