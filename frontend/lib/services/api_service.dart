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
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        
        // Use new format (results, answer) with fallback to legacy (places, response)
        final results = data['results'] as List<dynamic>?;
        final places = data['places'] as List<dynamic>?;
        final placesList = (results ?? places ?? [])
            .map((p) => Place.fromJson(p as Map<String, dynamic>))
            .toList();

        final answer = data['answer'] as String? ?? 
                      data['response'] as String? ?? 
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

/// Custom exception for API errors
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic originalError;

  ApiException(this.message, {this.statusCode, this.originalError});

  @override
  String toString() => message;
}


