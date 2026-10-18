/// API and app configuration constants
class AppConstants {
  // API Configuration: set at build time with
  // --dart-define=API_BASE_URL=https://<service>.onrender.com/api
  static const String apiBaseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000/api');

  // Timeouts
  static const Duration apiTimeout = Duration(seconds: 60);
  static const Duration connectionTimeout = Duration(seconds: 10);

  // A sleeping free-tier server takes about a minute to wake up.
  static const Duration healthPollInterval = Duration(seconds: 3);
  static const Duration serverWakeTimeout = Duration(seconds: 90);

  // Chat (the server enforces the same limits)
  static const int maxMessageLength = 400;
  static const int maxTurns = 4;
  
  // Location
  static const double defaultLatitude = -1.4558;  // Belém center
  static const double defaultLongitude = -48.4902;
  static const int locationTimeoutSeconds = 15;
  
  // Map
  static const double defaultMapZoom = 14.0;
  static const double placeMapZoom = 16.0;
  
  // Storage keys
  static const String languageKey = 'language';
  static const String lastCoordinatesKey = 'last_coordinates';
}

/// Supported languages per OpenAPI spec
enum AppLanguage {
  portuguese('pt-BR', 'Português', 'PT'),
  english('en', 'English', 'EN');
  
  final String code; // 'pt-BR' or 'en' per OpenAPI spec
  final String name;
  final String short; // button label; a flag emoji would cost a 0.7 MB font download
  
  const AppLanguage(this.code, this.name, this.short);
  
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


