import 'package:flutter/material.dart';

import '../../../app/theme/app_colors.dart';

class DemonstrationWarning extends StatelessWidget {
  const DemonstrationWarning({super.key});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Permanent demonstration safety notice',
      child: Container(
        key: const Key('demonstration-warning'),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.warningSurface,
          borderRadius: BorderRadius.circular(12),
          border: const Border(
            left: BorderSide(color: AppColors.moderate, width: 4),
          ),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.warning_amber_rounded, color: Color(0xFF725500)),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'DEMONSTRATION DATA—NOT OFFICIAL',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                  SizedBox(height: 6),
                  Text(
                    'Your selections are hypothetical planning scenarios. '
                    'FloodSense is not a live flood forecast, warning, or '
                    'evacuation order. Monitor PAGASA, BDRRMO, and other '
                    'authorized advisories.',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
