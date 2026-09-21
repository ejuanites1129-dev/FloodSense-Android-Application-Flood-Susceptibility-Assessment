import 'json_parsing.dart';
import 'verified_center.dart';

const nearestCenterDistanceMethod = 'APPROXIMATE_STRAIGHT_LINE';
const nearestCenterDistanceWarning =
    'Distances are approximate straight-line measurements. They do not '
    'represent road distance, route safety, accessibility, availability, or '
    'an evacuation recommendation.';
const nearestCenterEmptyWarning =
    'No eligible verified evacuation centers are currently available for '
    'this location.';
const nearestCenterEmptyDistanceWarning =
    'Distances, when available, are approximate straight-line measurements '
    'and are not route-safety recommendations.';
const nearestCenterVerificationLimitation =
    'Verification does not confirm current opening, accessibility, capacity, '
    'or route safety.';
const nearestCenterReferenceWarning =
    'DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED';
const nearestCenterBoundaryLimitation =
    'Administrative boundaries only; they do not indicate flood '
    'susceptibility or current conditions.';

/// Complete, validated response from the frozen nearest-center endpoint.
final class NearestCenterResult {
  NearestCenterResult({
    required List<VerifiedCenter> centers,
    required this.distanceMethod,
    required List<String> warnings,
  }) : centers = List.unmodifiable(centers),
       warnings = List.unmodifiable(warnings);

  factory NearestCenterResult.fromJson(
    Map<String, dynamic> json, {
    int requestedLimit = 3,
  }) {
    if (requestedLimit < 1 || requestedLimit > 10) {
      throw const ModelParsingException('Invalid requested center limit.');
    }
    _requireExactKeys(json, const {
      'centers',
      'distance_method',
      'warnings',
    }, 'nearest-center response');

    final distanceMethod = _strictText(json, 'distance_method');
    if (distanceMethod != nearestCenterDistanceMethod) {
      throw const ModelParsingException('Unknown distance method.');
    }

    final centerItems = requireList(json['centers'], 'centers');
    if (centerItems.length > requestedLimit || centerItems.length > 10) {
      throw const ModelParsingException('Too many centers in response.');
    }
    final centers = centerItems
        .map((item) => _parseCenter(requireMap(item, 'center')))
        .toList(growable: false);
    if (centers.map((item) => item.publicIdentifier).toSet().length !=
        centers.length) {
      throw const ModelParsingException('Duplicate center identifier.');
    }

    final warnings = _strictTextList(json['warnings'], 'warnings');
    final expectedWarnings = centers.isEmpty
        ? const [nearestCenterEmptyWarning, nearestCenterEmptyDistanceWarning]
        : const [nearestCenterDistanceWarning];
    if (!_sameStrings(warnings, expectedWarnings)) {
      throw const ModelParsingException('Unexpected nearest-center warnings.');
    }

    return NearestCenterResult(
      centers: centers,
      distanceMethod: distanceMethod,
      warnings: warnings,
    );
  }

  final List<VerifiedCenter> centers;
  final String distanceMethod;
  final List<String> warnings;
}

VerifiedCenter _parseCenter(Map<String, dynamic> json) {
  _requireExactKeys(json, const {
    'public_identifier',
    'name',
    'address',
    'barangay',
    'latitude',
    'longitude',
    'approximate_distance',
    'distance_unit',
    'verified_on',
    'source_attribution',
    'limitations',
  }, 'center');

  final identifier = _strictText(json, 'public_identifier');
  if (!RegExp(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
  ).hasMatch(identifier)) {
    throw const ModelParsingException('Invalid center public identifier.');
  }

  final barangayJson = requireMap(json['barangay'], 'barangay');
  _requireExactKeys(barangayJson, const {'psgc_code', 'name'}, 'barangay');
  final psgcCode = _strictText(barangayJson, 'psgc_code');
  if (!RegExp(r'^[0-9]{10}$').hasMatch(psgcCode)) {
    throw const ModelParsingException('Invalid barangay PSGC code.');
  }

  final latitude = _finiteNumber(json, 'latitude');
  final longitude = _finiteNumber(json, 'longitude');
  final distance = _finiteNumber(json, 'approximate_distance');
  if (latitude < -90 || latitude > 90) {
    throw const ModelParsingException('Invalid center latitude.');
  }
  if (longitude < -180 || longitude > 180) {
    throw const ModelParsingException('Invalid center longitude.');
  }
  if (distance < 0) {
    throw const ModelParsingException('Invalid approximate distance.');
  }
  if (_strictText(json, 'distance_unit') != 'meters') {
    throw const ModelParsingException('Unknown center distance unit.');
  }

  final limitations = _strictTextList(json['limitations'], 'limitations');
  const requiredLimitations = [
    nearestCenterVerificationLimitation,
    nearestCenterReferenceWarning,
    nearestCenterBoundaryLimitation,
  ];
  if (limitations.length < requiredLimitations.length ||
      !_sameStrings(
        limitations.take(requiredLimitations.length).toList(),
        requiredLimitations,
      ) ||
      limitations.toSet().length != limitations.length) {
    throw const ModelParsingException('Invalid center limitations.');
  }

  try {
    return VerifiedCenter(
      publicIdentifier: identifier,
      name: _strictText(json, 'name'),
      address: _strictText(json, 'address'),
      barangay: CenterBarangayIdentity(
        psgcCode: psgcCode,
        name: _strictText(barangayJson, 'name'),
      ),
      latitude: latitude,
      longitude: longitude,
      approximateDistance: distance,
      distanceUnit: CenterDistanceUnit.meters,
      verifiedOn: _strictDate(json, 'verified_on'),
      sourceAttribution: _strictText(json, 'source_attribution'),
      limitations: limitations,
    );
  } on ArgumentError {
    throw const ModelParsingException('Invalid center data.');
  }
}

String _strictText(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! String ||
      value.isEmpty ||
      value.trim() != value ||
      RegExp(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]').hasMatch(value)) {
    throw ModelParsingException('Invalid "$field" text.');
  }
  return value;
}

List<String> _strictTextList(Object? value, String field) {
  final list = requireList(value, field);
  final result = <String>[];
  for (final item in list) {
    if (item is! String) {
      throw ModelParsingException('Invalid "$field" text list.');
    }
    final wrapper = <String, dynamic>{field: item};
    result.add(_strictText(wrapper, field));
  }
  return List.unmodifiable(result);
}

double _finiteNumber(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! num || !value.isFinite) {
    throw ModelParsingException('Invalid "$field" number.');
  }
  return value.toDouble();
}

DateTime _strictDate(Map<String, dynamic> json, String field) {
  final value = _strictText(json, field);
  final match = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(value);
  if (match == null) {
    throw ModelParsingException('Invalid "$field" date.');
  }
  final year = int.parse(match.group(1)!);
  final month = int.parse(match.group(2)!);
  final day = int.parse(match.group(3)!);
  final parsed = DateTime.utc(year, month, day);
  if (parsed.year != year || parsed.month != month || parsed.day != day) {
    throw ModelParsingException('Invalid "$field" date.');
  }
  return parsed;
}

void _requireExactKeys(
  Map<String, dynamic> json,
  Set<String> expected,
  String context,
) {
  final actual = json.keys.toSet();
  if (actual.length != expected.length || !actual.containsAll(expected)) {
    throw ModelParsingException('Unexpected fields in $context.');
  }
}

bool _sameStrings(List<String> actual, List<String> expected) {
  if (actual.length != expected.length) return false;
  for (var index = 0; index < actual.length; index++) {
    if (actual[index] != expected[index]) return false;
  }
  return true;
}
