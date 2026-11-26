import argparse
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from calendar_manager import (
    NY_TZ,
    create_apple_calendar_event,
    sync_events_to_icloud,
)
from scraper import login_and_get_schedule_details

load_dotenv()


def parse_game_datetime(date_str: str, time_str: str, now: datetime | None = None) -> datetime | None:
    """
    Parses date (e.g., 'Mon, Oct 21' or 'Thu 04/16') and time (e.g., '7:00 PM' or '7:00')
    into a timezone-aware datetime in America/New_York.
    Infers year based on the current date.
    """
    if not date_str or not time_str:
        return None

    now_ny = now.astimezone(NY_TZ) if now is not None else datetime.now(NY_TZ)

    # Standardize time_str: '7:00' -> '7:00 PM' (most NY Urban games are evening PM)
    clean_time = time_str.strip()
    if "AM" not in clean_time.upper() and "PM" not in clean_time.upper():
        clean_time = f"{clean_time} PM"

    # Standardize date_str
    # Remove day of week: 'Thu 04/16' -> '04/16' or 'Mon, Oct 21' -> 'Oct 21'
    tokens = date_str.replace(",", "").split()
    days_of_week = {
        "mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday",
        "thu", "thur", "thurs", "thursday", "fri", "friday",
        "sat", "saturday", "sun", "sunday",
    }
    if tokens and tokens[0].lower().rstrip(".") in days_of_week:
        clean_date = " ".join(tokens[1:])
    else:
        clean_date = " ".join(tokens)

    current_year = now_ny.year
    formats = ["%m/%d %Y %I:%M %p", "%b %d %Y %I:%M %p", "%B %d %Y %I:%M %p"]

    for fmt in formats:
        try:
            dt_str = f"{clean_date} {current_year} {clean_time}"
            dt = datetime.strptime(dt_str, fmt).replace(tzinfo=NY_TZ)

            # If the date is in the past by more than 6 months, it's probably next year
            if dt < now_ny - timedelta(days=180):
                dt = dt.replace(year=current_year + 1)
            # If the date is in the future by more than 6 months, it might be last year (old data)
            elif dt > now_ny + timedelta(days=180):
                dt = dt.replace(year=current_year - 1)
            return dt
        except ValueError:
            continue

    print(f"Failed to parse date: {date_str} (cleaned: {clean_date}) {clean_time}")
    return None


def filter_upcoming_games(games, now: datetime | None = None):
    """
    Parses game datetimes, excludes games that have already occurred,
    and returns (upcoming_events, past_count, unparsed_count) sorted by start_time.
    """
    now_ny = now.astimezone(NY_TZ) if now is not None else datetime.now(NY_TZ)
    upcoming = []
    past_count = 0
    unparsed_count = 0

    for game in games:
        start_time = parse_game_datetime(game.date, game.time, now=now_ny)
        if start_time is None:
            unparsed_count += 1
            continue

        if start_time <= now_ny:
            past_count += 1
            continue

        # Games usually last ~75 minutes
        end_time = start_time + timedelta(minutes=75)
        upcoming.append((game, start_time, end_time))

    upcoming.sort(key=lambda item: item[1])
    return upcoming, past_count, unparsed_count


def resolve_backend(requested_backend: str) -> str:
    if requested_backend != "auto":
        return requested_backend

    if os.getenv("ICLOUD_USERNAME") and os.getenv("ICLOUD_APP_PASSWORD"):
        return "icloud"

    if sys.platform == "darwin":
        return "applescript"

    raise RuntimeError(
        "No calendar backend configured. Set ICLOUD_USERNAME and ICLOUD_APP_PASSWORD "
        "to sync via iCloud CalDAV."
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape NY Urban volleyball schedules and sync upcoming games to Apple Calendar."
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt (required for CI / scheduled runs).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be added, updated, or skipped without modifying the calendar.",
    )
    parser.add_argument(
        "--calendar",
        default=None,
        help="Target calendar name (overrides CALENDAR_NAME env var).",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "icloud", "applescript"],
        default="auto",
        help="Calendar sync backend (default: auto-detects iCloud CalDAV if configured, else AppleScript on macOS).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("Starting NY Urban Volleyball Scraper...")
    try:
        schedule = login_and_get_schedule_details()
    except Exception as e:
        print(f"Scraper failed: {e}", file=sys.stderr)
        sys.exit(1)

    games = schedule.games
    if not schedule.teams:
        print("No teams found for the latest season.")
        return

    now_ny = datetime.now(NY_TZ)
    upcoming, past_count, unparsed_count = filter_upcoming_games(games, now=now_ny)
    print(
        f"\nFiltered {len(games)} scraped game(s): "
        f"{len(upcoming)} upcoming, {past_count} already occurred, {unparsed_count} unparsed."
    )

    if upcoming:
        print("\nUpcoming games for the latest season:")
        print(f"{'Date':<15} | {'Time':<10} | {'Team':<20} | {'Location':<15} | {'Opponent'}")
        print("-" * 90)
        for game, _, _ in upcoming:
            print(
                f"{game.date:<15} | {game.time:<10} | {game.team_name:<20} | "
                f"{game.location:<15} | {game.opponent}"
            )
        print(f"\nTotal upcoming games: {len(upcoming)}")
    else:
        print("\nNo upcoming games found on the website; will still check calendar for cancelled games.")

    calendar_name = (args.calendar or os.getenv("CALENDAR_NAME") or "Calendar").strip()
    try:
        backend = resolve_backend(args.backend)
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    if not upcoming and backend != "icloud":
        print("No upcoming games to sync.")
        return

    if not args.yes and not args.dry_run:
        confirm = input(
            f"\nDo you want to sync these games to '{calendar_name}' via {backend}? (y/n): "
        )
        if confirm.lower() != "y":
            print("Operation cancelled.")
            return

    print(f"\nSyncing games to calendar '{calendar_name}' using backend '{backend}'...")

    event_payloads = [
        {
            "uid": game.uid,
            "summary": game.summary,
            "location": game.location,
            "start_time": start_time,
            "end_time": end_time,
            "description": (
                f"Season: {game.season}\n"
                f"Team: {game.team_name}\n"
                f"Gym: {game.location}\n"
                f"Opponent: {game.opponent}"
            ),
        }
        for game, start_time, end_time in upcoming
    ]

    if backend == "icloud":
        try:
            stats = sync_events_to_icloud(
                events=event_payloads,
                calendar_name=calendar_name,
                dry_run=args.dry_run,
                now=now_ny,
                scraped_season=schedule.season,
                scraped_teams=schedule.teams,
            )
        except Exception as e:
            print(f"iCloud CalDAV sync failed: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        stats = {"added": 0, "updated": 0, "skipped": 0, "deleted": 0, "failed": 0}
        for payload in event_payloads:
            result = create_apple_calendar_event(
                summary=payload["summary"],
                location=payload["location"],
                start_time=payload["start_time"],
                end_time=payload["end_time"],
                calendar_name=calendar_name,
                dry_run=args.dry_run,
            )
            stats[result] = stats.get(result, 0) + 1

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(
        f"\n{prefix}Finished! "
        f"Added: {stats['added']}, Updated: {stats['updated']}, "
        f"Skipped: {stats['skipped']}, Deleted: {stats.get('deleted', 0)}, "
        f"Failed: {stats['failed']}."
    )

    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
