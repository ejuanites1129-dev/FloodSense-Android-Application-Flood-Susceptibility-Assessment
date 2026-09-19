import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import 'location_controller.dart';
import 'location_copy.dart';
import 'location_flow_state.dart';

class LocationCard extends StatelessWidget {
  const LocationCard({required this.controller, super.key});

  final LocationController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final state = controller.state;
        return Card(
          key: const Key('location-card'),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Optional device location',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 6),
                const Text(
                  'Use one temporary foreground reading, or continue with the map pin and selector.',
                ),
                const SizedBox(height: 12),
                if (state.phase == LocationFlowPhase.acquired)
                  _TemporaryLocationIndicator(controller: controller)
                else ...[
                  Semantics(
                    liveRegion: state.phase != LocationFlowPhase.initial,
                    child: Text(
                      state.message,
                      key: const Key('location-state-message'),
                    ),
                  ),
                  const SizedBox(height: 12),
                  _LocationActions(controller: controller),
                ],
                const SizedBox(height: 10),
                Text(
                  'GPS is optional. Manual pin placement and manual selection remain available below.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

Future<void> _showLocationPurpose(
  BuildContext context,
  LocationController controller,
) async {
  controller.showPurposeExplanation();
  final proceed = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (context) => AlertDialog(
      key: const Key('location-purpose-dialog'),
      title: const Text(LocationCopy.purposeTitle),
      content: const Text('${LocationCopy.purpose}\n\n${LocationCopy.privacy}'),
      actions: [
        TextButton(
          key: const Key('location-purpose-cancel'),
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Use manual selection'),
        ),
        FilledButton(
          key: const Key('location-purpose-continue'),
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Continue'),
        ),
      ],
    ),
  );
  if (proceed == true) {
    await controller.continueAfterPurposeExplanation();
  } else {
    await controller.cancel();
  }
}

class _LocationActions extends StatelessWidget {
  const _LocationActions({required this.controller});

  final LocationController controller;

  @override
  Widget build(BuildContext context) {
    final phase = controller.state.phase;
    if (phase == LocationFlowPhase.acquiring) {
      return Row(
        children: [
          const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 10),
          const Expanded(child: Text('Getting one temporary location...')),
          TextButton(
            key: const Key('location-cancel-button'),
            onPressed: controller.cancel,
            child: const Text('Cancel'),
          ),
        ],
      );
    }

    final actions = <Widget>[];
    if (phase == LocationFlowPhase.initial ||
        phase == LocationFlowPhase.cleared ||
        phase == LocationFlowPhase.cancelled) {
      actions.add(
        FilledButton.icon(
          key: const Key('use-my-location-button'),
          onPressed: () => _showLocationPurpose(context, controller),
          icon: const Icon(Icons.my_location),
          label: const Text('Use my location'),
        ),
      );
    }
    if (controller.state.retryAllowed) {
      actions.add(
        OutlinedButton.icon(
          key: const Key('location-retry-button'),
          onPressed: controller.retry,
          icon: const Icon(Icons.refresh),
          label: const Text('Try again'),
        ),
      );
    }
    if (phase == LocationFlowPhase.serviceDisabled) {
      actions.add(
        OutlinedButton(
          key: const Key('open-location-settings-button'),
          onPressed: controller.openLocationSettings,
          child: const Text('Open location settings'),
        ),
      );
    }
    if (phase == LocationFlowPhase.permissionDeniedPermanently) {
      actions.add(
        OutlinedButton(
          key: const Key('open-app-settings-button'),
          onPressed: controller.openAppSettings,
          child: const Text('Open app settings'),
        ),
      );
    }
    return Wrap(spacing: 8, runSpacing: 8, children: actions);
  }
}

class _TemporaryLocationIndicator extends StatelessWidget {
  const _TemporaryLocationIndicator({required this.controller});

  final LocationController controller;

  @override
  Widget build(BuildContext context) {
    final accuracy = controller.temporaryLocation!.accuracyMeters.round();
    return Semantics(
      container: true,
      liveRegion: true,
      label:
          'Temporary device location acquired. Reported accuracy about $accuracy meters.',
      child: Container(
        key: const Key('temporary-location-indicator'),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.activeBackground,
          border: Border.all(color: AppColors.primary),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Row(
              children: [
                Icon(Icons.location_on_outlined, color: AppColors.primary),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Temporary location acquired',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text('Android reported an accuracy of about $accuracy meters.'),
            const Text(
              'No barangay or susceptibility result has been assumed.',
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              key: const Key('clear-location-button'),
              onPressed: controller.clearLocation,
              icon: const Icon(Icons.location_off_outlined),
              label: const Text('Clear temporary location'),
            ),
          ],
        ),
      ),
    );
  }
}
