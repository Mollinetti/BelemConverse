import 'package:geolocator/geolocator.dart';
import '../config/constants.dart';

/// Service for handling device location
class LocationService {
  Position? _lastPosition;
  
  Position? get lastPosition => _lastPosition;
  
  /// Check if location services are enabled and permissions are granted
  Future<bool> checkPermissions() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return false;
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        return false;
      }
    }

    if (permission == LocationPermission.deniedForever) {
      return false;
    }

    return true;
  }

  /// Get current position
  Future<Position?> getCurrentPosition() async {
    try {
      final hasPermission = await checkPermissions();
      if (!hasPermission) {
        return null;
      }

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: AppConstants.locationTimeoutSeconds),
      );
      
      _lastPosition = position;
      return position;
    } catch (e) {
      return null;
    }
  }

  /// Get last known position (faster, may be stale)
  Future<Position?> getLastKnownPosition() async {
    try {
      final position = await Geolocator.getLastKnownPosition();
      if (position != null) {
        _lastPosition = position;
      }
      return position;
    } catch (e) {
      return null;
    }
  }

  /// Check if we're in Belém area
  bool isInBelemArea(Position position) {
    // Belém bounding box (approximate)
    const minLat = -1.55;
    const maxLat = -1.35;
    const minLng = -48.60;
    const maxLng = -48.35;

    return position.latitude >= minLat &&
        position.latitude <= maxLat &&
        position.longitude >= minLng &&
        position.longitude <= maxLng;
  }

  /// Get default Belém coordinates if location not available
  Position getDefaultPosition() {
    return Position(
      latitude: AppConstants.defaultLatitude,
      longitude: AppConstants.defaultLongitude,
      timestamp: DateTime.now(),
      accuracy: 0,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );
  }
}


