"""
Business Hours Parser for BelemConverse.

Parses the businessTime column format which varies:
- "Monday-Friday: 3 to 9 PM; Saturday-Sunday: 8 to 11:30 AM, 4 to 8 PM"
- "Monday-Sunday: 10 AM to 3 PM"
- "Monday: Closed; Tuesday-Friday: 7 AM to 12 PM, 3 to 8:30 PM"

Provides functionality to check if a place is open at a given time.
"""

import re
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TimeRange:
    """Represents a time range (e.g., 9:00 AM to 5:00 PM)."""
    start: time
    end: time
    
    def contains(self, check_time: time) -> bool:
        """Check if a time falls within this range."""
        # Handle overnight ranges (e.g., 10 PM to 2 AM)
        if self.start <= self.end:
            return self.start <= check_time <= self.end
        else:
            return check_time >= self.start or check_time <= self.end
    
    def __str__(self) -> str:
        return f"{self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')}"


@dataclass
class DaySchedule:
    """Represents the schedule for a single day."""
    day_name: str
    is_closed: bool = False
    time_ranges: List[TimeRange] = field(default_factory=list)
    
    def is_open_at(self, check_time: time) -> bool:
        """Check if open at a specific time."""
        if self.is_closed:
            return False
        return any(tr.contains(check_time) for tr in self.time_ranges)
    
    def __str__(self) -> str:
        if self.is_closed:
            return f"{self.day_name}: Closed"
        ranges = ", ".join(str(tr) for tr in self.time_ranges)
        return f"{self.day_name}: {ranges}"


@dataclass
class BusinessHours:
    """Complete business hours for a place."""
    raw_text: str
    schedules: Dict[str, DaySchedule] = field(default_factory=dict)
    parse_error: Optional[str] = None
    
    # Day name mappings
    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    DAY_ABBREV = {
        'mon': 'Monday', 'tue': 'Tuesday', 'wed': 'Wednesday',
        'thu': 'Thursday', 'fri': 'Friday', 'sat': 'Saturday', 'sun': 'Sunday',
        'segunda': 'Monday', 'terça': 'Tuesday', 'quarta': 'Wednesday',
        'quinta': 'Thursday', 'sexta': 'Friday', 'sábado': 'Saturday', 'domingo': 'Sunday'
    }
    
    def is_open_at(self, day: str, check_time: time) -> bool:
        """Check if open on a specific day and time."""
        day_schedule = self.schedules.get(day)
        if day_schedule is None:
            return False
        return day_schedule.is_open_at(check_time)
    
    def is_open_now(self) -> bool:
        """Check if currently open."""
        now = datetime.now()
        day_name = now.strftime('%A')
        current_time = now.time()
        return self.is_open_at(day_name, current_time)
    
    def get_hours_for_day(self, day: str) -> Optional[DaySchedule]:
        """Get schedule for a specific day."""
        return self.schedules.get(day)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'raw_text': self.raw_text,
            'schedules': {
                day: {
                    'is_closed': sched.is_closed,
                    'ranges': [
                        {'start': str(tr.start), 'end': str(tr.end)}
                        for tr in sched.time_ranges
                    ]
                }
                for day, sched in self.schedules.items()
            },
            'parse_error': self.parse_error
        }
    
    def __str__(self) -> str:
        if self.parse_error:
            return f"Parse error: {self.parse_error}. Raw: {self.raw_text}"
        return "; ".join(str(s) for s in self.schedules.values())


class BusinessHoursParser:
    """Parser for business hours strings."""
    
    # Regex patterns
    TIME_PATTERN = re.compile(
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)?',
        re.IGNORECASE
    )
    
    DAY_RANGE_PATTERN = re.compile(
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|'
        r'Mon|Tue|Wed|Thu|Fri|Sat|Sun|'
        r'Segunda|Terça|Quarta|Quinta|Sexta|Sábado|Domingo)'
        r'(?:\s*[-–]\s*'
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|'
        r'Mon|Tue|Wed|Thu|Fri|Sat|Sun|'
        r'Segunda|Terça|Quarta|Quinta|Sexta|Sábado|Domingo))?',
        re.IGNORECASE
    )
    
    def __init__(self):
        self.day_order = [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 
            'Friday', 'Saturday', 'Sunday'
        ]
    
    def parse(self, hours_string: str) -> BusinessHours:
        """
        Parse a business hours string.
        
        Supports:
        1. JSON-like weekly structure: {"Mon":"09:00-18:00", ...}
        2. Semicolon-delimited text: "Mon 09:00-18:00; Tue 09:00-18:00; ..."
        3. "Open 24 hours" / "24 horas" => always open
        
        Args:
            hours_string: Raw business hours text
            
        Returns:
            BusinessHours object
        """
        result = BusinessHours(raw_text=hours_string)
        
        if not hours_string or hours_string.strip() == '':
            result.parse_error = "Empty hours string"
            return result
        
        hours_lower = hours_string.lower().strip()
        
        # Check for "Open 24 hours" / "24 horas"
        if ('24' in hours_lower and ('hour' in hours_lower or 'hora' in hours_lower)) or \
           hours_lower in ['open 24 hours', '24 horas', 'aberto 24 horas', '24/7']:
            # Always open - set all days to 00:00-23:59
            for day in self.day_order:
                result.schedules[day] = DaySchedule(
                    day_name=day,
                    is_closed=False,
                    time_ranges=[TimeRange(start=time(0, 0), end=time(23, 59))]
                )
            return result
        
        try:
            # Try JSON-like format first
            if hours_string.strip().startswith('{') and hours_string.strip().endswith('}'):
                import json
                try:
                    json_data = json.loads(hours_string)
                    # Parse JSON structure
                    for day_key, time_str in json_data.items():
                        day = self._normalize_single_day(day_key)
                        if day:
                            if time_str and time_str.lower() != 'closed':
                                time_ranges = self._parse_time_ranges(time_str)
                                result.schedules[day] = DaySchedule(
                                    day_name=day,
                                    is_closed=False,
                                    time_ranges=time_ranges
                                )
                            else:
                                result.schedules[day] = DaySchedule(
                                    day_name=day,
                                    is_closed=True
                                )
                    
                    # Fill in missing days as closed
                    for day in self.day_order:
                        if day not in result.schedules:
                            result.schedules[day] = DaySchedule(
                                day_name=day,
                                is_closed=True
                            )
                    
                    return result
                except json.JSONDecodeError:
                    # Not valid JSON, fall through to semicolon parsing
                    pass
            
            # Semicolon-delimited format
            parts = hours_string.split(';')
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                
                # Split by colon to get days and times
                if ':' in part:
                    day_part, time_part = part.split(':', 1)
                else:
                    continue
                
                # Parse days
                days = self._parse_days(day_part.strip())
                
                # Parse times
                if 'closed' in time_part.lower():
                    # Mark as closed
                    for day in days:
                        result.schedules[day] = DaySchedule(
                            day_name=day, 
                            is_closed=True
                        )
                else:
                    time_ranges = self._parse_time_ranges(time_part.strip())
                    for day in days:
                        result.schedules[day] = DaySchedule(
                            day_name=day,
                            is_closed=False,
                            time_ranges=time_ranges
                        )
            
            # Fill in missing days as closed
            for day in self.day_order:
                if day not in result.schedules:
                    result.schedules[day] = DaySchedule(
                        day_name=day,
                        is_closed=True
                    )
                    
        except Exception as e:
            logger.warning(f"Error parsing hours '{hours_string}': {e}")
            result.parse_error = str(e)
        
        return result
    
    def _parse_days(self, day_string: str) -> List[str]:
        """Parse day string into list of day names."""
        days = []
        day_string = day_string.strip()
        
        # Normalize day names
        day_string = self._normalize_day_names(day_string)
        
        # Check for day range (e.g., "Monday-Friday")
        if '-' in day_string or '–' in day_string:
            # Replace en-dash with hyphen
            day_string = day_string.replace('–', '-')
            parts = day_string.split('-')
            
            if len(parts) == 2:
                start_day = self._normalize_single_day(parts[0].strip())
                end_day = self._normalize_single_day(parts[1].strip())
                
                if start_day and end_day:
                    start_idx = self.day_order.index(start_day)
                    end_idx = self.day_order.index(end_day)
                    
                    # Handle wrap-around (e.g., Friday-Monday)
                    if start_idx <= end_idx:
                        days = self.day_order[start_idx:end_idx + 1]
                    else:
                        days = self.day_order[start_idx:] + self.day_order[:end_idx + 1]
        else:
            # Single day or comma-separated days
            for day_part in day_string.split(','):
                day = self._normalize_single_day(day_part.strip())
                if day:
                    days.append(day)
        
        return days
    
    def _normalize_day_names(self, text: str) -> str:
        """Normalize day abbreviations and Portuguese names."""
        replacements = {
            'Mon': 'Monday', 'Tue': 'Tuesday', 'Wed': 'Wednesday',
            'Thu': 'Thursday', 'Fri': 'Friday', 'Sat': 'Saturday', 'Sun': 'Sunday',
            'Segunda': 'Monday', 'Terça': 'Tuesday', 'Quarta': 'Wednesday',
            'Quinta': 'Thursday', 'Sexta': 'Friday', 'Sábado': 'Saturday', 
            'Domingo': 'Sunday', 'Sabado': 'Saturday'
        }
        
        for abbrev, full in replacements.items():
            text = re.sub(rf'\b{abbrev}\b', full, text, flags=re.IGNORECASE)
        
        return text
    
    def _normalize_single_day(self, day: str) -> Optional[str]:
        """Normalize a single day name."""
        day_lower = day.lower().strip()
        
        for full_day in self.day_order:
            if day_lower == full_day.lower() or day_lower.startswith(full_day.lower()[:3]):
                return full_day
        
        # Check abbreviations
        abbrev_map = {
            'mon': 'Monday', 'tue': 'Tuesday', 'wed': 'Wednesday',
            'thu': 'Thursday', 'fri': 'Friday', 'sat': 'Saturday', 'sun': 'Sunday',
            'segunda': 'Monday', 'terca': 'Tuesday', 'quarta': 'Wednesday',
            'quinta': 'Thursday', 'sexta': 'Friday', 'sabado': 'Saturday', 
            'domingo': 'Sunday'
        }
        
        return abbrev_map.get(day_lower)
    
    def _parse_time_ranges(self, time_string: str) -> List[TimeRange]:
        """Parse time ranges from string."""
        ranges = []
        
        # Split by comma for multiple ranges (e.g., "8 to 11:30 AM, 4 to 8 PM")
        parts = time_string.split(',')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Look for "to" or "-" between times
            time_range = self._parse_single_range(part)
            if time_range:
                ranges.append(time_range)
        
        return ranges
    
    def _parse_single_range(self, text: str) -> Optional[TimeRange]:
        """Parse a single time range (e.g., '9 AM to 5 PM')."""
        try:
            # Replace various separators
            text = text.replace(' to ', ' - ').replace(' a ', ' - ').replace(' até ', ' - ')
            
            # Find all time matches
            times = self.TIME_PATTERN.findall(text)
            
            if len(times) < 2:
                return None
            
            # Parse start and end times
            start_time = self._parse_time(times[0])
            end_time = self._parse_time(times[1])
            
            if start_time and end_time:
                return TimeRange(start=start_time, end=end_time)
                
        except Exception as e:
            logger.debug(f"Error parsing time range '{text}': {e}")
        
        return None
    
    def _parse_time(self, time_tuple: Tuple) -> Optional[time]:
        """Parse a time from regex match tuple."""
        try:
            hour = int(time_tuple[0])
            minute = int(time_tuple[1]) if time_tuple[1] else 0
            am_pm = time_tuple[2].upper() if time_tuple[2] else None
            
            # Convert to 24-hour format
            if am_pm == 'PM' and hour != 12:
                hour += 12
            elif am_pm == 'AM' and hour == 12:
                hour = 0
            
            # If no AM/PM specified, make educated guess
            if am_pm is None:
                # Assume PM for typical business hours
                if hour < 12 and hour > 0:
                    # Small hours might be AM for early morning
                    # Larger hours (like 6, 7, 8) might need PM for evening
                    pass  # Keep as-is, context dependent
            
            return time(hour=hour % 24, minute=minute)
            
        except Exception as e:
            logger.debug(f"Error parsing time {time_tuple}: {e}")
            return None
    
    def is_open_at(
        self, 
        hours_string: str, 
        day: str, 
        check_time: time
    ) -> bool:
        """
        Quick check if a place is open.
        
        Args:
            hours_string: Raw business hours text
            day: Day name (e.g., "Monday")
            check_time: Time to check
            
        Returns:
            True if open, False otherwise
        """
        hours = self.parse(hours_string)
        return hours.is_open_at(day, check_time)
    
    def is_open_now(self, hours_string: str) -> bool:
        """Quick check if a place is currently open."""
        hours = self.parse(hours_string)
        return hours.is_open_now()
    
    def get_open_hours_for_day(
        self, 
        hours_string: str, 
        day: str
    ) -> Optional[List[Tuple[str, str]]]:
        """
        Get open hours for a specific day.
        
        Returns:
            List of (start_time, end_time) tuples or None if closed
        """
        hours = self.parse(hours_string)
        schedule = hours.get_hours_for_day(day)
        
        if schedule is None or schedule.is_closed:
            return None
        
        return [
            (tr.start.strftime('%H:%M'), tr.end.strftime('%H:%M'))
            for tr in schedule.time_ranges
        ]


# Global instance for convenience
business_hours_parser = BusinessHoursParser()


