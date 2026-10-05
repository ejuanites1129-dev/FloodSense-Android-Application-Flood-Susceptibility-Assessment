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
              controller.isDemonstration
                  ? 'Local test center preview'
                  : 'Nearby verified center information',
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
            if (controller.canRefresh) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                key: const Key('nearest-centers-refresh'),
                onPressed: controller.refresh,
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh centers'),
              ),
            ],
            if (controller.warnings.isNotEmpty) ...[
              const SizedBox(height: 12),
              Semantics(
                container: true,
                label: controller.warnings.join(' '),
                child: Container(
                  key: const Key('nearest-center-response-warnings'),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.warningSurface,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final warning in controller.warnings)
                        Text('• $warning'),
                    ],
                  ),
                ),
              ),
            ],
            if (controller.centers.isNotEmpty) ...[
              const SizedBox(height: 14),
              _NearestDistanceSummary(controller: controller),
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

class _NearestDistanceSummary extends StatelessWidget {
  const _NearestDistanceSummary({required this.controller});

  final NearestCenterController controller;

  @override
  Widget build(BuildContext context) {
    final center = controller.centers.first;
    return Container(
      key: const Key('nearest-center-distance-summary'),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.pageBackground,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.primary),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.night_shelter_outlined, color: AppColors.primary),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Nearest by straight-line distance',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Nearest: ${center.name}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            'Distance: ${center.distanceLabel}',
            style: Theme.of(context).textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w800),
          ),
          Text(
            controller.distanceOriginLabel,
            key: const Key('nearest-center-distance-origin'),
          ),
          if (center.isDemonstration)
            const Text('LOCAL TEST—not a real or verified facility.'),
          const SizedBox(height: 4),
          const Text('Not road distance or a safest-route recommendation.'),
        ],
      ),
    );
  }
}

class _CenterCard extends StatelessWidget {
  const _CenterCard({required this.center, required this.controller});

  final VerifiedCenter center;
  final NearestCenterController controller;

  @override
  Widget build(BuildContext context) {
    final selected =
        controller.selectedCenterIdentifier == center.publicIdentifier;
    final nearest =
        controller.centers.first.publicIdentifier == center.publicIdentifier;
    final verificationLabel = center.verificationLabel;
    return Semantics(
      button: true,
      selected: selected,
      excludeSemantics: true,
      label:
          '${center.name}. ${center.distanceLabel}. '
          '${nearest ? 'Nearest by straight-line distance. ' : ''}'
          '${controller.distanceOriginLabel}. '
          '$verificationLabel. '
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
              if (nearest) ...[
                const Text(
                  'Nearest by straight-line distance',
                  style: TextStyle(
                    fontWeight: FontWeight.w800,
                    color: AppColors.primary,
                  ),
                ),
                const SizedBox(height: 4),
              ],
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
              Text(verificationLabel),
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
