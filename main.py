import os
from datetime import datetime, timedelta
from scraper import login_and_get_schedule
from calendar_manager import create_apple_calendar_event
from dotenv import load_dotenv

load_dotenv()

def parse_game_datetime(date_str, time_str):
    """
    Parses date (e.g., 'Mon, Oct 21' or 'Thu 04/16') and time (e.g., '7:00 PM' or '7:00') into datetime objects.
    Infers year based on current date.
    """
    # Standardize time_str: '7:00' -> '7:00 PM' (if it looks like a night game)
    # Most NY Urban games are PM.
    if 'AM' not in time_str.upper() and 'PM' not in time_str.upper():
        time_str = f"{time_str} PM"

    # Standardize date_str
    # Remove day of week: 'Thu 04/16' -> '04/16' or 'Mon, Oct 21' -> 'Oct 21'
    clean_date = date_str.replace(',', '').split()[-1].strip()
    
    current_year = datetime.now().year
    # Try different formats
    formats = ["%m/%d %Y %I:%M %p", "%b %d %Y %I:%M %p"]
    
    for fmt in formats:
        try:
            dt_str = f"{clean_date} {current_year} {time_str}"
            dt = datetime.strptime(dt_str, fmt)
            
            # If the date is in the past by more than 6 months, it's probably next year
            if dt < datetime.now() - timedelta(days=180):
                dt = dt.replace(year=current_year + 1)
            # If the date is in the future by more than 6 months, it might be last year (old data)
            elif dt > datetime.now() + timedelta(days=180):
                 dt = dt.replace(year=current_year - 1)
            return dt
        except ValueError:
            continue
            
    print(f"Failed to parse date: {date_str} (cleaned: {clean_date}) {time_str}")
    return None

def main():
    print("Starting NY Urban Volleyball Scraper...")
    games = login_and_get_schedule()
    
    if not games:
        print("No games found or login failed.")
        return

    # Sort games by date
    games.sort(key=lambda g: parse_game_datetime(g.date, g.time) or datetime.max)

    print("\nGames found for the latest season:")
    print(f"{'Date':<15} | {'Time':<10} | {'Team':<15} | {'Location':<15} | {'Opponent'}")
    print("-" * 80)
    for game in games:
        print(f"{game.date:<15} | {game.time:<10} | {game.team_name:<15} | {game.location:<15} | {game.opponent}")
    
    print(f"\nTotal games: {len(games)}")
    
    confirm = input("\nDo you want to add these games to your Apple Calendar? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    calendar_name = os.getenv("CALENDAR_NAME", "Work")
    print(f"Adding games to calendar: {calendar_name}")
    
    success_count = 0
    for game in games:
        start_time = parse_game_datetime(game.date, game.time)
        if start_time:
            # Games usually last ~75 minutes
            end_time = start_time + timedelta(minutes=75)
            
            success = create_apple_calendar_event(
                summary=game.summary,
                location=game.location,
                start_time=start_time,
                end_time=end_time,
                calendar_name=calendar_name
            )
            if success:
                success_count += 1
    
    print(f"\nFinished! Added {success_count} games to Apple Calendar.")

if __name__ == "__main__":
    main()
