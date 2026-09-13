import 'package:flutter/material.dart';

import '../../../app/theme/app_colors.dart';
import '../../../data/models/guidance_item.dart';

class GuidanceSection extends StatelessWidget {
  const GuidanceSection({required this.items, super.key});

  static const emptyMessage =
      'Susceptibility was assessed, but no enabled preparedness guidance is '
      'currently available for this result. Continue monitoring official advisories.';

  final List<GuidanceItem> items;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: const Key('guidance-section'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.checklist_rounded, color: AppColors.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Preparedness guidance',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'This guidance supports preparedness. It does not change the susceptibility result.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 14),
            if (items.isEmpty)
              const Text(emptyMessage)
            else
              for (var index = 0; index < items.length; index++) ...[
                _GuidanceTile(item: items[index], number: index + 1),
                if (index != items.length - 1) const Divider(height: 24),
              ],
          ],
        ),
      ),
    );
  }
}

class _GuidanceTile extends StatelessWidget {
  const _GuidanceTile({required this.item, required this.number});

  final GuidanceItem item;
  final int number;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      label: 'Preparedness action $number: ${item.title}',
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: const Color(0xFFEAF6FC),
            foregroundColor: AppColors.primary,
            child: Text(
              '$number',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.title,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 4),
                Text(item.instruction),
                const SizedBox(height: 6),
                Text(
                  item.readableCategory,
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
