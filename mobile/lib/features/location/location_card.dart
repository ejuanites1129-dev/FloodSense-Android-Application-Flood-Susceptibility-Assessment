import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/models/barangay_resolution.dart';
import '../../data/models/geographic_area.dart';
import '../map/map_pin_location_notice.dart';
import 'location_controller.dart';
import 'location_copy.dart';
import 'location_flow_state.dart';

class LocationCard extends StatefulWidget {
  const LocationCard({
    required this.controller,
    this.barangays = const [],
    this.showAreaConfirmation = true,
    super.key,
  });

  final LocationController controller;
  final List<GeographicArea> barangays;

  /// The guided resident flow provides its single Confirm area action outside
  /// the card. Standalone assessment screens still need one action here.
  final bool showAreaConfirmation;

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
                Text('Location', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 12),
                if (controller.lookupCoordinate != null &&
                    controller.coordinateDescription != null) ...[
                  MapPinLocationNotice(
                    description: controller.coordinateDescription!,
                    displayDescription: controller.isApproximateCoordinate
                        ? 'Approximate barangay reference point'
                        : null,
                    icon: switch (controller.coordinateOrigin) {
                      LocationCoordinateOrigin.deviceGps => Icons.my_location,
                      LocationCoordinateOrigin.barangayReference =>
                        Icons.location_city,
                      _ => Icons.location_on,
                    },
                    key: controller.isApproximateCoordinate
                        ? const Key('approximate-barangay-reference-point')
                        : const Key('location-card-pin-description'),
                  ),
                  const SizedBox(height: 4),
                ],
                if (controller.candidateBarangay ?? controller.confirmedBarangay
                    case final barangay?) ...[
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      barangay.name,
                      key: controller.candidateBarangay != null
                          ? const Key('detected-barangay-candidate')
                          : const Key('confirmed-barangay'),
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
                if (_showsRecoveryMessage(state.phase)) ...[
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      state.message,
                      key: const Key('location-state-message'),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                _LocationActions(
                  controller: controller,
                  showAreaConfirmation: widget.showAreaConfirmation,
                ),
                if (widget.barangays.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _ManualBarangaySelector(
                    controller: controller,
                    barangays: widget.barangays,
                  ),
                ],
                if (!controller.isBusy &&
                    (controller.hasTemporaryLocation ||
                        controller.lookupCoordinate != null ||
                        controller.confirmedBarangay != null)) ...[
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      key: const Key('clear-location-button'),
                      onPressed: controller.clearLocation,
                      icon: const Icon(Icons.location_off_outlined),
                      label: Text(
                        controller.hasTemporaryLocation
                            ? 'Clear temporary location'
                            : 'Clear location choice',
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  bool _showsRecoveryMessage(LocationFlowPhase phase) => switch (phase) {
    LocationFlowPhase.initial ||
    LocationFlowPhase.purposeExplanation ||
    LocationFlowPhase.acquiring ||
    LocationFlowPhase.acquired ||
    LocationFlowPhase.resolvingBarangay ||
    LocationFlowPhase.resolvedCandidate ||
    LocationFlowPhase.confirmed ||
    LocationFlowPhase.cleared ||
    LocationFlowPhase.cancelled => false,
    _ => true,
  };
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
  const _LocationActions({
    required this.controller,
    required this.showAreaConfirmation,
  });

  final LocationController controller;
  final bool showAreaConfirmation;

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
    if (phase == LocationFlowPhase.resolvedCandidate && showAreaConfirmation) {
      actions.add(
        FilledButton.icon(
          key: const Key('confirm-detected-barangay-button'),
          onPressed: controller.confirmCandidate,
          icon: const Icon(Icons.check_circle_outline),
          label: const Text('Confirm area'),
        ),
      );
    }
    if (!controller.state.retryAllowed &&
        phase != LocationFlowPhase.permissionDeniedPermanently &&
        phase != LocationFlowPhase.purposeExplanation) {
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
    return Wrap(spacing: 8, runSpacing: 8, children: actions);
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
            geometry: area.geometry,
          );
        },
      ),
    );
  }
}
