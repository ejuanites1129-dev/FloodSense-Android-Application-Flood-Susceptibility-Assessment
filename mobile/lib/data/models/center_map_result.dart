import 'center_map_record.dart';
import 'json_parsing.dart';
import 'nearest_center_result.dart';
import 'verified_center.dart';

const centerMapWarning =
    'Evacuation-center reference information only. This map does not confirm '
    'that a center is open, available, reachable, or safe.';
const centerMapEmptyWarning =
    'No eligible verified evacuation-center information is available for this map.';
const centerMapLocalEmptyWarning =
    'No locally approved temporary evacuation-center records are available for this map.';
const centerMapLimitWarning =
    'Only the first 1,000 eligible centers are shown. Other eligible centers may exist.';
const centerMapNearbyLimitWarning =
    'Only the 25 nearest eligible centers around the map pin are shown. '
    'Other centers remain hidden until the pin location changes.';

final class CenterMapResult {
  CenterMapResult({
    required List<CenterMapRecord> centers,
    required List<String> warnings,
    required this.hasMore,
    this.isDemonstration = false,
  }) : centers = List.unmodifiable(centers),
       warnings = List.unmodifiable(warnings);

  factory CenterMapResult.fromJson(
    Map<String, dynamic> json, {
    bool localTesting = false,
    bool nearby = false,
  }) {
    _keys(json, {
      'centers',
      'warnings',
      'has_more',
      if (localTesting) 'data_status',
    });
    if (localTesting && json['data_status'] != 'DEMONSTRATION') {
      _invalid();
    }
    final hasMore = json['has_more'];
    if (hasMore is! bool) {
      _invalid();
    }
    final items = requireList(json['centers'], 'centers');
    final maximum = nearby ? 25 : 1000;
    if (items.length > maximum || (hasMore && items.length != maximum)) {
      _invalid();
    }
    final centers = items
        .map((item) {
          final row = requireMap(item, 'center');
          _keys(row, {
            'public_identifier',
            'name',
            'address',
            'barangay',
            'latitude',
            'longitude',
            'verified_on',
            'source_attribution',
            'limitations',
            if (localTesting) 'data_status',
          });
          final identifier = _text(row['public_identifier']);
          if (!RegExp(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
          ).hasMatch(identifier)) {
            _invalid();
          }
          final barangay = requireMap(row['barangay'], 'barangay');
          _keys(barangay, {'psgc_code', 'name'});
          final psgc = _text(barangay['psgc_code']);
          if (!RegExp(r'^\d{10}$').hasMatch(psgc)) {
            _invalid();
          }
          final latitude = row['latitude'];
          final longitude = row['longitude'];
          if (latitude is! num ||
              !latitude.isFinite ||
              latitude < -90 ||
              latitude > 90 ||
              longitude is! num ||
              !longitude.isFinite ||
              longitude < -180 ||
              longitude > 180) {
            _invalid();
          }
          DateTime? date;
          if (localTesting) {
            if (row['data_status'] != 'DEMONSTRATION' ||
                row['verified_on'] != null) {
              _invalid();
            }
          } else {
            final value = _text(row['verified_on']);
            if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
              _invalid();
            }
            date = DateTime.tryParse(value);
            if (date == null ||
                date.year < 1 ||
                date.toIso8601String().substring(0, 10) != value) {
              _invalid();
            }
          }
          final limits = _texts(row['limitations']);
          final prefix = [
            localTesting
                ? localCenterPreviewWarning
                : nearestCenterVerificationLimitation,
            nearestCenterReferenceWarning,
            nearestCenterBoundaryLimitation,
          ];
          if (limits.length < prefix.length ||
              !_same(limits.take(prefix.length).toList(), prefix) ||
              limits.toSet().length != limits.length) {
            _invalid();
          }
          return CenterMapRecord(
            publicIdentifier: identifier,
            name: _boundedText(row['name'], 180),
            address: _text(row['address']),
            barangay: CenterBarangayIdentity(
              psgcCode: psgc,
              name: _boundedText(barangay['name'], 160),
            ),
            latitude: latitude.toDouble(),
            longitude: longitude.toDouble(),
            verifiedOn: date,
            sourceAttribution: _boundedText(row['source_attribution'], 200),
            limitations: limits,
            isDemonstration: localTesting,
          );
        })
        .toList(growable: false);
    if (centers.map((center) => center.publicIdentifier).toSet().length !=
        centers.length) {
      _invalid();
    }
    final warnings = _texts(json['warnings']);
    final expected = [
      if (localTesting) localCenterPreviewWarning,
      if (centers.isEmpty)
        localTesting ? centerMapLocalEmptyWarning : centerMapEmptyWarning,
      centerMapWarning,
      if (hasMore) nearby ? centerMapNearbyLimitWarning : centerMapLimitWarning,
    ];
    if (!_same(warnings, expected)) {
      _invalid();
    }
    return CenterMapResult(
      centers: centers,
      warnings: warnings,
      hasMore: hasMore,
      isDemonstration: localTesting,
    );
  }

  final List<CenterMapRecord> centers;
  final List<String> warnings;
  final bool hasMore;
  final bool isDemonstration;
}

Never _invalid() =>
    throw const ModelParsingException('Invalid evacuation map response.');
void _keys(Map<String, dynamic> value, Set<String> expected) {
  if (value.length != expected.length || !value.keys.every(expected.contains)) {
    _invalid();
  }
}

String _text(Object? value) {
  if (value is! String ||
      value.isEmpty ||
      value.trim() != value ||
      RegExp(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]').hasMatch(value)) {
    _invalid();
  }
  return value;
}

List<String> _texts(Object? value) =>
    requireList(value, 'text list').map(_text).toList(growable: false);
String _boundedText(Object? value, int maximum) {
  final text = _text(value);
  if (text.runes.length > maximum) {
    _invalid();
  }
  return text;
}

bool _same(List<String> a, List<String> b) =>
    a.length == b.length &&
    List.generate(
      a.length,
      (index) => a[index] == b[index],
    ).every((same) => same);
