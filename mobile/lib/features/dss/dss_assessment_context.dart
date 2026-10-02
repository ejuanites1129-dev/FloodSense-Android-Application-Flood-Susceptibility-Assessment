import '../../data/models/assessment_result.dart';
import '../../data/models/scenario_option.dart';

/// A snapshot of one completed assessment, independent of later form choices.
class DssAssessmentContext {
  const DssAssessmentContext({
    required this.susceptibilityCode,
    required this.susceptibilityLabel,
    required this.operatingMode,
    required this.areaCode,
    required this.areaName,
    required this.intensityCode,
    required this.intensityLabel,
    required this.durationCode,
    required this.durationLabel,
    required this.dataStatus,
    this.rulesetName = '',
    this.rulesetVersion = '',
  });

  final String susceptibilityCode;
  final String susceptibilityLabel;
  final String operatingMode;
  final String areaCode;
  final String areaName;
  final String intensityCode;
  final String intensityLabel;
  final String durationCode;
  final String durationLabel;
  final String dataStatus;
  final String rulesetName;
  final String rulesetVersion;

  factory DssAssessmentContext.fromAssessment(
    AssessmentResult result, {
    required List<ScenarioOption> intensities,
    required List<ScenarioOption> durations,
  }) {
    if (!result.isClassified || result.susceptibility == null) {
      throw StateError('Preparedness requires a classified assessment.');
    }
    String label(List<ScenarioOption> options, String code) =>
        options
            .where((option) => option.code == code)
            .map((option) => option.label)
            .firstOrNull ??
        code;
    return DssAssessmentContext(
      susceptibilityCode: result.susceptibility!.code,
      susceptibilityLabel: result.susceptibility!.label,
      operatingMode: result.operatingMode,
      areaCode: result.area.code,
      areaName: result.area.name,
      intensityCode: result.scenario.rainfallIntensityCode,
      intensityLabel: label(intensities, result.scenario.rainfallIntensityCode),
      durationCode: result.scenario.rainfallDurationCode,
      durationLabel: label(durations, result.scenario.rainfallDurationCode),
      dataStatus: result.dataStatus,
      rulesetName: result.ruleset?.name ?? '',
      rulesetVersion: result.ruleset?.version ?? '',
    );
  }

  @override
  bool operator ==(Object other) =>
      other is DssAssessmentContext &&
      susceptibilityCode == other.susceptibilityCode &&
      susceptibilityLabel == other.susceptibilityLabel &&
      operatingMode == other.operatingMode &&
      areaCode == other.areaCode &&
      areaName == other.areaName &&
      intensityCode == other.intensityCode &&
      intensityLabel == other.intensityLabel &&
      durationCode == other.durationCode &&
      durationLabel == other.durationLabel &&
      dataStatus == other.dataStatus &&
      rulesetName == other.rulesetName &&
      rulesetVersion == other.rulesetVersion;

  @override
  int get hashCode => Object.hash(
    susceptibilityCode,
    susceptibilityLabel,
    operatingMode,
    areaCode,
    areaName,
    intensityCode,
    intensityLabel,
    durationCode,
    durationLabel,
    dataStatus,
    rulesetName,
    rulesetVersion,
  );
}
