class AssessmentRequest {
  const AssessmentRequest({
    required this.geographicAreaId,
    required this.rainfallIntensityCode,
    required this.rainfallDurationCode,
    this.mode = 'demonstration',
  });

  final int geographicAreaId;
  final String rainfallIntensityCode;
  final String rainfallDurationCode;
  final String mode;

  Map<String, dynamic> toJson() => {
    'mode': mode,
    'geographic_area_id': geographicAreaId,
    'rainfall_intensity_code': rainfallIntensityCode,
    'rainfall_duration_code': rainfallDurationCode,
  };
}
