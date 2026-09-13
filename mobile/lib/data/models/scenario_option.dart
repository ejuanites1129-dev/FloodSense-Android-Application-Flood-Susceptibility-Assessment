import 'json_parsing.dart';

class ScenarioOption {
  const ScenarioOption({
    required this.id,
    required this.category,
    required this.code,
    required this.label,
    required this.derivedValue,
    required this.unit,
    required this.displayOrder,
    required this.dataStatus,
  });

  final int id;
  final String category;
  final String code;
  final String label;
  final num? derivedValue;
  final String? unit;
  final int displayOrder;
  final String dataStatus;

  factory ScenarioOption.fromJson(Map<String, dynamic> json) {
    final derivedValue = json['derived_value'];
    if (derivedValue != null && derivedValue is! num) {
      throw const ModelParsingException(
        'Expected "derived_value" to be numeric or null.',
      );
    }
    return ScenarioOption(
      id: requireInt(json, 'id'),
      category: requireString(json, 'category'),
      code: requireString(json, 'code'),
      label: requireString(json, 'label'),
      derivedValue: derivedValue as num?,
      unit: nullableString(json, 'unit'),
      displayOrder: requireInt(json, 'display_order'),
      dataStatus: requireString(json, 'data_status'),
    );
  }
}

class AssessmentOptions {
  const AssessmentOptions({
    required this.intensityOptions,
    required this.durationOptions,
    required this.operatingMode,
    required this.dataStatus,
    required this.warnings,
  });

  final List<ScenarioOption> intensityOptions;
  final List<ScenarioOption> durationOptions;
  final String operatingMode;
  final String dataStatus;
  final List<String> warnings;

  factory AssessmentOptions.fromJson(Map<String, dynamic> json) {
    return AssessmentOptions(
      intensityOptions: _parseOptions(
        json['intensity_options'],
        'intensity_options',
      ),
      durationOptions: _parseOptions(
        json['duration_options'],
        'duration_options',
      ),
      operatingMode: requireString(json, 'operating_mode'),
      dataStatus: requireString(json, 'data_status'),
      warnings: requireStringList(json['warnings'], 'warnings'),
    );
  }

  static List<ScenarioOption> _parseOptions(Object? value, String field) {
    return List.unmodifiable(
      requireList(
        value,
        field,
      ).map((item) => ScenarioOption.fromJson(requireMap(item, field))),
    );
  }
}
