from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
from typing import Optional

def process_business_hours(file_path: str) -> Optional[pd.DataFrame]:
    """
    Process business hours from Google Maps links in a spreadsheet.
    
    Args:
        file_path: Path to CSV/XLSX file containing 'MapsLink' column
        
    Returns:
        Modified DataFrame or None if error occurs
    """
    try:
        # Read input file
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path, engine='openpyxl')
            
        # Verify columns
        if 'MapsLink' not in df.columns:
            print("Error: Missing 'MapsLink' column")
            return None
            
        # Add OpenTime column
        if 'OpenTime' in df.columns:
            print("Warning: Overwriting existing 'OpenTime' column")
        df['OpenTime'] = ''
        
        # Configure browser
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        driver = webdriver.Chrome(service=service, options=options)
        
        # Process each row
        for index, row in df.iterrows():
            url = row['MapsLink']
            if not isinstance(url, str) or 'maps.google' not in url:
                continue
                
            try:
                driver.get(url)
                time.sleep(2)  # Wait for page load
                
                # Extract business hours
                hours_element = driver.find_elements(By.CSS_SELECTOR, '[jsaction="pane.rating.moreReviews"]')
                if hours_element:
                    hours_text = hours_element[0].text
                    processed = process_hours_text(hours_text)
                    df.at[index, 'OpenTime'] = processed
                    
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")
                
        # Cleanup and save
        driver.quit()
        df.to_excel(file_path, index=False, engine='openpyxl')
        return df
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        return None

def process_hours_text(text: str) -> str:
    """Parse raw hours text into natural language format"""
    days_match = re.search(r'([A-Za-z]+(?:,[A-Za-z]+)*)\s+([\d:]+ [AP]M - [\d:]+ [AP]M)', text)
    if days_match:
        days = days_match.group(1).split(',')
        hours = days_match.group(2)
        
        if len(days) > 1:
            day_range = f"{days[0].strip()}s to {days[-1].strip()}s"
        else:
            day_range = f"{days[0].strip()}s"
            
        return f"{day_range}, {hours.replace('-', 'to')}"
    return text

def transfer_business_hours(source_path: str, dest_path: str) -> Optional[pd.DataFrame]:
    """
    Transfer processed business hours between files based on matching titles.
    
    Args:
        source_path: Path to source file with openingHours columns
        dest_path: Path to destination file to receive businessTime column
        
    Returns:
        Modified destination DataFrame or None if error occurs
    """
    try:
        from datetime import datetime
        import os
        
        # Create backup directory
        backup_dir = os.path.join(os.path.dirname(dest_path), 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Read files
        source_df = pd.read_csv(source_path) if source_path.endswith('.csv') else pd.read_excel(source_path, engine='openpyxl')
        dest_df = pd.read_csv(dest_path) if dest_path.endswith('.csv') else pd.read_excel(dest_path, engine='openpyxl')

        # Verify columns
        if 'title' not in source_df.columns or 'title' not in dest_df.columns:
            print("Error: Missing 'title' column in one or both files")
            return None

        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{os.path.basename(dest_path)}_{timestamp}")
        dest_df.to_csv(backup_path, index=False)
        print(f"Created backup at: {backup_path}")

        # Initialize businessTime column with N/A placeholders
        if 'businessTime' not in dest_df.columns:
            dest_df['businessTime'] = 'N/A'

        # Create title index for source data
        source_titles = source_df.set_index('title')
        error_log = []

        # Process each row in destination
        for index, row in dest_df.iterrows():
            try:
                title = row['title']
                if title not in source_titles.index:
                    continue
                
                source_row = source_titles.loc[title]
                current_business_time = dest_df.at[index, 'businessTime']
                
                # Only process N/A or empty values
                if pd.isna(current_business_time) or str(current_business_time).strip() in ['', 'N/A']:
                    hours_entries = []
                    current_range = []
                    current_hours = None
                    
                    for day in range(7):
                        col_name = f'openingHours/{day}/hours'
                        hour_data = str(source_row.get(col_name, '')).strip()
                        
                        if not hour_data or hour_data == 'nan':
                            continue
                            
                        try:
                            if hour_data == 'Fechado':
                                formatted = 'Closed'
                            else:
                                formatted = convert_to_12h(hour_data)
                            
                            if formatted == current_hours and current_range:
                                current_range[1] = day
                            else:
                                if current_range:
                                    hours_entries.append(format_range(current_range, current_hours))
                                current_range = [day, day]
                                current_hours = formatted
                        except Exception as e:
                            error_log.append({
                                'timestamp': datetime.now().isoformat(),
                                'title': title,
                                'error': f"Day {day} processing failed: {str(e)}"
                            })
                    
                    if current_range:
                        hours_entries.append(format_range(current_range, current_hours))
                    
                    dest_df.at[index, 'businessTime'] = '; '.join(hours_entries) if hours_entries else 'N/A'

            except Exception as e:
                error_log.append({
                    'timestamp': datetime.now().isoformat(),
                    'title': title,
                    'error': str(e)
                })

        # Save error log if any errors occurred
        if error_log:
            error_path = os.path.join(backup_dir, 'transfer_errors.csv')
            pd.DataFrame(error_log).to_csv(error_path, mode='a', header=not os.path.exists(error_path), index=False)
            print(f"Logged {len(error_log)} errors to: {error_path}")

        # Save updated destination file
        if dest_path.endswith('.csv'):
            dest_df.to_csv(dest_path, index=False)
        else:
            dest_df.to_excel(dest_path, index=False, engine='openpyxl')
            
        return dest_df

    except Exception as e:
        print(f"Fatal transfer error: {str(e)}")
        return None

def convert_to_12h(time_str: str) -> str:
    """Convert 24h time format to 12h format"""
    try:
        if '-' not in time_str:
            return time_str
            
        open_time, close_time = time_str.split('-')
        return f"{parse_time(open_time)}-{parse_time(close_time)}"
    except:
        return "Invalid format"

def parse_time(t: str) -> str:
    """Parse individual time string to 12h format"""
    try:
        hours, minutes = map(int, t.split(':'))
        period = 'am' if hours < 12 else 'pm'
        if hours > 12:
            hours -= 12
        elif hours == 0:
            hours = 12
        return f"{hours}:{minutes:02d}{period}" if minutes != 0 else f"{hours}{period}"
    except:
        return t

def format_range(day_range: list, hours: str) -> str:
    """Format day range and hours into natural language"""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    start_day = days[day_range[0]]
    end_day = days[day_range[1]]
    
    if day_range[0] == day_range[1]:
        return f"{start_day}: {hours}"
    return f"{start_day}-{end_day}: {hours}"

if __name__ == "__main__":
    # Example usage
    process_business_hours('../data/Tourist_attractions_ROI_formatted.csv')
    transfer_business_hours('source_data.xlsx', 'dest_data.csv')
