enum ApiFailureKind {
  validation,
  connectivity,
  timeout,
  service,
  malformedResponse,
}

class ApiException implements Exception {
  const ApiException(
    this.message, {
    required this.kind,
    this.fieldErrors = const {},
  });

  final String message;
  final ApiFailureKind kind;
  final Map<String, List<String>> fieldErrors;

  bool get canRetry => kind != ApiFailureKind.validation;

  @override
  String toString() => message;
}
