"""
Data loader module for loading all places into memory for fast structured filtering.
"""

import logging
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd

from belem_converse.utils.exceptions import DataLoadError

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Data loader for loading all places into memory for fast structured filtering.
    """
    
    def __init__(self, csv_path: str = None):
        """
        Initialize the data loader.
        
        Args:
            csv_path: Path to CSV file. If None, uses default from config.
        """
        if csv_path is None:
            from belem_converse.utils.config import DATA_CONFIG
            csv_path = DATA_CONFIG["csv_path"]
        
        self.csv_path = csv_path
        self.places_data = None
        self._loaded = False
    
    def load_all_places(self) -> List[Dict[str, Any]]:
        """
        Load all places from CSV into memory.
        
        Returns:
            List of all places as dictionaries
            
        Raises:
            DataLoadError: If there's an error loading the data
        """
        try:
            if self.places_data is not None:
                logger.info("Using cached places data")
                return self.places_data
            
            csv_file = Path(self.csv_path)
            if not csv_file.exists():
                raise DataLoadError(f"CSV file not found: {csv_file}")
            
            logger.info(f"Loading all places from {csv_file}")
            
            # Read CSV with pandas for better performance
            df = pd.read_csv(csv_file)
            logger.info(f"Loaded {len(df)} places from CSV")
            
            # Convert to list of dictionaries
            places_data = []
            for index, row in df.iterrows():
                try:
                    place_dict = {}
                    
                    # Convert all columns to place data format
                    for column in df.columns:
                        value = row[column]
                        
                        # Handle NaN values
                        if pd.isna(value):
                            place_dict[column] = ''
                        else:
                            # Keep original data type, only convert to string if needed
                            place_dict[column] = value
                    
                    places_data.append(place_dict)
                    
                    # Log progress every 100 rows
                    if (index + 1) % 100 == 0:
                        logger.info(f"Processed {index + 1} places...")
                        
                except Exception as row_error:
                    logger.warning(f"Error processing row {index}: {row_error}")
                    continue
            
            # Cache the data
            self.places_data = places_data
            
            logger.info(f"Successfully loaded {len(places_data)} places into memory")
            return places_data
            
        except Exception as e:
            logger.error(f"Error loading places data: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise DataLoadError(f"Failed to load places data: {str(e)}") from e
    
    def reload_data(self) -> List[Dict[str, Any]]:
        """
        Reload data from CSV (clears cache).
        
        Returns:
            List of all places as dictionaries
        """
        logger.info("Reloading places data from CSV")
        self.places_data = None
        return self.load_all_places()
    
    def get_places_count(self) -> int:
        """
        Get the total number of places loaded.
        
        Returns:
            Number of places
        """
        if self.places_data is None:
            self.load_all_places()
        return len(self.places_data)
    
    def get_sample_places(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get a sample of places for testing.
        
        Args:
            n: Number of sample places to return
            
        Returns:
            List of sample places
        """
        if self.places_data is None:
            self.load_all_places()
        
        return self.places_data[:n]
    
    def get_places_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all places in a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of places in the category
        """
        if self.places_data is None:
            self.load_all_places()
        
        category_lower = category.lower()
        filtered_places = []
        
        for place in self.places_data:
            # Check main category
            main_category = place.get('categoryName', '').lower()
            if category_lower in main_category:
                filtered_places.append(place)
                continue
            
            # Check sub-categories
            categories = []
            for i in range(9):  # categories/0 to categories/8
                cat_key = f'categories/{i}'
                cat_value = place.get(cat_key, '').lower()
                if cat_value:
                    categories.append(cat_value)
            
            if any(category_lower in cat for cat in categories):
                filtered_places.append(place)
        
        return filtered_places 