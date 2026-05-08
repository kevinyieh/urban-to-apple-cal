import subprocess
import os
from datetime import datetime

GYM_ADDRESSES = {
    "Beacon HS": "522 W 44th St, New York, NY",
    "BEC": "522 W 44th St, New York, NY",
    "BEC-F": "522 W 44th St, New York, NY",
    "BEC-N": "522 W 44th St, New York, NY",
    "LaGuardia HS": "100 Amsterdam Ave, New York, NY",
    "LAG": "100 Amsterdam Ave, New York, NY",
    "LAG-N": "100 Amsterdam Ave, New York, NY",
    "LAG-F": "100 Amsterdam Ave, New York, NY",
    "Hunter College": "E 68th St & Lexington Ave, New York, NY",
    "HTC": "E 68th St & Lexington Ave, New York, NY",
    "Hunter College High School": "E 94th St & Park Ave, New York, NY",
    "Baruch Simon JHS": "330 E 21st St, New York, NY",
    "MS 104": "330 E 21st St, New York, NY",
    "O'Shea J.H.S.": "100 W 77th St, New York, NY",
    "OJH": "100 W 77th St, New York, NY",
    "MS 44": "100 W 77th St, New York, NY",
    "Chelsea School": "281 9th Ave, New York, NY",
    "CHL": "281 9th Ave, New York, NY",
    "PS 33": "281 9th Ave, New York, NY",
    "John Jay College": "524 W 59th St, New York, NY",
    "JJC": "524 W 59th St, New York, NY",
    "JJC-A": "524 W 59th St, New York, NY",
    "JJC-N": "524 W 59th St, New York, NY",
    "JJC-F": "524 W 59th St, New York, NY",
    "Brandeis High School": "145 W 84th St, New York, NY",
    "BRN": "145 W 84th St, New York, NY",
    "BRN-N": "145 W 84th St, New York, NY",
    "BRN-F": "145 W 84th St, New York, NY",
    "St. John Nepomucene": "E 67th St & 1st Ave, New York, NY",
    "District 2 Pre-K": "E 76th St & 1st Ave, New York, NY",
    "D2P": "E 76th St & 1st Ave, New York, NY",
    "RSMA": "300 W 61st St, New York, NY",
    "SOA": "1515 Madison Ave, New York, NY", # School of Authors
}

def create_apple_calendar_event(summary, location, start_time, end_time, calendar_name="Calendar"):
    """
    Creates an event in Apple Calendar via AppleScript.
    start_time and end_time should be datetime objects.
    """
    # Map gym name to address
    full_location = GYM_ADDRESSES.get(location, location)
    
    # AppleScript date format: "May 8, 2026 at 10:00:00 AM"
    # Note: This is locale-dependent. We'll try to build it carefully.
    start_str = start_time.strftime("%B %d, %Y at %I:%M:%S %p")
    end_str = end_time.strftime("%B %d, %Y at %I:%M:%S %p")
    
    script = f'''
    tell application "Calendar"
        tell calendar "{calendar_name}"
            make new event with properties {{summary:"{summary}", location:"{full_location}", start date:date "{start_str}", end date:date "{end_str}"}}
        end tell
    end tell
    '''
    
    try:
        subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        print(f"Successfully added: {summary} at {location}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error adding event to Apple Calendar: {e.stderr.decode()}")
        return False

if __name__ == "__main__":
    # Test
    test_start = datetime(2026, 5, 8, 19, 0)
    test_end = datetime(2026, 5, 8, 20, 15)
    create_apple_calendar_event("Test Game vs Opponent", "Beacon HS", test_start, test_end)
