import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/constants.dart';
import '../models/message.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';

/// Provider for managing chat state
class ChatProvider extends ChangeNotifier {
  final ApiService _apiService;
  final LocationService _locationService;
  
  List<Message> _messages = [];
  bool _isLoading = false;
  String? _error;
  bool _useLocation = true;
  double? _latitude;
  double? _longitude;
  
  // Filters
  final Set<String> _selectedPlaceTypes = {};
  bool _openNowFilter = false;

  ChatProvider({
    ApiService? apiService,
    LocationService? locationService,
  })  : _apiService = apiService ?? ApiService(),
        _locationService = locationService ?? LocationService();

  // Getters
  List<Message> get messages => List.unmodifiable(_messages);
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get useLocation => _useLocation;
  bool get hasLocation => _latitude != null && _longitude != null;
  double? get latitude => _latitude;
  double? get longitude => _longitude;
  Set<String> get selectedPlaceTypes => Set.unmodifiable(_selectedPlaceTypes);
  bool get openNowFilter => _openNowFilter;

  /// Initialize the provider
  Future<void> initialize() async {
    await _loadHistory();
    await _updateLocation();
  }

  /// Send a message
  Future<void> sendMessage(String content, {required String language}) async {
    if (content.trim().isEmpty) return;

    // Clear any previous error
    _error = null;

    // Add user message
    final userMessage = Message.user(content.trim());
    _messages.add(userMessage);
    notifyListeners();

    // Show loading indicator
    _isLoading = true;
    _messages.add(Message.loading());
    notifyListeners();

    try {
      // Update location if enabled
      if (_useLocation) {
        await _updateLocation();
      }

      // Build filters
      final filters = <String, dynamic>{};
      if (_selectedPlaceTypes.isNotEmpty) {
        filters['placeType'] = _selectedPlaceTypes.toList();
      }
      if (_openNowFilter) {
        filters['openNow'] = true;
      }
      
      // Get current time in ISO-8601 format
      final nowIso = DateTime.now().toUtc().toIso8601String();
      
      // Send to API
      final response = await _apiService.sendMessage(
        message: content,
        language: language,
        latitude: _useLocation ? _latitude : null,
        longitude: _useLocation ? _longitude : null,
        nowIso: nowIso,
        filters: filters.isNotEmpty ? filters : null,
      );

      // Remove loading message and add response
      _messages.removeWhere((m) => m.isLoading);
      _messages.add(response);
      
      // Save history
      await _saveHistory();
    } catch (e) {
      // Remove loading message
      _messages.removeWhere((m) => m.isLoading);
      
      // Add error message
      _error = e.toString();
      _messages.add(Message.assistant(
        content: _getErrorMessage(e, language),
      ));
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Toggle place type filter
  void togglePlaceTypeFilter(String placeType) {
    if (_selectedPlaceTypes.contains(placeType)) {
      _selectedPlaceTypes.remove(placeType);
    } else {
      _selectedPlaceTypes.add(placeType);
    }
    notifyListeners();
  }
  
  /// Toggle open now filter
  void toggleOpenNowFilter() {
    _openNowFilter = !_openNowFilter;
    notifyListeners();
  }
  
  /// Clear all filters
  void clearFilters() {
    _selectedPlaceTypes.clear();
    _openNowFilter = false;
    notifyListeners();
  }

  /// Get user-friendly error message
  String _getErrorMessage(dynamic error, String language) {
    if (language == 'pt-BR' || language == 'pt') {
      return 'Desculpe, ocorreu um erro ao processar sua mensagem. '
          'Por favor, tente novamente.';
    } else {
      return 'Sorry, an error occurred while processing your message. '
          'Please try again.';
    }
  }

  /// Toggle location usage
  void toggleLocation() {
    _useLocation = !_useLocation;
    if (_useLocation) {
      _updateLocation();
    }
    notifyListeners();
  }

  /// Update current location
  Future<void> _updateLocation() async {
    final position = await _locationService.getCurrentPosition();
    if (position != null) {
      _latitude = position.latitude;
      _longitude = position.longitude;
      notifyListeners();
    }
  }

  /// Request location update
  Future<bool> requestLocation() async {
    final position = await _locationService.getCurrentPosition();
    if (position != null) {
      _latitude = position.latitude;
      _longitude = position.longitude;
      _useLocation = true;
      notifyListeners();
      return true;
    }
    return false;
  }

  /// Clear all messages
  Future<void> clearHistory() async {
    _messages.clear();
    _error = null;
    await _apiService.clearHistory();
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConstants.chatHistoryKey);
    
    notifyListeners();
  }

  /// Load chat history from local storage
  Future<void> _loadHistory() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final historyJson = prefs.getString(AppConstants.chatHistoryKey);
      
      if (historyJson != null) {
        final List<dynamic> historyList = jsonDecode(historyJson);
        _messages = historyList
            .map((json) => Message.fromJson(json as Map<String, dynamic>))
            .toList();
        
        // Limit history size
        if (_messages.length > AppConstants.maxHistoryMessages) {
          _messages = _messages.sublist(
            _messages.length - AppConstants.maxHistoryMessages,
          );
        }
        
        notifyListeners();
      }
    } catch (e) {
      debugPrint('Error loading chat history: $e');
    }
  }

  /// Save chat history to local storage
  Future<void> _saveHistory() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final historyJson = jsonEncode(
        _messages.where((m) => !m.isLoading).map((m) => m.toJson()).toList(),
      );
      await prefs.setString(AppConstants.chatHistoryKey, historyJson);
    } catch (e) {
      debugPrint('Error saving chat history: $e');
    }
  }

  @override
  void dispose() {
    _apiService.dispose();
    super.dispose();
  }
}


