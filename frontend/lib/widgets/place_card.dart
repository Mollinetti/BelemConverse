import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config/theme.dart';
import '../models/place.dart';

/// A card displaying place information per UX spec
class PlaceCard extends StatelessWidget {
  final Place place;
  final VoidCallback? onTap;
  final bool showOpenNow; // Whether to show open now badge

  const PlaceCard({
    super.key,
    required this.place,
    this.onTap,
    this.showOpenNow = false,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(),
              if (place.addressDisplay != null && place.addressDisplay!.isNotEmpty) ...[
                const SizedBox(height: 8),
                _buildAddress(),
              ],
              const SizedBox(height: 8),
              _buildFooter(),
              if (place.hasWebsite || showOpenNow) ...[
                const SizedBox(height: 8),
                _buildActions(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: ParaColors.vermelho.withOpacity(0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(
            _getCategoryIcon(),
            size: 20,
            color: ParaColors.vermelho,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                place.name,
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              if (place.categoryName != null && place.categoryName!.isNotEmpty)
                Text(
                  place.categoryName!,
                  style: TextStyle(
                    fontSize: 12,
                    color: ParaColors.textSecondary,
                  ),
                ),
            ],
          ),
        ),
        if (place.rating != null) _buildRating(),
      ],
    );
  }

  Widget _buildRating() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: ParaColors.azul,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.star,
            size: 14,
            color: Colors.white,
          ),
          const SizedBox(width: 4),
          Text(
            place.formattedRating,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAddress() {
    return Row(
      children: [
        Icon(
          Icons.location_on_outlined,
          size: 16,
          color: ParaColors.textSecondary,
        ),
        const SizedBox(width: 4),
        Expanded(
          child: Text(
            place.addressDisplay!,
            style: TextStyle(
              fontSize: 12,
              color: ParaColors.textSecondary,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }

  Widget _buildFooter() {
    return Row(
      children: [
        if (place.formattedDistance.isNotEmpty) ...[
          Icon(
            Icons.directions_walk,
            size: 14,
            color: ParaColors.vermelho,
          ),
          const SizedBox(width: 4),
          Text(
            place.formattedDistance,
            style: TextStyle(
              fontSize: 12,
              color: ParaColors.vermelho,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(width: 12),
        ],
        if (place.formattedReviews.isNotEmpty)
          Text(
            place.formattedReviews,
            style: TextStyle(
              fontSize: 11,
              color: ParaColors.textSecondary,
            ),
          ),
        const Spacer(),
        if (place.source == 'osm_realtime')
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.orange.withOpacity(0.1),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              'OSM',
              style: TextStyle(
                fontSize: 10,
                color: Colors.orange.shade700,
                fontWeight: FontWeight.w500,
              ),
          ),
        ),
      ],
    );
  }

  Widget _buildActions() {
    return Row(
      children: [
        // Open now badge (when requested and status available)
        if (showOpenNow && place.openNowStatus != null) ...[
          _buildOpenNowBadge(),
          const SizedBox(width: 8),
        ],
        const Spacer(),
        // Website/URL button
        if (place.hasWebsite) ...[
          TextButton.icon(
            onPressed: () => _openWebsite(),
            icon: const Icon(Icons.open_in_new, size: 16),
            label: const Text('Website', style: TextStyle(fontSize: 12)),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildOpenNowBadge() {
    Color badgeColor;
    String badgeText;
    IconData badgeIcon;

    switch (place.openNowStatus) {
      case 'open':
        badgeColor = Colors.green;
        badgeText = 'Open now';
        badgeIcon = Icons.check_circle;
        break;
      case 'closed':
        badgeColor = Colors.red;
        badgeText = 'Closed now';
        badgeIcon = Icons.cancel;
        break;
      case 'unknown':
        badgeColor = Colors.orange;
        badgeText = 'Hours unknown';
        badgeIcon = Icons.help_outline;
        break;
      default:
        return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: badgeColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: badgeColor.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(badgeIcon, size: 14, color: badgeColor),
          const SizedBox(width: 4),
          Text(
            badgeText,
            style: TextStyle(
              fontSize: 11,
              color: badgeColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openWebsite() async {
    final url = place.website ?? place.url;
    if (url == null || url.isEmpty) return;

    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  IconData _getCategoryIcon() {
    final category = place.categoryName?.toLowerCase() ?? '';
    final placeType = place.placeType.toLowerCase();
    
    // Check place_type first
    if (placeType == 'restaurant') {
      return Icons.restaurant;
    } else if (placeType == 'bar') {
      return Icons.local_bar;
    } else if (placeType == 'park') {
      return Icons.park;
    }
    
    // Fallback to category name
    if (category.contains('restaurant') || category.contains('restaurante')) {
      return Icons.restaurant;
    } else if (category.contains('hotel') || category.contains('pousada')) {
      return Icons.hotel;
    } else if (category.contains('cafe') || category.contains('café')) {
      return Icons.local_cafe;
    } else if (category.contains('bar') || category.contains('pub')) {
      return Icons.local_bar;
    } else if (category.contains('museum') || category.contains('museu')) {
      return Icons.museum;
    } else if (category.contains('park') || category.contains('parque')) {
      return Icons.park;
    } else if (category.contains('church') || category.contains('igreja')) {
      return Icons.church;
    } else if (category.contains('beach') || category.contains('praia')) {
      return Icons.beach_access;
    } else if (category.contains('theater') || category.contains('teatro')) {
      return Icons.theater_comedy;
    } else {
      return Icons.place;
    }
  }
}


