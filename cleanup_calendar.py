import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

def delete_volleyball_events(calendar_name="Work"):
    """
    Deletes events from Apple Calendar that start with 'Volleyball vs'
    """
    script = f'''
    tell application "Calendar"
        tell calendar "{calendar_name}"
            set events_to_delete to (every event whose summary begins with "Volleyball vs")
            repeat with an_event in events_to_delete
                delete an_event
            end repeat
            return (count of events_to_delete)
        end tell
    end tell
    '''
    
    try:
        result = subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        count = result.stdout.decode().strip()
        print(f"Successfully deleted {count} volleyball events from calendar '{calendar_name}'.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error deleting events: {e.stderr.decode()}")
        return False

if __name__ == "__main__":
    calendar_name = os.getenv("CALENDAR_NAME", "Work")
    print(f"Cleaning up volleyball events from calendar: {calendar_name}...")
    delete_volleyball_events(calendar_name)
