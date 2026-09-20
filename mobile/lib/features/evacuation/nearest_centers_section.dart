import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../data/models/verified_center.dart';
import 'nearest_center_controller.dart';

class NearestCentersSection extends StatelessWidget {
  const NearestCentersSection({required this.controller, super.key});

  final NearestCenterController controller;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => Card(
      key: const Key('nearest-centers-section'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Nearby verified center information',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 6),
            Semantics(
              liveRegion: controller.phase != NearestCenterPhase.initial,
              child: Text(
                controller.message,
                key: const Key('nearest-centers-state-message'),
              ),
            ),
            if (controller.phase == NearestCenterPhase.loading) ...[
              const SizedBox(height: 12),
              const LinearProgressIndicator(
                key: Key('nearest-centers-loading'),
                semanticsLabel: 'Loading verified center information',
              ),
            ],
            if (controller.canRetry) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                key: const Key('nearest-centers-retry'),
                onPressed: controller.retry,
                icon: const Icon(Icons.refresh),
                label: const Text('Try center request again'),
              ),
            ],
            if (controller.centers.isNotEmpty) ...[
              const SizedBox(height: 14),
              for (final center in controller.centers) ...[
                _CenterCard(center: center, controller: controller),
                if (center != controller.centers.last)
                  const SizedBox(height: 10),
              ],
              const SizedBox(height: 14),
              const _CenterSafetyNotice(),
            ],
          ],
        ),
      ),
    ),
  );
}

class _CenterCard extends StatelessWidget {
  const _CenterCard({required this.center, required this.controller});

  final VerifiedCenter center;
  final NearestCenterController controller;

  @override
  Widget build(BuildContext context) {
    final selected =
        controller.selectedCenterIdentifier == center.publicIdentifier;
    final verifiedDate =
        '${center.verifiedOn.year.toString().padLeft(4, '0')}-'
        '${center.verifiedOn.month.toString().padLeft(2, '0')}-'
        '${center.verifiedOn.day.toString().padLeft(2, '0')}';
    return Semantics(
      button: true,
      selected: selected,
      excludeSemantics: true,
      label:
          '${center.name}. ${center.distanceLabel}. '
          'Verified on $verifiedDate. '
          '${center.barangay.name}, PSGC ${center.barangay.psgcCode}. '
          'Address: ${center.address}. '
          'Source: ${center.sourceAttribution}. '
          '${center.limitations.map((item) => 'Limitation: $item.').join(' ')} '
          'Select this center on the map.',
      child: InkWell(
        key: Key('nearest-center-card-${center.publicIdentifier}'),
        onTap: () => controller.selectCenter(center.publicIdentifier),
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: selected ? AppColors.activeBackground : AppColors.surface,
            border: Border.all(
              color: selected ? AppColors.primary : AppColors.divider,
              width: selected ? 2 : 1,
            ),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                center.name,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 4),
              Text(center.address),
              Text('${center.barangay.name} (${center.barangay.psgcCode})'),
              const SizedBox(height: 6),
              Text(
                center.distanceLabel,
                key: Key('nearest-center-distance-${center.publicIdentifier}'),
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
              Text('Verified on $verifiedDate'),
              Text('Source: ${center.sourceAttribution}'),
              for (final limitation in center.limitations)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text('Limitation: $limitation'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CenterSafetyNotice extends StatelessWidget {
  const _CenterSafetyNotice();

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    label: 'Distance is approximate straight-line distance, not road distance. Nearest does not mean safest. FloodSense does not confirm that a center is open or reachable and does not guarantee available space. Follow official local instructions during an emergency.',
    child: Container(
      key: const Key('nearest-center-safety-warning'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warningSurface,
        borderRadius: BorderRadius.circular(10),
      ),
      child: const Text(
        'Distances are approximate straight-line distances, not road distances. '
        'Nearest does not mean safest. FloodSense does not confirm that a center '
        'is open or reachable and does not guarantee available space. Follow '
        'official local instructions during an emergency.',
      ),
    ),
  );
}
