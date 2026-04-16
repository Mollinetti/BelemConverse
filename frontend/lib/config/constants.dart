/// API and app configuration constants
class AppConstants {
  // API Configuration
  static const String apiBaseUrl = 'http://localhost:8000/api';
  
  // For mobile testing, use your machine's IP:
  // static const String apiBaseUrl = 'http://192.168.1.X:8000/api';
  
  // Timeouts
  static const Duration apiTimeout = Duration(seconds: 60);
  static const Duration connectionTimeout = Duration(seconds: 10);
  
  // Chat
  static const int maxMessageLength = 2000;
  static const int maxHistoryMessages = 50;
  
  // Location
  static const double defaultLatitude = -1.4558;  // Belém center
  static const double defaultLongitude = -48.4902;
  static const int locationTimeoutSeconds = 15;
  
  // Map
  static const double defaultMapZoom = 14.0;
  static const double placeMapZoom = 16.0;
  
  // Storage keys
  static const String chatHistoryKey = 'chat_history';
  static const String languageKey = 'language';
  static const String lastCoordinatesKey = 'last_coordinates';
}

/// Supported languages per OpenAPI spec
enum AppLanguage {
  portuguese('pt-BR', 'Português', '🇧🇷'),
  english('en', 'English', '🇺🇸');
  
  final String code; // 'pt-BR' or 'en' per OpenAPI spec
  final String name;
  final String flag;
  
  const AppLanguage(this.code, this.name, this.flag);
  
  static AppLanguage fromCode(String code) {
    // Handle both 'pt' and 'pt-BR' for backward compatibility
    if (code == 'pt' || code == 'pt-BR') {
      return AppLanguage.portuguese;
    }
    return AppLanguage.values.firstWhere(
      (lang) => lang.code == code,
      orElse: () => AppLanguage.portuguese,
    );
  }
}


