import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../config/api_config.dart';
import '../network/network_exception.dart';

/// Only public provenance fields from the resident response are retained.
class DssSource {
  const DssSource({
    this.name = '',
    this.organization = '',
    this.version = '',
    this.dataStatus = '',
    this.referenceDate = '',
    this.custodian = '',
    this.reviewedOn = '',
    this.limitations = '',
    this.citationUrl,
  });
  final String name;
  final String organization;
  final String version;
  final String dataStatus;
  final String referenceDate;
  final String custodian;
  final String reviewedOn;
  final String limitations;
  final Uri? citationUrl;

  String get label =>
      [name, organization].where((v) => v.isNotEmpty).join(' — ');

  factory DssSource.fromJson(Object? value) {
    final raw = value is Map ? value : const {};
    return DssSource(
      name: raw['name']?.toString() ?? '',
      organization: raw['organization']?.toString() ?? '',
      version: raw['version']?.toString() ?? '',
      dataStatus: raw['data_status']?.toString() ?? '',
      referenceDate:
          raw['date']?.toString() ?? raw['reference_date']?.toString() ?? '',
      custodian: raw['custodian']?.toString() ?? '',
      reviewedOn: raw['reviewed_on']?.toString() ?? '',
      limitations: raw['limitations']?.toString() ?? '',
      citationUrl: _publicHttpsUrl(raw['citation_url']),
    );
  }
}

class DssContentBlock {
  const DssContentBlock({
    required this.id,
    required this.title,
    required this.body,
    required this.phase,
    required this.contentType,
    required this.audience,
    this.displayOrder = 0,
    this.source = const DssSource(),
    this.sourceLocator = '',
    this.attribution = '',
    this.limitations = '',
    this.effectiveDate = '',
    this.reviewedOn = '',
    this.expiresOn = '',
    this.publicUrl,
  });
  final String id;
  final String title;
  final String body;
  final String phase;
  final String contentType;
  final String audience;
  final int displayOrder;
  final DssSource source;
  final String sourceLocator;
  final String attribution;
  final String limitations;
  final String effectiveDate;
  final String reviewedOn;
  final String expiresOn;
  final Uri? publicUrl;

  factory DssContentBlock.fromJson(Map raw) {
    // The API verifies publication and the public URL; retain only HTTPS URLs.
    final publicUrl = _publicHttpsUrl(raw['public_url']);
    return DssContentBlock(
      id: raw['id']?.toString() ?? '',
      title: raw['title']?.toString() ?? '',
      body: raw['body']?.toString() ?? '',
      phase: raw['phase']?.toString() ?? 'ALWAYS',
      contentType: raw['content_type']?.toString() ?? '',
      audience: raw['audience']?.toString() ?? '',
      displayOrder: raw['display_order'] is int
          ? raw['display_order'] as int
          : 0,
      source: DssSource.fromJson(raw['source']),
      sourceLocator: raw['source_locator']?.toString() ?? '',
      attribution: raw['attribution']?.toString() ?? '',
      limitations: raw['limitations']?.toString() ?? '',
      effectiveDate: raw['effective_date']?.toString() ?? '',
      reviewedOn: raw['reviewed_on']?.toString() ?? '',
      expiresOn: raw['expires_on']?.toString() ?? '',
      publicUrl: publicUrl,
    );
  }
}

Uri? _publicHttpsUrl(Object? value) {
  final candidate = Uri.tryParse(value?.toString() ?? '');
  return candidate != null &&
          candidate.scheme == 'https' &&
          candidate.host.isNotEmpty &&
          candidate.userInfo.isEmpty
      ? candidate
      : null;
}

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

class DssLinkedGuidance {
  const DssLinkedGuidance({
    required this.title,
    required this.instruction,
    required this.dataStatus,
    required this.attribution,
    required this.source,
  });
  final String title;
  final String instruction;
  final String dataStatus;
  final String attribution;
  final DssSource source;
}

class DssOutcome {
  const DssOutcome({
    required this.title,
    required this.instruction,
    required this.warning,
    required this.source,
    this.sourceDetails = const DssSource(),
    this.guidance = const [],
  });
  final String title;
  final String instruction;
  final String warning;
  final String source;
  final DssSource sourceDetails;
  final List<DssLinkedGuidance> guidance;
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
    this.contractVersion = 1,
    this.operatingMode = '',
    this.source = const DssSource(),
    this.sourceLocator = '',
    this.attribution = '',
    this.limitations = '',
    this.effectiveDate = '',
    this.reviewedOn = '',
    this.expiresOn = '',
    this.contentBlocks = const [],
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
  final int contractVersion;
  final String operatingMode;
  final DssSource source;
  final String sourceLocator;
  final String attribution;
  final String limitations;
  final String effectiveDate;
  final String reviewedOn;
  final String expiresOn;
  final List<DssContentBlock> contentBlocks;
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
      final source = DssSource.fromJson(raw['source']);
      outcome = DssOutcome(
        title: raw['title'] as String,
        instruction: raw['instruction'] as String,
        warning: raw['warning'] as String,
        source: source.label,
        sourceDetails: source,
        guidance: List.unmodifiable(
          (raw['guidance'] is List ? raw['guidance'] as List : const [])
              .whereType<Map>()
              .map(
                (item) => DssLinkedGuidance(
                  title: item['title']?.toString() ?? '',
                  instruction: item['instruction']?.toString() ?? '',
                  dataStatus: item['data_status']?.toString() ?? '',
                  attribution: item['attribution']?.toString() ?? '',
                  source: DssSource.fromJson(item['source']),
                ),
              ),
        ),
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
      contractVersion: json['contract_version'] as int? ?? 1,
      operatingMode: flow['operating_mode']?.toString() ?? '',
      source: DssSource.fromJson(flow['source']),
      sourceLocator: flow['source_locator']?.toString() ?? '',
      attribution: flow['attribution']?.toString() ?? '',
      limitations: flow['limitations']?.toString() ?? '',
      effectiveDate: flow['effective_date']?.toString() ?? '',
      reviewedOn: flow['reviewed_on']?.toString() ?? '',
      expiresOn: flow['expires_on']?.toString() ?? '',
      contentBlocks: _parseBlocks(json['content_blocks']),
      question: question,
      outcome: outcome,
    );
  }

  static List<DssContentBlock> _parseBlocks(Object? value) {
    if (value is! List) return const [];
    final blocks = value
        .whereType<Map>()
        .map(DssContentBlock.fromJson)
        .where(
          (block) => const {
            'RESIDENT',
            'HOUSEHOLD_SUPPORT',
            'PUBLIC_REFERENCE',
          }.contains(block.audience),
        )
        .toList();
    blocks.sort((a, b) {
      final order = a.displayOrder.compareTo(b.displayOrder);
      if (order != 0) return order;
      final firstId = int.tryParse(a.id);
      final secondId = int.tryParse(b.id);
      return firstId != null && secondId != null
          ? firstId.compareTo(secondId)
          : a.id.compareTo(b.id);
    });
    return List.unmodifiable(blocks);
  }
}

abstract interface class StructuredDssRepository {
  Future<DssStep> start(
    String susceptibilityCode, {
    required String operatingMode,
  });
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String operatingMode,
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
  Future<DssStep> start(
    String susceptibilityCode, {
    required String operatingMode,
  }) async {
    final uri = Uri.parse('$_baseUrl/dss/flows/start/').replace(
      queryParameters: {
        'mode': operatingMode,
        'susceptibility_level': susceptibilityCode,
      },
    );
    return DssStep.fromJson(
      await _send(
        () => _client.get(uri, headers: const {'accept': 'application/json'}),
      ),
    );
  }

  @override
  Future<DssStep> answer({
    required DssStep current,
    required String susceptibilityCode,
    required String operatingMode,
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
            'accept': 'application/json',
            'content-type': 'application/json; charset=utf-8',
          },
          body: jsonEncode({
            'mode': operatingMode,
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
    } on http.ClientException {
      throw StateError('The DSS is offline. Check your connection.');
    } on FormatException {
      throw StateError(
        'Structured guidance could not be read. Please try again.',
      );
    } catch (error) {
      if (isSocketException(error)) {
        throw StateError('The DSS is offline. Check your connection.');
      }
      rethrow;
    }
  }
}
