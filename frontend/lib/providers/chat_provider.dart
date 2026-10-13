import 'package:flutter/foundation.dart';
import '../config/constants.dart';
import '../models/message.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';
import '../utils/session_id.dart';

/// Provider for one conversation: up to [AppConstants.maxTurns] questions,
/// free "see more" pages, and a fresh start on "Nova conversa" or reload.
class ChatProvider extends ChangeNotifier {
  final ApiService _apiService;
  final LocationService _locationService;

  final List<Message> _messages = [];
  bool _isLoading = false;
  String? _error;
  bool _useLocation = true;
  double? _latitude;
  double? _longitude;
  String _sessionId = newSessionId();
  int _turnsLeft = AppConstants.maxTurns;
  bool _serverReady = false;
  bool _serverUnavailable = false;

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
  String get sessionId => _sessionId;
  int get turnsLeft => _turnsLeft;
  bool get canSend => _turnsLeft > 0 && !_isLoading;

  /// The backend has answered a health check (it may have been asleep).
  bool get serverReady => _serverReady;

  /// The backend did not wake up within [AppConstants.serverWakeTimeout].
  bool get serverUnavailable => _serverUnavailable;

  /// Initialize the provider
  Future<void> initialize() async {
    _updateLocation();
    await _waitForServer();
  }

  /// Poll the health endpoint until it answers: a free-tier server sleeps
  /// when idle and takes about a minute to wake up.
  Future<void> _waitForServer() async {
    final attempts = AppConstants.serverWakeTimeout.inMilliseconds ~/
        AppConstants.healthPollInterval.inMilliseconds;
    for (var i = 0; i < attempts && !_serverReady; i++) {
      if (await _apiService.checkHealth()) {
        _markReady();
        return;
      }
      await Future.delayed(AppConstants.healthPollInterval);
    }
    if (!_serverReady) {
      _serverUnavailable = true;
      notifyListeners();
    }
  }

  void _markReady() {
    _serverReady = true;
    _serverUnavailable = false;
    notifyListeners();
  }

  /// Ask a question; spends one of the conversation's questions.
  Future<void> sendMessage(String content, {required String language}) async {
    if (content.trim().isEmpty || !canSend) return;
    _messages.add(Message.user(content.trim()));
    await _request(language, (location) {
      final filters = <String, dynamic>{
        if (_selectedPlaceTypes.isNotEmpty) 'placeType': _selectedPlaceTypes.toList(),
        if (_openNowFilter) 'openNow': true,
      };
      return _apiService.sendMessage(
        message: content.trim(),
        language: language,
        sessionId: _sessionId,
        latitude: location ? _latitude : null,
        longitude: location ? _longitude : null,
        filters: filters,
      );
    });
  }

  /// The next results of the last answer; free, no question spent.
  Future<void> seeMore({required String language}) async {
    if (_isLoading) return;
    final previous = _messages.lastWhere((m) => !m.isUser, orElse: () => Message.loading());
    await _request(language, (_) async {
      final page = await _apiService.sendMessage(
        language: language,
        sessionId: _sessionId,
        action: 'more',
      );
      // Keep offering the last answer's follow-ups under the newest page.
      return Message.assistant(
        content: page.content,
        places: page.places,
        followUps: previous.followUps,
        hasMore: page.hasMore,
        turnsLeft: page.turnsLeft,
      );
    });
  }

  Future<void> _request(String language, Future<Message> Function(bool location) call) async {
    _error = null;
    _isLoading = true;
    _messages.add(Message.loading());
    notifyListeners();
    try {
      if (_useLocation) await _updateLocation();
      final response = await call(_useLocation);
      _messages.removeWhere((m) => m.isLoading);
      _messages.add(response);
      _turnsLeft = response.turnsLeft ?? _turnsLeft;
      if (!_serverReady) _markReady();
    } catch (e) {
      _messages.removeWhere((m) => m.isLoading);
      _error = e.toString();
      if (e is ConversationFinished) _turnsLeft = 0;
      _messages.add(Message.assistant(content: _errorMessage(e, language == 'en')));
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Start a new conversation with all its questions.
  void newConversation() {
    _messages.clear();
    _error = null;
    _sessionId = newSessionId();
    _turnsLeft = AppConstants.maxTurns;
    notifyListeners();
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

  String _errorMessage(Object error, bool english) {
    if (error is ConversationFinished) {
      return english
          ? 'This conversation is over. Tap "New conversation" to keep exploring.'
          : 'Esta conversa terminou. Toque em "Nova conversa" para continuar.';
    }
    if (error is NoPreviousResults) {
      return english
          ? 'There are no more results for that search. Ask a new question.'
          : 'Não há mais resultados para essa busca. Faça uma nova pergunta.';
    }
    if (error is TooManyRequests) {
      return english
          ? 'Too many messages in a short time. Please wait a few minutes.'
          : 'Muitas mensagens em pouco tempo. Aguarde alguns minutos.';
    }
    if (error is InvalidInput) {
      return english
          ? 'Use only letters, digits, spaces and the marks , . : ? !'
          : 'Use apenas letras, números, espaços e os sinais , . : ? !';
    }
    return english
        ? 'Sorry, an error occurred while processing your message. Please try again.'
        : 'Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.';
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

  @override
  void dispose() {
    _apiService.dispose();
    super.dispose();
  }
}
