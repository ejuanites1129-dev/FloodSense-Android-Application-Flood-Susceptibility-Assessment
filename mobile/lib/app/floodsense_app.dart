import 'package:flutter/material.dart';

import '../data/api/floodsense_api_client.dart';
import '../features/assessment/assessment_screen.dart';
import 'theme/app_theme.dart';

class FloodSenseApp extends StatelessWidget {
  const FloodSenseApp({super.key, this.api, this.showBasemap = true});

  final FloodSenseApi? api;
  final bool showBasemap;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FloodSense',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: AssessmentScreen(
        api: api ?? FloodSenseApiClient(),
        showBasemap: showBasemap,
      ),
    );
  }
}
