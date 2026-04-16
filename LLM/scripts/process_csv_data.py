#!/usr/bin/env python3
"""
Script to process and combine all CSV files using the new DataTools module.
"""

import sys
import os
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.datatools import DataTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to process CSV data."""
    print("🔄 Processing CSV Data with DataTools")
    print("=" * 50)
    
    try:
        # Initialize DataTools
        print("📂 Initializing DataTools...")
        data_tools = DataTools()
        
        # Load and combine all data
        print("\n📊 Loading and combining all CSV files...")
        combined_data = data_tools.load_and_combine_all_data()
        
        print(f"✅ Successfully loaded {len(combined_data)} total entries")
        
        # Get category statistics
        print("\n📈 Getting category statistics...")
        stats = data_tools.get_category_statistics()
        
        print(f"📊 Total entries: {stats['total_entries']}")
        print(f"🏷️  Total distinct categories: {stats['total_categories']}")
        
        print("\n📋 Category distribution:")
        for category_type, count in stats['category_counts'].items():
            if count > 0:
                print(f"  {category_type}: {count} entries")
        
        # Show some sample categories
        print(f"\n🏷️  Sample distinct categories:")
        sample_categories = list(data_tools.distinct_categories)[:20]
        for i, category in enumerate(sample_categories, 1):
            print(f"  {i:2d}. {category}")
        
        if len(data_tools.distinct_categories) > 20:
            print(f"  ... and {len(data_tools.distinct_categories) - 20} more")
        
        # Save combined data
        print("\n💾 Saving combined data...")
        output_path = data_tools.save_combined_data()
        print(f"✅ Combined data saved to: {output_path}")
        
        # Show sample data
        print("\n📋 Sample data (5 entries):")
        sample_data = data_tools.get_sample_data(5)
        for i, (_, row) in enumerate(sample_data.iterrows(), 1):
            title = row.get('title', 'No title')
            category = row.get('categoryName', 'No category')
            address = row.get('address', 'No address')[:50] + "..." if len(str(row.get('address', ''))) > 50 else row.get('address', 'No address')
            print(f"  {i}. {title}")
            print(f"     Category: {category}")
            print(f"     Address: {address}")
            print()
        
        # Update config to use new CSV
        print("⚙️  Updating config to use new combined CSV...")
        data_tools.update_config_csv_path(output_path)
        print("✅ Config updated successfully")
        
        print("\n🎉 Data processing completed successfully!")
        print(f"📁 Combined CSV: {output_path}")
        print(f"📊 Total entries: {len(combined_data)}")
        print(f"🏷️  Categories: {len(data_tools.distinct_categories)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error processing data: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 