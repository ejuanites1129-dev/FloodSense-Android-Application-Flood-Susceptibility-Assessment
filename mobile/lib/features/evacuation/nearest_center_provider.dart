import '../../data/models/nearest_center_result.dart';

/// Replaceable boundary for the Stream C nearest-center service.
///
abstract interface class NearestCenterProvider {
  Future<NearestCenterResult> findNearest({
    required double latitude,
    required double longitude,
  });
}

enum CenterLookupFailureKind {
  offline,
  timeout,
  serverUnavailable,
  malformedResponse,
  requestRejected,
  rateLimited,
  recoverable,
}

final class CenterLookupException implements Exception {
  const CenterLookupException(this.kind, {this.retryAfter});

  final CenterLookupFailureKind kind;
  final Duration? retryAfter;
}
