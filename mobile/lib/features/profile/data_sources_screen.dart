import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';

class DataSourcesScreen extends StatelessWidget {
  const DataSourcesScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Data sources')),
    body: ListView(
      key: const Key('data-sources-screen'),
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 28),
      children: const [
        Text(
          'FloodSense data register',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
        ),
        SizedBox(height: 8),
        Text(
          'This page identifies the information behind the map and the datasets being reviewed for the research. A listed source is not automatically an input to the susceptibility assessment.',
        ),
        SizedBox(height: 22),
        _SourceSectionLabel('Used in the application'),
        _SourceCard(
          icon: Icons.map_outlined,
          title: 'Background map',
          provider: 'OpenStreetMap; Mapbox when configured',
          status: 'Map display only',
          description: 'Provides roads, places, and other visual context. Basemap features do not determine flood susceptibility.',
        ),
        _SourceCard(
          icon: Icons.border_outer_outlined,
          title: 'Bacoor administrative boundaries',
          provider: 'OCHA Humanitarian Data Exchange COD-AB, with NAMRIA and PSA named in the source metadata; updated using the PSA 2023 Bacoor barangay merger record',
          status: 'Administrative map layer',
          description: 'Provides the Bacoor City outline and 47 current barangay areas used for map display, barangay selection, and spatial summaries. The boundaries contain no rainfall, flood-depth, or susceptibility values.',
        ),
        _SourceCard(
          icon: Icons.science_outlined,
          title: 'Presentation assessment content',
          provider: 'FloodSense research team',
          status: 'Demonstration data',
          description: 'Exercises the scenario-assessment and preparedness interfaces while source-backed parameters and expert-reviewed guidance are being completed. Demonstration results are not Bacoor flood classifications.',
        ),
        SizedBox(height: 18),
        _SourceSectionLabel('Under research review'),
        _SourceCard(
          icon: Icons.layers_outlined,
          title: 'Detailed flood-susceptibility layer',
          provider: 'Department of Environment and Natural Resources – Mines and Geosciences Bureau (DENR-MGB)',
          status: 'Provisional consultation material',
          description: 'A Bacoor-area extract is being reviewed for source metadata, class definitions, reuse conditions, processing, and methodological suitability. It is not automatically used by the normal assessment flow.',
        ),
        SizedBox(height: 18),
        _SourceSectionLabel('Requested or awaiting integration'),
        _SourceCard(
          icon: Icons.water_drop_outlined,
          title: 'Rainfall and RIDF references',
          provider: 'Philippine Atmospheric, Geophysical and Astronomical Services Administration (DOST-PAGASA)',
          status: 'Received / under research review',
          description: 'The Sangley RIDF release is being reviewed as the primary nearby reference for hypothetical rainfall scenarios, with NAIA retained for comparison. Integration still requires documented station coverage, period, units, permitted use, and methodological validation.',
        ),
        _SourceCard(
          icon: Icons.sensors_outlined,
          title: 'Rainfall and water-level station records',
          provider: 'Department of Science and Technology – Advanced Science and Technology Institute (DOST-ASTI)',
          status: 'Requested',
          description: 'Station observations are being requested for research and validation. They are not live monitoring feeds in FloodSense and are not assessment inputs until reviewed.',
        ),
        _SourceCard(
          icon: Icons.terrain_outlined,
          title: 'Digital Terrain Model',
          provider: 'UP DREAM / PHIL-LiDAR through the LiPAD portal',
          status: 'Requested',
          description: 'Requested to support terrain and elevation analysis for Bacoor. It will require coverage, resolution, coordinate-system, processing, and permitted-use checks before integration.',
        ),
        _SourceCard(
          icon: Icons.history_outlined,
          title: 'Historical flood and preparedness records',
          provider: 'Bacoor City Disaster Risk Reduction and Management Office (BDRRMO)',
          status: 'Consulted / requested',
          description: 'Consultation findings, historical flood records, and preparedness references may support validation and guidance. They do not become assessment rules merely because they were received or discussed.',
        ),
        SizedBox(height: 12),
        _RegisterNotice(),
      ],
    ),
  );
}

class _SourceSectionLabel extends StatelessWidget {
  const _SourceSectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Text(
      text.toUpperCase(),
      style: Theme.of(context).textTheme.labelLarge?.copyWith(
        color: AppColors.secondaryText,
        fontWeight: FontWeight.w800,
        letterSpacing: 0.7,
      ),
    ),
  );
}

class _SourceCard extends StatelessWidget {
  const _SourceCard({
    required this.icon,
    required this.title,
    required this.provider,
    required this.status,
    required this.description,
  });

  final IconData icon;
  final String title;
  final String provider;
  final String status;
  final String description;

  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 10),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: AppColors.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _SourceField(label: 'Source', value: provider),
          const SizedBox(height: 7),
          _SourceField(label: 'Current use', value: status),
          const SizedBox(height: 9),
          Text(description),
        ],
      ),
    ),
  );
}

class _SourceField extends StatelessWidget {
  const _SourceField({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Text.rich(
    TextSpan(
      children: [
        TextSpan(
          text: '$label: ',
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        TextSpan(text: value),
      ],
    ),
  );
}

class _RegisterNotice extends StatelessWidget {
  const _RegisterNotice();

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: AppColors.primary.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: AppColors.primary.withValues(alpha: 0.25)),
    ),
    child: const Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.info_outline, color: AppColors.primary),
        SizedBox(width: 10),
        Expanded(
          child: Text(
            'FloodSense keeps data provenance separate from scientific approval. Integration requires source review, documented processing, applicable permission, and the validation required by the research method.',
          ),
        ),
      ],
    ),
  );
}
