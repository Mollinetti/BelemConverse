import 'place.dart';

/// Represents a chat message
class Message {
  final String id;
  final String content;
  final bool isUser;
  final DateTime timestamp;
  final List<Place> places;
  final String? source;
  final double? processingTimeMs;

  Message({
    required this.id,
    required this.content,
    required this.isUser,
    required this.timestamp,
    this.places = const [],
    this.source,
    this.processingTimeMs,
  });

  /// Create a user message
  factory Message.user(String content) {
    return Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      content: content,
      isUser: true,
      timestamp: DateTime.now(),
    );
  }

  /// Create an assistant message from API response
  factory Message.assistant({
    required String content,
    List<Place> places = const [],
    String? source,
    double? processingTimeMs,
  }) {
    return Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      content: content,
      isUser: false,
      timestamp: DateTime.now(),
      places: places,
      source: source,
      processingTimeMs: processingTimeMs,
    );
  }

  /// Create a loading message
  factory Message.loading() {
    return Message(
      id: 'loading',
      content: '',
      isUser: false,
      timestamp: DateTime.now(),
    );
  }

  bool get isLoading => id == 'loading';

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'content': content,
      'isUser': isUser,
      'timestamp': timestamp.toIso8601String(),
      'places': places.map((p) => p.toJson()).toList(),
      'source': source,
      'processingTimeMs': processingTimeMs,
    };
  }

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] as String,
      content: json['content'] as String,
      isUser: json['isUser'] as bool,
      timestamp: DateTime.parse(json['timestamp'] as String),
      places: (json['places'] as List<dynamic>?)
              ?.map((p) => Place.fromJson(p as Map<String, dynamic>))
              .toList() ??
          [],
      source: json['source'] as String?,
      processingTimeMs: json['processingTimeMs'] as double?,
    );
  }
}


