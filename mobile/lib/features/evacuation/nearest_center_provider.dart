import '../../data/models/verified_center.dart';

/// Replaceable boundary for the Stream C nearest-center service.
///
/// There is deliberately no production HTTP implementation until Stream C
/// publishes exact request, response, limit, and error contracts.
abstract interface class NearestCenterProvider {
  Future<List<VerifiedCenter>> findNearest({
    required double latitude,
    required double longitude,
  });
}

enum CenterLookupFailureKind {
  offline,
  timeout,
  serverUnavailable,
  malformedResponse,
  recoverable,
}

final class CenterLookupException implements Exception {
  const CenterLookupException(this.kind);

  final CenterLookupFailureKind kind;
}
