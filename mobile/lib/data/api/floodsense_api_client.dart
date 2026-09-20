import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../../config/api_config.dart';
import '../models/assessment_request.dart';
import '../models/assessment_result.dart';
import '../models/barangay_resolution.dart';
import '../models/geographic_area.dart';
import '../models/json_parsing.dart';
import '../models/map_assessment_result.dart';
import '../models/point_resolution.dart';
import '../models/scenario_option.dart';
import 'api_exception.dart';

abstract interface class BarangayResolver {
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  });
}

abstract interface class FloodSenseApi implements BarangayResolver {
  Future<AssessmentOptions> fetchAssessmentOptions();
  Future<List<GeographicArea>> fetchDemonstrationAreas();
  Future<List<GeographicArea>> fetchReferenceBoundaries();
  Future<AssessmentResult> evaluateAssessment(AssessmentRequest request);
  Future<PointResolution> resolvePoint({
    required double latitude,
    required double longitude,
  });
  @override
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  });
  Future<MapAssessmentResult> evaluateMapScenario({
    required String intensityCode,
    required String durationCode,
  });
  void close();
}

class FloodSenseApiClient implements FloodSenseApi {
  FloodSenseApiClient({
    http.Client? client,
    String? baseUrl,
    this.timeout = const Duration(seconds: 15),
  }) : _client = client ?? http.Client(),
       _ownsClient = client == null,
       _baseUrl = ApiConfig.normalizeBaseUrl(baseUrl ?? ApiConfig.baseUrl);

  final http.Client _client;
  final bool _ownsClient;
  final String _baseUrl;
  final Duration timeout;

  Uri _uri(String route, [Map<String, String>? query]) {
    final cleanRoute = route.replaceFirst(RegExp(r'^/+'), '');
    return Uri.parse('$_baseUrl/$cleanRoute').replace(queryParameters: query);
  }

  @override
  Future<AssessmentOptions> fetchAssessmentOptions() async {
    final json = await _get(
      _uri('assessment-options/', const {'mode': 'demonstration'}),
    );
    return _parse(() => AssessmentOptions.fromJson(json));
  }

  @override
  Future<List<GeographicArea>> fetchDemonstrationAreas() async {
    final json = await _get(
      _uri('geography/areas/', const {'mode': 'demonstration'}),
    );
    return _parse(() => GeographicArea.listFromFeatureCollection(json));
  }

  @override
  Future<List<GeographicArea>> fetchReferenceBoundaries() async {
    final json = await _get(_uri('geography/reference-boundaries/'));
    return _parse(() => GeographicArea.listFromFeatureCollection(json));
  }

  @override
  Future<AssessmentResult> evaluateAssessment(AssessmentRequest request) async {
    final json = await _send(
      () => _client.post(
        _uri('assessments/evaluate/'),
        headers: const {
          HttpHeaders.acceptHeader: 'application/json',
          HttpHeaders.contentTypeHeader: 'application/json; charset=utf-8',
        },
        body: jsonEncode(request.toJson()),
      ),
    );
    return _parse(() => AssessmentResult.fromJson(json));
  }

  @override
  Future<PointResolution> resolvePoint({
    required double latitude,
    required double longitude,
  }) async {
    final json = await _postJson('geography/resolve-point/', {
      'mode': 'demonstration',
      'latitude': latitude,
      'longitude': longitude,
    });
    return _parse(() => PointResolution.fromJson(json));
  }

  @override
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  }) async {
    final json = await _postJson('geography/resolve-barangay/', {
      'latitude': latitude,
      'longitude': longitude,
    }, exposeValidationDetails: false);
    final result = _parse(() => BarangayResolution.fromJson(json));
    const maximumEchoDifference = 0.0000051;
    if ((result.coordinate.latitude - latitude).abs() > maximumEchoDifference ||
        (result.coordinate.longitude - longitude).abs() >
            maximumEchoDifference) {
      throw const ApiException(
        'FloodSense received an inconsistent location response from the server.',
        kind: ApiFailureKind.malformedResponse,
      );
    }
    return result;
  }

  @override
  Future<MapAssessmentResult> evaluateMapScenario({
    required String intensityCode,
    required String durationCode,
  }) async {
    final json = await _postJson('assessments/evaluate-map/', {
      'mode': 'demonstration',
      'rainfall_intensity_code': intensityCode,
      'rainfall_duration_code': durationCode,
    });
    return _parse(() => MapAssessmentResult.fromJson(json));
  }

  Future<Map<String, dynamic>> _postJson(
    String route,
    Map<String, dynamic> body, {
    bool exposeValidationDetails = true,
  }) => _send(
    () => _client.post(
      _uri(route),
      headers: const {
        HttpHeaders.acceptHeader: 'application/json',
        HttpHeaders.contentTypeHeader: 'application/json; charset=utf-8',
      },
      body: jsonEncode(body),
    ),
    exposeValidationDetails: exposeValidationDetails,
  );

  Future<Map<String, dynamic>> _get(Uri uri) => _send(
    () => _client.get(
      uri,
      headers: const {HttpHeaders.acceptHeader: 'application/json'},
    ),
  );

  Future<Map<String, dynamic>> _send(
    Future<http.Response> Function() request, {
    bool exposeValidationDetails = true,
  }) async {
    try {
      final response = await request().timeout(timeout);
      final body = _decodeObject(response.bodyBytes);
      if (response.statusCode >= 200 && response.statusCode < 300) return body;
      if (response.statusCode == 400) {
        if (!exposeValidationDetails) {
          throw const ApiException(
            'The location lookup request was not accepted.',
            kind: ApiFailureKind.validation,
          );
        }
        final errors = _fieldErrors(body);
        throw ApiException(
          errors.values.expand((messages) => messages).join(' '),
          kind: ApiFailureKind.validation,
          fieldErrors: errors,
        );
      }
      throw const ApiException(
        'The FloodSense service is temporarily unavailable. Please try again.',
        kind: ApiFailureKind.service,
      );
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException(
        'The request timed out. Check your connection and try again.',
        kind: ApiFailureKind.timeout,
      );
    } on SocketException {
      throw const ApiException(
        'Unable to reach FloodSense. Check that the server and network are available.',
        kind: ApiFailureKind.connectivity,
      );
    } on http.ClientException {
      throw const ApiException(
        'Unable to reach FloodSense. Check that the server and network are available.',
        kind: ApiFailureKind.connectivity,
      );
    } on FormatException {
      throw const ApiException(
        'FloodSense received an unreadable response from the server.',
        kind: ApiFailureKind.malformedResponse,
      );
    }
  }

  Map<String, dynamic> _decodeObject(List<int> bytes) {
    final decoded = jsonDecode(utf8.decode(bytes));
    if (decoded is! Map) {
      throw const FormatException('Expected a JSON object.');
    }
    return decoded.map((key, value) => MapEntry(key.toString(), value));
  }

  T _parse<T>(T Function() parser) {
    try {
      return parser();
    } on ModelParsingException {
      throw const ApiException(
        'FloodSense received an incomplete response from the server.',
        kind: ApiFailureKind.malformedResponse,
      );
    }
  }

  Map<String, List<String>> _fieldErrors(Map<String, dynamic> body) {
    final result = <String, List<String>>{};
    for (final entry in body.entries) {
      final value = entry.value;
      if (value is List) {
        result[entry.key] = value.map((item) => item.toString()).toList();
      } else {
        result[entry.key] = [value.toString()];
      }
    }
    if (result.isEmpty) {
      result['request'] = ['The assessment selections were not accepted.'];
    }
    return Map.unmodifiable(result);
  }

  @override
  void close() {
    if (_ownsClient) _client.close();
  }
}
