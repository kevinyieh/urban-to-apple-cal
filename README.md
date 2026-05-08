# NY Urban Volleyball Calendar Sync

Sync your NY Urban volleyball schedule directly to your Apple Calendar with physical gym addresses and team names.

## Features

- **Automated Login**: Securely logs into your `nyurban.com` account.
- **Latest Season Detection**: Automatically finds your teams for the most recent season (e.g., Spring 2026).
- **Direct Apple Calendar Integration**: Adds games via AppleScript—no `.ics` file importing required.
- **Address Mapping**: Converts gym codes (like `SOA`, `LAG-N`, `JJC-A`) into full physical addresses.
- **Preview Mode**: Shows you a table of games and asks for confirmation before adding them to your calendar.

## Prerequisites

- **macOS**: Required for Apple Calendar (iCal) integration via AppleScript.
- **Python 3.12+**: The core language used for the script.

## Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/ny-urban-calendar-sync.git
   cd ny-urban-calendar-sync
   ```

2. **Install Dependencies**:
   ```bash
   # Create a virtual environment
   python3 -m venv venv
   source venv/bin/activate

   # Install required packages
   pip install -r requirements.txt

   # Install Playwright browser
   playwright install chromium
   ```

3. **Configure Environment Variables**:
   Copy the example environment file and fill in your details:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and provide:
   - `NY_URBAN_USERNAME`: Your login email/username.
   - `NY_URBAN_PASSWORD`: Your login password.
   - `CALENDAR_NAME`: The name of your target Apple Calendar (e.g., "Work", "Home").

## Usage

Run the main script:
```bash
python3 main.py
```

1. The script will log in and detect your latest season.
2. It will display a table of upcoming games for review.
3. Type `y` and press `Enter` to sync them to your Apple Calendar.

## Cleanup

If you ever need to remove the synced events from your calendar, you can run:
```bash
python3 cleanup_calendar.py
```
This will delete any events in your specified calendar that start with "Volleyball vs" or your team names.

## Security Note

- **Never** commit your `.env` file to GitHub. It contains your plain-text password.
- The script uses Playwright in headless mode by default.
