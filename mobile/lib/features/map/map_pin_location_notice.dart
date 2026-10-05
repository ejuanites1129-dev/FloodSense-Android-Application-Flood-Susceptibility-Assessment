import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';

/// Identifies the location represented by the draggable pin, without implying
/// that a manually selected barangay anchor is the user's measured position.
class MapPinLocationNotice extends StatelessWidget {
  const MapPinLocationNotice({
    required this.description,
    this.displayDescription,
    this.icon = Icons.location_on,
    super.key,
  });

  final String description;
  final String? displayDescription;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    label: '$description This map coordinate is temporary and is not saved.',
    excludeSemantics: true,
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: AppColors.primary),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            displayDescription ?? description,
            key: const Key('map-pin-coordinate-description'),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      ],
    ),
  );
}
