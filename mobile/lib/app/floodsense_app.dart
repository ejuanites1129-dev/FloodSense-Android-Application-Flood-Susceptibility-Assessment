import 'package:flutter/material.dart';

import '../data/api/floodsense_api_client.dart';
import '../features/assessment/assessment_screen.dart';
import '../features/evacuation/nearest_center_provider.dart';
import '../features/location/location_service.dart';
import 'theme/app_theme.dart';

class FloodSenseApp extends StatelessWidget {
  const FloodSenseApp({
    super.key,
    this.api,
    this.locationService,
    this.nearestCenterProvider,
    this.showBasemap = true,
  });

  final FloodSenseApi? api;
  final LocationService? locationService;
  final NearestCenterProvider? nearestCenterProvider;
  final bool showBasemap;

  @override
  Widget build(BuildContext context) {
    final activeApi = api ?? FloodSenseApiClient();
    NearestCenterProvider? activeCenterProvider = nearestCenterProvider;
    if (activeCenterProvider == null && activeApi is NearestCenterProvider) {
      activeCenterProvider = activeApi as NearestCenterProvider;
    }
    return MaterialApp(
      title: 'FloodSense',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: AssessmentScreen(
        api: activeApi,
        locationService: locationService,
        nearestCenterProvider: activeCenterProvider,
        showBasemap: showBasemap,
      ),
    );
  }
}
