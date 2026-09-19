import 'package:flutter/material.dart';

import '../data/api/floodsense_api_client.dart';
import '../features/assessment/assessment_screen.dart';
import '../features/location/location_service.dart';
import 'theme/app_theme.dart';

class FloodSenseApp extends StatelessWidget {
  const FloodSenseApp({
    super.key,
    this.api,
    this.locationService,
    this.showBasemap = true,
  });

  final FloodSenseApi? api;
  final LocationService? locationService;
  final bool showBasemap;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FloodSense',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: AssessmentScreen(
        api: api ?? FloodSenseApiClient(),
        locationService: locationService,
        showBasemap: showBasemap,
      ),
    );
  }
}
