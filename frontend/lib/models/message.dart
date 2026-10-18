import 'place.dart';

/// Represents a chat message
class Message {
  final String id;
  final String content;
  final bool isUser;
  final DateTime timestamp;
  final List<Place> places;
  final double? processingTimeMs;

  /// Suggested next questions (assistant answers only).
  final List<String> followUps;

  /// Whether "see more" has further results for this answer.
  final bool hasMore;

  /// Questions left in the conversation after this answer.
  final int? turnsLeft;

  Message({
    required this.id,
    required this.content,
    required this.isUser,
    required this.timestamp,
    this.places = const [],
    this.processingTimeMs,
    this.followUps = const [],
    this.hasMore = false,
    this.turnsLeft,
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
    double? processingTimeMs,
    List<String> followUps = const [],
    bool hasMore = false,
    int? turnsLeft,
  }) {
    return Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      content: content,
      isUser: false,
      timestamp: DateTime.now(),
      places: places,
      processingTimeMs: processingTimeMs,
      followUps: followUps,
      hasMore: hasMore,
      turnsLeft: turnsLeft,
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
}
