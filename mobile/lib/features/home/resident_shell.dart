import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/api/floodsense_api_client.dart';
import '../../data/auth/resident_auth_repository.dart';
import '../../data/dss/structured_dss_repository.dart';
import '../../data/models/assessment_result.dart';
import '../../data/models/geographic_area.dart';
import '../../data/models/scenario_option.dart';
import '../assessment/assessment_controller.dart';
import '../assessment/widgets/duration_selector.dart';
import '../assessment/widgets/scenario_selector.dart';
import '../assessment/widgets/zone_selector.dart';
import '../auth/auth_screens.dart';
import '../auth/session_controller.dart';
import '../auth/setup_screens.dart';
import '../dss/dss_controller.dart';
import '../dss/dss_flow_view.dart';
import '../evacuation/nearest_center_controller.dart';
import '../evacuation/nearest_center_provider.dart';
import '../evacuation/nearest_centers_section.dart';
import '../location/location_card.dart';
import '../location/location_controller.dart';
import '../location/location_service.dart';
import 'hybrid_map_surface.dart';

class ResidentShell extends StatefulWidget {
  const ResidentShell({
    required this.session,
    required this.api,
    this.locationService,
    this.nearestCenterProvider,
    this.dssRepository,
    this.showBasemap = true,
    super.key,
  });
  final SessionController session;
  final FloodSenseApi api;
  final LocationService? locationService;
  final NearestCenterProvider? nearestCenterProvider;
  final StructuredDssRepository? dssRepository;
  final bool showBasemap;
  @override
  State<ResidentShell> createState() => _ResidentShellState();
}

class _ResidentShellState extends State<ResidentShell> {
  static const double _collapsedSheetSize = 0;
  static const double _collapseThreshold = 0.065;
  static const double _maximumSheetSize = 0.9;

  late final AssessmentController _assessment;
  late final DssController _dss;
  final DraggableScrollableController _sheetController =
      DraggableScrollableController();
  LocationController? _location;
  NearestCenterController? _centers;
  int _index = 0;
  int _assessmentStep = 0;
  bool _sheetIsCollapsed = false;
  bool _synchronizingBarangay = false;

  @override
  void initState() {
    super.initState();
    _assessment = AssessmentController(widget.api, closeApiOnDispose: false)
      ..load();
    _dss = DssController(widget.dssRepository ?? HttpStructuredDssRepository());
    _sheetController.addListener(_handleSheetExtentChange);
    if (widget.locationService case final service?) {
      _location = LocationController(service, resolver: widget.api);
      _location!.addListener(_synchronizeConfirmedBarangay);
      _assessment.addListener(_synchronizeConfirmedBarangay);
      _centers = NearestCenterController(
        _location!,
        provider: widget.nearestCenterProvider,
      );
    }
  }

  @override
  void dispose() {
    _location?.removeListener(_synchronizeConfirmedBarangay);
    _assessment.removeListener(_synchronizeConfirmedBarangay);
    _sheetController.removeListener(_handleSheetExtentChange);
    _sheetController.dispose();
    _assessment.dispose();
    _dss.dispose();
    _centers?.dispose();
    _location?.dispose();
    super.dispose();
  }

  bool get _usesBarangayAssessments =>
      _assessment.areas.isNotEmpty &&
      _assessment.areas.every((area) => area.areaType == 'BARANGAY');

  void _synchronizeConfirmedBarangay() {
    if (_synchronizingBarangay || !_usesBarangayAssessments) return;
    final confirmedCode = _location?.confirmedBarangay?.geographicAreaCode;
    if (_assessment.selectedArea?.code == confirmedCode) return;
    _synchronizingBarangay = true;
    _assessment.selectAreaByCode(confirmedCode);
    _synchronizingBarangay = false;
  }

  void _selectDestination(int value) {
    setState(() {
      _index = value;
      if (value == 1 && _assessment.result != null) {
        _assessmentStep = 0;
      }
    });
    _restorePreferredSheetExtent();
  }

  double get _preferredSheetSize {
    final result = _assessment.result;
    final selected = _assessment.selectedArea;
    return switch (_index) {
      1 => 0.52,
      2 => 0.58,
      _ when result != null => 0.55,
      _ when selected != null => 0.3,
      _ => 0.16,
    };
  }

  void _handleSheetExtentChange() {
    if (!_sheetController.isAttached || !mounted) return;
    final collapsed = _sheetController.size <= _collapseThreshold;
    if (collapsed == _sheetIsCollapsed) return;
    setState(() => _sheetIsCollapsed = collapsed);
    if (collapsed && _sheetController.size > _collapsedSheetSize) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _sheetController.isAttached) {
          _animateSheetTo(_collapsedSheetSize);
        }
      });
    }
  }

  void _restorePreferredSheetExtent() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_sheetController.isAttached) return;
      _animateSheetTo(_preferredSheetSize);
    });
  }

  Future<void> _animateSheetTo(double size) async {
    if (!_sheetController.isAttached) return;
    await _sheetController.animateTo(
      size,
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOutCubic,
    );
  }

  void _expandSheet() {
    if (!_sheetController.isAttached) return;
    _animateSheetTo(_preferredSheetSize);
  }

  void _collapseSheet() {
    if (!_sheetController.isAttached) return;
    _animateSheetTo(_collapsedSheetSize);
  }

  void _dragSheetHandle(DragUpdateDetails details) {
    if (!_sheetController.isAttached) return;
    final availableHeight = MediaQuery.sizeOf(context).height;
    final delta = (details.primaryDelta ?? 0) / availableHeight;
    final nextSize = (_sheetController.size - delta).clamp(
      _collapsedSheetSize,
      _maximumSheetSize,
    );
    _sheetController.jumpTo(nextSize);
  }

  void _changeScenario(void Function() change) {
    change();
    _dss.resetForScenarioChange();
  }

  Future<void> _continueAssessment() async {
    if (_assessmentStep < 2) {
      setState(() => _assessmentStep++);
      return;
    }
    await _assessment.submit();
    if (!mounted || _assessment.result == null) return;
    setState(() => _index = 0);
    _restorePreferredSheetExtent();
  }

  void _backAssessment() {
    if (_assessmentStep > 0) {
      setState(() => _assessmentStep--);
    } else {
      setState(() => _index = 0);
      _restorePreferredSheetExtent();
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: _index == 0,
    onPopInvokedWithResult: (didPop, _) {
      if (didPop) return;
      if (_index == 1 && _assessmentStep > 0) {
        setState(() => _assessmentStep--);
      } else {
        setState(() => _index = 0);
        _restorePreferredSheetExtent();
      }
    },
    child: Scaffold(
      body: _index == 3
          ? AccountScreen(session: widget.session, api: widget.api)
          : AnimatedBuilder(
              animation: _assessment,
              builder: (context, _) => _mapExperience(context),
            ),
      bottomNavigationBar: NavigationBar(
        key: const Key('resident-bottom-navigation'),
        selectedIndex: _index,
        indicatorColor: AppColors.activeBackground,
        onDestinationSelected: _selectDestination,
        destinations: const [
          NavigationDestination(
            key: Key('resident-nav-map'),
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map),
            label: 'Map',
          ),
          NavigationDestination(
            key: Key('resident-nav-assess'),
            icon: Icon(Icons.search_outlined),
            selectedIcon: Icon(Icons.search),
            label: 'Assess',
          ),
          NavigationDestination(
            key: Key('resident-nav-prepare'),
            icon: Icon(Icons.shield_outlined),
            selectedIcon: Icon(Icons.shield),
            label: 'Prepare',
          ),
          NavigationDestination(
            key: Key('resident-nav-profile'),
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
      ),
    ),
  );

  Widget _mapExperience(BuildContext context) => Stack(
    fit: StackFit.expand,
    children: [
      HybridMapSurface(
        key: const Key('resident-hybrid-map'),
        controller: _assessment,
        locationController: _location,
        nearestCenterController: _centers,
        showBasemap: widget.showBasemap,
      ),
      const _MapBrandBar(),
      Positioned(
        top: MediaQuery.paddingOf(context).top + 68,
        left: 14,
        child: _ScenarioChip(
          assessment: _assessment,
          onTap: () {
            setState(() {
              _assessmentStep = 0;
              _index = 1;
            });
            _restorePreferredSheetExtent();
          },
        ),
      ),
      _sheet(),
      if (_sheetIsCollapsed)
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: Center(child: _CollapsedSheetTab(onTap: _expandSheet)),
        ),
    ],
  );

  Widget _sheet() {
    return DraggableScrollableSheet(
      key: const Key('resident-draggable-sheet'),
      controller: _sheetController,
      initialChildSize: _preferredSheetSize,
      minChildSize: _collapsedSheetSize,
      maxChildSize: _maximumSheetSize,
      snap: false,
      builder: (context, scrollController) => Material(
        key: const Key('resident-context-sheet'),
        color: _sheetIsCollapsed ? Colors.transparent : AppColors.surface,
        elevation: _sheetIsCollapsed ? 0 : 12,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        clipBehavior: Clip.antiAlias,
        child: _sheetIsCollapsed
            ? ListView(
                controller: scrollController,
                padding: EdgeInsets.zero,
                children: const [],
              )
            : Column(
                children: [
                  _SheetHandle(
                    onCollapse: _collapseSheet,
                    onVerticalDragUpdate: _dragSheetHandle,
                  ),
                  Expanded(child: _sheetBody(scrollController)),
                ],
              ),
      ),
    );
  }

  Widget _sheetBody(ScrollController scrollController) => switch (_index) {
    1 => _assessmentSheet(scrollController),
    2 => _prepareSheet(scrollController),
    _ => _mapSheet(scrollController),
  };

  Widget _mapSheet(ScrollController scrollController) {
    final result = _assessment.result;
    return ListView(
      key: const Key('map-context-sheet-content'),
      controller: scrollController,
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 24),
      children: [
        if (result == null) ...[
          Row(
            children: [
              const _RoundIcon(icon: Icons.water, color: AppColors.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _assessment.selectedArea == null
                          ? 'Flood information'
                          : _assessment.selectedArea!.name,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    Text(
                      _assessment.selectedArea == null
                          ? 'Swipe up for scenario and area details'
                          : 'Supported assessment area selected',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerLeft,
            child: _StatusPill(
              label: _assessment.hasCompleteScenario
                  ? 'Scenario selected'
                  : 'Choose scenario',
              ready: _assessment.hasCompleteScenario,
            ),
          ),
          const SizedBox(height: 16),
          const _PlanningNotice(),
          const SizedBox(height: 12),
          Text(
            _assessment.selectedArea == null
                ? 'Tap the map to place a temporary pin, or begin the guided assessment to select a supported area.'
                : 'Selected area: ${_assessment.selectedArea!.name}. Continue through the guided review before running an assessment.',
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            key: const Key('map-start-assessment'),
            onPressed: () {
              setState(() {
                _assessmentStep = _assessment.hasCompleteScenario ? 1 : 0;
                _index = 1;
              });
              _restorePreferredSheetExtent();
            },
            icon: const Icon(Icons.search),
            label: Text(
              _assessment.hasCompleteScenario
                  ? 'Continue Assessment'
                  : 'Choose a Scenario',
            ),
          ),
        ] else ...[
          _ResultSummary(
            result: result,
            intensity: _assessment.selectedIntensity?.label ?? 'Not available',
            duration: _assessment.selectedDuration?.label ?? 'Not available',
            onPrepare: result.isClassified
                ? () {
                    setState(() => _index = 2);
                    _restorePreferredSheetExtent();
                  }
                : null,
            onRestart: () {
              setState(() {
                _assessmentStep = 0;
                _index = 1;
              });
              _restorePreferredSheetExtent();
            },
          ),
        ],
      ],
    );
  }

  Widget _assessmentSheet(ScrollController scrollController) {
    if (_assessment.isLoading) {
      return const Center(
        child: CircularProgressIndicator(
          semanticsLabel: 'Loading assessment options',
        ),
      );
    }
    if (_assessment.loadError != null) {
      return ListView(
        controller: scrollController,
        padding: const EdgeInsets.all(20),
        children: [
          const Text('Assessment options could not be loaded.'),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _assessment.load,
            child: const Text('Retry loading assessment'),
          ),
        ],
      );
    }
    return switch (_assessmentStep) {
      0 => _scenarioStep(scrollController),
      1 => _locationStep(scrollController),
      _ => _reviewStep(scrollController),
    };
  }

  Widget _scenarioStep(ScrollController scrollController) => ListView(
    key: const Key('hybrid-assessment-scenario'),
    controller: scrollController,
    padding: const EdgeInsets.fromLTRB(18, 0, 18, 28),
    children: [
      const _StepHeading(
        icon: Icons.search,
        title: 'Assess your area',
        step: 'Step 1 of 3',
        description: 'Choose a hypothetical rainfall scenario.',
      ),
      const SizedBox(height: 14),
      ScenarioSelector(
        title: 'Rainfall intensity',
        semanticLabel: 'Rainfall intensity selector',
        options: _assessment.intensities,
        selected: _assessment.selectedIntensity,
        onSelected: (value) =>
            _changeScenario(() => _assessment.selectIntensity(value)),
      ),
      const SizedBox(height: 18),
      DurationSelector(
        options: _assessment.durations,
        selected: _assessment.selectedDuration,
        onSelected: (value) =>
            _changeScenario(() => _assessment.selectDuration(value)),
      ),
      const SizedBox(height: 14),
      const _PlanningNotice(),
      const SizedBox(height: 14),
      FilledButton(
        key: const Key('hybrid-assessment-continue'),
        onPressed: _assessment.hasCompleteScenario ? _continueAssessment : null,
        child: const Text('Continue'),
      ),
    ],
  );

  Widget _locationStep(ScrollController scrollController) => ListView(
    key: const Key('hybrid-assessment-location'),
    controller: scrollController,
    padding: const EdgeInsets.fromLTRB(18, 0, 18, 28),
    children: [
      const _StepHeading(
        icon: Icons.location_on_outlined,
        title: 'Choose your area',
        step: 'Step 2 of 3',
        description: 'Place a temporary pin on the visible map or choose a supported area.',
      ),
      const SizedBox(height: 12),
      if (_location case final location?) ...[
        LocationCard(
          controller: location,
          barangays: _assessment.referenceAreas,
        ),
        const SizedBox(height: 12),
      ],
      if (!_usesBarangayAssessments || _location == null)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _usesBarangayAssessments
                      ? 'Choose a barangay manually'
                      : 'Supported assessment area',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 10),
                ZoneSelector(
                  areas: _assessment.areas,
                  selected: _assessment.selectedArea,
                  onChanged: _assessment.selectArea,
                  title: _usesBarangayAssessments
                      ? 'Barangay'
                      : 'Demonstration zone',
                  description: _usesBarangayAssessments
                      ? 'Choose one current Bacoor barangay for this explicit scenario.'
                      : 'Choose a fictional zone supplied by the FloodSense API.',
                  hintText: _usesBarangayAssessments
                      ? 'Select a barangay'
                      : 'Select a demonstration zone',
                  semanticLabel: _usesBarangayAssessments
                      ? 'Barangay selector'
                      : 'Demonstration zone selector',
                ),
                const SizedBox(height: 8),
                const Text(
                  'The map pin and device location are temporary and are not saved to your account.',
                  style: TextStyle(color: AppColors.secondaryText),
                ),
              ],
            ),
          ),
        )
      else
        const _PlanningNotice(
          text: 'Confirm one barangay through GPS, a temporary map pin, or the manual barangay selector. This selects the same polygon used by the assessment—there is no separate demo-zone choice.',
        ),
      const SizedBox(height: 14),
      _NavigationButtons(
        backKey: const Key('hybrid-assessment-back'),
        continueKey: const Key('hybrid-assessment-continue'),
        onBack: _backAssessment,
        onContinue: _assessment.selectedArea != null
            ? _continueAssessment
            : null,
        continueLabel: 'Confirm area',
      ),
    ],
  );

  Widget _reviewStep(ScrollController scrollController) => ListView(
    key: const Key('hybrid-assessment-review'),
    controller: scrollController,
    padding: const EdgeInsets.fromLTRB(18, 0, 18, 28),
    children: [
      const _StepHeading(
        icon: Icons.fact_check_outlined,
        title: 'Review assessment',
        step: 'Step 3 of 3',
        description:
            'Confirm the scenario and supported area before evaluation.',
      ),
      const SizedBox(height: 12),
      _ReviewTile(
        label: 'Rainfall intensity',
        value: _assessment.selectedIntensity?.label ?? 'Not selected',
      ),
      _ReviewTile(
        label: 'Rainfall duration',
        value: _assessment.selectedDuration?.label ?? 'Not selected',
      ),
      _ReviewTile(
        label: _usesBarangayAssessments
            ? 'Assessment barangay'
            : 'Assessment area',
        value: _assessment.selectedArea?.name ?? 'Not selected',
      ),
      if (_assessment.selectedArea?.susceptibilitySummary case final summary?)
        _ReviewTile(
          label: 'Provisional MGB-derived baseline',
          value: summary.hasDominantClass
              ? '${summary.dominantClassLabel} (${summary.dominantPercent!.toStringAsFixed(2)}% of barangay area; ${summary.mappedPercent.toStringAsFixed(2)}% mapped)'
              : 'Unavailable—no mapped LF/MF/HF/VHF class covers this barangay',
        ),
      if (_location?.confirmedBarangay case final barangay?)
        _ReviewTile(label: 'Confirmed barangay', value: barangay.name),
      const SizedBox(height: 12),
      const _PlanningNotice(
        text: 'This explicit assessment produces a scenario-based result—not a live forecast, warning, safety guarantee, or evacuation order.',
      ),
      if (_assessment.submissionError case final error?) ...[
        const SizedBox(height: 10),
        Text(error.message, style: const TextStyle(color: AppColors.error)),
      ],
      const SizedBox(height: 14),
      _NavigationButtons(
        backKey: const Key('hybrid-assessment-back'),
        continueKey: const Key('hybrid-run-assessment'),
        onBack: _backAssessment,
        onContinue: _assessment.canSubmit && !_assessment.isSubmitting
            ? _continueAssessment
            : null,
        continueLabel: _assessment.isSubmitting
            ? 'Assessing…'
            : 'Assess Susceptibility',
      ),
    ],
  );

  Widget _prepareSheet(ScrollController scrollController) {
    final result = _assessment.result;
    if (result == null || !result.isClassified) {
      return ListView(
        key: const Key('prepare-empty-state'),
        controller: scrollController,
        padding: const EdgeInsets.fromLTRB(18, 0, 18, 28),
        children: [
          const _StepHeading(
            icon: Icons.shield_outlined,
            title: 'Preparedness',
            step: 'Assessment required',
            description: 'Complete a classified scenario assessment before opening tailored guidance.',
          ),
          const SizedBox(height: 14),
          const _PlanningNotice(
            text: 'Preparedness guidance never changes the susceptibility classification and is not an evacuation order.',
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            onPressed: () {
              setState(() {
                _assessmentStep = 0;
                _index = 1;
              });
              _restorePreferredSheetExtent();
            },
            icon: const Icon(Icons.search),
            label: const Text('Start an Assessment'),
          ),
        ],
      );
    }
    return DssFlowView(
      key: ValueKey('dss-${result.susceptibility!.code}'),
      controller: _dss,
      susceptibilityCode: result.susceptibility!.code,
      scrollController: scrollController,
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 28),
      header: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(result.area.name, style: Theme.of(context).textTheme.bodySmall),
          Text(
            'Preparedness',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const Text('Based on your scenario result'),
          const SizedBox(height: 12),
          _SusceptibilityBanner(
            result: result,
            intensity: _assessment.selectedIntensity?.label ?? 'Not available',
            duration: _assessment.selectedDuration?.label ?? 'Not available',
          ),
          const SizedBox(height: 10),
          const _PlanningNotice(
            text: 'Follow official authorities and emergency services during an emergency.',
          ),
          const SizedBox(height: 16),
        ],
      ),
      footer: _centers == null
          ? null
          : Padding(
              padding: const EdgeInsets.only(top: 14),
              child: NearestCentersSection(controller: _centers!),
            ),
    );
  }
}

class _MapBrandBar extends StatelessWidget {
  const _MapBrandBar();

  @override
  Widget build(BuildContext context) => Positioned(
    top: 0,
    left: 0,
    right: 0,
    child: Material(
      color: AppColors.surface,
      elevation: 2,
      child: SafeArea(
        bottom: false,
        child: SizedBox(
          height: 58,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.waves, color: Colors.white),
                ),
                const SizedBox(width: 10),
                const Text(
                  'FloodSense',
                  style: TextStyle(
                    color: AppColors.primary,
                    fontSize: 21,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class _ScenarioChip extends StatelessWidget {
  const _ScenarioChip({required this.assessment, required this.onTap});

  final AssessmentController assessment;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final intensity = assessment.selectedIntensity?.label;
    final duration = assessment.selectedDuration?.label;
    final label = intensity == null || duration == null
        ? 'Choose planning scenario'
        : '$intensity rainfall · $duration';
    return Material(
      color: AppColors.surface,
      elevation: 3,
      borderRadius: BorderRadius.circular(24),
      child: InkWell(
        key: const Key('map-scenario-chip'),
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                intensity == null ? Icons.tune : Icons.water_drop,
                color: AppColors.primary,
                size: 20,
              ),
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 220),
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(width: 4),
              const Icon(Icons.keyboard_arrow_down, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

class _SheetHandle extends StatelessWidget {
  const _SheetHandle({
    required this.onCollapse,
    required this.onVerticalDragUpdate,
  });

  final VoidCallback onCollapse;
  final GestureDragUpdateCallback onVerticalDragUpdate;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Drag to resize the information panel',
      child: GestureDetector(
        key: const Key('resident-sheet-handle'),
        behavior: HitTestBehavior.opaque,
        onVerticalDragUpdate: onVerticalDragUpdate,
        child: SizedBox(
          height: 48,
          child: Stack(
            alignment: Alignment.center,
            children: [
              Container(
                width: 48,
                height: 5,
                decoration: BoxDecoration(
                  color: AppColors.secondaryText,
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
              Positioned(
                right: 12,
                child: IconButton(
                  key: const Key('resident-sheet-collapse-button'),
                  tooltip: 'Hide information panel',
                  onPressed: onCollapse,
                  icon: const Icon(
                    Icons.keyboard_arrow_down_rounded,
                    color: AppColors.secondaryText,
                    size: 26,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CollapsedSheetTab extends StatelessWidget {
  const _CollapsedSheetTab({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    key: const Key('resident-sheet-expand-tab'),
    color: AppColors.surface,
    elevation: 10,
    borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: onTap,
      child: Semantics(
        button: true,
        label: 'Expand information panel',
        child: const SizedBox(
          width: 78,
          height: 52,
          child: Icon(
            Icons.keyboard_arrow_up_rounded,
            color: AppColors.bodyText,
            size: 32,
          ),
        ),
      ),
    ),
  );
}

class _RoundIcon extends StatelessWidget {
  const _RoundIcon({required this.icon, required this.color});

  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    width: 48,
    height: 48,
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.12),
      shape: BoxShape.circle,
    ),
    child: Icon(icon, color: color),
  );
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.label, required this.ready});

  final String label;
  final bool ready;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
    decoration: BoxDecoration(
      color: ready ? AppColors.activeBackground : AppColors.pageBackground,
      borderRadius: BorderRadius.circular(20),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          ready ? Icons.check_circle : Icons.info_outline,
          size: 16,
          color: ready ? AppColors.low : AppColors.secondaryText,
        ),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    ),
  );
}

class _PlanningNotice extends StatelessWidget {
  const _PlanningNotice({
    this.text = 'Planning scenario only—not a live warning.',
  });

  final String text;

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    label: text,
    child: Container(
      key: const Key('planning-only-notice'),
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: const Color(0xFFE1F2FC),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info, size: 19, color: AppColors.primary),
          const SizedBox(width: 8),
          Expanded(child: Text(text)),
        ],
      ),
    ),
  );
}

class _StepHeading extends StatelessWidget {
  const _StepHeading({
    required this.icon,
    required this.title,
    required this.step,
    required this.description,
  });

  final IconData icon;
  final String title;
  final String step;
  final String description;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          _RoundIcon(icon: icon, color: AppColors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleLarge),
                Text(step, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ],
      ),
      const SizedBox(height: 10),
      Text(description),
    ],
  );
}

class _NavigationButtons extends StatelessWidget {
  const _NavigationButtons({
    required this.backKey,
    required this.continueKey,
    required this.onBack,
    required this.onContinue,
    required this.continueLabel,
  });

  final Key backKey;
  final Key continueKey;
  final VoidCallback onBack;
  final VoidCallback? onContinue;
  final String continueLabel;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: OutlinedButton(
          key: backKey,
          onPressed: onBack,
          child: const Text('Back'),
        ),
      ),
      const SizedBox(width: 10),
      Expanded(
        child: FilledButton(
          key: continueKey,
          onPressed: onContinue,
          child: Text(continueLabel),
        ),
      ),
    ],
  );
}

class _ReviewTile extends StatelessWidget {
  const _ReviewTile({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: const Icon(Icons.check_circle_outline, color: AppColors.low),
      title: Text(label),
      subtitle: Text(value),
    ),
  );
}

class _ResultSummary extends StatelessWidget {
  const _ResultSummary({
    required this.result,
    required this.intensity,
    required this.duration,
    required this.onPrepare,
    required this.onRestart,
  });

  final AssessmentResult result;
  final String intensity;
  final String duration;
  final VoidCallback? onPrepare;
  final VoidCallback onRestart;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(result.area.name, style: Theme.of(context).textTheme.bodySmall),
      Text(
        'Assessment result',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 10),
      if (result.isClassified)
        _SusceptibilityBanner(
          result: result,
          intensity: intensity,
          duration: duration,
        )
      else
        Card(
          child: ListTile(
            leading: const Icon(
              Icons.info_outline,
              color: AppColors.limitation,
            ),
            title: Text(_limitationTitle(result.state)),
            subtitle: Text(result.explanation.summary),
          ),
        ),
      const SizedBox(height: 10),
      const _PlanningNotice(
        text: 'Scenario-based result—not a live warning or safety guarantee.',
      ),
      const SizedBox(height: 10),
      Card(
        child: Column(
          children: [
            ExpansionTile(
              leading: const Icon(Icons.article_outlined),
              title: const Text('Why this result?'),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: Text(result.explanation.summary),
                ),
              ],
            ),
            ExpansionTile(
              leading: const Icon(Icons.account_tree_outlined),
              title: const Text('Matched rule summary'),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: Text(
                    result.matchedRuleCodes.isEmpty
                        ? 'No eligible stored rule was reported.'
                        : result.matchedRuleCodes.join(', '),
                  ),
                ),
              ],
            ),
            ExpansionTile(
              leading: const Icon(Icons.menu_book_outlined),
              title: const Text('Sources & version'),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: Text(
                    'Rule set: ${result.ruleset == null ? 'Not available' : '${result.ruleset!.name} v${result.ruleset!.version}'}\n'
                    'Data status: ${result.dataStatus}\n'
                    'Operating mode: ${result.operatingMode}',
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
      const SizedBox(height: 12),
      if (onPrepare != null)
        FilledButton.icon(
          key: const Key('result-view-preparedness'),
          onPressed: onPrepare,
          icon: const Icon(Icons.shield_outlined),
          label: const Text('View Preparedness'),
        )
      else
        OutlinedButton(
          onPressed: onRestart,
          child: const Text('Review another scenario'),
        ),
    ],
  );
}

class _SusceptibilityBanner extends StatelessWidget {
  const _SusceptibilityBanner({
    required this.result,
    required this.intensity,
    required this.duration,
  });

  final AssessmentResult result;
  final String intensity;
  final String duration;

  @override
  Widget build(BuildContext context) {
    final susceptibility = result.susceptibility!;
    final color = Color(susceptibility.colorValue);
    return Semantics(
      container: true,
      label: '${susceptibility.label} susceptibility for $intensity, $duration',
      child: Container(
        key: const Key('hybrid-result-banner'),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          border: Border.all(color: color),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            CircleAvatar(
              backgroundColor: color,
              foregroundColor: Colors.white,
              child: const Icon(Icons.warning_amber_rounded),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${susceptibility.label} susceptibility',
                    style: TextStyle(
                      color: color,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text('$intensity rainfall · $duration'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _limitationTitle(AssessmentState state) => switch (state) {
  AssessmentState.uncertain => 'Uncertain result',
  AssessmentState.insufficientData => 'Insufficient data',
  _ => 'Result unavailable',
};

class AccountScreen extends StatelessWidget {
  const AccountScreen({required this.session, required this.api, super.key});
  final SessionController session;
  final FloodSenseApi api;

  Future<String?> _password(BuildContext context, String title) async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Current password'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Continue'),
          ),
        ],
      ),
    );
    controller.dispose();
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final user = session.user!;
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'FloodSense',
          style: TextStyle(
            color: AppColors.primary,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      body: ListView(
        key: const Key('profile-secondary-options'),
        padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
        children: [
          Text('Profile', style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 14),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  const CircleAvatar(
                    radius: 28,
                    backgroundColor: Color(0xFFE7EDF5),
                    child: Icon(
                      Icons.person,
                      size: 34,
                      color: AppColors.secondaryText,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          user.username ?? 'Resident account',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          user.email,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(
                              user.emailVerified
                                  ? Icons.verified
                                  : Icons.warning_amber,
                              size: 16,
                              color: user.emailVerified
                                  ? AppColors.low
                                  : AppColors.high,
                            ),
                            const SizedBox(width: 5),
                            const Expanded(
                              child: Text(
                                'Verified email address',
                                style: TextStyle(fontSize: 12),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.edit_outlined),
                    tooltip: 'Edit username',
                    onPressed: () => _editUsername(context),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          const _ProfileSectionLabel('Preferences'),
          _ProfileGroup(
            children: [
              ListTile(
                key: const Key('profile-preferences'),
                leading: const Icon(Icons.home_outlined),
                title: const Text('Preferences'),
                subtitle: const Text(
                  'Home barangay, default scenario, and accessibility',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => PreferencesScreen(
                      repository: session.repository,
                      api: api,
                    ),
                  ),
                ),
              ),
              const ListTile(
                leading: Icon(Icons.notifications_off_outlined),
                title: Text('Notifications'),
                subtitle: Text(
                  'Live alerts are not enabled in this scenario-based prototype',
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          const _ProfileSectionLabel('About & support'),
          _ProfileGroup(
            children: [
              ListTile(
                leading: const Icon(Icons.description_outlined),
                title: const Text('Data & methodology'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _methodology(context),
              ),
              ListTile(
                leading: const Icon(Icons.gavel_outlined),
                title: const Text('Terms of Use'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _legal(context, 'terms'),
              ),
              ListTile(
                leading: const Icon(Icons.privacy_tip_outlined),
                title: const Text('Privacy Policy'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _legal(context, 'privacy'),
              ),
              ListTile(
                leading: const Icon(Icons.help_outline),
                title: const Text('Help & onboarding'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => OnboardingScreen(controller: session),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          const _ProfileSectionLabel('Account security'),
          _ProfileGroup(
            children: [
              if (user.passwordLoginAvailable)
                ListTile(
                  leading: const Icon(Icons.password),
                  title: const Text('Change password'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _changePassword(context),
                ),
              if (user.linkedProviders.contains('GOOGLE'))
                ListTile(
                  leading: const Icon(Icons.link_off),
                  title: const Text('Unlink Google'),
                  subtitle: const Text('Password reauthentication required'),
                  onTap: () async {
                    final password = await _password(context, 'Unlink Google');
                    if (password != null) await session.unlinkGoogle(password);
                  },
                )
              else if (user.passwordLoginAvailable)
                ListTile(
                  leading: const Icon(Icons.add_link),
                  title: const Text('Link Google'),
                  subtitle: const Text(
                    'Password and Google reauthentication required',
                  ),
                  onTap: () async {
                    final password = await _password(context, 'Link Google');
                    if (password != null) await session.linkGoogle(password);
                  },
                ),
              ListTile(
                leading: const Icon(Icons.delete_outline),
                title: const Text('Delete account'),
                subtitle: const Text(
                  'Permanent after a 30-day recovery period',
                ),
                onTap: () => _scheduleDeletion(context),
              ),
            ],
          ),
          const SizedBox(height: 18),
          OutlinedButton.icon(
            key: const Key('profile-logout'),
            onPressed: session.busy ? null : session.logout,
            icon: const Icon(Icons.logout),
            label: const Text('Log out'),
          ),
          if (session.message != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Text(
                session.message!,
                style: const TextStyle(color: AppColors.error),
              ),
            ),
        ],
      ),
    );
  }

  void _methodology(BuildContext context) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => Scaffold(
        appBar: AppBar(title: const Text('Data & methodology')),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: const [
            Text(
              'How FloodSense works',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
            ),
            SizedBox(height: 12),
            Text(
              'FloodSense evaluates a user-confirmed hypothetical rainfall scenario and supported area using a fixed deterministic inference method and eligible stored knowledge.',
            ),
            SizedBox(height: 12),
            Text(
              'The OpenStreetMap layer provides geographic context. Administrative boundaries do not assign susceptibility by themselves. Every result must retain its data status, limitations, rule-set version, and source context.',
            ),
            SizedBox(height: 12),
            Text(
              'The application does not continuously monitor rainfall, generate live warnings, guarantee safety, or issue evacuation orders.',
            ),
          ],
        ),
      ),
    ),
  );

  void _legal(BuildContext context, String type) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => LegalDocumentScreen(
        repository: session.repository,
        type: type,
        originLabel: 'Account',
      ),
    ),
  );

  Future<void> _editUsername(BuildContext context) async {
    final input = TextEditingController(text: session.user?.username ?? '');
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit username'),
        content: TextField(
          controller: input,
          decoration: const InputDecoration(labelText: 'Username'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, input.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    input.dispose();
    if (value != null) await session.updateUsername(value);
  }

  Future<void> _changePassword(BuildContext context) async {
    final current = TextEditingController();
    final replacement = TextEditingController();
    final values = await showDialog<List<String>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Change password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: current,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Current password'),
            ),
            TextField(
              controller: replacement,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'New password'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, [current.text, replacement.text]),
            child: const Text('Change'),
          ),
        ],
      ),
    );
    current.dispose();
    replacement.dispose();
    if (values != null) {
      try {
        await session.repository.changePassword(values[0], values[1]);
      } on ResidentAuthException catch (error) {
        session.message = error.message;
      }
    }
  }

  Future<void> _scheduleDeletion(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: const Icon(
          Icons.warning_amber_rounded,
          color: AppColors.high,
          size: 42,
        ),
        title: const Text('Delete your account?'),
        content: const Text(
          'Your account will be scheduled for permanent deletion in 30 days. '
          'You will be signed out now. Signing in again during those 30 days '
          'automatically cancels the deletion.',
          textAlign: TextAlign.center,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(backgroundColor: AppColors.high),
            child: const Text('Delete my account'),
          ),
        ],
      ),
    );
    if (!(confirmed ?? false)) return;
    final scheduled = await session.scheduleAccountDeletion();
    if (scheduled) await session.logout();
  }
}

class _ProfileSectionLabel extends StatelessWidget {
  const _ProfileSectionLabel(this.label);

  final String label;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(left: 4, bottom: 8),
    child: Text(
      label,
      style: const TextStyle(
        color: AppColors.secondaryText,
        fontWeight: FontWeight.w800,
      ),
    ),
  );
}

class _ProfileGroup extends StatelessWidget {
  const _ProfileGroup({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Card(
    child: Column(
      children: [
        for (var index = 0; index < children.length; index++) ...[
          children[index],
          if (index != children.length - 1)
            const Divider(height: 1, indent: 56),
        ],
      ],
    ),
  );
}

class PreferencesScreen extends StatefulWidget {
  const PreferencesScreen({
    required this.repository,
    required this.api,
    super.key,
  });
  final ResidentAuthRepository repository;
  final FloodSenseApi api;
  @override
  State<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends State<PreferencesScreen> {
  List<GeographicArea> _barangays = const [];
  List<ScenarioOption> _intensities = const [];
  List<ScenarioOption> _durations = const [];
  int? _barangayId;
  int? _intensityId;
  int? _durationId;
  bool _highContrast = false;
  bool _reduceMotion = false;
  bool _loading = true;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final values = await Future.wait([
        widget.repository.preferences(),
        widget.api.fetchAssessmentOptions(),
        widget.api.fetchReferenceBoundaries(),
      ]);
      final preferences = values[0] as Map<String, dynamic>;
      final options = values[1] as AssessmentOptions;
      _barangays = (values[2] as List<GeographicArea>)
          .where((area) => area.areaType == 'BARANGAY')
          .toList();
      _intensities = options.intensityOptions;
      _durations = options.durationOptions;
      _barangayId = (preferences['home_barangay'] as Map?)?['id'] as int?;
      _intensityId =
          (preferences['default_rainfall_intensity'] as Map?)?['id'] as int?;
      _durationId =
          (preferences['default_rainfall_duration'] as Map?)?['id'] as int?;
      _highContrast = preferences['high_contrast'] as bool? ?? false;
      _reduceMotion = preferences['reduce_motion'] as bool? ?? false;
    } catch (error) {
      _message = '$error';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Preferences')),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Text(
                'Preferences never store exact GPS coordinates and never run an assessment automatically.',
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<int?>(
                key: ValueKey('barangay-$_barangayId'),
                initialValue: _barangays.any((item) => item.id == _barangayId)
                    ? _barangayId
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Home barangay (optional)',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: null,
                    child: Text('No default'),
                  ),
                  ..._barangays.map(
                    (item) => DropdownMenuItem(
                      value: item.id,
                      child: Text(item.name),
                    ),
                  ),
                ],
                onChanged: (value) => setState(() => _barangayId = value),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<int?>(
                key: ValueKey('intensity-$_intensityId'),
                initialValue:
                    _intensities.any((item) => item.id == _intensityId)
                    ? _intensityId
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Default hypothetical intensity',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: null,
                    child: Text('No default'),
                  ),
                  ..._intensities.map(
                    (item) => DropdownMenuItem(
                      value: item.id,
                      child: Text(item.label),
                    ),
                  ),
                ],
                onChanged: (value) => setState(() => _intensityId = value),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<int?>(
                key: ValueKey('duration-$_durationId'),
                initialValue: _durations.any((item) => item.id == _durationId)
                    ? _durationId
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Default hypothetical duration',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: null,
                    child: Text('No default'),
                  ),
                  ..._durations.map(
                    (item) => DropdownMenuItem(
                      value: item.id,
                      child: Text(item.label),
                    ),
                  ),
                ],
                onChanged: (value) => setState(() => _durationId = value),
              ),
              SwitchListTile(
                value: _highContrast,
                onChanged: (value) => setState(() => _highContrast = value),
                title: const Text('High contrast'),
              ),
              SwitchListTile(
                value: _reduceMotion,
                onChanged: (value) => setState(() => _reduceMotion = value),
                title: const Text('Reduce motion'),
              ),
              FilledButton(
                onPressed: _save,
                child: const Text('Save Preferences'),
              ),
              if (_message != null)
                Semantics(liveRegion: true, child: Text(_message!)),
            ],
          ),
  );

  Future<void> _save() async {
    try {
      await widget.repository.updatePreferences({
        'home_barangay_id': _barangayId,
        'default_rainfall_intensity_id': _intensityId,
        'default_rainfall_duration_id': _durationId,
        'high_contrast': _highContrast,
        'reduce_motion': _reduceMotion,
      });
      _message = 'Preferences saved. No assessment was run.';
    } on ResidentAuthException catch (error) {
      _message = error.message;
    }
    if (mounted) setState(() {});
  }
}
