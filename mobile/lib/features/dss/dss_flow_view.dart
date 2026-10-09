import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/widgets/measured_scroll_view.dart';
import '../../data/dss/structured_dss_repository.dart';
import '../profile/data_sources_screen.dart';
import 'dss_assessment_context.dart';
import 'dss_controller.dart';

const dssScenarioDisclaimer =
    'This is a hypothetical, scenario-based preparedness assessment. It is not a current flood warning, forecast, water-level observation, safety guarantee, or evacuation order. Follow PAGASA, Bacoor DRRMO, your barangay, and emergency services for official instructions.';

class DssFlowView extends StatefulWidget {
  const DssFlowView({
    required this.controller,
    required this.assessmentContext,
    this.scrollController,
    this.padding = const EdgeInsets.all(16),
    this.header,
    this.footer,
    this.onContentHeightChanged,
    this.householdOnly = false,
    super.key,
  });
  final DssController controller;
  final DssAssessmentContext assessmentContext;
  final ScrollController? scrollController;
  final EdgeInsetsGeometry padding;
  final Widget? header;
  final Widget? footer;
  final ValueChanged<double>? onContentHeightChanged;

  /// The optional household check has its own focused reading view.
  final bool householdOnly;
  @override
  State<DssFlowView> createState() => _DssFlowViewState();
}

class _DssFlowViewState extends State<DssFlowView> {
  @override
  void initState() {
    super.initState();
    _startIfNeeded();
  }

  @override
  void didUpdateWidget(DssFlowView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller ||
        oldWidget.assessmentContext != widget.assessmentContext) {
      _startIfNeeded();
    }
  }

  void _startIfNeeded() {
    if (widget.controller.assessmentContext != widget.assessmentContext ||
        (widget.controller.current == null &&
            !widget.controller.busy &&
            widget.controller.error == null)) {
      widget.controller.start(widget.assessmentContext);
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) {
      final step = widget.controller.current;
      if (widget.householdOnly && step != null) {
        return _focusedHouseholdCheck(step);
      }
      final children = <Widget>[
        ?widget.header,
        _ScenarioContextCard(assessment: widget.assessmentContext),
        const SizedBox(height: 12),
        const _Notice(dssScenarioDisclaimer),
        const SizedBox(height: 16),
      ];
      if (widget.controller.busy && step == null) {
        children.add(
          const Center(
            child: CircularProgressIndicator(
              semanticsLabel: 'Loading structured guidance',
            ),
          ),
        );
      } else if (step == null) {
        children.addAll([
          Semantics(
            liveRegion: true,
            child: Text(
              widget.controller.error ?? 'Published structured guidance is not available for this result.',
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'An unavailable guide does not change your scenario result.',
          ),
          FilledButton(
            onPressed: widget.controller.restart,
            child: const Text('Try again'),
          ),
          _dataSourcesButton(context),
        ]);
      } else {
        children.addAll([
          Text(step.title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('Guide ${step.flowCode} • Version ${step.flowVersion}'),
          Text('Guidance data status: ${_statusLabel(step.dataStatus)}'),
          if (step.warning.isNotEmpty &&
              step.warning.trim() != dssScenarioDisclaimer) ...[
            const SizedBox(height: 12),
            _Notice(step.warning),
          ],
          ..._contentSections(step),
          const SizedBox(height: 20),
          Text(
            'Household support check',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const Text(
            'Your answers help tailor preparedness guidance. They stay in memory and do not change susceptibility.',
          ),
          const SizedBox(height: 12),
          LinearProgressIndicator(
            value: step.isOutcome
                ? 1
                : (step.position / step.total.clamp(1, 1000)).clamp(0, 1),
            semanticsLabel: 'Decision support progress',
          ),
          const SizedBox(height: 12),
          if (step.question case final question?)
            ..._question(question)
          else if (step.outcome case final outcome?)
            ..._outcome(step, outcome),
          TextButton.icon(
            onPressed: widget.controller.busy
                ? null
                : widget.controller.restart,
            icon: const Icon(Icons.restart_alt),
            label: const Text('Exit and restart guidance'),
          ),
          ..._sources(step),
        ]);
      }
      if (widget.footer case final footer?) children.add(footer);
      if (widget.onContentHeightChanged case final onHeightChanged?) {
        return MeasuredScrollView(
          key: const Key('dss-flow-view'),
          controller: widget.scrollController,
          padding: widget.padding,
          onHeightChanged: onHeightChanged,
          children: children,
        );
      }
      return ListView(
        key: const Key('dss-flow-view'),
        controller: widget.scrollController,
        padding: widget.padding,
        children: children,
      );
    },
  );

  Widget _focusedHouseholdCheck(DssStep step) {
    final children = <Widget>[
      Text(
        'Household support check',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 6),
      Text(
        '${widget.assessmentContext.areaName} • '
        '${widget.assessmentContext.susceptibilityLabel} scenario',
      ),
      Text('Guidance: ${_statusLabel(step.dataStatus)}'),
      const SizedBox(height: 8),
      const Text(
        'Optional. Answers stay in memory and do not change susceptibility. '
        'This is not a live warning or evacuation order.',
      ),
      Align(
        alignment: Alignment.centerLeft,
        child: TextButton.icon(
          key: const Key('dss-close-household'),
          onPressed: () {
            widget.controller.closeHouseholdCheck();
            _showQuestionTop();
          },
          icon: const Icon(Icons.close),
          label: const Text('Close household check'),
        ),
      ),
      const SizedBox(height: 12),
      LinearProgressIndicator(
        value: step.isOutcome
            ? 1
            : (step.position / step.total.clamp(1, 1000)).clamp(0, 1),
        semanticsLabel: 'Decision support progress',
      ),
      const SizedBox(height: 16),
      if (step.question case final question?) ..._question(question),
      if (step.outcome case final outcome?) ..._outcome(step, outcome),
      if (!step.isOutcome)
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            key: const Key('dss-reset-answers'),
            onPressed: widget.controller.busy ? null : _resetAnswers,
            child: const Text('Reset answers'),
          ),
        ),
      ExpansionTile(
        key: const Key('dss-household-details'),
        title: const Text('Sources and limitations'),
        children: [
          const Text(dssScenarioDisclaimer),
          if (step.warning.isNotEmpty && step.warning != dssScenarioDisclaimer)
            _Notice(step.warning),
          ..._sources(step).skip(3),
        ],
      ),
    ];
    if (widget.onContentHeightChanged case final onHeightChanged?) {
      return MeasuredScrollView(
        key: const Key('dss-flow-view'),
        controller: widget.scrollController,
        padding: widget.padding,
        onHeightChanged: onHeightChanged,
        children: children,
      );
    }
    return SingleChildScrollView(
      key: const Key('dss-flow-view'),
      controller: widget.scrollController,
      padding: widget.padding,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    );
  }

  void _showQuestionTop() {
    if (!widget.householdOnly) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && widget.scrollController?.hasClients == true) {
        widget.scrollController!.jumpTo(0);
      }
    });
  }

  Future<void> _resetAnswers() async {
    await widget.controller.restart();
    _showQuestionTop();
  }

  List<Widget> _question(DssQuestion question) => [
    Text(question.prompt, style: Theme.of(context).textTheme.titleLarge),
    if (question.explanation.isNotEmpty)
      Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Text(question.explanation),
      ),
    const SizedBox(height: 12),
    RadioGroup<String>(
      groupValue: widget.controller.selectedOptionCode,
      onChanged: widget.controller.busy
          ? (_) {}
          : (value) {
              if (value != null) widget.controller.select(value);
            },
      child: Column(
        children: [
          for (final option in question.options)
            Card(
              child: RadioListTile<String>(
                key: Key('dss-option-${option.code}'),
                value: option.code,
                enabled: !widget.controller.busy,
                title: Text(option.label),
                subtitle: option.supportingText.isEmpty
                    ? null
                    : Text(option.supportingText),
              ),
            ),
        ],
      ),
    ),
    if (widget.controller.error case final error?)
      Semantics(liveRegion: true, child: Text(error)),
    const SizedBox(height: 12),
    _navigation(isOutcome: false),
  ];

  List<Widget> _outcome(DssStep step, DssOutcome outcome) => [
    Text(outcome.title, style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 10),
    // Preserve the compatible outcome without repeating an identical ordered block.
    if (outcome.instruction.isNotEmpty &&
        !step.contentBlocks.any(
          (block) => block.body.trim() == outcome.instruction.trim(),
        ))
      Text(outcome.instruction),
    if (outcome.warning.isNotEmpty && outcome.warning != step.warning) ...[
      const SizedBox(height: 12),
      Text(
        outcome.warning,
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ],
    for (final item in outcome.guidance)
      if (item.instruction.trim() != outcome.instruction.trim() &&
          !step.contentBlocks.any(
            (block) => block.body.trim() == item.instruction.trim(),
          ))
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  item.title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Text(item.instruction),
                Text('Guidance status: ${_statusLabel(item.dataStatus)}'),
                if (item.source.name.isNotEmpty)
                  Text('Source: ${item.source.label}'),
                if (item.attribution.isNotEmpty)
                  Text('Attribution: ${item.attribution}'),
              ],
            ),
          ),
        ),
    if (widget.controller.answers.isNotEmpty) ...[
      const SizedBox(height: 12),
      ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Your household support answers'),
        children: [
          for (final answer in widget.controller.answers)
            ListTile(
              title: Text(answer.question),
              subtitle: Text(
                [
                  answer.option.label,
                  answer.option.supportingText,
                ].where((text) => text.isNotEmpty).join(' — '),
              ),
            ),
        ],
      ),
    ],
    const SizedBox(height: 16),
    _navigation(isOutcome: true),
  ];

  Widget _navigation({required bool isOutcome}) => LayoutBuilder(
    builder: (context, constraints) {
      final back = OutlinedButton(
        onPressed: widget.controller.canGoBack && !widget.controller.busy
            ? () {
                widget.controller.goBack();
                _showQuestionTop();
              }
            : null,
        child: const Text('Back'),
      );
      final next = FilledButton(
        onPressed: widget.controller.busy
            ? null
            : isOutcome
            ? _resetAnswers
            : widget.controller.selectedOptionCode == null
            ? null
            : () async {
                await widget.controller.continueFlow();
                if (widget.controller.error == null) _showQuestionTop();
              },
        child: Text(
          widget.controller.busy
              ? 'Loading…'
              : isOutcome
              ? (widget.householdOnly ? 'Reset answers' : 'Restart')
              : 'Continue',
        ),
      );
      if (widget.householdOnly && !widget.controller.canGoBack) {
        return SizedBox(width: double.infinity, child: next);
      }
      if (constraints.maxWidth < 360 &&
          MediaQuery.textScalerOf(context).scale(16) > 22) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [back, const SizedBox(height: 8), next],
        );
      }
      return IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(child: back),
            const SizedBox(width: 12),
            Expanded(child: next),
          ],
        ),
      );
    },
  );

  List<Widget> _contentSections(DssStep step) {
    List<DssContentBlock> ofType(String type, {Set<String>? phases}) => step
        .contentBlocks
        .where(
          (block) =>
              block.contentType == type &&
              (phases == null || phases.contains(block.phase)),
        )
        .toList();
    final children = <Widget>[];
    void section(
      String title,
      List<DssContentBlock> blocks, {
      String? note,
      bool checklist = false,
    }) {
      if (blocks.isEmpty) return;
      children.addAll([
        const SizedBox(height: 18),
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        if (note != null) Text(note),
        const SizedBox(height: 8),
        for (var i = 0; i < blocks.length; i++)
          DssContentCard(block: blocks[i], ordinal: checklist ? i + 1 : null),
      ]);
    }

    section('What this scenario may mean', ofType('SCENARIO_EXPLANATION'));
    section(
      'What your household can prepare',
      ofType('HOUSEHOLD_ACTION', phases: {'BEFORE', 'ALWAYS'}),
      checklist: true,
      note: 'Before a flood • Preparedness checklist',
    );
    section(
      'During a flood — educational reference',
      ofType('HOUSEHOLD_ACTION', phases: {'DURING'}),
      note: 'This reference does not indicate that a flood is occurring.',
    );
    section(
      'After a flood — educational reference',
      ofType('HOUSEHOLD_ACTION', phases: {'AFTER'}),
      note: 'This reference does not indicate that an event has ended.',
    );
    section('Official information channels', ofType('OFFICIAL_CHANNEL'));
    section(
      'What local authorities may coordinate',
      ofType('AUTHORITY_ACTIVITY'),
      note: 'Educational reference; activities and availability must be confirmed with the responsible authorities.',
    );
    section(
      'Risk and alert reference',
      ofType('RISK_REFERENCE'),
      note: 'FloodSense susceptibility, BDRRMO alert stages, water-level markers, and PAGASA rainfall warnings are separate systems. Colors do not establish a mapping.',
    );
    final monitoring = ofType('MONITORING_REFERENCE');
    if (monitoring.isNotEmpty) {
      children.add(
        ExpansionTile(
          key: const Key('dss-monitoring-reference'),
          tilePadding: EdgeInsets.zero,
          title: const Text('What local responders monitor'),
          subtitle: const Text(
            'FloodSense does not monitor these sources live.',
          ),
          children: [
            for (final block in monitoring) DssContentCard(block: block),
          ],
        ),
      );
    }
    return children;
  }

  List<Widget> _sources(DssStep step) => [
    const SizedBox(height: 18),
    Text(
      'Sources and limitations',
      style: Theme.of(context).textTheme.titleLarge,
    ),
    const SizedBox(height: 8),
    DssProvenance(
      source: step.source,
      sourceLocator: step.sourceLocator,
      attribution: step.attribution,
      limitations: step.limitations,
      effectiveDate: step.effectiveDate,
      reviewedOn: step.reviewedOn,
      expiresOn: step.expiresOn,
    ),
    if (step.source.name.isEmpty && step.outcome?.source.isNotEmpty == true)
      Text('Source: ${step.outcome!.source}'),
    if (step.source.name.isEmpty && step.outcome?.source.isNotEmpty != true)
      const Text('Source details were not provided by this guide version.'),
    if (step.outcome case final outcome?) ...[
      if (outcome.sourceDetails.name.isNotEmpty)
        ExpansionTile(
          key: const Key('dss-outcome-source'),
          tilePadding: EdgeInsets.zero,
          title: Text('Outcome source for ${outcome.title}'),
          children: [DssProvenance(source: outcome.sourceDetails)],
        ),
      for (final item in outcome.guidance)
        if (item.source.name.isNotEmpty || item.attribution.isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text('Linked guidance source for ${item.title}'),
            children: [
              DssProvenance(source: item.source, attribution: item.attribution),
            ],
          ),
    ],
    for (final block in step.contentBlocks)
      ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: Text('Source for ${block.title}'),
        children: [
          DssProvenance(
            source: block.source,
            sourceLocator: block.sourceLocator,
            attribution: block.attribution,
            limitations: block.limitations,
            effectiveDate: block.effectiveDate,
            reviewedOn: block.reviewedOn,
            expiresOn: block.expiresOn,
          ),
        ],
      ),
    _dataSourcesButton(context),
  ];

  Widget _dataSourcesButton(BuildContext context) => TextButton.icon(
    key: const Key('dss-data-sources'),
    onPressed: () => Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => const DataSourcesScreen())),
    icon: const Icon(Icons.source_outlined),
    label: const Text('View app Data Sources'),
  );
}

String _statusLabel(String status) => status == 'DEMONSTRATION'
    ? 'Demonstration — pending expert validation'
    : status.replaceAll('_', ' ');

class _ScenarioContextCard extends StatelessWidget {
  const _ScenarioContextCard({required this.assessment});
  final DssAssessmentContext assessment;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Scenario-based susceptibility: ${assessment.susceptibilityLabel}',
            key: const Key('dss-scenario-susceptibility'),
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text('Hypothetical rainfall intensity: ${assessment.intensityLabel}'),
          Text('Selected duration: ${assessment.durationLabel}'),
          Text('Assessed location: ${assessment.areaName}'),
          Text(
            'Assessment data status: ${_statusLabel(assessment.dataStatus)}',
          ),
          Text('Assessment mode: ${assessment.operatingMode}'),
          if (assessment.rulesetName.isNotEmpty)
            Text(
              'Assessment knowledge version: ${assessment.rulesetName} ${assessment.rulesetVersion}',
            ),
        ],
      ),
    ),
  );
}

class _Notice extends StatelessWidget {
  const _Notice(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Card(
    color: const Color(0xFFFFF4CE),
    child: Padding(padding: const EdgeInsets.all(12), child: Text(text)),
  );
}

class DssContentCard extends StatelessWidget {
  const DssContentCard({
    required this.block,
    this.ordinal,
    this.showProvenance = false,
    super.key,
  });
  final DssContentBlock block;
  final int? ordinal;
  final bool showProvenance;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '${ordinal == null ? '' : '$ordinal. '}${block.title}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          Text(block.body),
          if (block.contentType == 'AUTHORITY_ACTIVITY')
            Text('Phase reference: ${block.phase.toLowerCase()}'),
          if (block.source.name.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'Source: ${block.source.label}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          if (block.limitations.isNotEmpty)
            Text('Limitations: ${block.limitations}'),
          if (block.publicUrl != null)
            TextButton.icon(
              onPressed: () => _showAddress(context),
              icon: const Icon(Icons.link),
              label: Text(
                block.contentType == 'OFFICIAL_CHANNEL'
                    ? 'Verified official channel address'
                    : 'Verified public source address',
              ),
            ),
          if (showProvenance)
            ExpansionTile(
              title: const Text('Full source details'),
              tilePadding: EdgeInsets.zero,
              children: [
                DssProvenance(
                  source: block.source,
                  sourceLocator: block.sourceLocator,
                  attribution: block.attribution,
                  limitations: block.limitations,
                  effectiveDate: block.effectiveDate,
                  reviewedOn: block.reviewedOn,
                  expiresOn: block.expiresOn,
                ),
              ],
            ),
        ],
      ),
    ),
  );
  Future<void> _showAddress(BuildContext context) => showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(block.title),
      content: SelectableText(block.publicUrl.toString()),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: () async {
            await Clipboard.setData(
              ClipboardData(text: block.publicUrl.toString()),
            );
            if (context.mounted) Navigator.pop(context);
          },
          child: const Text('Copy address'),
        ),
      ],
    ),
  );
}

class DssProvenance extends StatelessWidget {
  const DssProvenance({
    required this.source,
    this.sourceLocator = '',
    this.attribution = '',
    this.limitations = '',
    this.effectiveDate = '',
    this.reviewedOn = '',
    this.expiresOn = '',
    super.key,
  });
  final DssSource source;
  final String sourceLocator;
  final String attribution;
  final String limitations;
  final String effectiveDate;
  final String reviewedOn;
  final String expiresOn;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (source.name.isNotEmpty) Text('Source: ${source.label}'),
      if (source.version.isNotEmpty) Text('Source version: ${source.version}'),
      if (source.custodian.isNotEmpty) Text('Custodian: ${source.custodian}'),
      if (source.dataStatus.isNotEmpty)
        Text('Source status: ${_statusLabel(source.dataStatus)}'),
      if (source.referenceDate.isNotEmpty)
        Text('Reference date: ${source.referenceDate}'),
      if (source.reviewedOn.isNotEmpty)
        Text('Source review date: ${source.reviewedOn}'),
      if (source.limitations.isNotEmpty && source.limitations != limitations)
        Text('Source limitations: ${source.limitations}'),
      if (source.citationUrl != null)
        TextButton.icon(
          onPressed: () => showDialog<void>(
            context: context,
            builder: (context) => AlertDialog(
              title: Text(source.name),
              content: SelectableText(source.citationUrl.toString()),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Close'),
                ),
                FilledButton(
                  onPressed: () async {
                    await Clipboard.setData(
                      ClipboardData(text: source.citationUrl.toString()),
                    );
                    if (context.mounted) Navigator.pop(context);
                  },
                  child: const Text('Copy address'),
                ),
              ],
            ),
          ),
          icon: const Icon(Icons.link),
          label: const Text('Verified source and version address'),
        ),
      if (sourceLocator.isNotEmpty) Text('Source locator: $sourceLocator'),
      if (attribution.isNotEmpty) Text('Attribution: $attribution'),
      if (effectiveDate.isNotEmpty)
        Text('Effective/reference date: $effectiveDate'),
      if (reviewedOn.isNotEmpty) Text('Review date: $reviewedOn'),
      if (expiresOn.isNotEmpty) Text('Content expiry: $expiresOn'),
      if (limitations.isNotEmpty) Text('Limitations: $limitations'),
    ],
  );
}
