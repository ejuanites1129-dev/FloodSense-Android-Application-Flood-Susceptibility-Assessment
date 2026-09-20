import 'dart:async';

import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/models/barangay_resolution.dart';
import '../../data/models/geographic_area.dart';
import 'location_controller.dart';
import 'location_copy.dart';
import 'location_flow_state.dart';

class LocationCard extends StatefulWidget {
  const LocationCard({
    required this.controller,
    this.barangays = const [],
    super.key,
  });

  final LocationController controller;
  final List<GeographicArea> barangays;

  @override
  State<LocationCard> createState() => _LocationCardState();
}

class _LocationCardState extends State<LocationCard>
    with WidgetsBindingObserver {
  LocationController get controller => widget.controller;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(controller.resumeAfterLocationSettings());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

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
                if (controller.hasTemporaryLocation) ...[
                  _TemporaryLocationIndicator(controller: controller),
                  const SizedBox(height: 12),
                ],
                Semantics(
                  liveRegion: state.phase != LocationFlowPhase.initial,
                  child: Text(
                    state.message,
                    key: const Key('location-state-message'),
                  ),
                ),
                if (state.phase == LocationFlowPhase.resolvedCandidate) ...[
                  const SizedBox(height: 12),
                  _CandidateDetails(controller: controller),
                ],
                if (state.phase == LocationFlowPhase.confirmed) ...[
                  const SizedBox(height: 12),
                  _ConfirmedBarangay(controller: controller),
                ],
                const SizedBox(height: 12),
                _LocationActions(controller: controller),
                if (widget.barangays.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _ManualBarangaySelector(
                    controller: controller,
                    barangays: widget.barangays,
                  ),
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
      scrollable: true,
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
    if (phase == LocationFlowPhase.acquiring ||
        phase == LocationFlowPhase.resolvingBarangay) {
      return Row(
        children: [
          const SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              phase == LocationFlowPhase.acquiring
                  ? 'Getting one temporary location...'
                  : 'Checking the barangay boundary...',
            ),
          ),
          TextButton(
            key: const Key('location-cancel-button'),
            onPressed: controller.cancel,
            child: const Text('Cancel'),
          ),
        ],
      );
    }

    final actions = <Widget>[];
    if (phase == LocationFlowPhase.resolvedCandidate) {
      actions.addAll([
        FilledButton.icon(
          key: const Key('confirm-detected-barangay-button'),
          onPressed: controller.confirmCandidate,
          icon: const Icon(Icons.check_circle_outline),
          label: const Text('Confirm barangay'),
        ),
        OutlinedButton.icon(
          key: const Key('reject-detected-barangay-button'),
          onPressed: controller.rejectCandidate,
          icon: const Icon(Icons.edit_location_alt_outlined),
          label: const Text('Correct manually'),
        ),
      ]);
    }
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
    if (phase == LocationFlowPhase.permissionDeniedPermanently) {
      actions.add(
        OutlinedButton(
          key: const Key('open-app-settings-button'),
          onPressed: controller.openAppSettings,
          child: const Text('Open app settings'),
        ),
      );
    }
    if (!controller.hasTemporaryLocation &&
        (phase == LocationFlowPhase.confirmed ||
            phase == LocationFlowPhase.rejected ||
            phase == LocationFlowPhase.outsideBacoor ||
            phase == LocationFlowPhase.ambiguousBoundary ||
            phase == LocationFlowPhase.resolverUnavailable ||
            phase == LocationFlowPhase.resolverTimeout ||
            phase == LocationFlowPhase.resolverFailure ||
            phase == LocationFlowPhase.malformedResponse)) {
      actions.add(
        TextButton.icon(
          key: const Key('clear-location-button'),
          onPressed: controller.clearLocation,
          icon: const Icon(Icons.location_off_outlined),
          label: const Text('Clear location choice'),
        ),
      );
    }
    return Wrap(spacing: 8, runSpacing: 8, children: actions);
  }
}

class _CandidateDetails extends StatelessWidget {
  const _CandidateDetails({required this.controller});

  final LocationController controller;

  @override
  Widget build(BuildContext context) {
    final resolution = controller.resolution!;
    final barangay = resolution.barangay!;
    return Container(
      key: const Key('detected-barangay-candidate'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warningSurface,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Proposed barangay—confirmation required',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 5),
          Text('${barangay.name} (${barangay.psgcCode})'),
          const SizedBox(height: 5),
          const Text(
            'Matched using the derived administrative reference. It is pending validation and not City-verified.',
          ),
          ...resolution.limitations.map(
            (limitation) => Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                limitation,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ConfirmedBarangay extends StatelessWidget {
  const _ConfirmedBarangay({required this.controller});

  final LocationController controller;

  @override
  Widget build(BuildContext context) {
    final barangay = controller.confirmedBarangay!;
    return Container(
      key: const Key('confirmed-barangay'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.activeBackground,
        border: Border.all(color: AppColors.primary),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        '${barangay.name} (${barangay.psgcCode}) is the confirmed administrative location. No susceptibility assessment was started automatically.',
      ),
    );
  }
}

class _ManualBarangaySelector extends StatelessWidget {
  const _ManualBarangaySelector({
    required this.controller,
    required this.barangays,
  });

  final LocationController controller;
  final List<GeographicArea> barangays;

  @override
  Widget build(BuildContext context) {
    final eligible = barangays
        .where((area) => RegExp(r'^PSGC_\d{10}$').hasMatch(area.code))
        .toList(growable: false);
    if (eligible.isEmpty) return const SizedBox.shrink();
    final confirmedCode = controller.confirmedBarangay?.geographicAreaCode;
    final selected = eligible.where((area) => area.code == confirmedCode);
    return KeyedSubtree(
      key: const Key('manual-barangay-selector'),
      child: DropdownButtonFormField<GeographicArea>(
        key: ValueKey(confirmedCode),
        initialValue: selected.length == 1 ? selected.single : null,
        decoration: const InputDecoration(
          labelText: 'Choose a barangay manually',
          helperText: 'Manual selection remains available if GPS or boundaries are uncertain.',
          border: OutlineInputBorder(),
        ),
        isExpanded: true,
        items: eligible
            .map(
              (area) => DropdownMenuItem(
                value: area,
                child: Text(area.name, overflow: TextOverflow.ellipsis),
              ),
            )
            .toList(growable: false),
        onChanged: (area) {
          if (area == null) return;
          controller.selectManualBarangay(
            BarangayIdentity(
              psgcCode: area.code.substring('PSGC_'.length),
              name: area.name,
            ),
          );
        },
      ),
    );
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
