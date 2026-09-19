import 'package:flutter/widgets.dart';

import 'app/floodsense_app.dart';
import 'features/location/geolocator_location_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(FloodSenseApp(locationService: GeolocatorLocationService()));
}
