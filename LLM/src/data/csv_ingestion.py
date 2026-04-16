"""
CSV Ingestion Pipeline for Places PoC.

Implements exact CSV mapping per spec/02-csv-mapping.md:
- Handles adressFormatted typo → addressFormatted
- Builds categories[] from categories/0..8 + categoryName
- Computes place_type using inference rules
- Normalizes all fields per spec
- Outputs canonical_places.jsonl and ingestion_report.json
"""

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import pandas as pd

logger = logging.getLogger(__name__)


class PlaceTypeInference:
    """Deterministic place type inference per spec/01-domain-model.md"""
    
    # Mapping dictionary (case-insensitive, accent-insensitive)
    TYPE_MAPPINGS = {
        'restaurant': [
            'restaurant', 'restaurante', 'steakhouse', 'pizza', 'pizzaria',
            'sushi', 'churrascaria', 'buffet', 'cafe', 'café', 'coffee'
        ],
        'bar': [
            'bar', 'pub', 'brewery', 'cervejaria', 'boteco'
        ],
        'park': [
            'park', 'parque', 'garden', 'jardim', 'praça', 'praca'
        ]
    }
    
    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Normalize text: remove accents, lowercase."""
        if not text:
            return ''
        # Remove accents
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text.lower().strip()
    
    @classmethod
    def infer_place_type(cls, category_name: Optional[str], categories: List[str]) -> str:
        """
        Infer place_type using precedence rules:
        1. Check categoryName first, if matches STOP
        2. Else check categories/0..8 in order, pick first mapping
        3. If none matches, return 'other'
        """
        # Build candidate list: categoryName first, then categories[]
        candidates = []
        if category_name:
            candidates.append(category_name)
        candidates.extend(categories)
        
        # Check each candidate against mappings
        for candidate in candidates:
            normalized = cls.normalize_text(candidate)
            
            # Check against each type
            for place_type, keywords in cls.TYPE_MAPPINGS.items():
                for keyword in keywords:
                    normalized_keyword = cls.normalize_text(keyword)
                    if normalized_keyword in normalized or normalized in normalized_keyword:
                        return place_type
        
        return 'other'


class CSVIngestionPipeline:
    """CSV ingestion pipeline per PoC spec"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize ingestion pipeline.
        
        Args:
            output_dir: Directory for output files. Defaults to data/ directory.
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "data"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.place_type_inference = PlaceTypeInference()
        self.places_index: List[Dict[str, Any]] = []
    
    def normalize_string(self, value: Any) -> Optional[str]:
        """Normalize string: trim whitespace, empty string => null"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if pd.isna(value):
                return None
            return str(value).strip() if str(value).strip() else None
        value_str = str(value).strip()
        return value_str if value_str else None
    
    def normalize_number(self, value: Any, default: Optional[float] = None) -> Optional[float]:
        """Parse number, invalid => null"""
        if value is None or pd.isna(value):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def normalize_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        """Parse int, invalid => null (or default for distribution fields)"""
        if value is None or pd.isna(value):
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    def normalize_bool(self, value: Any) -> bool:
        """Parse isSponsored boolean"""
        if value is None or pd.isna(value):
            return False
        value_str = str(value).strip().upper()
        true_values = ["TRUE", "1", "YES", "SIM"]
        return value_str in true_values
    
    def build_categories(self, row: pd.Series) -> List[str]:
        """Build categories[] from categories/0..8 + ensure categoryName included"""
        categories = []
        
        # Add categories/0..8 (non-empty, in order)
        for i in range(9):
            cat_key = f'categories/{i}'
            if cat_key in row.index:
                cat_value = self.normalize_string(row[cat_key])
                if cat_value:
                    categories.append(cat_value)
        
        # Ensure categoryName is included if not present
        category_name = self.normalize_string(row.get('categoryName'))
        if category_name and category_name not in categories:
            categories.insert(0, category_name)  # Prepend for precedence
        
        return categories
    
    def ingest_csv(self, csv_path: Path) -> Dict[str, Any]:
        """
        Ingest CSV file and produce canonical places.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Ingestion report dictionary
        """
        logger.info(f"Starting CSV ingestion from {csv_path}")
        
        report = {
            'ingestedCount': 0,
            'skippedCount': 0,
            'parseErrors': [],
            'outputFiles': []
        }
        
        places = []
        jsonl_path = self.output_dir / "canonical_places.jsonl"
        
        try:
            # Read CSV
            df = pd.read_csv(csv_path, low_memory=False)
            logger.info(f"Loaded {len(df)} rows from CSV")
            
            # Check for required placeId column
            if 'placeId' not in df.columns:
                raise ValueError("CSV must contain 'placeId' column")
            
            # Process each row
            for index, row in df.iterrows():
                try:
                    place = self.process_row(row, index)
                    if place:
                        places.append(place)
                        report['ingestedCount'] += 1
                    else:
                        report['skippedCount'] += 1
                except Exception as e:
                    error_msg = f"Row {index}: {str(e)}"
                    logger.warning(error_msg)
                    report['parseErrors'].append(error_msg)
                    report['skippedCount'] += 1
            
            # Write canonical_places.jsonl
            logger.info(f"Writing {len(places)} places to {jsonl_path}")
            with open(jsonl_path, 'w', encoding='utf-8') as f:
                for place in places:
                    f.write(json.dumps(place, ensure_ascii=False) + '\n')
            
            report['outputFiles'].append(str(jsonl_path))
            
            # Build in-memory index
            self.places_index = places
            logger.info(f"Built searchable index with {len(places)} places")
            
            # Write ingestion report
            report_path = self.output_dir / "ingestion_report.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            report['outputFiles'].append(str(report_path))
            
            logger.info(f"Ingestion complete: {report['ingestedCount']} ingested, "
                       f"{report['skippedCount']} skipped, {len(report['parseErrors'])} errors")
            
            return report
            
        except Exception as e:
            logger.error(f"CSV ingestion failed: {e}")
            raise
    
    def process_row(self, row: pd.Series, row_index: int) -> Optional[Dict[str, Any]]:
        """
        Process a single CSV row into canonical Place format.
        
        Returns:
            Place dictionary or None if skipped (missing placeId)
        """
        # Check required placeId
        place_id = self.normalize_string(row.get('placeId'))
        if not place_id:
            logger.warning(f"Row {row_index}: Missing placeId, skipping")
            return None
        
        # Map adressFormatted typo → addressFormatted
        address_formatted = self.normalize_string(
            row.get('addressFormatted') or row.get('adressFormatted')
        )
        
        # Build categories[]
        categories = self.build_categories(row)
        category_name = self.normalize_string(row.get('categoryName'))
        
        # Infer place_type
        place_type = self.place_type_inference.infer_place_type(category_name, categories)
        
        # Build Place object per spec
        place = {
            'placeId': place_id,
            'cid': self.normalize_string(row.get('cid')),
            'fid': self.normalize_string(row.get('fid')),
            'title': self.normalize_string(row.get('title')),
            'titleFormatted': self.normalize_string(row.get('titleFormatted')),
            'subTitle': self.normalize_string(row.get('subTitle')),
            'categoryName': category_name,
            'categories': categories,
            'address': self.normalize_string(row.get('address')),
            'addressFormatted': address_formatted,
            'street': self.normalize_string(row.get('street')),
            'streetFormatted': self.normalize_string(row.get('streetFormatted')),
            'neighborhood': self.normalize_string(row.get('neighborhood')),
            'locatedIn': self.normalize_string(row.get('locatedIn')),
            'city': self.normalize_string(row.get('city')),
            'state': self.normalize_string(row.get('state')),
            'postalCode': self.normalize_string(row.get('postalCode')),
            'countryCode': self.normalize_string(row.get('countryCode')),
            'location': {
                'lat': self.normalize_number(row.get('location/lat')),
                'lng': self.normalize_number(row.get('location/lng'))
            },
            'phone': self.normalize_string(row.get('phone')),
            'phoneUnformatted': self.normalize_string(row.get('phoneUnformatted')),
            'url': self.normalize_string(row.get('url')),
            'website': self.normalize_string(row.get('website')),
            'googleFoodUrl': self.normalize_string(row.get('googleFoodUrl')),
            'menu': self.normalize_string(row.get('menu')),
            'reserveTableUrl': self.normalize_string(row.get('reserveTableUrl')),
            'price': self.normalize_number(row.get('price')),
            'rank': self.normalize_number(row.get('rank')),
            'totalScore': self.normalize_number(row.get('totalScore')),
            'reviewsCount': self.normalize_int(row.get('reviewsCount')),
            'reviewsDistribution': {
                'oneStar': self.normalize_int(row.get('reviewsDistribution/oneStar'), 0),
                'twoStar': self.normalize_int(row.get('reviewsDistribution/twoStar'), 0),
                'threeStar': self.normalize_int(row.get('reviewsDistribution/threeStar'), 0),
                'fourStar': self.normalize_int(row.get('reviewsDistribution/fourStar'), 0),
                'fiveStar': self.normalize_int(row.get('reviewsDistribution/fiveStar'), 0)
            },
            'isSponsored': self.normalize_bool(row.get('IsSponsored')),
            'businessTime': self.normalize_string(row.get('businessTime')),
            'place_type': place_type
        }
        
        return place
    
    def get_places_index(self) -> List[Dict[str, Any]]:
        """Get the in-memory searchable index of places"""
        return self.places_index
