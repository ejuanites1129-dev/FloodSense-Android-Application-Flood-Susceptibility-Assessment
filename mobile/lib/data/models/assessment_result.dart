import 'dart:collection';

import 'guidance_item.dart';
import 'json_parsing.dart';

enum AssessmentState { classified, uncertain, insufficientData, unknown }

class Susceptibility {
  const Susceptibility({
    required this.code,
    required this.label,
    required this.mapColor,
  });

  static const neutralColorValue = 0xFF8791A1;

  final String code;
  final String label;
  final String mapColor;

  int get colorValue {
    final match = RegExp(r'^#([0-9A-Fa-f]{6})$').firstMatch(mapColor.trim());
    if (match == null) return neutralColorValue;
    return 0xFF000000 | int.parse(match.group(1)!, radix: 16);
  }

  factory Susceptibility.fromJson(Map<String, dynamic> json) => Susceptibility(
    code: requireString(json, 'code'),
    label: requireString(json, 'label'),
    mapColor: requireString(json, 'map_color'),
  );
}

class AreaSummary {
  const AreaSummary({required this.id, required this.code, required this.name});

  final int id;
  final String code;
  final String name;

  factory AreaSummary.fromJson(Map<String, dynamic> json) => AreaSummary(
    id: requireInt(json, 'id'),
    code: requireString(json, 'code'),
    name: requireString(json, 'name'),
  );
}

class ScenarioSummary {
  const ScenarioSummary({
    required this.rainfallIntensityCode,
    required this.rainfallDurationCode,
  });

  final String rainfallIntensityCode;
  final String rainfallDurationCode;

  factory ScenarioSummary.fromJson(Map<String, dynamic> json) =>
      ScenarioSummary(
        rainfallIntensityCode: requireString(json, 'rainfall_intensity_code'),
        rainfallDurationCode: requireString(json, 'rainfall_duration_code'),
      );
}

class AssessmentExplanation {
  const AssessmentExplanation({
    required this.summary,
    required this.matchedRuleCodes,
    required this.factsUsed,
    required this.ruleRationales,
    required this.ruleset,
    required this.warnings,
  });

  final String summary;
  final List<String> matchedRuleCodes;
  final List<String> factsUsed;
  final List<String> ruleRationales;
  final String? ruleset;
  final List<String> warnings;

  factory AssessmentExplanation.fromJson(Map<String, dynamic> json) {
    return AssessmentExplanation(
      summary: requireString(json, 'summary'),
      matchedRuleCodes: requireStringList(
        json['matched_rule_codes'],
        'explanation.matched_rule_codes',
      ),
      factsUsed: requireStringList(
        json['facts_used'],
        'explanation.facts_used',
      ),
      ruleRationales: requireStringList(
        json['rule_rationales'],
        'explanation.rule_rationales',
      ),
      ruleset: nullableString(json, 'ruleset'),
      warnings: requireStringList(json['warnings'], 'explanation.warnings'),
    );
  }
}

class RuleSetSummary {
  const RuleSetSummary({required this.name, required this.version});

  final String name;
  final String version;

  factory RuleSetSummary.fromJson(Map<String, dynamic> json) => RuleSetSummary(
    name: requireString(json, 'name'),
    version: requireString(json, 'version'),
  );
}

class AssessmentResult {
  AssessmentResult({
    required this.state,
    required this.rawState,
    required this.susceptibility,
    required this.area,
    required this.scenario,
    required Map<String, dynamic> facts,
    required this.matchedRuleCodes,
    required this.explanation,
    required this.ruleset,
    required this.guidance,
    required this.operatingMode,
    required this.dataStatus,
    required this.warnings,
  }) : facts = UnmodifiableMapView(facts);

  final AssessmentState state;
  final String rawState;
  final Susceptibility? susceptibility;
  final AreaSummary area;
  final ScenarioSummary scenario;
  final Map<String, dynamic> facts;
  final List<String> matchedRuleCodes;
  final AssessmentExplanation explanation;
  final RuleSetSummary? ruleset;
  final List<GuidanceItem> guidance;
  final String operatingMode;
  final String dataStatus;
  final List<String> warnings;

  bool get isClassified => state == AssessmentState.classified;

  factory AssessmentResult.fromJson(Map<String, dynamic> json) {
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
        'A classified result requires susceptibility details.',
      );
    }
    if (state != AssessmentState.classified && susceptibility != null) {
      throw const ModelParsingException(
        'A limitation result cannot contain susceptibility details.',
      );
    }

    final rulesetJson = nullableMap(json['ruleset'], 'ruleset');
    return AssessmentResult(
      state: state,
      rawState: rawState,
      susceptibility: susceptibility,
      area: AreaSummary.fromJson(requireMap(json['area'], 'area')),
      scenario: ScenarioSummary.fromJson(
        requireMap(json['scenario'], 'scenario'),
      ),
      facts: Map.unmodifiable(requireMap(json['facts'], 'facts')),
      matchedRuleCodes: requireStringList(
        json['matched_rule_codes'],
        'matched_rule_codes',
      ),
      explanation: AssessmentExplanation.fromJson(
        requireMap(json['explanation'], 'explanation'),
      ),
      ruleset: rulesetJson == null
          ? null
          : RuleSetSummary.fromJson(rulesetJson),
      guidance: List.unmodifiable(
        requireList(
          json['guidance'],
          'guidance',
        ).map((item) => GuidanceItem.fromJson(requireMap(item, 'guidance'))),
      ),
      operatingMode: requireString(json, 'operating_mode'),
      dataStatus: requireString(json, 'data_status'),
      warnings: requireStringList(json['warnings'], 'warnings'),
    );
  }
}
