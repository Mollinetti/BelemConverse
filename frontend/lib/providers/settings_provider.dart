import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/constants.dart';

/// Provider for managing app settings
class SettingsProvider extends ChangeNotifier {
  AppLanguage _language = AppLanguage.portuguese;
  bool _isInitialized = false;

  // Getters
  AppLanguage get language => _language;
  String get languageCode => _language.code;
  bool get isInitialized => _isInitialized;

  /// Initialize settings from storage
  Future<void> initialize() async {
    if (_isInitialized) return;

    try {
      final prefs = await SharedPreferences.getInstance();
      final savedLanguage = prefs.getString(AppConstants.languageKey);
      
      if (savedLanguage != null) {
        _language = AppLanguage.fromCode(savedLanguage);
      }
      
      _isInitialized = true;
      notifyListeners();
    } catch (e) {
      debugPrint('Error loading settings: $e');
      _isInitialized = true;
    }
  }

  /// Set the app language
  Future<void> setLanguage(AppLanguage language) async {
    if (_language == language) return;

    _language = language;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConstants.languageKey, language.code);
    } catch (e) {
      debugPrint('Error saving language setting: $e');
    }
  }

  /// Toggle between Portuguese and English
  Future<void> toggleLanguage() async {
    final newLanguage = _language == AppLanguage.portuguese
        ? AppLanguage.english
        : AppLanguage.portuguese;
    await setLanguage(newLanguage);
  }
}


