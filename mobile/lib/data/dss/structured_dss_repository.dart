import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../../config/api_config.dart';

class DssOption {
  const DssOption({
    required this.code,
    required this.label,
    required this.supportingText,
  });
  final String code;
  final String label;
  final String supportingText;
}

class DssQuestion {
  const DssQuestion({
    required this.code,
    required this.prompt,
    required this.explanation,
    required this.options,
  });
  final String code;
  final String prompt;
  final String explanation;
  final List<DssOption> options;
}

class DssOutcome {
  const DssOutcome({
    required this.title,
    required this.instruction,
    required this.warning,
    required this.source,
  });
  final String title;
  final String instruction;
  final String warning;
  final String source;
}

class DssStep {
  const DssStep({
    required this.flowCode,
    required this.flowVersion,
    required this.title,
    required this.dataStatus,
    required this.warning,
    required this.position,
    required this.total,
    this.question,
    this.outcome,
  });
  final String flowCode;
  final String flowVersion;
  final String title;
  final String dataStatus;
  final String warning;
  final int position;
  final int total;
  final DssQuestion? question;
  final DssOutcome? outcome;
  bool get isOutcome => outcome != null;

  factory DssStep.fromJson(Map<String, dynamic> json) {
    final flow = Map<String, dynamic>.from(json['flow'] as Map);
    final progress = json['progress'] == null
        ? const <String, dynamic>{}
        : Map<String, dynamic>.from(json['progress'] as Map);
    DssQuestion? question;
    DssOutcome? outcome;
    if (json['kind'] == 'question') {
      final raw = Map<String, dynamic>.from(json['question'] as Map);
      question = DssQuestion(
        code: raw['code'] as String,
        prompt: raw['prompt'] as String,
        explanation: raw['explanatory_text'] as String? ?? '',
        options: List.unmodifiable(
          (raw['options'] as List).map((item) {
            final option = Map<String, dynamic>.from(item as Map);
            return DssOption(
              code: option['code'] as String,
              label: option['label'] as String,
              supportingText: option['supporting_text'] as String? ?? '',
            );
          }),
        ),
      );
    } else {
      final raw = Map<String, dynamic>.from(json['outcome'] as Map);
      final source = Map<String, dynamic>.from(raw['source'] as Map);
      outcome = DssOutcome(
        title: raw['title'] as String,
        instruction: raw['instruction'] as String,
        warning: raw['warning'] as String,
        source: [
          source['name'],
          source['organization'],
        ].where((value) => value != null && '$value'.isNotEmpty).join(' — '),
      );
    }
    return DssStep(
      flowCode: flow['code'] as String,
      flowVersion: flow['version'] as String,
      title: flow['title'] as String,
      dataStatus: flow['data_status'] as String,
      warning: flow['warning'] as String,
      position: progress['position'] as int? ?? 1,
      total: progress['question_count'] as int? ?? 1,
      question: question,
      outcome: outcome,
    );
  }
}

abstract interface class StructuredDssRepository {
  Future<DssStep> start(String susceptibilityCode);
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String optionCode,
  });
}

class HttpStructuredDssRepository implements StructuredDssRepository {
  HttpStructuredDssRepository({
    http.Client? client,
    String? baseUrl,
    this.timeout = const Duration(seconds: 15),
  }) : _client = client ?? http.Client(),
       _baseUrl = ApiConfig.normalizeBaseUrl(baseUrl ?? ApiConfig.baseUrl);
  final http.Client _client;
  final String _baseUrl;
  final Duration timeout;

  @override
  Future<DssStep> start(String susceptibilityCode) async {
    final uri = Uri.parse('$_baseUrl/dss/flows/start/').replace(
      queryParameters: {
        'mode': 'demonstration',
        'susceptibility_level': susceptibilityCode,
      },
    );
    return DssStep.fromJson(
      await _send(
        () => _client.get(
          uri,
          headers: const {HttpHeaders.acceptHeader: 'application/json'},
        ),
      ),
    );
  }

  @override
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String optionCode,
  }) async {
    final uri = Uri.parse(
      '$_baseUrl/dss/flows/${current.flowCode}/${current.flowVersion}/answer/',
    );
    return DssStep.fromJson(
      await _send(
        () => _client.post(
          uri,
          headers: const {
            HttpHeaders.acceptHeader: 'application/json',
            HttpHeaders.contentTypeHeader: 'application/json; charset=utf-8',
          },
          body: jsonEncode({
            'mode': 'demonstration',
            'susceptibility_level': susceptibilityCode,
            'question_code': current.question!.code,
            'option_code': optionCode,
          }),
        ),
      ),
    );
  }

  Future<Map<String, dynamic>> _send(
    Future<http.Response> Function() request,
  ) async {
    try {
      final response = await request().timeout(timeout);
      final json = Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map,
      );
      if (response.statusCode >= 200 && response.statusCode < 300) return json;
      throw StateError(
        json['detail']?.toString() ?? 'Structured guidance is unavailable.',
      );
    } on TimeoutException {
      throw StateError('The DSS request timed out.');
    } on SocketException {
      throw StateError('The DSS is offline. Check your connection.');
    }
  }
}
