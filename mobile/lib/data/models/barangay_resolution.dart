import 'json_parsing.dart';

enum BarangayResolutionState {
  resolved,
  outsideBacoor,
  ambiguousBoundary,
  unavailable,
}

abstract final class BarangayResolutionContract {
  static const boundaryWarning =
      'DERIVED ADMINISTRATIVE REFERENCE—NOT CITY-VERIFIED';
  static const boundaryLimitation =
      'Administrative boundaries only; they do not indicate flood susceptibility or current conditions.';
}

class ResolverCoordinate {
  const ResolverCoordinate({
    required this.latitude,
    required this.longitude,
    required this.precisionDecimalPlaces,
  });

  final double latitude;
  final double longitude;
  final int precisionDecimalPlaces;

  factory ResolverCoordinate.fromJson(Map<String, dynamic> json) {
    final latitude = requireNumber(json, 'latitude').toDouble();
    final longitude = requireNumber(json, 'longitude').toDouble();
    final precision = requireInt(json, 'precision_decimal_places');
    if (latitude < -90 || latitude > 90) {
      throw const ModelParsingException(
        'Resolver latitude is outside -90..90.',
      );
    }
    if (longitude < -180 || longitude > 180) {
      throw const ModelParsingException(
        'Resolver longitude is outside -180..180.',
      );
    }
    if (precision != 5) {
      throw const ModelParsingException(
        'Resolver coordinate precision does not match the frozen contract.',
      );
    }
    return ResolverCoordinate(
      latitude: latitude,
      longitude: longitude,
      precisionDecimalPlaces: precision,
    );
  }
}

class BarangayIdentity {
  BarangayIdentity({required this.psgcCode, required String name})
    : name = name.trim() {
    if (!RegExp(r'^\d{10}$').hasMatch(psgcCode)) {
      throw const ModelParsingException(
        'Expected a ten-digit barangay PSGC code.',
      );
    }
    if (this.name.isEmpty) {
      throw const ModelParsingException('Expected a barangay display name.');
    }
  }

  final String psgcCode;
  final String name;

  String get geographicAreaCode => 'PSGC_$psgcCode';

  factory BarangayIdentity.fromJson(Map<String, dynamic> json) =>
      BarangayIdentity(
        psgcCode: requireString(json, 'psgc_code'),
        name: requireString(json, 'name'),
      );
}

class BoundaryReference {
  BoundaryReference({
    required this.layerKind,
    required this.dataStatus,
    required this.sourceStatus,
    required this.cityVerified,
  }) {
    if (layerKind != 'ADMINISTRATIVE_REFERENCE' ||
        dataStatus != 'PENDING_VALIDATION' ||
        sourceStatus != 'PENDING_VALIDATION' ||
        cityVerified) {
      throw const ModelParsingException(
        'Resolver boundary metadata does not match the pending-validation contract.',
      );
    }
  }

  final String layerKind;
  final String dataStatus;
  final String sourceStatus;
  final bool cityVerified;

  factory BoundaryReference.fromJson(Map<String, dynamic> json) {
    final cityVerified = json['city_verified'];
    if (cityVerified is! bool) {
      throw const ModelParsingException(
        'Expected "city_verified" to be a boolean.',
      );
    }
    return BoundaryReference(
      layerKind: requireString(json, 'layer_kind'),
      dataStatus: requireString(json, 'data_status'),
      sourceStatus: requireString(json, 'source_status'),
      cityVerified: cityVerified,
    );
  }
}

class BarangayResolution {
  BarangayResolution({
    required this.state,
    required this.coordinate,
    required this.barangay,
    required this.boundary,
    required this.limitations,
  }) {
    final hasBarangay = barangay != null;
    if ((state == BarangayResolutionState.resolved) != hasBarangay) {
      throw const ModelParsingException(
        'Only a resolved response may contain a barangay identity.',
      );
    }
    if (limitations.isEmpty ||
        limitations.any((limitation) => limitation.trim().isEmpty)) {
      throw const ModelParsingException(
        'Resolver responses require non-empty boundary limitations.',
      );
    }
    final limitationSet = limitations.toSet();
    if (!limitationSet.contains(BarangayResolutionContract.boundaryWarning) ||
        !limitationSet.contains(
          BarangayResolutionContract.boundaryLimitation,
        )) {
      throw const ModelParsingException(
        'Resolver response is missing the required boundary limitations.',
      );
    }
  }

  final BarangayResolutionState state;
  final ResolverCoordinate coordinate;
  final BarangayIdentity? barangay;
  final BoundaryReference boundary;
  final List<String> limitations;

  factory BarangayResolution.fromJson(Map<String, dynamic> json) {
    final rawState = requireString(json, 'resolution_state');
    final state = switch (rawState) {
      'RESOLVED' => BarangayResolutionState.resolved,
      'OUTSIDE_BACOOR' => BarangayResolutionState.outsideBacoor,
      'AMBIGUOUS_BOUNDARY' => BarangayResolutionState.ambiguousBoundary,
      'UNAVAILABLE' => BarangayResolutionState.unavailable,
      _ => throw const ModelParsingException(
        'Unsupported barangay resolution state.',
      ),
    };
    final barangayJson = nullableMap(json['barangay'], 'barangay');
    return BarangayResolution(
      state: state,
      coordinate: ResolverCoordinate.fromJson(
        requireMap(json['coordinate'], 'coordinate'),
      ),
      barangay: barangayJson == null
          ? null
          : BarangayIdentity.fromJson(barangayJson),
      boundary: BoundaryReference.fromJson(
        requireMap(json['boundary'], 'boundary'),
      ),
      limitations: requireStringList(json['limitations'], 'limitations'),
    );
  }
}
