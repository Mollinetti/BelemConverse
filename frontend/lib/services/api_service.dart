import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/constants.dart';
import '../models/message.dart';
import '../models/place.dart';

/// API service for communicating with the BelemConverse backend
class ApiService {
  final String baseUrl;
  final http.Client _client;

  ApiService({
    String? baseUrl,
    http.Client? client,
  })  : baseUrl = baseUrl ?? AppConstants.apiBaseUrl,
        _client = client ?? http.Client();

  /// Ask [message] in conversation [sessionId], or page the last answer with
  /// `action: 'more'` (no message, costs no question).
  Future<Message> sendMessage({
    String? message,
    required String language, // 'en' or 'pt-BR'
    required String sessionId,
    String? action,
    double? latitude,
    double? longitude,
    Map<String, dynamic>? filters,
  }) async {
    final body = <String, dynamic>{
      'session_id': sessionId,
      'language': language,
      if (message != null) 'message': message,
      if (action != null) 'action': action,
      if (latitude != null && longitude != null)
        'userLocation': {'lat': latitude, 'lng': longitude},
      if (filters != null && filters.isNotEmpty) 'filters': filters,
    };

    final http.Response response;
    try {
      response = await _client
          .post(
            Uri.parse('$baseUrl/chat'),
            headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(AppConstants.apiTimeout);
    } catch (e) {
      throw ApiException('Could not reach the server: $e', originalError: e);
    }

    switch (response.statusCode) {
      case 200:
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        return Message.assistant(
          content: data['answer'] as String? ?? '',
          places: (data['results'] as List<dynamic>? ?? [])
              .map((p) => Place.fromJson(p as Map<String, dynamic>))
              .toList(),
          followUps: (data['follow_ups'] as List<dynamic>? ?? []).cast<String>(),
          hasMore: data['has_more'] as bool? ?? false,
          turnsLeft: data['turns_left'] as int?,
          processingTimeMs: (data['processing_time_ms'] as num?)?.toDouble(),
        );
      case 409:
        final code = (jsonDecode(response.body) as Map<String, dynamic>)['code'];
        throw code == 'no_previous_results' ? NoPreviousResults() : ConversationFinished();
      case 422:
        throw InvalidInput();
      case 429:
        throw TooManyRequests();
      default:
        throw ApiException('HTTP ${response.statusCode}', statusCode: response.statusCode);
    }
  }

  /// Check if the API is healthy
  Future<bool> checkHealth() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/health'))
          .timeout(AppConstants.connectionTimeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return data['status'] == 'healthy';
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  void dispose() {
    _client.close();
  }
}

/// Custom exception for API errors
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic originalError;

  ApiException(this.message, {this.statusCode, this.originalError});

  @override
  String toString() => message;
}

/// 409: no questions left in this conversation.
class ConversationFinished extends ApiException {
  ConversationFinished() : super('conversation finished', statusCode: 409);
}

/// 409 on "see more": the server has no previous results (e.g. it restarted).
class NoPreviousResults extends ApiException {
  NoPreviousResults() : super('no previous results', statusCode: 409);
}

/// 422: the server's input gate refused the message.
class InvalidInput extends ApiException {
  InvalidInput() : super('invalid input', statusCode: 422);
}

/// 429: too many messages from this visitor; wait a few minutes.
class TooManyRequests extends ApiException {
  TooManyRequests() : super('too many requests', statusCode: 429);
}
