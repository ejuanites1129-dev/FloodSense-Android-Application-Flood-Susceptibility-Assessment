import 'dart:async';

import 'package:floodsense/data/api/floodsense_api_client.dart';
import 'package:floodsense/data/models/assessment_request.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/data/models/barangay_resolution.dart';
import 'package:floodsense/data/models/geographic_area.dart';
import 'package:floodsense/data/models/map_assessment_result.dart';
import 'package:floodsense/data/models/point_resolution.dart';
import 'package:floodsense/data/models/scenario_option.dart';

Map<String, dynamic> optionJson({
  int id = 1,
  String category = 'INTENSITY',
  String code = 'DEMO_LIGHT',
  String label = 'Light',
  num? value = 1,
  String unit = '',
  int order = 1,
}) => {
  'id': id,
  'category': category,
  'code': code,
  'label': label,
  'derived_value': value,
  'unit': unit,
  'display_order': order,
  'data_status': 'DEMONSTRATION',
};

Map<String, dynamic> optionsJson({bool empty = false}) => {
  'intensity_options': empty
      ? <dynamic>[]
      : [
          optionJson(),
          optionJson(id: 2, code: 'DEMO_HEAVY', label: 'Heavy', value: 3),
        ],
  'duration_options': empty
      ? <dynamic>[]
      : [
          optionJson(
            id: 3,
            category: 'DURATION',
            code: 'DEMO_1_HOUR',
            label: '1 hour',
            unit: 'hours',
          ),
          optionJson(
            id: 4,
            category: 'DURATION',
            code: 'DEMO_6_HOURS',
            label: '6 hours',
            value: 6,
            unit: 'hours',
            order: 2,
          ),
        ],
  'operating_mode': 'DEMONSTRATION',
  'data_status': 'DEMONSTRATION',
  'warnings': [
    'DEMONSTRATION DATA—NOT OFFICIAL',
    'This result is not an official flood forecast, warning, or emergency instruction.',
  ],
};

Map<String, dynamic> areaCollectionJson({bool empty = false}) => {
  'type': 'FeatureCollection',
  'features': empty
      ? <dynamic>[]
      : [
          {
            'type': 'Feature',
            'id': 7,
            'geometry': {
              'type': 'MultiPolygon',
              'coordinates': [
                [
                  [
                    [120.0, 14.0],
                    [120.0, 14.01],
                    [120.01, 14.01],
                    [120.01, 14.0],
                    [120.0, 14.0],
                  ],
                ],
              ],
            },
            'properties': {
              'id': 7,
              'code': 'DEMO_ZONE_A',
              'name': 'Demo Zone A',
              'area_type': 'DEMO_ZONE',
              'data_status': 'DEMONSTRATION',
              'updated_at': '2026-09-13T00:00:00+08:00',
              'source': {'name': 'DEMONSTRATION DATA—NOT OFFICIAL'},
            },
          },
        ],
  'operating_mode': 'DEMONSTRATION',
  'data_status': 'DEMONSTRATION',
  'warnings': ['DEMONSTRATION DATA—NOT OFFICIAL'],
};

Map<String, dynamic> referenceBoundaryCollectionJson({bool empty = false}) => {
  'type': 'FeatureCollection',
  'features': empty
      ? <dynamic>[]
      : [
          {
            'type': 'Feature',
            'id': 101,
            'geometry': {
              'type': 'MultiPolygon',
              'coordinates': [
                [
                  [
                    [120.96, 14.40],
                    [120.96, 14.41],
                    [120.97, 14.41],
                    [120.97, 14.40],
                    [120.96, 14.40],
                  ],
                ],
              ],
            },
            'properties': {
              'id': 101,
              'code': 'PSGC_0402103004',
              'name': 'Bayanan',
              'area_type': 'BARANGAY',
              'data_status': 'PENDING_VALIDATION',
              'updated_at': '2026-09-16T00:00:00+08:00',
              'source': {
                'name': 'Bacoor administrative boundaries—derived reference',
              },
            },
          },
        ],
  'layer_kind': 'ADMINISTRATIVE_REFERENCE',
  'data_status': 'PENDING_VALIDATION',
  'warnings': [
    'DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED',
    'Administrative boundaries only; they do not indicate flood susceptibility or current conditions.',
  ],
};

Map<String, dynamic> assessmentJson({
  String state = 'CLASSIFIED',
  bool guidance = true,
  bool longText = false,
}) {
  final isClassified = state == 'CLASSIFIED';
  final summary = longText
      ? List.filled(
          30,
          'A long explanation remains readable and scrollable.',
        ).join(' ')
      : switch (state) {
          'UNCERTAIN' => 'Two equally ranked demonstration rules disagree.',
          'INSUFFICIENT_DATA' => 'No eligible stored rule matched these facts.',
          _ => 'The selected demonstration facts matched the stored rule.',
        };
  return {
    'assessment_state': state,
    'susceptibility': isClassified
        ? {'code': 'HIGH', 'label': 'High', 'map_color': '#E2691B'}
        : null,
    'area': {'id': 7, 'code': 'DEMO_ZONE_A', 'name': 'Demo Zone A'},
    'scenario': {
      'rainfall_intensity_code': 'DEMO_HEAVY',
      'rainfall_duration_code': 'DEMO_6_HOURS',
    },
    'facts': {
      'zone_code': 'DEMO_ZONE_A',
      'zone_baseline_rank': 2,
      'rainfall_intensity_rank': 3,
      'rainfall_duration_hours': 6,
    },
    'matched_rule_codes': state == 'INSUFFICIENT_DATA'
        ? <String>[]
        : state == 'UNCERTAIN'
        ? ['DEMO-RULE-A', 'DEMO-RULE-B']
        : ['DEMO-RULE-300'],
    'explanation': {
      'summary': summary,
      'matched_rule_codes': state == 'INSUFFICIENT_DATA'
          ? <String>[]
          : state == 'UNCERTAIN'
          ? ['DEMO-RULE-A', 'DEMO-RULE-B']
          : ['DEMO-RULE-300'],
      'facts_used': ['zone_code=DEMO_ZONE_A'],
      'rule_rationales': isClassified
          ? ['Stored demonstration rationale.']
          : <String>[],
      'ruleset': 'Demonstration Rules v1.0',
      'warnings': ['DEMONSTRATION DATA—NOT OFFICIAL'],
    },
    'ruleset': {'name': 'Demonstration Rules', 'version': '1.0'},
    'guidance': isClassified && guidance
        ? [
            {
              'id': 2,
              'title': 'Second API action',
              'instruction': longText
                  ? List.filled(
                      20,
                      'Continue monitoring authorized advisories.',
                    ).join(' ')
                  : 'Protect important documents.',
              'category': 'PROTECT',
              'display_order': 20,
              'data_status': 'DEMONSTRATION',
            },
            {
              'id': 3,
              'title': 'Third API action',
              'instruction': 'Review household supplies.',
              'category': 'PREPARE',
              'display_order': 30,
              'data_status': 'DEMONSTRATION',
            },
          ]
        : <dynamic>[],
    'operating_mode': 'DEMONSTRATION',
    'data_status': 'DEMONSTRATION',
    'warnings': [
      'DEMONSTRATION DATA—NOT OFFICIAL',
      'This result is not an official flood forecast, warning, or emergency instruction.',
    ],
  };
}

AssessmentOptions sampleOptions({bool empty = false}) =>
    AssessmentOptions.fromJson(optionsJson(empty: empty));

List<GeographicArea> sampleAreas({bool empty = false}) =>
    GeographicArea.listFromFeatureCollection(areaCollectionJson(empty: empty));

List<GeographicArea> sampleReferenceAreas({bool empty = false}) =>
    GeographicArea.listFromFeatureCollection(
      referenceBoundaryCollectionJson(empty: empty),
    );

AssessmentResult sampleResult({
  String state = 'CLASSIFIED',
  bool guidance = true,
  bool longText = false,
}) => AssessmentResult.fromJson(
  assessmentJson(state: state, guidance: guidance, longText: longText),
);

Map<String, dynamic> pointResolutionJson({
  String state = 'RESOLVED',
  double latitude = 14.005,
  double longitude = 120.005,
}) => {
  'resolution_state': state,
  'coordinate': {'latitude': latitude, 'longitude': longitude},
  'area': state == 'RESOLVED'
      ? {
          'id': 7,
          'code': 'DEMO_ZONE_A',
          'name': 'Demo Zone A',
          'area_type': 'DEMO_ZONE',
          'data_status': 'DEMONSTRATION',
        }
      : null,
  'operating_mode': 'DEMONSTRATION',
  'data_status': 'DEMONSTRATION',
  'warnings': ['DEMONSTRATION DATA—NOT OFFICIAL'],
};

Map<String, dynamic> mapAssessmentJson({
  String intensityCode = 'DEMO_HEAVY',
  String durationCode = 'DEMO_6_HOURS',
  String state = 'CLASSIFIED',
}) => {
  'scenario': {
    'rainfall_intensity_code': intensityCode,
    'rainfall_duration_code': durationCode,
  },
  'results': [
    {
      'area': {'id': 7, 'code': 'DEMO_ZONE_A', 'name': 'Demo Zone A'},
      'assessment_state': state,
      'susceptibility': state == 'CLASSIFIED'
          ? {'code': 'HIGH', 'label': 'High', 'map_color': '#E2691B'}
          : null,
      'matched_rule_codes': state == 'INSUFFICIENT_DATA'
          ? <String>[]
          : ['DEMO-RULE-300'],
      'ruleset': {'name': 'Demonstration Rules', 'version': '1.0'},
      'summary': state == 'CLASSIFIED'
          ? 'Stored demonstration rule matched.'
          : 'No eligible stored rule matched.',
    },
  ],
  'operating_mode': 'DEMONSTRATION',
  'data_status': 'DEMONSTRATION',
  'warnings': ['DEMONSTRATION DATA—NOT OFFICIAL'],
};

PointResolution samplePointResolution({String state = 'RESOLVED'}) =>
    PointResolution.fromJson(pointResolutionJson(state: state));

Map<String, dynamic> barangayResolutionJson({
  String state = 'RESOLVED',
  double latitude = 14.405,
  double longitude = 120.965,
}) => {
  'resolution_state': state,
  'coordinate': {
    'latitude': latitude,
    'longitude': longitude,
    'precision_decimal_places': 5,
  },
  'barangay': state == 'RESOLVED'
      ? {'psgc_code': '0402103004', 'name': 'Bayanan'}
      : null,
  'boundary': {
    'layer_kind': 'ADMINISTRATIVE_REFERENCE',
    'data_status': 'PENDING_VALIDATION',
    'source_status': 'PENDING_VALIDATION',
    'city_verified': false,
  },
  'limitations': [
    'DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED',
    'Administrative boundaries only; they do not indicate flood susceptibility or current conditions.',
  ],
};

BarangayResolution sampleBarangayResolution({String state = 'RESOLVED'}) =>
    BarangayResolution.fromJson(barangayResolutionJson(state: state));

MapAssessmentResult sampleMapAssessment({
  String intensityCode = 'DEMO_HEAVY',
  String durationCode = 'DEMO_6_HOURS',
  String state = 'CLASSIFIED',
}) => MapAssessmentResult.fromJson(
  mapAssessmentJson(
    intensityCode: intensityCode,
    durationCode: durationCode,
    state: state,
  ),
);

class FakeFloodSenseApi implements FloodSenseApi {
  FakeFloodSenseApi({
    AssessmentOptions? options,
    List<GeographicArea>? areas,
    List<GeographicArea>? referenceAreas,
    AssessmentResult? result,
    this.loadError,
    this.evaluateError,
    this.optionsCompleter,
    this.areasCompleter,
    this.evaluateCompleter,
    this.mapResult,
    this.pointResult,
    this.mapError,
    this.pointError,
    this.mapHandler,
    this.pointHandler,
    this.barangayResult,
    this.barangayError,
    this.barangayHandler,
  }) : options = options ?? sampleOptions(),
       areas = areas ?? sampleAreas(),
       referenceAreas = referenceAreas ?? sampleReferenceAreas(),
       result = result ?? sampleResult();

  AssessmentOptions options;
  List<GeographicArea> areas;
  List<GeographicArea> referenceAreas;
  AssessmentResult result;
  Object? loadError;
  Object? evaluateError;
  Completer<AssessmentOptions>? optionsCompleter;
  Completer<List<GeographicArea>>? areasCompleter;
  Completer<AssessmentResult>? evaluateCompleter;
  MapAssessmentResult? mapResult;
  PointResolution? pointResult;
  Object? mapError;
  Object? pointError;
  Future<MapAssessmentResult> Function(String intensity, String duration)?
  mapHandler;
  Future<PointResolution> Function(double latitude, double longitude)?
  pointHandler;
  BarangayResolution? barangayResult;
  Object? barangayError;
  Future<BarangayResolution> Function(double latitude, double longitude)?
  barangayHandler;
  int optionsCalls = 0;
  int areasCalls = 0;
  int referenceAreasCalls = 0;
  int evaluateCalls = 0;
  int mapCalls = 0;
  int pointCalls = 0;
  int barangayCalls = 0;
  bool closed = false;
  AssessmentRequest? lastRequest;
  String? lastMapIntensity;
  String? lastMapDuration;
  double? lastLatitude;
  double? lastLongitude;
  double? lastBarangayLatitude;
  double? lastBarangayLongitude;

  @override
  Future<AssessmentOptions> fetchAssessmentOptions() async {
    optionsCalls++;
    if (loadError != null) throw loadError!;
    return optionsCompleter?.future ?? options;
  }

  @override
  Future<List<GeographicArea>> fetchDemonstrationAreas() async {
    areasCalls++;
    if (loadError != null) throw loadError!;
    return areasCompleter?.future ?? areas;
  }

  @override
  Future<List<GeographicArea>> fetchReferenceBoundaries() async {
    referenceAreasCalls++;
    if (loadError != null) throw loadError!;
    return referenceAreas;
  }

  @override
  Future<AssessmentResult> evaluateAssessment(AssessmentRequest request) async {
    evaluateCalls++;
    lastRequest = request;
    if (evaluateError != null) throw evaluateError!;
    return evaluateCompleter?.future ?? result;
  }

  @override
  Future<MapAssessmentResult> evaluateMapScenario({
    required String intensityCode,
    required String durationCode,
  }) async {
    mapCalls++;
    lastMapIntensity = intensityCode;
    lastMapDuration = durationCode;
    if (mapError != null) throw mapError!;
    if (mapHandler != null) return mapHandler!(intensityCode, durationCode);
    return mapResult ??
        sampleMapAssessment(
          intensityCode: intensityCode,
          durationCode: durationCode,
        );
  }

  @override
  Future<PointResolution> resolvePoint({
    required double latitude,
    required double longitude,
  }) async {
    pointCalls++;
    lastLatitude = latitude;
    lastLongitude = longitude;
    if (pointError != null) throw pointError!;
    if (pointHandler != null) return pointHandler!(latitude, longitude);
    return pointResult ?? samplePointResolution();
  }

  @override
  Future<BarangayResolution> resolveBarangay({
    required double latitude,
    required double longitude,
  }) async {
    barangayCalls++;
    lastBarangayLatitude = latitude;
    lastBarangayLongitude = longitude;
    if (barangayError != null) throw barangayError!;
    if (barangayHandler != null) {
      return barangayHandler!(latitude, longitude);
    }
    return barangayResult ?? sampleBarangayResolution();
  }

  @override
  void close() => closed = true;
}
