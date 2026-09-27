import 'package:flutter_test/flutter_test.dart';
import 'package:floodsense/data/models/assessment_result.dart';
import 'package:floodsense/data/models/map_assessment_result.dart';
import 'package:floodsense/features/map/flood_map_palette.dart';

void main() {
  test('uses the backend map color for classified scenario output', () {
    const result = MapAreaAssessment(
      area: AreaSummary(id: 1, code: 'TEST', name: 'Test area'),
      state: AssessmentState.classified,
      rawState: 'CLASSIFIED',
      susceptibility: Susceptibility(
        code: 'HIGH',
        label: 'High',
        mapColor: '#123456',
      ),
      matchedRuleCodes: [],
      ruleset: null,
      summary: 'Test only',
    );

    expect(
      FloodMapPalette.cssHex(FloodMapPalette.forAssessment(result)),
      '#123456',
    );
  });

  test('uses the neutral limitation color when no classification exists', () {
    expect(
      FloodMapPalette.cssHex(FloodMapPalette.forAssessment(null)),
      '#8791A1',
    );
  });
}
