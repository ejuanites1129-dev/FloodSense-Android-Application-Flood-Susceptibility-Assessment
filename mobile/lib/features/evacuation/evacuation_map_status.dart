import 'package:flutter/material.dart';

import '../../data/models/center_map_result.dart';
import '../../data/models/nearest_center_result.dart';
import 'evacuation_map_controller.dart';
import 'nearest_center_controller.dart';

class EvacuationMapStatus extends StatelessWidget {
  const EvacuationMapStatus({
    required this.controller,
    this.nearestController,
    this.showRefresh = true,
    super.key,
  });
  final EvacuationMapController controller;
  final NearestCenterController? nearestController;
  final bool showRefresh;

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (controller.message.isNotEmpty &&
              (!controller.isDemonstration ||
                  controller.isLoading ||
                  controller.failure != null ||
                  controller.centers.isEmpty))
            Text(controller.message, key: const Key('evacuation-map-status')),
          for (final warning in controller.warnings)
            if (warning != localCenterPreviewWarning)
              Text(
                warning == centerMapWarning
                    ? 'This map does not confirm that a center is open, available, reachable, or safe.'
                    : warning,
                style: Theme.of(context).textTheme.bodySmall,
              ),
          if (showRefresh && !controller.isLoading)
            TextButton.icon(
              key: const Key('refresh-evacuation-map'),
              onPressed: controller.origin == null
                  ? null
                  : () {
                      if (nearestController?.canRefresh ?? false) {
                        nearestController!.refresh();
                      } else {
                        controller.load(refresh: true);
                      }
                    },
              icon: const Icon(Icons.refresh),
              label: Text(
                controller.failure == null
                    ? 'Refresh map centers'
                    : 'Retry map centers',
              ),
            ),
        ],
      ),
    ),
  );
}
