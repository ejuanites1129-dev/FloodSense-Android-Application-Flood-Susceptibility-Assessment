import 'package:flutter/foundation.dart';

import '../../data/dss/structured_dss_repository.dart';
import 'dss_assessment_context.dart';

class DssAnswer {
  const DssAnswer({required this.question, required this.option});
  final String question;
  final DssOption option;
}

class DssController extends ChangeNotifier {
  DssController(this.repository);
  final StructuredDssRepository repository;
  final List<DssStep> _history = [];
  final List<DssAnswer> _answers = [];
  DssAssessmentContext? assessmentContext;
  int _generation = 0;
  bool _disposed = false;
  String? get susceptibilityCode => assessmentContext?.susceptibilityCode;
  List<DssAnswer> get answers => List.unmodifiable(_answers);
  DssStep? current;
  DssStep? overview;
  bool householdCheckOpen = false;
  String? selectedOptionCode;
  String? error;
  bool busy = false;

  bool get canGoBack => _history.isNotEmpty;

  Future<void> start(DssAssessmentContext context) async {
    final generation = ++_generation;
    busy = true;
    error = null;
    _history.clear();
    _answers.clear();
    current = null;
    overview = null;
    householdCheckOpen = false;
    selectedOptionCode = null;
    assessmentContext = context;
    notifyListeners();
    try {
      final step = await repository.start(
        context.susceptibilityCode,
        operatingMode: context.operatingMode,
      );
      _validateMode(step, context);
      if (generation == _generation && !_disposed) {
        current = step;
        overview = step;
      }
    } catch (failure) {
      if (generation == _generation && !_disposed) {
        error = _errorMessage(failure);
      }
    } finally {
      if (generation == _generation && !_disposed) {
        busy = false;
        notifyListeners();
      }
    }
  }

  void select(String code) {
    if (busy ||
        !(current?.question?.options.any((option) => option.code == code) ??
            false)) {
      return;
    }
    selectedOptionCode = code;
    notifyListeners();
  }

  Future<void> continueFlow() async {
    final step = current;
    final option = selectedOptionCode;
    final context = assessmentContext;
    if (busy || step?.question == null || option == null || context == null) {
      return;
    }
    busy = true;
    final generation = _generation;
    error = null;
    notifyListeners();
    try {
      final next = await repository.answer(
        current: step!,
        susceptibilityCode: context.susceptibilityCode,
        operatingMode: context.operatingMode,
        optionCode: option,
      );
      _validateMode(next, context);
      if (generation != _generation || _disposed) return;
      _history.add(step);
      _answers.add(
        DssAnswer(
          question: step.question!.prompt,
          option: step.question!.options.firstWhere(
            (item) => item.code == option,
          ),
        ),
      );
      current = next;
      selectedOptionCode = null;
    } catch (failure) {
      if (generation == _generation && !_disposed) {
        error = _errorMessage(failure);
      }
    } finally {
      if (generation == _generation && !_disposed) {
        busy = false;
        notifyListeners();
      }
    }
  }

  void goBack() {
    if (_history.isEmpty || busy) return;
    current = _history.removeLast();
    selectedOptionCode = _answers.removeLast().option.code;
    error = null;
    notifyListeners();
  }

  Future<void> restart() async {
    final context = assessmentContext;
    final reopen = householdCheckOpen;
    if (context != null) {
      final request = start(context);
      final generation = _generation;
      await request;
      if (!_disposed &&
          generation == _generation &&
          assessmentContext == context &&
          current != null) {
        householdCheckOpen = reopen;
        notifyListeners();
      }
    }
  }

  void openHouseholdCheck() {
    if (current == null || busy) return;
    householdCheckOpen = true;
    notifyListeners();
  }

  void closeHouseholdCheck() {
    householdCheckOpen = false;
    notifyListeners();
  }

  void _validateMode(DssStep step, DssAssessmentContext context) {
    // Legacy contract responses omit mode; explicit v2 modes must agree with
    // the completed assessment instead of allowing a mixed-content guide.
    if (step.operatingMode.isNotEmpty &&
        step.operatingMode != context.operatingMode) {
      throw StateError(
        'Preparedness guidance is unavailable for this assessment mode.',
      );
    }
  }

  String _errorMessage(Object failure) => failure is StateError
      ? failure.message.toString()
      : 'Preparedness guidance is unavailable. Please try again.';

  void resetForScenarioChange() {
    ++_generation;
    _history.clear();
    _answers.clear();
    current = null;
    overview = null;
    householdCheckOpen = false;
    selectedOptionCode = null;
    assessmentContext = null;
    busy = false;
    error = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    super.dispose();
  }
}
