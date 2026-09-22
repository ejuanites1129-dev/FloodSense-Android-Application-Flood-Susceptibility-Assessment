import 'package:flutter/material.dart';

import 'dss_controller.dart';

class DssFlowView extends StatefulWidget {
  const DssFlowView({
    required this.controller,
    required this.susceptibilityCode,
    super.key,
  });
  final DssController controller;
  final String susceptibilityCode;
  @override
  State<DssFlowView> createState() => _DssFlowViewState();
}

class _DssFlowViewState extends State<DssFlowView> {
  @override
  void initState() {
    super.initState();
    if (widget.controller.susceptibilityCode != widget.susceptibilityCode ||
        widget.controller.current == null) {
      widget.controller.start(widget.susceptibilityCode);
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.controller,
    builder: (context, _) {
      final step = widget.controller.current;
      if (widget.controller.busy && step == null) {
        return const Center(
          child: CircularProgressIndicator(
            semanticsLabel: 'Loading structured guidance',
          ),
        );
      }
      if (widget.controller.error != null && step == null) {
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(widget.controller.error!),
              FilledButton(
                onPressed: widget.controller.restart,
                child: const Text('Try again'),
              ),
            ],
          ),
        );
      }
      if (step == null) {
        return const Text(
          'Structured guidance is not available for this result.',
        );
      }
      return ListView(
        key: const Key('dss-flow-view'),
        padding: const EdgeInsets.all(16),
        children: [
          Text(step.title, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: step.isOutcome
                ? 1
                : step.position / step.total.clamp(1, 1000),
            semanticsLabel: 'Decision support progress',
          ),
          const SizedBox(height: 8),
          Text('${step.dataStatus} • Deterministic decision support'),
          const SizedBox(height: 12),
          Card(
            color: const Color(0xFFFFF4CE),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text(step.warning),
            ),
          ),
          const SizedBox(height: 12),
          if (step.question case final question?) ...[
            Text(
              question.prompt,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (question.explanation.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(question.explanation),
              ),
            const SizedBox(height: 12),
            RadioGroup<String>(
              groupValue: widget.controller.selectedOptionCode,
              onChanged: (value) {
                if (value != null) {
                  widget.controller.select(value);
                }
              },
              child: Column(
                children: [
                  for (final option in question.options)
                    Card(
                      child: RadioListTile<String>(
                        key: Key('dss-option-${option.code}'),
                        value: option.code,
                        title: Text(option.label),
                        subtitle: option.supportingText.isEmpty
                            ? null
                            : Text(option.supportingText),
                      ),
                    ),
                ],
              ),
            ),
            if (widget.controller.error != null)
              Text(
                widget.controller.error!,
                style: const TextStyle(color: Colors.red),
              ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: widget.controller.canGoBack
                        ? widget.controller.goBack
                        : null,
                    child: const Text('Back'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed:
                        widget.controller.selectedOptionCode == null ||
                            widget.controller.busy
                        ? null
                        : widget.controller.continueFlow,
                    child: const Text('Continue'),
                  ),
                ),
              ],
            ),
          ] else if (step.outcome case final outcome?) ...[
            Text(outcome.title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 10),
            Text(outcome.instruction),
            const SizedBox(height: 12),
            Text(
              outcome.warning,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text('Source: ${outcome.source}'),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: widget.controller.goBack,
                    child: const Text('Back'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton(
                    onPressed: widget.controller.restart,
                    child: const Text('Restart'),
                  ),
                ),
              ],
            ),
          ],
          TextButton.icon(
            onPressed: widget.controller.restart,
            icon: const Icon(Icons.restart_alt),
            label: const Text('Exit and restart guidance'),
          ),
        ],
      );
    },
  );
}
