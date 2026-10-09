import 'package:flutter/material.dart';

import '../../app/widgets/measured_scroll_view.dart';
import '../../data/dss/structured_dss_repository.dart';
import '../../data/models/guidance_item.dart';
import '../profile/data_sources_screen.dart';
import 'dss_assessment_context.dart';
import 'dss_controller.dart';
import 'dss_flow_view.dart';

/// Answer-first presentation of eligible API content, not a new inference rule.
/// Household branches remain optional and use the existing versioned contract.
class PreparednessDashboard extends StatefulWidget {
  const PreparednessDashboard({
    required this.controller,
    required this.assessmentContext,
    required this.guidance,
    this.resources,
    this.scrollController,
    this.onContentHeightChanged,
    this.padding = const EdgeInsets.all(16),
    super.key,
  });

  final DssController controller;
  final DssAssessmentContext assessmentContext;
  final List<GuidanceItem> guidance;
  final Widget? resources;
  final ScrollController? scrollController;
  final ValueChanged<double>? onContentHeightChanged;
  final EdgeInsetsGeometry padding;

  @override
  State<PreparednessDashboard> createState() => _PreparednessDashboardState();
}

class _PreparednessDashboardState extends State<PreparednessDashboard> {
  final _localScrollController = ScrollController();
  bool _lastHouseholdOpen = false;
  ScrollController get _scrollController =>
      widget.scrollController ?? _localScrollController;

  @override
  void initState() {
    super.initState();
    _lastHouseholdOpen = widget.controller.householdCheckOpen;
    widget.controller.addListener(_onControllerChanged);
    _startIfNeeded();
  }

  @override
  void didUpdateWidget(PreparednessDashboard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_onControllerChanged);
      _lastHouseholdOpen = widget.controller.householdCheckOpen;
      widget.controller.addListener(_onControllerChanged);
    }
    if (oldWidget.controller != widget.controller ||
        oldWidget.assessmentContext != widget.assessmentContext) {
      _startIfNeeded();
      _returnToTop();
    }
  }

  void _onControllerChanged() {
    final open = widget.controller.householdCheckOpen;
    if (open == _lastHouseholdOpen) return;
    _lastHouseholdOpen = open;
    _returnToTop();
  }

  void _startIfNeeded() {
    final controller = widget.controller;
    if (controller.assessmentContext != widget.assessmentContext ||
        (controller.current == null &&
            !controller.busy &&
            controller.error == null)) {
      controller.start(widget.assessmentContext);
    }
  }

  void _returnToTop() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scrollController.hasClients) _scrollController.jumpTo(0);
    });
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _localScrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) {
      final controller = widget.controller;
      // Never expose a previous scenario's guidance while a new request loads.
      final sameScenario =
          controller.assessmentContext == widget.assessmentContext;
      final overview = sameScenario ? controller.overview : null;
      if (sameScenario &&
          controller.householdCheckOpen &&
          controller.current != null) {
        return DssFlowView(
          controller: controller,
          assessmentContext: widget.assessmentContext,
          householdOnly: true,
          scrollController: _scrollController,
          onContentHeightChanged: widget.onContentHeightChanged,
          padding: widget.padding,
        );
      }
      final before =
          overview?.contentBlocks
              .where(
                (block) =>
                    block.contentType == 'HOUSEHOLD_ACTION' &&
                    (block.phase == 'BEFORE' || block.phase == 'ALWAYS'),
              )
              .toList() ??
          <DssContentBlock>[];
      final basics = List<GuidanceItem>.of(widget.guidance)
        ..sort((a, b) {
          final order = a.displayOrder.compareTo(b.displayOrder);
          return order == 0 ? a.id.compareTo(b.id) : order;
        });
      final children = <Widget>[
        Text('Preparedness', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 10),
        _scenarioSummary(),
        const SizedBox(height: 10),
        const Text(
          'Planning scenario—not a live warning or evacuation order. '
          'Follow official local instructions.',
        ),
        const SizedBox(height: 18),
        Text(
          'Your preparation priorities',
          key: const Key('prepare-priorities'),
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 6),
        if (before.isNotEmpty)
          for (var i = 0; i < before.take(3).length; i++)
            _action(
              before[i].title,
              before[i].body,
              i + 1,
              details: DssProvenance(
                source: before[i].source,
                sourceLocator: before[i].sourceLocator,
                attribution: before[i].attribution,
                limitations: before[i].limitations,
                effectiveDate: before[i].effectiveDate,
                reviewedOn: before[i].reviewedOn,
                expiresOn: before[i].expiresOn,
              ),
            ),
        if (before.isEmpty)
          for (var i = 0; i < basics.take(3).length; i++)
            _action(
              basics[i].title,
              basics[i].instruction,
              i + 1,
              details: Text(
                'Guidance status: ${_status(basics[i].dataStatus)}',
              ),
            ),
        if (before.isEmpty && basics.isEmpty)
          const Text(
            'No eligible preparation actions are available for this result. '
            'Your susceptibility result is unchanged.',
          ),
        const SizedBox(height: 12),
        if (overview != null)
          Text(
            'Guidance: ${_status(overview.dataStatus)}',
            key: const Key('prepare-guidance-status'),
          ),
        if (sameScenario)
          if (controller.current?.outcome case final outcome?)
            if (controller.answers.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                'Your household recommendation',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(
                outcome.title,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              Text(outcome.instruction),
              if (outcome.warning.isNotEmpty) Text(outcome.warning),
            ],
        const SizedBox(height: 8),
        if (sameScenario && controller.current != null)
          OutlinedButton.icon(
            key: const Key('prepare-tailor-household'),
            onPressed: controller.busy
                ? null
                : () {
                    controller.openHouseholdCheck();
                    _returnToTop();
                  },
            icon: const Icon(Icons.tune),
            label: Text(
              controller.answers.isEmpty
                  ? 'Tailor for my household · Optional'
                  : 'Resume household check / view answers',
            ),
          )
        else if (controller.busy)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('Loading optional household check…'),
          )
        else ...[
          Text(
            controller.error ?? 'The optional household check is unavailable.',
            key: const Key('prepare-household-unavailable'),
          ),
          TextButton(
            onPressed: controller.restart,
            child: const Text('Retry household check'),
          ),
        ],
        if (before.length > 3 || (before.isEmpty && basics.length > 3))
          ExpansionTile(
            key: const Key('prepare-more-actions'),
            title: const Text('All preparation actions'),
            children: [
              if (before.isNotEmpty)
                for (final block in before.skip(3))
                  DssContentCard(block: block, showProvenance: true),
              if (before.isEmpty)
                for (var i = 3; i < basics.length; i++)
                  _action(basics[i].title, basics[i].instruction, i + 1),
            ],
          ),
        const SizedBox(height: 12),
        ?widget.resources,
        if (overview != null) ..._references(overview),
        ExpansionTile(
          key: const Key('prepare-sources-details'),
          title: const Text('Sources and limitations'),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          expandedCrossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(dssScenarioDisclaimer),
            const SizedBox(height: 12),
            Text('Assessment mode: ${widget.assessmentContext.operatingMode}'),
            if (widget.assessmentContext.rulesetName.isNotEmpty)
              Text(
                'Assessment knowledge version: '
                '${widget.assessmentContext.rulesetName} '
                '${widget.assessmentContext.rulesetVersion}',
              ),
            if (overview != null) ...[
              const SizedBox(height: 12),
              Text(
                'Household guide: ${overview.title} • '
                '${overview.flowCode} ${overview.flowVersion}',
              ),
              if (overview.warning.isNotEmpty &&
                  overview.warning != dssScenarioDisclaimer)
                Text(overview.warning),
              DssProvenance(
                source: overview.source,
                sourceLocator: overview.sourceLocator,
                attribution: overview.attribution,
                limitations: overview.limitations,
                effectiveDate: overview.effectiveDate,
                reviewedOn: overview.reviewedOn,
                expiresOn: overview.expiresOn,
              ),
            ],
            TextButton.icon(
              key: const Key('prepare-data-sources'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const DataSourcesScreen(),
                ),
              ),
              icon: const Icon(Icons.source_outlined),
              label: const Text('View app Data Sources'),
            ),
          ],
        ),
      ];
      if (widget.onContentHeightChanged case final onHeightChanged?) {
        return MeasuredScrollView(
          key: const Key('prepare-dashboard'),
          controller: _scrollController,
          padding: widget.padding,
          onHeightChanged: onHeightChanged,
          children: children,
        );
      }
      return SingleChildScrollView(
        key: const Key('prepare-dashboard'),
        controller: _scrollController,
        padding: widget.padding,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: children,
        ),
      );
    },
  );

  Widget _scenarioSummary() {
    final scenario = widget.assessmentContext;
    return Card(
      key: const Key('prepare-scenario-summary'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '${scenario.areaName} • ${scenario.susceptibilityLabel} susceptibility',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              '${scenario.intensityLabel} rainfall scenario · ${scenario.durationLabel}',
            ),
            Text(
              scenario.operatingMode == 'DEMONSTRATION'
                  ? 'Demonstration — pending validation'
                  : 'Assessment data: ${_status(scenario.dataStatus)}',
            ),
          ],
        ),
      ),
    );
  }

  Widget _action(String title, String body, int number, {Widget? details}) =>
      Card(
        key: Key('prepare-action-$number'),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '$number. $title',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 4),
              Text(body),
              if (details != null)
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Details and source'),
                  children: [details],
                ),
            ],
          ),
        ),
      );

  List<Widget> _references(DssStep overview) {
    final groups = <(String, String, String?)>[
      ('SCENARIO_EXPLANATION', 'What this scenario may mean', null),
      (
        'HOUSEHOLD_ACTION',
        'During / after a flood — educational reference',
        'Reference only; this does not indicate a flood is occurring or has ended.',
      ),
      ('OFFICIAL_CHANNEL', 'Official information channels', null),
      (
        'AUTHORITY_ACTIVITY',
        'What local authorities may coordinate',
        'Confirm activities and availability with the responsible authority.',
      ),
      (
        'RISK_REFERENCE',
        'Risk and alert reference',
        'Susceptibility and official warning colors are separate systems.',
      ),
      (
        'MONITORING_REFERENCE',
        'What local responders monitor',
        'FloodSense does not monitor these sources live.',
      ),
    ];
    return [
      for (final (type, title, note) in groups)
        if (overview.contentBlocks.any(
          (block) =>
              block.contentType == type &&
              (type != 'HOUSEHOLD_ACTION' ||
                  {'DURING', 'AFTER'}.contains(block.phase)),
        ))
          ExpansionTile(
            key: Key('prepare-reference-$type'),
            title: Text(title),
            children: [
              if (note != null) Text(note),
              for (final block in overview.contentBlocks)
                if (block.contentType == type &&
                    (type != 'HOUSEHOLD_ACTION' ||
                        {'DURING', 'AFTER'}.contains(block.phase)))
                  DssContentCard(block: block, showProvenance: true),
            ],
          ),
    ];
  }

  String _status(String value) => value == 'DEMONSTRATION'
      ? 'Demonstration — pending expert validation'
      : value.replaceAll('_', ' ');
}
