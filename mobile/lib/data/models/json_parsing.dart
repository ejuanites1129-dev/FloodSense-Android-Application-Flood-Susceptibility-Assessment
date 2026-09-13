class ModelParsingException implements FormatException {
  const ModelParsingException(this.message);

  @override
  final String message;

  @override
  int? get offset => null;

  @override
  dynamic get source => null;

  @override
  String toString() => 'ModelParsingException: $message';
}

Map<String, dynamic> requireMap(Object? value, String field) {
  if (value is! Map) {
    throw ModelParsingException('Expected "$field" to be an object.');
  }
  return value.map((key, item) => MapEntry(key.toString(), item));
}

Map<String, dynamic>? nullableMap(Object? value, String field) {
  if (value == null) return null;
  return requireMap(value, field);
}

List<dynamic> requireList(Object? value, String field) {
  if (value is! List) {
    throw ModelParsingException('Expected "$field" to be an array.');
  }
  return value;
}

String requireString(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! String || value.trim().isEmpty) {
    throw ModelParsingException('Expected "$field" to be a non-empty string.');
  }
  return value;
}

String? nullableString(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) return null;
  if (value is! String) {
    throw ModelParsingException('Expected "$field" to be a string or null.');
  }
  return value;
}

int requireInt(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! int) {
    throw ModelParsingException('Expected "$field" to be an integer.');
  }
  return value;
}

num requireNumber(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! num || !value.isFinite) {
    throw ModelParsingException('Expected "$field" to be a finite number.');
  }
  return value;
}

List<String> requireStringList(Object? value, String field) {
  final list = requireList(value, field);
  if (list.any((item) => item is! String)) {
    throw ModelParsingException('Expected "$field" to contain only strings.');
  }
  return List.unmodifiable(list.cast<String>());
}
