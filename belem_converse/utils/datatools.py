"""
Data Tools Module for loading and preprocessing multiple CSV files.
Handles concatenation, data cleaning, and category extraction for the RAG travel guide system.
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class DataTools:
    """
    Comprehensive data tools for loading and preprocessing multiple CSV files.
    Handles concatenation, data cleaning, and category extraction.
    """
    
    def __init__(self, csvs_directory: Optional[str] = None):
        """
        Initialize DataTools.
        
        Args:
            csvs_directory: Path to directory containing CSV files. If None, uses default.
        """
        if csvs_directory is None:
            try:
                from ..agent.config import DATA_CONFIG
                base_path = Path(DATA_CONFIG["csv_path"]).parent
                csvs_directory = str(base_path)
            except ImportError:
                # Fallback to default path
                csvs_directory = str(Path(__file__).parent.parent.parent / "data" / "csvs")
        
        self.csvs_directory = Path(csvs_directory)
        self.combined_data: Optional[pd.DataFrame] = None
        self.distinct_categories: Set[str] = set()
        self.category_mapping: Dict[str, List[str]] = {}
        
    def get_csv_files(self) -> List[Path]:
        """
        Get all CSV files in the directory.
        
        Returns:
            List of CSV file paths
        """
        csv_files = []
        if self.csvs_directory.exists():
            csv_files = list(self.csvs_directory.glob("*.csv"))
            # Also include Excel files
            csv_files.extend(list(self.csvs_directory.glob("*.xlsx")))
        
        logger.info(f"Found {len(csv_files)} data files: {[f.name for f in csv_files]}")
        return csv_files
    
    def load_csv_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """
        Load a single CSV file with error handling.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            DataFrame or None if loading fails
        """
        try:
            logger.info(f"Loading {file_path.name}...")
            
            # Handle different file types
            if file_path.suffix.lower() == '.xlsx':
                df = pd.read_excel(file_path)
            else:
                # Try different encodings
                encodings = ['utf-8', 'latin-1', 'windows-1252', 'iso-8859-1']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        logger.info(f"Successfully loaded {file_path.name} with {encoding} encoding")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    logger.error(f"Failed to load {file_path.name} with any encoding")
                    return None
            
            # Add source file information
            df['source_file'] = file_path.name
            df['loaded_at'] = datetime.now().isoformat()
            
            logger.info(f"Loaded {len(df)} rows from {file_path.name}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading {file_path.name}: {str(e)}")
            return None
    
    def preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess a DataFrame to clean and standardize data.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Preprocessed DataFrame
        """
        logger.info("Preprocessing DataFrame...")
        
        # Make a copy to avoid modifying original
        df_clean = df.copy()
        
        # Handle missing values
        df_clean = df_clean.fillna('')
        
        # Clean string columns
        string_columns = df_clean.select_dtypes(include=['object']).columns
        for col in string_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str).str.strip()
                # Replace empty strings with empty string instead of NaN
                df_clean[col] = df_clean[col].replace(['nan', 'None', 'NULL'], '')
        
        # Clean numeric columns
        numeric_columns = ['reviewsCount', 'totalScore', 'rank', 'price']
        for col in numeric_columns:
            if col in df_clean.columns:
                # Convert to numeric, errors='coerce' will convert invalid values to NaN
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                # Fill NaN with 0 for numeric columns
                df_clean[col] = df_clean[col].fillna(0)
        
        # Clean coordinate columns
        coord_columns = ['location/lat', 'location/lng']
        for col in coord_columns:
            if col in df_clean.columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
                # Remove invalid coordinates (outside reasonable bounds)
                if col == 'location/lat':
                    df_clean[col] = df_clean[col].apply(
                        lambda x: x if -90 <= x <= 90 else np.nan
                    )
                elif col == 'location/lng':
                    df_clean[col] = df_clean[col].apply(
                        lambda x: x if -180 <= x <= 180 else np.nan
                    )
        
        # Standardize title and titleFormatted columns
        if 'title' in df_clean.columns:
            df_clean['title'] = df_clean['title'].str.strip()
        
        if 'titleFormatted' in df_clean.columns:
            df_clean['titleFormatted'] = df_clean['titleFormatted'].str.strip()
            # If titleFormatted is empty, use title
            df_clean['titleFormatted'] = df_clean['titleFormatted'].fillna(df_clean['title'])
        
        # Standardize address columns
        address_columns = ['address', 'addressFormatted']
        for col in address_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].str.strip()
                # If addressFormatted is empty, use address
                if col == 'addressFormatted':
                    df_clean[col] = df_clean[col].fillna(df_clean['address'])
        
        # Clean category columns
        category_columns = ['categoryName'] + [f'categories/{i}' for i in range(10)]
        for col in category_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].str.strip()
                df_clean[col] = df_clean[col].replace(['nan', 'None', 'NULL'], '')
        
        # Remove completely empty rows
        df_clean = df_clean.dropna(how='all')
        
        logger.info(f"Preprocessing completed. DataFrame shape: {df_clean.shape}")
        return df_clean
    
    def extract_distinct_categories(self, df: pd.DataFrame) -> Set[str]:
        """
        Extract distinct categories from the DataFrame.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Set of distinct categories
        """
        categories = set()
        
        # Check categoryName column
        if 'categoryName' in df.columns:
            categories.update(df['categoryName'].dropna().unique())
        
        # Check categories/0 through categories/9 columns
        for i in range(10):
            col_name = f'categories/{i}'
            if col_name in df.columns:
                categories.update(df[col_name].dropna().unique())
        
        # Clean categories
        cleaned_categories = set()
        for category in categories:
            if category and str(category).strip():
                cleaned_cat = str(category).strip()
                cleaned_categories.add(cleaned_cat)
        
        logger.info(f"Extracted {len(cleaned_categories)} distinct categories")
        return cleaned_categories
    
    def create_category_mapping(self, categories: Set[str]) -> Dict[str, List[str]]:
        """
        Create a mapping of category types to specific categories.
        
        Args:
            categories: Set of distinct categories
            
        Returns:
            Dictionary mapping category types to lists of categories
        """
        category_mapping = {
            'restaurant': [],
            'hotel': [],
            'bar': [],
            'cafe': [],
            'ice_cream': [],
            'tourist_attraction': [],
            'shopping': [],
            'entertainment': [],
            'other': []
        }
        
        # Define patterns for each category type
        patterns = {
            'restaurant': [
                'restaurant', 'restaurante', 'dining', 'eatery', 'food', 'comida',
                'pizzeria', 'pizzaria', 'steakhouse', 'churrascaria', 'buffet',
                'fast food', 'lanchonete', 'padaria', 'bakery'
            ],
            'hotel': [
                'hotel', 'motel', 'pousada', 'hostel', 'accommodation', 'lodging',
                'inn', 'resort', 'guesthouse', 'hospedagem'
            ],
            'bar': [
                'bar', 'pub', 'tavern', 'nightclub', 'club', 'disco', 'boate',
                'lounge', 'cocktail bar', 'beer garden'
            ],
            'cafe': [
                'cafe', 'café', 'coffee shop', 'coffeehouse', 'espresso bar',
                'tea house', 'cafeteria'
            ],
            'ice_cream': [
                'ice cream', 'sorvete', 'gelato', 'ice cream shop', 'sorveteria',
                'frozen yogurt', 'gelateria'
            ],
            'tourist_attraction': [
                'tourist attraction', 'atração turística', 'museum', 'museu',
                'park', 'parque', 'monument', 'monumento', 'landmark', 'ponto turístico',
                'historical site', 'sítio histórico', 'church', 'igreja', 'temple',
                'templo', 'theater', 'teatro', 'cinema'
            ],
            'shopping': [
                'shopping', 'mall', 'shopping center', 'center', 'centro comercial',
                'market', 'mercado', 'store', 'loja', 'shop', 'boutique'
            ],
            'entertainment': [
                'entertainment', 'entretenimento', 'amusement', 'diversão',
                'game', 'jogo', 'arcade', 'bowling', 'cinema', 'theater', 'teatro'
            ]
        }
        
        # Categorize each category
        for category in categories:
            category_lower = category.lower()
            categorized = False
            
            for category_type, pattern_list in patterns.items():
                if any(pattern in category_lower for pattern in pattern_list):
                    category_mapping[category_type].append(category)
                    categorized = True
                    break
            
            if not categorized:
                category_mapping['other'].append(category)
        
        # Log category distribution
        for category_type, cat_list in category_mapping.items():
            if cat_list:
                logger.info(f"{category_type}: {len(cat_list)} categories")
        
        return category_mapping
    
    def load_and_combine_all_data(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Load and combine all CSV files into a single DataFrame.
        
        Args:
            force_reload: Force reload even if data is cached
            
        Returns:
            Combined DataFrame
        """
        if self.combined_data is not None and not force_reload:
            logger.info("Using cached combined data")
            return self.combined_data
        
        csv_files = self.get_csv_files()
        if not csv_files:
            raise ValueError(f"No CSV files found in {self.csvs_directory}")
        
        all_dataframes = []
        
        for file_path in csv_files:
            df = self.load_csv_file(file_path)
            if df is not None:
                # Preprocess the DataFrame
                df_clean = self.preprocess_dataframe(df)
                all_dataframes.append(df_clean)
        
        if not all_dataframes:
            raise ValueError("No valid CSV files could be loaded")
        
        # Combine all DataFrames
        logger.info("Combining all DataFrames...")
        combined_df = pd.concat(all_dataframes, ignore_index=True, sort=False)
        
        # Remove duplicates based on key columns
        key_columns = ['title', 'address', 'categoryName']
        available_columns = [col for col in key_columns if col in combined_df.columns]
        
        if available_columns:
            initial_count = len(combined_df)
            combined_df = combined_df.drop_duplicates(subset=available_columns, keep='first')
            removed_count = initial_count - len(combined_df)
            logger.info(f"Removed {removed_count} duplicate entries")
        
        # Extract distinct categories
        self.distinct_categories = self.extract_distinct_categories(combined_df)
        self.category_mapping = self.create_category_mapping(self.distinct_categories)
        
        # Cache the combined data
        self.combined_data = combined_df
        
        logger.info(f"Successfully combined {len(combined_df)} entries from {len(csv_files)} files")
        logger.info(f"Total distinct categories: {len(self.distinct_categories)}")
        
        return combined_df
    
    def save_combined_data(self, output_path: Optional[str] = None) -> str:
        """
        Save the combined data to a CSV file.
        
        Args:
            output_path: Output file path. If None, uses default location.
            
        Returns:
            Path to saved file
        """
        if self.combined_data is None:
            self.load_and_combine_all_data()
        
        if output_path is None:
            output_path = str(self.csvs_directory / "combined_all_data.csv")
        
        output_path_str = str(Path(output_path))
        
        logger.info(f"Saving combined data to {output_path_str}")
        if self.combined_data is not None:
            self.combined_data.to_csv(output_path_str, index=False, encoding='utf-8')
        
        logger.info(f"Combined data saved successfully to {output_path_str}")
        return output_path_str
    
    def get_category_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about categories in the data.
        
        Returns:
            Dictionary with category statistics
        """
        if self.combined_data is None:
            self.load_and_combine_all_data()
        
        stats = {
            'total_entries': len(self.combined_data) if self.combined_data is not None else 0,
            'total_categories': len(self.distinct_categories),
            'category_mapping': self.category_mapping,
            'category_counts': {}
        }
        
        # Count entries per category type
        if self.combined_data is not None:
            for category_type, categories in self.category_mapping.items():
                if categories:
                    # Count entries that have any of these categories
                    count = 0
                    for category in categories:
                        # Build mask dynamically based on available columns
                        mask_conditions = []
                        
                        # Check categoryName column
                        if 'categoryName' in self.combined_data.columns:
                            mask_conditions.append(self.combined_data['categoryName'] == category)
                        
                        # Check categories/0 through categories/9 columns
                        for i in range(10):
                            col_name = f'categories/{i}'
                            if col_name in self.combined_data.columns:
                                mask_conditions.append(self.combined_data[col_name] == category)
                        
                        # Combine all conditions with OR
                        if mask_conditions:
                            mask = mask_conditions[0]
                            for condition in mask_conditions[1:]:
                                mask = mask | condition
                            count += mask.sum()
                    
                    stats['category_counts'][category_type] = int(count)
        
        return stats
    
    def get_sample_data(self, n: int = 5, category: Optional[str] = None) -> pd.DataFrame:
        """
        Get a sample of the data.
        
        Args:
            n: Number of samples to return
            category: Optional category to filter by
            
        Returns:
            Sample DataFrame
        """
        if self.combined_data is None:
            self.load_and_combine_all_data()
        
        if category and self.combined_data is not None:
            # Filter by category
            mask_conditions = []
            
            # Check categoryName column
            if 'categoryName' in self.combined_data.columns:
                mask_conditions.append(self.combined_data['categoryName'] == category)
            
            # Check categories/0 through categories/9 columns
            for i in range(10):
                col_name = f'categories/{i}'
                if col_name in self.combined_data.columns:
                    mask_conditions.append(self.combined_data[col_name] == category)
            
            # Combine all conditions with OR
            if mask_conditions:
                mask = mask_conditions[0]
                for condition in mask_conditions[1:]:
                    mask = mask | condition
                filtered_data = self.combined_data[mask]
                return filtered_data.head(n)
        
        # Return sample without filtering
        if self.combined_data is not None:
            return self.combined_data.head(n)
        else:
            return pd.DataFrame()
    
    def update_config_csv_path(self, new_path: str) -> None:
        """
        Update the config to use the new combined CSV file.
        
        Args:
            new_path: Path to the new combined CSV file
        """
        try:
            # Get the config file path
            config_path = Path(__file__).parent.parent / "agent" / "config.py"
            
            if config_path.exists():
                # Read the current config
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                
                # Find and replace the CSV path
                import re
                # Look for the DATA_CONFIG pattern
                pattern = r'("csv_path":\s*str\()([^)]+)("\))'
                replacement = r'\1' + str(Path(new_path).parent.parent.parent / "data" / "csvs" / Path(new_path).name) + r'\3'
                
                new_config_content = re.sub(pattern, replacement, config_content)
                
                # Write the updated config
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(new_config_content)
                
                logger.info(f"Updated config CSV path to {new_path}")
            else:
                logger.warning(f"Config file not found at {config_path}")
                
        except Exception as e:
            logger.error(f"Error updating config: {str(e)}")


def main():
    """
    Main function to run the data tools.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Data Tools for CSV processing')
    parser.add_argument('--csvs-dir', type=str, help='Directory containing CSV files')
    parser.add_argument('--output', type=str, help='Output path for combined CSV')
    parser.add_argument('--update-config', action='store_true', help='Update config to use new CSV')
    parser.add_argument('--stats', action='store_true', help='Show category statistics')
    parser.add_argument('--sample', type=int, default=5, help='Show sample data')
    
    args = parser.parse_args()
    
    # Initialize DataTools
    data_tools = DataTools(args.csvs_dir)
    
    try:
        # Load and combine data
        print("Loading and combining CSV files...")
        combined_data = data_tools.load_and_combine_all_data()
        
        # Save combined data
        if args.output:
            output_path = data_tools.save_combined_data(args.output)
        else:
            output_path = data_tools.save_combined_data()
        
        print(f"Combined data saved to: {output_path}")
        
        # Update config if requested
        if args.update_config:
            data_tools.update_config_csv_path(output_path)
            print("Config updated to use new CSV file")
        
        # Show statistics if requested
        if args.stats:
            stats = data_tools.get_category_statistics()
            print("\nCategory Statistics:")
            print(f"Total entries: {stats['total_entries']}")
            print(f"Total categories: {stats['total_categories']}")
            print("\nCategory counts:")
            for category_type, count in stats['category_counts'].items():
                print(f"  {category_type}: {count}")
        
        # Show sample data if requested
        if args.sample > 0:
            sample_data = data_tools.get_sample_data(args.sample)
            print(f"\nSample data ({args.sample} entries):")
            print(sample_data[['title', 'categoryName', 'address']].to_string())
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
