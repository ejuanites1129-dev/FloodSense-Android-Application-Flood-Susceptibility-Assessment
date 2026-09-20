/// Contract-neutral public center data used by the resident presentation layer.
///
/// Stream C must map its eventual frozen response into this model. This type
/// intentionally has no JSON parser so the mobile app cannot silently invent
/// or depend on an unfrozen wire contract.
final class VerifiedCenter {
  VerifiedCenter({
    required String publicIdentifier,
    required String name,
    required String address,
    required this.barangay,
    required this.latitude,
    required this.longitude,
    required this.approximateDistance,
    required this.distanceUnit,
    required this.verifiedOn,
    required String sourceAttribution,
    List<String> limitations = const [],
  }) : publicIdentifier = _requiredText(publicIdentifier, 'publicIdentifier'),
       name = _requiredText(name, 'name'),
       address = _requiredText(address, 'address'),
       sourceAttribution = _requiredText(
         sourceAttribution,
         'sourceAttribution',
       ),
       limitations = List.unmodifiable(
         limitations.map((value) => _requiredText(value, 'limitation')),
       ) {
    _coordinate(latitude, 'latitude', -90, 90);
    _coordinate(longitude, 'longitude', -180, 180);
    if (!approximateDistance.isFinite || approximateDistance < 0) {
      throw ArgumentError.value(
        approximateDistance,
        'approximateDistance',
        'must be finite and non-negative',
      );
    }
  }

  final String publicIdentifier;
  final String name;
  final String address;
  final CenterBarangayIdentity barangay;
  final double latitude;
  final double longitude;
  final double approximateDistance;
  final CenterDistanceUnit distanceUnit;
  final DateTime verifiedOn;
  final String sourceAttribution;
  final List<String> limitations;

  String get distanceLabel => switch (distanceUnit) {
    CenterDistanceUnit.meters =>
      '${approximateDistance.round()} m approximate straight-line distance',
    CenterDistanceUnit.kilometers =>
      '${_kilometerText(approximateDistance)} km approximate straight-line distance',
  };

  static String _kilometerText(double value) {
    final rounded = (value * 10).roundToDouble() / 10;
    return rounded == rounded.truncateToDouble()
        ? rounded.toStringAsFixed(0)
        : rounded.toStringAsFixed(1);
  }

  static String _requiredText(String value, String field) {
    final normalized = value.trim();
    if (normalized.isEmpty) {
      throw ArgumentError.value(value, field, 'must not be empty');
    }
    return normalized;
  }

  static void _coordinate(
    double value,
    String field,
    double minimum,
    double maximum,
  ) {
    if (!value.isFinite || value < minimum || value > maximum) {
      throw ArgumentError.value(
        value,
        field,
        'must be finite and between $minimum and $maximum',
      );
    }
  }
}

final class CenterBarangayIdentity {
  CenterBarangayIdentity({required String psgcCode, required String name})
    : psgcCode = _validatePsgc(psgcCode),
      name = _validateName(name);

  final String psgcCode;
  final String name;

  static String _validatePsgc(String value) {
    final normalized = value.trim();
    if (!RegExp(r'^\d{10}$').hasMatch(normalized)) {
      throw ArgumentError.value(
        value,
        'psgcCode',
        'must be a 10-digit PSGC code',
      );
    }
    return normalized;
  }

  static String _validateName(String value) {
    final normalized = value.trim();
    if (normalized.isEmpty) {
      throw ArgumentError.value(value, 'name', 'must not be empty');
    }
    return normalized;
  }
}

enum CenterDistanceUnit { meters, kilometers }
