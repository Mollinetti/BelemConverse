import 'dart:convert';

import 'package:flutter/foundation.dart';
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

  /// Send a chat message and get a response per OpenAPI spec
  Future<Message> sendMessage({
    required String message,
    required String language, // Should be 'en' or 'pt-BR'
    double? latitude,
    double? longitude,
    String? nowIso,
    Map<String, dynamic>? filters,
  }) async {
    try {
      final body = <String, dynamic>{
        'message': message,
        'language': language, // 'en' or 'pt-BR'
      };

      // Add userLocation (preferred) or coordinates (legacy fallback)
      if (latitude != null && longitude != null) {
        body['userLocation'] = {
          'lat': latitude,
          'lng': longitude,
        };
        // Also include legacy coordinates for backward compatibility
        body['coordinates'] = {
          'lat': latitude,
          'lng': longitude,
        };
      }

      // Add nowIso if provided
      if (nowIso != null) {
        body['nowIso'] = nowIso;
      }

      // Add filters if provided
      if (filters != null && filters.isNotEmpty) {
        body['filters'] = filters;
      }

      final response = await _client
          .post(
            Uri.parse('$baseUrl/chat'),
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
            body: jsonEncode(body),
          )
          .timeout(AppConstants.apiTimeout);

      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        if (decoded is! Map) {
          throw FormatException('Chat response is not a JSON object: $decoded');
        }
        final data = Map<String, dynamic>.from(decoded);

        if (kDebugMode) {
          final answerLen = _stringField(data, 'answer')?.length;
          final responseLen = _stringField(data, 'response')?.length;
          debugPrint(
            'api chat: keys=${data.keys.toList()} answerLen=$answerLen '
            'responseLen=$responseLen',
          );
        }

        // Tour responses use results=[]; only the *answer* text is shown. If
        // any one place object is malformed, we must still show the answer —
        // never let Place.fromJson break the whole response.
        final placesList = _parsePlaceResults(data);

        // New format (answer) + legacy (response). Tour often has only answer.
        var answer = _stringField(data, 'answer') ??
            _stringField(data, 'response') ??
            _stringField(data, 'message') ??
            '';

        return Message.assistant(
          content: answer,
          places: placesList,
          source: data['source'] as String?,
          processingTimeMs: (data['processing_time_ms'] as num?)?.toDouble(),
        );
      } else if (response.statusCode == 503) {
        throw ApiException(
          'O servidor está inicializando. Por favor, aguarde um momento.',
          statusCode: 503,
        );
      } else {
        final error = jsonDecode(response.body);
        throw ApiException(
          error['detail'] ?? 'Erro desconhecido',
          statusCode: response.statusCode,
        );
      }
    } on http.ClientException catch (e) {
      throw ApiException(
        'Não foi possível conectar ao servidor. Verifique sua conexão.',
        originalError: e,
      );
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException(
        'Erro ao processar a solicitação: $e',
        originalError: e,
      );
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

  /// Clear conversation history on the server
  Future<void> clearHistory() async {
    try {
      await _client
          .post(Uri.parse('$baseUrl/clear-history'))
          .timeout(AppConstants.connectionTimeout);
    } catch (e) {
      // Ignore errors when clearing history
    }
  }

  void dispose() {
    _client.close();
  }
}

/// Build [Place] list from `results` or `places` without ever throwing: a single
/// bad place must not hide a valid `answer` (tour can return `results: []` but
/// long `answer` text; conversely a bad `results` entry must not blank the UI).
List<Place> _parsePlaceResults(Map<String, dynamic> data) {
  final out = <Place>[];
  final List<dynamic> raw;
  if (data['results'] is List) {
    raw = data['results'] as List<dynamic>;
  } else if (data['places'] is List) {
    raw = data['places'] as List<dynamic>;
  } else {
    return out;
  }
  for (var i = 0; i < raw.length; i++) {
    final item = raw[i];
    if (item is! Map) {
      if (kDebugMode) {
        debugPrint('Skipping place $i: not a Map');
      }
      continue;
    }
    try {
      out.add(Place.fromJson(Map<String, dynamic>.from(item)));
    } catch (e) {
      if (kDebugMode) {
        debugPrint('Place.fromJson failed at $i: $e');
      }
    }
  }
  return out;
}

/// Coerce a JSON value to a non-empty display string, or `null` if missing.
String? _stringField(Map<String, dynamic> data, String key) {
  final v = data[key];
  if (v == null) return null;
  if (v is String) return v.isEmpty ? null : v;
  if (v is num || v is bool) return v.toString();
  if (v is Map) {
    // Rare: some gateways wrap text; best-effort extract.
    final t = v['text'] ?? v['content'];
    if (t is String && t.isNotEmpty) return t;
  }
  final s = v.toString();
  return s.isEmpty ? null : s;
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


