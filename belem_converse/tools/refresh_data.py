#!/usr/bin/env python3
"""Data Refresh CLI Tool.

Command-line interface for refreshing the places database using OpenStreetMap.

Usage:
    python -m belem_converse.tools.refresh_data --dry-run   # preview only
    python -m belem_converse.tools.refresh_data --execute   # apply + rebuild
    python -m belem_converse.tools.refresh_data --report    # comparison only

Options:
    --categories    Comma-separated category list (default: all)
    --no-backup     Skip creating a backup before merge
    --update-coords Update coordinates from OSM for matched places
    --verbose       Enable verbose logging
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, List

from belem_converse.ingest.osm_fetcher import OSMFetcher, get_all_categories
from belem_converse.ingest.place_matcher import PlaceMatcher
from belem_converse.ingest.data_merger import DataMerger, run_full_merge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_progress(message: str):
    """Print progress message to console."""
    print(f"  → {message}")


def find_csv_path() -> Optional[Path]:
    """Find the main CSV file in the project."""
    possible_paths = [
        Path(__file__).parent.parent.parent / 'data' / 'csvs' / 'combined_all_data.csv',
        Path(__file__).parent.parent.parent / 'data' / 'csvs' / 'Cleaned_data_all_filtered.csv',
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def run_dry_run(
    csv_path: Path,
    categories: Optional[List[str]] = None,
    verbose: bool = False
):
    """
    Run in dry-run mode: fetch OSM data, match, and report without saving.
    """
    print("\n" + "=" * 60)
    print("OSM DATA REFRESH - DRY RUN MODE")
    print("=" * 60)
    print(f"\nCSV file: {csv_path}")
    print(f"Categories: {categories if categories else 'all'}")
    print("\nThis will NOT modify any files.\n")
    
    # Fetch OSM data
    print("Step 1: Fetching OSM data...")
    fetcher = OSMFetcher()
    osm_places = fetcher.fetch(categories=categories, progress_callback=print_progress)
    print(f"  ✓ Fetched {len(osm_places)} places from OSM\n")
    
    # Run merge in dry-run mode
    print("Step 2: Matching and analyzing...")
    result = run_full_merge(
        csv_path=str(csv_path),
        osm_places=osm_places,
        dry_run=True,
        progress_callback=print_progress
    )
    
    # Print summary
    summary = result['summary']
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Matched places:       {summary['matched_count']}")
    print(f"  New places (OSM):     {summary['new_count']}")
    print(f"  Possibly closed:      {summary['possibly_closed_count']}")
    print(f"  Average confidence:   {summary['average_confidence']:.2f}")
    print(f"\n  Report saved to: {result['report_path']}")
    print("\nTo apply these changes, run with --execute flag.")


def run_execute(
    csv_path: Path,
    categories: Optional[List[str]] = None,
    update_coords: bool = False,
    no_backup: bool = False,
    verbose: bool = False
):
    """
    Run in execute mode: fetch, match, merge, and rebuild vector store.
    """
    print("\n" + "=" * 60)
    print("OSM DATA REFRESH - EXECUTE MODE")
    print("=" * 60)
    print(f"\nCSV file: {csv_path}")
    print(f"Categories: {categories if categories else 'all'}")
    print(f"Update coordinates: {update_coords}")
    print(f"Create backup: {not no_backup}")
    
    # Confirm
    response = input("\nThis will modify the database. Continue? [y/N]: ")
    if response.lower() != 'y':
        print("Aborted.")
        return
    
    print("\nStep 1: Fetching OSM data...")
    fetcher = OSMFetcher()
    osm_places = fetcher.fetch(categories=categories, progress_callback=print_progress)
    print(f"  ✓ Fetched {len(osm_places)} places from OSM\n")
    
    # Run full merge
    print("Step 2: Matching and merging...")
    merger = DataMerger(str(csv_path), backup_on_merge=not no_backup)
    
    result = run_full_merge(
        csv_path=str(csv_path),
        osm_places=osm_places,
        update_coordinates=update_coords,
        dry_run=False,
        progress_callback=print_progress
    )
    
    # Print summary
    summary = result['summary']
    print("\n" + "=" * 60)
    print("MERGE COMPLETE")
    print("=" * 60)
    print(f"  Matched places:       {summary['matched_count']}")
    print(f"  New places added:     {summary['new_count']}")
    print(f"  Marked as closed:     {summary['possibly_closed_count']}")
    print(f"  Total records now:    {result.get('total_records', 'N/A')}")
    print(f"\n  Output file: {result.get('output_path', 'N/A')}")
    print(f"  Report: {result['report_path']}")
    
    # Rebuild vector store
    print("\nStep 3: Rebuilding vector store...")
    try:
        from belem_converse.ingest.vector_store import VectorStoreManager
        vsm = VectorStoreManager()
        if hasattr(vsm, 'rebuild_from_csv'):
            vsm.rebuild_from_csv(result.get('output_path'))
            print("  ✓ Vector store rebuilt successfully")
        else:
            print("  ⚠ rebuild_from_csv not available - please rebuild manually")
    except Exception as e:
        logger.warning(f"Could not rebuild vector store: {e}")
        print(f"  ⚠ Could not rebuild vector store: {e}")
        print("  Run your normal initialization to rebuild the vector store.")
    
    print("\n✓ Data refresh complete!")


def run_report_only(csv_path: Path, verbose: bool = False):
    """
    Run in report-only mode: just generate a comparison report.
    """
    print("\n" + "=" * 60)
    print("OSM DATA REFRESH - REPORT ONLY MODE")
    print("=" * 60)
    print(f"\nCSV file: {csv_path}")
    print("\nThis will fetch OSM data and generate a comparison report.\n")
    
    # Fetch OSM data
    print("Step 1: Fetching OSM data...")
    fetcher = OSMFetcher()
    osm_places = fetcher.fetch(progress_callback=print_progress)
    print(f"  ✓ Fetched {len(osm_places)} places from OSM\n")
    
    # Run merge in dry-run mode
    print("Step 2: Generating report...")
    result = run_full_merge(
        csv_path=str(csv_path),
        osm_places=osm_places,
        dry_run=True,
        progress_callback=print_progress
    )
    
    print("\n" + "=" * 60)
    print("REPORT GENERATED")
    print("=" * 60)
    print(f"\n  Report saved to: {result['report_path']}")
    print("\n  You can review the report and then run with --execute to apply changes.")


def main():
    parser = argparse.ArgumentParser(
        description='Refresh places database using OpenStreetMap data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tools.refresh_data --dry-run
  python -m tools.refresh_data --execute --update-coords
  python -m tools.refresh_data --report --categories restaurant,cafe,hotel
        """
    )
    
    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without saving'
    )
    mode_group.add_argument(
        '--execute',
        action='store_true',
        help='Apply changes and rebuild vector store'
    )
    mode_group.add_argument(
        '--report',
        action='store_true',
        help='Generate comparison report only'
    )
    
    # Options
    parser.add_argument(
        '--csv-path',
        type=str,
        help='Path to the CSV file (auto-detected if not specified)'
    )
    parser.add_argument(
        '--categories',
        type=str,
        help='Comma-separated list of categories to fetch (default: all)'
    )
    parser.add_argument(
        '--update-coords',
        action='store_true',
        help='Update coordinates from OSM for matched places'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating a backup before merge'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Find CSV path
    if args.csv_path:
        csv_path = Path(args.csv_path)
        if not csv_path.exists():
            print(f"Error: CSV file not found: {csv_path}")
            sys.exit(1)
    else:
        csv_path = find_csv_path()
        if not csv_path:
            print("Error: Could not find CSV file. Please specify with --csv-path")
            sys.exit(1)
    
    # Parse categories
    categories = None
    if args.categories:
        categories = [c.strip() for c in args.categories.split(',')]
        valid_cats = get_all_categories()
        for cat in categories:
            if cat not in valid_cats:
                print(f"Warning: Unknown category '{cat}'. Valid categories:")
                for c in sorted(valid_cats):
                    print(f"  - {c}")
                sys.exit(1)
    
    # Run appropriate mode
    try:
        if args.dry_run:
            run_dry_run(csv_path, categories, args.verbose)
        elif args.execute:
            run_execute(csv_path, categories, args.update_coords, args.no_backup, args.verbose)
        elif args.report:
            run_report_only(csv_path, args.verbose)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception("Error during data refresh")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()


