import 'verified_center.dart';

/// Public map reference. A startup marker has no user-distance measurement.
final class CenterMapRecord {
  CenterMapRecord({
    required this.publicIdentifier,
    required this.name,
    required this.address,
    required this.barangay,
    required this.latitude,
    required this.longitude,
    required this.verifiedOn,
    required this.sourceAttribution,
    required List<String> limitations,
    this.isDemonstration = false,
    this.distanceLabel,
  }) : limitations = List.unmodifiable(limitations);

  factory CenterMapRecord.fromVerifiedCenter(VerifiedCenter center) =>
      CenterMapRecord(
        publicIdentifier: center.publicIdentifier,
        name: center.name,
        address: center.address,
        barangay: center.barangay,
        latitude: center.latitude,
        longitude: center.longitude,
        verifiedOn: center.verifiedOn,
        sourceAttribution: center.sourceAttribution,
        limitations: center.limitations,
        isDemonstration: center.isDemonstration,
        distanceLabel: center.distanceLabel,
      );

  final String publicIdentifier;
  final String name;
  final String address;
  final CenterBarangayIdentity barangay;
  final double latitude;
  final double longitude;
  final DateTime? verifiedOn;
  final String sourceAttribution;
  final List<String> limitations;
  final bool isDemonstration;
  final String? distanceLabel;

  String get verificationLabel {
    if (isDemonstration) {
      return 'LOCAL TEST - not verified; not a real facility';
    }
    final date = verifiedOn!;
    return 'Verified on ${date.year.toString().padLeft(4, '0')}-'
        '${date.month.toString().padLeft(2, '0')}-'
        '${date.day.toString().padLeft(2, '0')}';
  }
}
