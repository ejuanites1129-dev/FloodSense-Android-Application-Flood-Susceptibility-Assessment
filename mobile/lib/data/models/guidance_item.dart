import 'json_parsing.dart';

class GuidanceItem {
  const GuidanceItem({
    required this.id,
    required this.title,
    required this.instruction,
    required this.category,
    required this.displayOrder,
    required this.dataStatus,
  });

  final int id;
  final String title;
  final String instruction;
  final String category;
  final int displayOrder;
  final String dataStatus;

  String get readableCategory => category
      .toLowerCase()
      .split('_')
      .where((part) => part.isNotEmpty)
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');

  factory GuidanceItem.fromJson(Map<String, dynamic> json) => GuidanceItem(
    id: requireInt(json, 'id'),
    title: requireString(json, 'title'),
    instruction: requireString(json, 'instruction'),
    category: requireString(json, 'category'),
    displayOrder: requireInt(json, 'display_order'),
    dataStatus: requireString(json, 'data_status'),
  );
}
