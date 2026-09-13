import 'assessment_result.dart';
import 'json_parsing.dart';

class MapAreaAssessment {
  const MapAreaAssessment({
    required this.area,
    required this.state,
    required this.rawState,
    required this.susceptibility,
    required this.matchedRuleCodes,
    required this.ruleset,
    required this.summary,
  });

  final AreaSummary area;
  final AssessmentState state;
  final String rawState;
  final Susceptibility? susceptibility;
  final List<String> matchedRuleCodes;
  final RuleSetSummary? ruleset;
  final String summary;

  bool get isClassified => state == AssessmentState.classified;

  factory MapAreaAssessment.fromJson(Map<String, dynamic> json) {
    final rawState = requireString(json, 'assessment_state');
    final state = switch (rawState) {
      'CLASSIFIED' => AssessmentState.classified,
      'UNCERTAIN' => AssessmentState.uncertain,
      'INSUFFICIENT_DATA' => AssessmentState.insufficientData,
      _ => AssessmentState.unknown,
    };
    final susceptibilityJson = nullableMap(
      json['susceptibility'],
      'susceptibility',
    );
    final susceptibility = susceptibilityJson == null
        ? null
        : Susceptibility.fromJson(susceptibilityJson);
    if (state == AssessmentState.classified && susceptibility == null) {
      throw const ModelParsingException(
        'A classified map result requires susceptibility details.',
      );
    }
    if (state != AssessmentState.classified && susceptibility != null) {
      throw const ModelParsingException(
        'A map limitation cannot contain susceptibility details.',
      );
    }
    final rulesetJson = nullableMap(json['ruleset'], 'ruleset');
    return MapAreaAssessment(
      area: AreaSummary.fromJson(requireMap(json['area'], 'area')),
      state: state,
      rawState: rawState,
      susceptibility: susceptibility,
      matchedRuleCodes: requireStringList(
        json['matched_rule_codes'],
        'matched_rule_codes',
      ),
      ruleset: rulesetJson == null
          ? null
          : RuleSetSummary.fromJson(rulesetJson),
      summary: requireString(json, 'summary'),
    );
  }
}

class MapAssessmentResult {
  MapAssessmentResult({
    required this.scenario,
    required List<MapAreaAssessment> results,
    required this.operatingMode,
    required this.dataStatus,
    required this.warnings,
  }) : results = List.unmodifiable(results),
       resultsByAreaId = Map.unmodifiable({
         for (final result in results) result.area.id: result,
       });

  final ScenarioSummary scenario;
  final List<MapAreaAssessment> results;
  final Map<int, MapAreaAssessment> resultsByAreaId;
  final String operatingMode;
  final String dataStatus;
  final List<String> warnings;

  factory MapAssessmentResult.fromJson(Map<String, dynamic> json) =>
      MapAssessmentResult(
        scenario: ScenarioSummary.fromJson(
          requireMap(json['scenario'], 'scenario'),
        ),
        results: requireList(json['results'], 'results')
            .map(
              (item) => MapAreaAssessment.fromJson(requireMap(item, 'results')),
            )
            .toList(),
        operatingMode: requireString(json, 'operating_mode'),
        dataStatus: requireString(json, 'data_status'),
        warnings: requireStringList(json['warnings'], 'warnings'),
      );
}
