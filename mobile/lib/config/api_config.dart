import 'package:flutter/foundation.dart';

abstract final class ApiConfig {
  static const androidEmulatorBaseUrl = 'http://10.0.2.2:8000/api/v1';
  static const webDevelopmentBaseUrl = 'http://127.0.0.1:8000/api/v1';

  static const _configuredBaseUrl = String.fromEnvironment(
    'FLOODSENSE_API_BASE_URL',
    defaultValue: '',
  );

  static String get defaultBaseUrl =>
      kIsWeb ? webDevelopmentBaseUrl : androidEmulatorBaseUrl;

  static String get baseUrl => normalizeBaseUrl(
    _configuredBaseUrl.trim().isEmpty ? defaultBaseUrl : _configuredBaseUrl,
  );

  static String normalizeBaseUrl(String value) {
    final normalized = value.trim().replaceFirst(RegExp(r'/+$'), '');
    if (normalized.isEmpty) {
      throw const FormatException(
        'The FloodSense API base URL cannot be empty.',
      );
    }
    final uri = Uri.tryParse(normalized);
    if (uri == null || !uri.hasScheme || !uri.hasAuthority) {
      throw const FormatException('The FloodSense API base URL is invalid.');
    }
    return normalized;
  }
}
