import 'package:flutter/foundation.dart';

import '../../data/dss/structured_dss_repository.dart';

class DssController extends ChangeNotifier {
  DssController(this.repository);
  final StructuredDssRepository repository;
  final List<DssStep> _history = [];
  String? susceptibilityCode;
  DssStep? current;
  String? selectedOptionCode;
  String? error;
  bool busy = false;

  bool get canGoBack => _history.isNotEmpty;

  Future<void> start(String code) async {
    if (busy) return;
    busy = true;
    error = null;
    _history.clear();
    selectedOptionCode = null;
    susceptibilityCode = code;
    notifyListeners();
    try {
      current = await repository.start(code);
    } catch (failure) {
      error = '$failure'.replaceFirst('Bad state: ', '');
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  void select(String code) {
    selectedOptionCode = code;
    notifyListeners();
  }

  Future<void> continueFlow() async {
    final step = current;
    final option = selectedOptionCode;
    final susceptibility = susceptibilityCode;
    if (busy ||
        step?.question == null ||
        option == null ||
        susceptibility == null) {
      return;
    }
    busy = true;
    error = null;
    notifyListeners();
    try {
      final next = await repository.answer(
        current: step!,
        susceptibilityCode: susceptibility,
        optionCode: option,
      );
      _history.add(step);
      current = next;
      selectedOptionCode = null;
    } catch (failure) {
      error = '$failure'.replaceFirst('Bad state: ', '');
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  void goBack() {
    if (_history.isEmpty || busy) return;
    current = _history.removeLast();
    selectedOptionCode = null;
    error = null;
    notifyListeners();
  }

  Future<void> restart() async {
    final code = susceptibilityCode;
    if (code != null) await start(code);
  }

  void resetForScenarioChange() {
    _history.clear();
    current = null;
    selectedOptionCode = null;
    susceptibilityCode = null;
    error = null;
    notifyListeners();
  }
}
