/// Represents a place/establishment per OpenAPI PlaceResult schema
class Place {
  // Required fields
  final String placeId;
  
  // Basic info
  final String? title;
  final String? titleFormatted;
  final String? subTitle;
  final String? categoryName;
  final List<String> categories;
  
  // Address
  final String? address;
  final String? addressFormatted;
  final String? street;
  final String? streetFormatted;
  final String? neighborhood;
  final String? city;
  final String? state;
  final String? postalCode;
  final String? countryCode;
  
  // Location
  final double? lat;
  final double? lng;
  
  // Contact
  final String? phone;
  final String? phoneUnformatted;
  
  // URLs
  final String? url;
  final String? website;
  final String? googleFoodUrl;
  final String? menu;
  final String? reserveTableUrl;
  
  // Ratings & reviews
  final double? totalScore;
  final int? reviewsCount;
  
  // Other
  final double? price;
  final double? rank;
  final bool isSponsored;
  final String? businessTime;
  final String placeType; // restaurant, bar, park, other
  
  // PlaceResult specific fields
  final double? distanceKm;
  final String? openNowStatus; // "open" | "closed" | "unknown"
  final String? source; // Data source: "database", "osm_realtime", etc.
  
  // Legacy fields for backward compatibility
  String get name => title ?? titleFormatted ?? 'Unknown';
  String? get addressDisplay => addressFormatted ?? address;
  String? get category => categoryName;
  double? get rating => totalScore;

  Place({
    required this.placeId,
    this.title,
    this.titleFormatted,
    this.subTitle,
    this.categoryName,
    this.categories = const [],
    this.address,
    this.addressFormatted,
    this.street,
    this.streetFormatted,
    this.neighborhood,
    this.city,
    this.state,
    this.postalCode,
    this.countryCode,
    this.lat,
    this.lng,
    this.phone,
    this.phoneUnformatted,
    this.url,
    this.website,
    this.googleFoodUrl,
    this.menu,
    this.reserveTableUrl,
    this.totalScore,
    this.reviewsCount,
    this.price,
    this.rank,
    this.isSponsored = false,
    this.businessTime,
    this.placeType = 'other',
    this.distanceKm,
    this.openNowStatus,
    this.source,
  });

  bool get hasCoordinates => lat != null && lng != null;
  
  bool get hasWebsite => (website != null && website!.isNotEmpty) || 
                         (url != null && url!.isNotEmpty);

  String get formattedRating {
    if (totalScore == null) return 'N/A';
    return totalScore!.toStringAsFixed(1);
  }

  String get formattedDistance {
    if (distanceKm == null) return '';
    if (distanceKm! < 1) {
      return '${(distanceKm! * 1000).round()}m';
    }
    return '${distanceKm!.toStringAsFixed(1)}km';
  }

  String get formattedReviews {
    if (reviewsCount == null || reviewsCount == 0) return '';
    if (reviewsCount! >= 1000) {
      return '${(reviewsCount! / 1000).toStringAsFixed(1)}k reviews';
    }
    return '$reviewsCount reviews';
  }
  
  String get openNowStatusText {
    switch (openNowStatus) {
      case 'open':
        return 'Open now';
      case 'closed':
        return 'Closed now';
      case 'unknown':
        return 'Hours unknown';
      default:
        return '';
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'placeId': placeId,
      'title': title,
      'titleFormatted': titleFormatted,
      'categoryName': categoryName,
      'addressFormatted': addressFormatted,
      'address': address,
      'totalScore': totalScore,
      'reviewsCount': reviewsCount,
      'lat': lat,
      'lng': lng,
      'phone': phone,
      'distanceKm': distanceKm,
      'openNowStatus': openNowStatus,
      'website': website,
      'url': url,
      // Legacy fields
      'name': name,
      'category': category,
      'rating': rating,
      'reviews_count': reviewsCount,
      'distance_km': distanceKm,
    };
  }

  factory Place.fromJson(Map<String, dynamic> json) {
    // Handle location object
    double? lat, lng;
    if (json['location'] != null) {
      final loc = json['location'] as Map<String, dynamic>;
      lat = (loc['lat'] as num?)?.toDouble();
      lng = (loc['lng'] as num?)?.toDouble();
    } else {
      // Fallback to direct lat/lng fields
      lat = (json['lat'] as num?)?.toDouble();
      lng = (json['lng'] as num?)?.toDouble();
    }
    
    return Place(
      placeId: json['placeId'] as String? ?? json['place_id'] as String? ?? '',
      title: json['title'] as String?,
      titleFormatted: json['titleFormatted'] as String?,
      subTitle: json['subTitle'] as String?,
      categoryName: json['categoryName'] as String?,
      categories: (json['categories'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      address: json['address'] as String?,
      addressFormatted: json['addressFormatted'] as String?,
      street: json['street'] as String?,
      streetFormatted: json['streetFormatted'] as String?,
      neighborhood: json['neighborhood'] as String?,
      city: json['city'] as String?,
      state: json['state'] as String?,
      postalCode: json['postalCode'] as String?,
      countryCode: json['countryCode'] as String?,
      lat: lat,
      lng: lng,
      phone: json['phone'] as String?,
      phoneUnformatted: json['phoneUnformatted'] as String?,
      url: json['url'] as String?,
      website: json['website'] as String?,
      googleFoodUrl: json['googleFoodUrl'] as String?,
      menu: json['menu'] as String?,
      reserveTableUrl: json['reserveTableUrl'] as String?,
      totalScore: (json['totalScore'] as num?)?.toDouble() ?? 
                  (json['rating'] as num?)?.toDouble(),
      reviewsCount: json['reviewsCount'] as int? ?? 
                    json['reviews_count'] as int?,
      price: (json['price'] as num?)?.toDouble(),
      rank: (json['rank'] as num?)?.toDouble(),
      isSponsored: json['isSponsored'] as bool? ?? false,
      businessTime: json['businessTime'] as String?,
      placeType: json['place_type'] as String? ?? 'other',
      distanceKm: (json['distanceKm'] as num?)?.toDouble() ?? 
                  (json['distance_km'] as num?)?.toDouble(),
      openNowStatus: json['openNowStatus'] as String?,
      source: json['source'] as String?,
    );
  }
}


