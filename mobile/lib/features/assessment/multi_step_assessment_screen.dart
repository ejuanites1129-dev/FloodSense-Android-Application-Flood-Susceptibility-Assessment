import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/api/floodsense_api_client.dart';
import '../../data/dss/structured_dss_repository.dart';
import '../dss/dss_controller.dart';
import '../dss/dss_flow_view.dart';
import '../evacuation/nearest_center_controller.dart';
import '../evacuation/nearest_center_provider.dart';
import '../evacuation/nearest_centers_section.dart';
import '../location/location_card.dart';
import '../location/location_controller.dart';
import '../location/location_service.dart';
import 'assessment_controller.dart';
import 'widgets/assessment_result_card.dart';
import 'widgets/demonstration_warning.dart';
import 'widgets/duration_selector.dart';
import 'widgets/limitation_result_card.dart';
import 'widgets/reference_boundary_map_card.dart';
import 'widgets/scenario_selector.dart';
import 'widgets/zone_selector.dart';

class MultiStepAssessmentScreen extends StatefulWidget {
  const MultiStepAssessmentScreen({
    required this.api,
    this.locationService,
    this.nearestCenterProvider,
    this.dssRepository,
    this.showBasemap = true,
    super.key,
  });
  final FloodSenseApi api;
  final LocationService? locationService;
  final NearestCenterProvider? nearestCenterProvider;
  final StructuredDssRepository? dssRepository;
  final bool showBasemap;

  @override
  State<MultiStepAssessmentScreen> createState() =>
      _MultiStepAssessmentScreenState();
}

class _MultiStepAssessmentScreenState extends State<MultiStepAssessmentScreen> {
  late final AssessmentController _assessment;
  late final DssController _dss;
  LocationController? _location;
  NearestCenterController? _centers;
  int _step = 0;

  @override
  void initState() {
    super.initState();
    _assessment = AssessmentController(widget.api, closeApiOnDispose: false)
      ..load();
    _dss = DssController(widget.dssRepository ?? HttpStructuredDssRepository());
    if (widget.locationService case final service?) {
      _location = LocationController(service, resolver: widget.api);
      _centers = NearestCenterController(
        _location!,
        provider: widget.nearestCenterProvider,
      );
    }
  }

  @override
  void dispose() {
    _assessment.dispose();
    _dss.dispose();
    _centers?.dispose();
    _location?.dispose();
    super.dispose();
  }

  void _scenarioChanged(void Function() change) {
    change();
    _dss.resetForScenarioChange();
  }

  Future<void> _advance() async {
    if (_step == 2) {
      await _assessment.submit();
      if (!mounted || _assessment.result == null) return;
    }
    if (_step < 4) setState(() => _step++);
  }

  bool get _canContinue => switch (_step) {
    0 => _assessment.hasCompleteScenario,
    1 => _assessment.selectedArea != null,
    2 => _assessment.canSubmit,
    3 => _assessment.result?.isClassified ?? false,
    _ => false,
  };

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: _step == 0,
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop && _step > 0) setState(() => _step--);
    },
    child: AnimatedBuilder(
      animation: _assessment,
      builder: (context, _) => Scaffold(
        appBar: AppBar(
          title: const Text('Assess'),
          automaticallyImplyLeading: false,
        ),
        body: SafeArea(
          child: Column(
            children: [
              LinearProgressIndicator(
                value: (_step + 1) / 5,
                semanticsLabel: 'Assessment step ${_step + 1} of 5',
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Step ${_step + 1} of 5',
                    key: const Key('assessment-step-indicator'),
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                ),
              ),
              Expanded(child: _body()),
              if (_step < 4)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          key: const Key('assessment-back'),
                          onPressed: _step == 0
                              ? null
                              : () => setState(() => _step--),
                          child: const Text('Back'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton(
                          key: const Key('assessment-continue'),
                          onPressed: _canContinue && !_assessment.isSubmitting
                              ? _advance
                              : null,
                          child: Text(
                            _step == 2
                                ? (_assessment.isSubmitting
                                      ? 'Assessing…'
                                      : 'Assess Susceptibility')
                                : 'Continue',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    ),
  );

  Widget _body() {
    if (_assessment.isLoading) {
      return const Center(
        child: CircularProgressIndicator(
          semanticsLabel: 'Loading assessment options',
        ),
      );
    }
    if (_assessment.loadError != null) {
      return Center(
        child: FilledButton(
          onPressed: _assessment.load,
          child: const Text('Retry loading assessment'),
        ),
      );
    }
    return switch (_step) {
      0 => _scenario(),
      1 => _locationStep(),
      2 => _review(),
      3 => _result(),
      _ => _decisionSupport(),
    };
  }

  Widget _page(List<Widget> children) => ListView(
    key: Key('assessment-page-$_step'),
    padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
    children: [
      Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children,
          ),
        ),
      ),
    ],
  );

  Widget _scenario() => _page([
    Text(
      'Hypothetical rainfall scenario',
      style: Theme.of(context).textTheme.headlineSmall,
    ),
    const SizedBox(height: 8),
    const Text(
      'These choices are not live weather observations or a forecast.',
    ),
    const SizedBox(height: 12),
    const DemonstrationWarning(),
    const SizedBox(height: 16),
    ScenarioSelector(
      title: 'Rainfall intensity',
      semanticLabel: 'Rainfall intensity selector',
      options: _assessment.intensities,
      selected: _assessment.selectedIntensity,
      onSelected: (value) =>
          _scenarioChanged(() => _assessment.selectIntensity(value)),
    ),
    const SizedBox(height: 20),
    DurationSelector(
      options: _assessment.durations,
      selected: _assessment.selectedDuration,
      onSelected: (value) =>
          _scenarioChanged(() => _assessment.selectDuration(value)),
    ),
  ]);

  Widget _locationStep() => _page([
    Text(
      'Confirm a supported location',
      style: Theme.of(context).textTheme.headlineSmall,
    ),
    const SizedBox(height: 8),
    const Text(
      'GPS is optional, foreground-only, and user initiated. The pin is temporary. Manual selection is always available.',
    ),
    const SizedBox(height: 12),
    if (_location case final location?) ...[
      LocationCard(controller: location, barangays: _assessment.referenceAreas),
      const SizedBox(height: 12),
    ],
    ReferenceBoundaryMapCard(
      controller: _assessment,
      locationController: _location,
      nearestCenterController: _centers,
      showBasemap: widget.showBasemap,
    ),
    const SizedBox(height: 12),
    Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Assessment demonstration zone',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            ZoneSelector(
              areas: _assessment.areas,
              selected: _assessment.selectedArea,
              onChanged: _assessment.selectArea,
            ),
            const SizedBox(height: 8),
            const Text(
              'Unsupported or unresolved areas cannot proceed. Selecting a zone does not run an assessment.',
            ),
          ],
        ),
      ),
    ),
  ]);

  Widget _review() => _page([
    Text(
      'Review before assessment',
      style: Theme.of(context).textTheme.headlineSmall,
    ),
    const SizedBox(height: 12),
    _ReviewRow(
      label: 'Rainfall intensity',
      value: _assessment.selectedIntensity?.label ?? 'Not selected',
    ),
    _ReviewRow(
      label: 'Rainfall duration',
      value: _assessment.selectedDuration?.label ?? 'Not selected',
    ),
    _ReviewRow(
      label: 'Assessment zone',
      value: _assessment.selectedArea?.name ?? 'Not selected',
    ),
    if (_location?.confirmedBarangay case final barangay?)
      _ReviewRow(label: 'Resolved barangay', value: barangay.name),
    _ReviewRow(
      label: 'Data status',
      value: _assessment.selectedArea?.dataStatus ?? 'Unavailable',
    ),
    const SizedBox(height: 12),
    const Card(
      color: AppColors.warningSurface,
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Text(
          'The result is scenario-based, not a live forecast, official warning, or evacuation order. Select Assess Susceptibility to run it explicitly.',
        ),
      ),
    ),
    if (_assessment.submissionError case final error?)
      Padding(
        padding: const EdgeInsets.only(top: 12),
        child: Text(
          error.message,
          style: const TextStyle(color: AppColors.error),
        ),
      ),
  ]);

  Widget _result() {
    final result = _assessment.result!;
    return _page([
      Text(
        'Assessment result',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 12),
      if (result.isClassified)
        AssessmentResultCard(
          result: result,
          intensity: _assessment.selectedIntensity!,
          duration: _assessment.selectedDuration!,
        )
      else
        LimitationResultCard(result: result),
      const SizedBox(height: 12),
      const Text(
        'Decision Support is available only for a classified result and cannot change this classification.',
      ),
    ]);
  }

  Widget _decisionSupport() {
    final result = _assessment.result!;
    if (!result.isClassified) {
      return _page([
        const Text(
          'Structured guidance is unavailable because no susceptibility class was assigned.',
        ),
      ]);
    }
    return Column(
      children: [
        Expanded(
          child: DssFlowView(
            controller: _dss,
            susceptibilityCode: result.susceptibility!.code,
          ),
        ),
        if (_centers case final centers?)
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: NearestCentersSection(controller: centers),
            ),
          ),
      ],
    );
  }
}

class _ReviewRow extends StatelessWidget {
  const _ReviewRow({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => ListTile(
    contentPadding: EdgeInsets.zero,
    title: Text(label),
    subtitle: Text(value),
    trailing: const Icon(Icons.check_circle_outline),
  );
}
