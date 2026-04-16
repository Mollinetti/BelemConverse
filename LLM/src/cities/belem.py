"""
Belém city configuration.

Belém do Pará, Brazil - the original city for BelemConverse.
This is the reference implementation for city configurations.
"""

from .base_city import CityConfig


def get_belem_config() -> CityConfig:
    """Get the configuration for Belém, Brazil."""
    
    return CityConfig(
        # Basic info
        name="Belém",
        slug="belem",
        country="Brazil",
        country_code="BR",
        state="Pará",
        
        # Languages
        primary_language="pt",
        supported_languages=["pt", "en"],
        
        # Geographic bounds
        # Belém is roughly at lat -1.4 to -1.5, lng -48.4 to -48.5
        center_coordinates=(-1.4558, -48.4902),
        bounds_min=(-1.6, -48.6),  # SW corner
        bounds_max=(-1.3, -48.3),  # NE corner
        
        # Timezone
        timezone="America/Belem",
        
        # Data paths (relative to LLM/ directory)
        csv_path="data/csvs/combined_all_data.csv",
        chroma_db_path="data/chroma_db",
        
        # Category mappings - generic category to local search terms
        category_mappings={
            'restaurant': [
                'restaurant', 'Restaurant', 'restaurante',
                'Tapioca Restaurant', 'Breakfast restaurant',
                'hamburger restaurant', 'lunch restaurant',
                'traditional foods restaurant', 'fast food restaurant',
                'barbecue restaurant', 'churrascaria', 'Churrascaria',
                'steakhouse', 'Brazilian grill', 'pizza restaurant',
                'Italian restaurant', 'sushi restaurant',
                'Japanese restaurant', 'seafood restaurant',
                'Chinese restaurant', 'regional restaurant'
            ],
            'cafe': [
                'cafe', 'Cafe', 'coffee', 'Coffee shop',
                'ice cream', 'Ice cream shop', 'açaí', 'açaí shop',
                'bakery', 'Espresso bar', 'Snack bar', 'padaria'
            ],
            'hotel': [
                'hotel', 'Hotel', 'hostel', 'pousada',
                'love hotel', 'Motel'
            ],
            'bar': [
                'bar', 'Bar', 'Bar & grill', 'pub', 'nightclub'
            ],
            'shopping': [
                'shopping', 'mall', 'Shopping mall', 'store', 
                'loja', 'mercado', 'feira'
            ],
            'tourist_attraction': [
                'museum', 'Museu', 'church', 'Igreja',
                'park', 'Parque', 'monument', 'Monumento',
                'historical site', 'fortress', 'Fortaleza',
                'plaza', 'Praça', 'beach', 'Praia',
                'cultural center', 'theater', 'Teatro'
            ]
        },
        
        # Subcategory mappings - map subcategories to parent categories
        subcategory_mappings={
            'ice_cream': 'cafe',
            'acai': 'cafe',
            'açaí': 'cafe',
            'coffee': 'cafe',
            'bakery': 'cafe',
            'pizza': 'restaurant',
            'sushi': 'restaurant',
            'barbecue': 'restaurant',
            'churrascaria': 'restaurant',
            'tapioca': 'restaurant',
            'museum': 'tourist_attraction',
            'church': 'tourist_attraction',
            'park': 'tourist_attraction',
            'beach': 'tourist_attraction'
        },
        
        # Special local categories unique to Belém
        local_categories=[
            'açaí',  # Açaí is especially important in Belém
            'tapioca',  # Tapioca restaurants
            'regional cuisine',  # Amazonian cuisine
            'fish market',  # Ver-o-Peso and other markets
            'riverside',  # Places along the river
        ],
        
        # Default search radius in km
        default_search_radius=5.0,
        
        # Currency
        currency_code="BRL",
        currency_symbol="R$"
    )


# Convenience: export the config directly
BELEM_CONFIG = get_belem_config()


