"""
Data Merger - Combines OSM and CSV data with intelligent priority rules.

This module handles the merging of fresh OSM data with the existing CSV database,
preserving valuable metadata (ratings, reviews, hours) while incorporating new places
and flagging potentially closed establishments.
"""

import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import shutil

from .osm_fetcher import OSMPlace
from .place_matcher import MatchResult, MatchStatus, PlaceMatcher

logger = logging.getLogger(__name__)


class DataMerger:
    """
    Merges OSM data with existing CSV database.
    
    Priority rules:
    - Matched places: Keep rich CSV data, optionally update coordinates
    - New places: Add from OSM with basic info, mark for enrichment
    - Possibly closed: Keep in database but flag for review
    """
    
    # CSV columns to preserve from original data (these have valuable info)
    PRESERVE_COLUMNS = [
        'title', 'titleFormatted', 'address', 'adressFormatted', 'addressFormatted',
        'phone', 'phoneUnformatted', 'website',
        'totalScore', 'reviewsCount',
        'reviewsDistribution/fiveStar', 'reviewsDistribution/fourStar',
        'reviewsDistribution/threeStar', 'reviewsDistribution/twoStar',
        'reviewsDistribution/oneStar',
        'categoryName', 'categories/0', 'categories/1', 'categories/2',
        'categories/3', 'categories/4', 'categories/5', 'categories/6',
        'categories/7', 'categories/8',
        'businessTime', 'price', 'menu',
        'placeId', 'cid', 'fid', 'url', 'googleFoodUrl', 'reserveTableUrl',
        'city', 'state', 'countryCode', 'postalCode',
        'neighborhood', 'street', 'streetFormatted',
        'locatedIn', 'subTitle',
        'source_file', 'Custom'
    ]
    
    def __init__(
        self,
        csv_path: str,
        output_dir: str = None,
        backup_on_merge: bool = True
    ):
        """
        Initialize the merger.
        
        Args:
            csv_path: Path to the existing CSV file
            output_dir: Directory for output files (default: same as csv_path)
            backup_on_merge: Whether to create a backup before merging
        """
        self.csv_path = Path(csv_path)
        self.output_dir = Path(output_dir) if output_dir else self.csv_path.parent
        self.backup_on_merge = backup_on_merge
        
        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'refresh_reports').mkdir(exist_ok=True)
        
    def load_csv(self) -> pd.DataFrame:
        """Load the existing CSV database."""
        logger.info(f"Loading CSV from {self.csv_path}")
        df = pd.read_csv(self.csv_path, low_memory=False)
        logger.info(f"Loaded {len(df)} places from CSV")
        return df
    
    def backup_csv(self) -> Path:
        """Create a timestamped backup of the CSV file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{self.csv_path.stem}_backup_{timestamp}.csv"
        backup_path = self.output_dir / backup_name
        
        shutil.copy2(self.csv_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        return backup_path
    
    def osm_place_to_csv_row(self, osm_place: OSMPlace) -> Dict[str, Any]:
        """
        Convert an OSM place to a CSV row format.
        
        Args:
            osm_place: The OSM place to convert
            
        Returns:
            Dictionary matching CSV column format
        """
        return {
            'title': osm_place.name,
            'titleFormatted': osm_place.name,
            'address': osm_place.address or '',
            'adressFormatted': osm_place.address or '',
            'addressFormatted': osm_place.address or '',
            'formattedAddress': osm_place.address or '',
            'location/lat': osm_place.latitude,
            'location/lng': osm_place.longitude,
            'phone': osm_place.phone or '',
            'phoneUnformatted': (osm_place.phone or '').replace(' ', '').replace('-', ''),
            'website': osm_place.website or '',
            'categoryName': osm_place.category.replace('_', ' ').title(),
            'categories/0': osm_place.category.replace('_', ' ').title(),
            'businessTime': osm_place.opening_hours or '',
            'city': 'Belém',
            'state': 'Pará',
            'countryCode': 'BR',
            'totalScore': None,
            'reviewsCount': 0,
            'placeId': f"osm_{osm_place.osm_type}_{osm_place.osm_id}",
            'source_file': 'osm_import',
            'loaded_at': datetime.now().isoformat(),
            'data_source': 'osm',
            'needs_enrichment': True,
            'status': 'active',
            'osm_id': osm_place.osm_id,
            'osm_type': osm_place.osm_type,
        }
    
    def merge(
        self,
        match_results: List[MatchResult],
        update_coordinates: bool = False,
        progress_callback: Optional[callable] = None
    ) -> pd.DataFrame:
        """
        Merge OSM data with CSV based on match results.
        
        Args:
            match_results: Results from PlaceMatcher.match_all()
            update_coordinates: Whether to update coordinates from OSM
            progress_callback: Optional callback for progress updates
            
        Returns:
            Merged DataFrame
        """
        if self.backup_on_merge:
            self.backup_csv()
        
        df = self.load_csv()
        
        # Add new columns if they don't exist
        for col in ['data_source', 'needs_enrichment', 'status', 'osm_id', 'osm_type', 'match_confidence']:
            if col not in df.columns:
                df[col] = None
        
        # Set default values for existing data
        df['data_source'] = df['data_source'].fillna('google')
        df['needs_enrichment'] = df['needs_enrichment'].fillna(False)
        df['status'] = df['status'].fillna('active')
        
        # Create a mapping from placeId/cid to row index
        id_to_index = {}
        for idx, row in df.iterrows():
            place_id = row.get('placeId') or row.get('cid')
            if place_id:
                id_to_index[place_id] = idx
        
        new_rows = []
        matched_count = 0
        updated_count = 0
        closed_count = 0
        
        if progress_callback:
            progress_callback("Processing match results...")
        
        for i, result in enumerate(match_results):
            if progress_callback and i % 500 == 0:
                progress_callback(f"Processing: {i}/{len(match_results)}")
            
            if result.status == MatchStatus.MATCHED:
                # Update existing record
                csv_place = result.csv_place
                place_id = csv_place.get('placeId') or csv_place.get('cid')
                
                if place_id and place_id in id_to_index:
                    idx = id_to_index[place_id]
                    
                    # Update coordinates if requested and OSM has them
                    if update_coordinates and result.osm_place:
                        df.at[idx, 'location/lat'] = result.osm_place.latitude
                        df.at[idx, 'location/lng'] = result.osm_place.longitude
                    
                    # Add OSM metadata
                    if result.osm_place:
                        df.at[idx, 'osm_id'] = result.osm_place.osm_id
                        df.at[idx, 'osm_type'] = result.osm_place.osm_type
                    
                    df.at[idx, 'match_confidence'] = result.confidence
                    df.at[idx, 'status'] = 'active'
                    
                    matched_count += 1
            
            elif result.status == MatchStatus.NEW:
                # Add new place from OSM
                if result.osm_place:
                    new_row = self.osm_place_to_csv_row(result.osm_place)
                    new_rows.append(new_row)
            
            elif result.status == MatchStatus.POSSIBLY_CLOSED:
                # Mark as possibly closed
                csv_place = result.csv_place
                place_id = csv_place.get('placeId') or csv_place.get('cid')
                
                if place_id and place_id in id_to_index:
                    idx = id_to_index[place_id]
                    df.at[idx, 'status'] = 'possibly_closed'
                    closed_count += 1
        
        # Add new rows
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            df = pd.concat([df, new_df], ignore_index=True)
            logger.info(f"Added {len(new_rows)} new places from OSM")
        
        logger.info(f"Merge complete: {matched_count} matched, {len(new_rows)} new, {closed_count} possibly closed")
        
        return df
    
    def save_merged(self, df: pd.DataFrame, suffix: str = None) -> Path:
        """
        Save the merged DataFrame.
        
        Args:
            df: Merged DataFrame
            suffix: Optional suffix for filename
            
        Returns:
            Path to saved file
        """
        if suffix:
            output_name = f"{self.csv_path.stem}_{suffix}.csv"
        else:
            output_name = self.csv_path.name
        
        output_path = self.output_dir / 'csvs' / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_path, index=False)
        logger.info(f"Saved merged data to {output_path}")
        
        return output_path
    
    def generate_report(
        self,
        match_results: List[MatchResult],
        matcher: PlaceMatcher
    ) -> str:
        """
        Generate a detailed text report of the refresh operation.
        
        Args:
            match_results: Results from matching
            matcher: The PlaceMatcher used (for summary stats)
            
        Returns:
            Report text
        """
        summary = matcher.get_match_summary(match_results)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Categorize results
        matched = [r for r in match_results if r.status == MatchStatus.MATCHED]
        new = [r for r in match_results if r.status == MatchStatus.NEW]
        possibly_closed = [r for r in match_results if r.status == MatchStatus.POSSIBLY_CLOSED]
        
        report_lines = [
            "=" * 60,
            "OSM DATA REFRESH REPORT",
            f"Generated: {timestamp}",
            "=" * 60,
            "",
            "SUMMARY",
            "-" * 40,
            f"Total OSM places fetched:    {summary['total_osm_places']}",
            f"Total CSV places:            {summary['total_csv_places']}",
            f"Matched places:              {summary['matched_count']}",
            f"New places (from OSM):       {summary['new_count']}",
            f"Possibly closed:             {summary['possibly_closed_count']}",
            "",
            f"Average match confidence:    {summary['average_confidence']:.3f}",
            f"Average distance (matched):  {summary['average_distance_meters']:.1f}m",
            f"Average name similarity:     {summary['average_name_similarity']:.3f}",
            "",
        ]
        
        # Top new places (by category)
        if new:
            report_lines.extend([
                "NEW PLACES FROM OSM (sample)",
                "-" * 40,
            ])
            
            # Group by category
            by_category = {}
            for r in new:
                if r.osm_place:
                    cat = r.osm_place.category
                    if cat not in by_category:
                        by_category[cat] = []
                    by_category[cat].append(r.osm_place.name)
            
            for cat, names in sorted(by_category.items()):
                report_lines.append(f"\n{cat.upper()} ({len(names)} places):")
                for name in sorted(names)[:10]:  # Show first 10
                    report_lines.append(f"  - {name}")
                if len(names) > 10:
                    report_lines.append(f"  ... and {len(names) - 10} more")
            
            report_lines.append("")
        
        # Possibly closed places
        if possibly_closed:
            report_lines.extend([
                "POSSIBLY CLOSED (not found in OSM)",
                "-" * 40,
                "Note: These may need manual verification",
                "",
            ])
            
            # Sort by review count (popular places first)
            sorted_closed = sorted(
                possibly_closed,
                key=lambda r: r.csv_place.get('reviewsCount', 0) if r.csv_place else 0,
                reverse=True
            )
            
            for r in sorted_closed[:20]:  # Show top 20
                if r.csv_place:
                    name = r.csv_place.get('title', 'Unknown')
                    reviews = r.csv_place.get('reviewsCount', 0)
                    score = r.csv_place.get('totalScore', 'N/A')
                    report_lines.append(f"  - {name} ({reviews} reviews, {score}★)")
            
            if len(possibly_closed) > 20:
                report_lines.append(f"  ... and {len(possibly_closed) - 20} more")
            
            report_lines.append("")
        
        # Low confidence matches (may need review)
        low_confidence = [r for r in matched if r.confidence < 0.7]
        if low_confidence:
            report_lines.extend([
                "LOW CONFIDENCE MATCHES (may need review)",
                "-" * 40,
            ])
            
            for r in sorted(low_confidence, key=lambda x: x.confidence)[:10]:
                osm_name = r.osm_place.name if r.osm_place else 'N/A'
                csv_name = r.csv_place.get('title', 'N/A') if r.csv_place else 'N/A'
                report_lines.append(
                    f"  - OSM: {osm_name}\n"
                    f"    CSV: {csv_name}\n"
                    f"    Confidence: {r.confidence:.2f}, Distance: {r.distance_meters:.1f}m\n"
                )
            
            report_lines.append("")
        
        report_lines.extend([
            "=" * 60,
            "END OF REPORT",
            "=" * 60,
        ])
        
        return "\n".join(report_lines)
    
    def save_report(self, report: str) -> Path:
        """
        Save the report to a file.
        
        Args:
            report: Report text
            
        Returns:
            Path to saved report
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.output_dir / 'refresh_reports' / f"refresh_{timestamp}.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_path.write_text(report, encoding='utf-8')
        logger.info(f"Saved report to {report_path}")
        
        return report_path


def run_full_merge(
    csv_path: str,
    osm_places: List[OSMPlace],
    output_dir: str = None,
    update_coordinates: bool = False,
    dry_run: bool = False,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Run the full merge process.
    
    Args:
        csv_path: Path to existing CSV
        osm_places: List of OSMPlace objects from fetcher
        output_dir: Output directory (optional)
        update_coordinates: Whether to update coordinates from OSM
        dry_run: If True, don't save changes, just generate report
        progress_callback: Optional progress callback
        
    Returns:
        Dictionary with results and paths
    """
    # Load CSV data
    merger = DataMerger(csv_path, output_dir, backup_on_merge=not dry_run)
    df = merger.load_csv()
    csv_places = df.to_dict('records')
    
    # Match places
    if progress_callback:
        progress_callback("Matching places...")
    
    matcher = PlaceMatcher()
    match_results = matcher.match_all(osm_places, csv_places, progress_callback)
    
    # Generate report
    if progress_callback:
        progress_callback("Generating report...")
    
    report = merger.generate_report(match_results, matcher)
    report_path = merger.save_report(report)
    
    result = {
        'report': report,
        'report_path': str(report_path),
        'summary': matcher.get_match_summary(match_results),
    }
    
    if not dry_run:
        # Perform merge
        if progress_callback:
            progress_callback("Merging data...")
        
        merged_df = merger.merge(match_results, update_coordinates, progress_callback)
        output_path = merger.save_merged(merged_df)
        
        result['output_path'] = str(output_path)
        result['total_records'] = len(merged_df)
    
    return result


