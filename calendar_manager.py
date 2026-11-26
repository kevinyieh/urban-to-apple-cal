import os
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import caldav
from icalendar import Calendar, Event, vDatetime, vText

NY_TZ = ZoneInfo("America/New_York")
DEFAULT_ICLOUD_CALDAV_URL = "https://caldav.icloud.com/"

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
    "SOA": "1515 Madison Ave, New York, NY",  # School of Authors
}


def resolve_location(location: str) -> str:
    """Maps a known NY Urban gym code/name to its street address."""
    return GYM_ADDRESSES.get(location, location)


def _to_utc_datetime(val) -> datetime | None:
    """Normalizes an icalendar DTSTART/DTEND value to a UTC datetime, or None for all-day dates."""
    if not isinstance(val, datetime):
        return None
    if val.tzinfo is None:
        val = val.replace(tzinfo=NY_TZ)
    return val.astimezone(timezone.utc)


def _normalize_minute(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(second=0, microsecond=0)


def build_ical_event(
    uid: str,
    summary: str,
    location: str,
    start_time: datetime,
    end_time: datetime,
    description: str = "",
) -> bytes:
    """Builds an RFC 5545 VCALENDAR payload containing a single VEVENT."""
    cal = Calendar()
    cal.add("prodid", "-//NY Urban Volleyball Scraper//urban-scraper//EN")
    cal.add("version", "2.0")

    ev = Event()
    ev.add("uid", uid)
    ev.add("dtstamp", datetime.now(timezone.utc))
    ev.add("dtstart", _to_utc_datetime(start_time))
    ev.add("dtend", _to_utc_datetime(end_time))
    ev.add("summary", summary)
    ev.add("location", location)
    if description:
        ev.add("description", description)

    cal.add_component(ev)
    return cal.to_ical()


def _find_calendar(principal, calendar_name: str):
    """Finds a calendar by name from the user's iCloud principal (including shared calendars)."""
    calendars = principal.calendars()
    target = calendar_name.strip()

    for cal in calendars:
        if cal.name and cal.name == target:
            return cal

    for cal in calendars:
        if cal.name and cal.name.strip().lower() == target.lower():
            return cal

    available = [cal.name for cal in calendars if cal.name]
    raise ValueError(
        f"Calendar '{calendar_name}' not found in iCloud. "
        f"Available calendars: {available}"
    )


def _index_existing_events(existing_events) -> tuple[dict, dict]:
    """
    Indexes fetched CalDAV events by:
      1. UID (primary deterministic dedupe key)
      2. (normalized summary, UTC start minute) fallback for events added previously without our UID
    """
    by_uid = {}
    by_summary_start = {}

    for ev in existing_events:
        try:
            comp = ev.icalendar_component
        except Exception:
            continue
        if comp is None:
            continue

        uid = comp.get("uid")
        if uid:
            by_uid[str(uid)] = ev

        summary = comp.get("summary")
        dtstart_prop = comp.get("dtstart")
        if summary and dtstart_prop is not None:
            dtstart_utc = _to_utc_datetime(dtstart_prop.dt)
            if dtstart_utc is not None:
                key = (str(summary).strip().lower(), _normalize_minute(dtstart_utc))
                by_summary_start[key] = ev

    return by_uid, by_summary_start


def _event_needs_update(
    existing_comp,
    summary: str,
    full_location: str,
    start_utc: datetime,
    end_utc: datetime,
) -> bool:
    existing_summary = str(existing_comp.get("summary", "")).strip()
    existing_location = str(existing_comp.get("location", "")).strip()
    existing_start = _to_utc_datetime(existing_comp.get("dtstart").dt) if existing_comp.get("dtstart") else None
    existing_end = _to_utc_datetime(existing_comp.get("dtend").dt) if existing_comp.get("dtend") else None

    if existing_summary != summary.strip():
        return True
    if existing_location != full_location.strip():
        return True
    if existing_start is None or _normalize_minute(existing_start) != _normalize_minute(start_utc):
        return True
    if existing_end is None or _normalize_minute(existing_end) != _normalize_minute(end_utc):
        return True
    return False


def _is_nyurban_uid(uid: str) -> bool:
    return uid.startswith("nyurban-") and uid.endswith("@urban-scraper")


def _extract_event_season(comp) -> str | None:
    desc = str(comp.get("description", ""))
    for line in desc.splitlines():
        if line.strip().lower().startswith("season:"):
            return line.split(":", 1)[1].strip()
    return None


def _is_managed_nyurban_event(
    comp,
    scraped_season: str | None = None,
    scraped_teams: list[str] | None = None,
) -> bool:
    """
    Determines whether an existing calendar event is a NY Urban event within the
    scope of the current scrape (and thus safe to remove if no longer on the site).

    - Events created by this scraper (nyurban-*@urban-scraper UID) are matched
      unless their description explicitly tags a *different* season (protects
      remaining games of a prior season when a new season opens).
    - Legacy events (e.g. added via local AppleScript without our UID) are only
      matched if their summary begins with "<scraped_team> vs ".
    """
    uid = str(comp.get("uid", "")).strip()
    if _is_nyurban_uid(uid):
        event_season = _extract_event_season(comp)
        if scraped_season and event_season and event_season.lower() != scraped_season.strip().lower():
            return False
        return True

    summary_lower = str(comp.get("summary", "")).strip().lower()
    if scraped_teams and summary_lower:
        for team in scraped_teams:
            prefix = f"{team.strip().lower()} vs "
            if team.strip() and summary_lower.startswith(prefix):
                return True

    return False


def sync_events_to_calendar(
    calendar,
    events: list[dict],
    dry_run: bool = False,
    now: datetime | None = None,
    scraped_season: str | None = None,
    scraped_teams: list[str] | None = None,
    prune_stale: bool = True,
) -> dict:
    """
    Syncs a list of game event dicts to a CalDAV calendar with deduplication,
    in-place updates, and removal of future NY Urban events that are no longer
    on the NY Urban schedule (cancelled or rescheduled).

    Each event dict should contain:
        uid, summary, location, start_time, end_time, and optional description.
    """
    stats = {"added": 0, "updated": 0, "skipped": 0, "deleted": 0, "failed": 0}
    now_utc = _to_utc_datetime(now) if now is not None else datetime.now(timezone.utc)

    # Safety guard: if we have neither upcoming events nor any scraped teams, don't touch the calendar
    if not events and not (prune_stale and scraped_teams):
        return stats

    if events:
        min_event_start = min(_to_utc_datetime(e["start_time"]) for e in events)
        max_event_end = max(_to_utc_datetime(e["end_time"]) for e in events)
        search_start = min(now_utc, min_event_start) - timedelta(days=30)
        search_end = max(now_utc + timedelta(days=365), max_event_end + timedelta(days=30))
    else:
        search_start = now_utc - timedelta(days=30)
        search_end = now_utc + timedelta(days=365)

    try:
        existing_events = calendar.search(start=search_start, end=search_end, event=True)
    except Exception as e:
        print(f"Warning: time-range search failed ({e}); falling back to fetching all events.")
        existing_events = calendar.events()

    by_uid, by_summary_start = _index_existing_events(existing_events)
    print(f"Loaded {len(existing_events)} existing calendar event(s) for deduplication and verification.")

    matched_existing_ids = set()

    for event in events:
        uid = event["uid"]
        summary = event["summary"]
        raw_location = event["location"]
        full_location = resolve_location(raw_location)
        start_utc = _to_utc_datetime(event["start_time"])
        end_utc = _to_utc_datetime(event["end_time"])
        description = event.get("description", "")

        try:
            if uid in by_uid:
                existing_ev = by_uid[uid]
                matched_existing_ids.add(id(existing_ev))
                comp = existing_ev.icalendar_component
                if not _event_needs_update(comp, summary, full_location, start_utc, end_utc):
                    print(f"Skipped (already synced): {summary} ({event['start_time'].strftime('%a %m/%d %I:%M %p')})")
                    stats["skipped"] += 1
                    continue

                if dry_run:
                    print(f"[DRY RUN] Would update: {summary} at {full_location}")
                    stats["updated"] += 1
                    continue

                ical_inst = existing_ev.icalendar_instance
                comp["summary"] = vText(summary)
                comp["location"] = vText(full_location)
                comp["dtstart"] = vDatetime(start_utc)
                comp["dtend"] = vDatetime(end_utc)
                if description:
                    comp["description"] = vText(description)
                comp["dtstamp"] = vDatetime(datetime.now(timezone.utc))
                # Re-assigning icalendar_instance clears cached raw _data so save() serializes changes
                existing_ev.icalendar_instance = ical_inst
                existing_ev.save()
                print(f"Updated: {summary} at {raw_location}")
                stats["updated"] += 1
                continue

            fallback_key = (summary.strip().lower(), _normalize_minute(start_utc))
            if fallback_key in by_summary_start:
                matched_existing_ids.add(id(by_summary_start[fallback_key]))
                print(f"Skipped (matching event already exists): {summary} ({event['start_time'].strftime('%a %m/%d %I:%M %p')})")
                stats["skipped"] += 1
                continue

            if dry_run:
                print(f"[DRY RUN] Would add: {summary} at {full_location} ({event['start_time'].strftime('%a %m/%d %I:%M %p')})")
                stats["added"] += 1
                continue

            ical_bytes = build_ical_event(
                uid=uid,
                summary=summary,
                location=full_location,
                start_time=start_utc,
                end_time=end_utc,
                description=description,
            )
            calendar.save_event(ical_bytes)
            print(f"Added: {summary} at {raw_location} ({event['start_time'].strftime('%a %m/%d %I:%M %p')})")
            stats["added"] += 1
        except Exception as e:
            print(f"Error syncing event '{summary}' (uid={uid}): {e}")
            stats["failed"] += 1

    # Remove future NY Urban events on the calendar that are no longer on the NY Urban website
    if prune_stale and (scraped_teams or events):
        for existing_ev in existing_events:
            if id(existing_ev) in matched_existing_ids:
                continue

            try:
                comp = existing_ev.icalendar_component
            except Exception:
                continue
            if comp is None:
                continue

            dtstart_prop = comp.get("dtstart")
            if dtstart_prop is None:
                continue
            dtstart_utc = _to_utc_datetime(dtstart_prop.dt)
            if dtstart_utc is None or dtstart_utc <= now_utc:
                # Ignore all-day events and games that have already occurred
                continue

            if not _is_managed_nyurban_event(
                comp,
                scraped_season=scraped_season,
                scraped_teams=scraped_teams,
            ):
                continue

            summary = str(comp.get("summary", "(no summary)"))
            start_label = dtstart_utc.astimezone(NY_TZ).strftime("%a %m/%d %I:%M %p")
            try:
                if dry_run:
                    print(f"[DRY RUN] Would delete (no longer on schedule): {summary} ({start_label})")
                    stats["deleted"] += 1
                else:
                    existing_ev.delete()
                    print(f"Deleted (no longer on schedule): {summary} ({start_label})")
                    stats["deleted"] += 1
            except Exception as e:
                print(f"Error deleting stale event '{summary}': {e}")
                stats["failed"] += 1

    return stats


def sync_events_to_icloud(
    events: list[dict],
    calendar_name: str,
    username: str | None = None,
    password: str | None = None,
    caldav_url: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
    scraped_season: str | None = None,
    scraped_teams: list[str] | None = None,
    prune_stale: bool = True,
) -> dict:
    """Connects to iCloud CalDAV and syncs events into the configured Apple Calendar."""
    username = username or os.getenv("ICLOUD_USERNAME")
    password = password or os.getenv("ICLOUD_APP_PASSWORD")
    caldav_url = caldav_url or os.getenv("ICLOUD_CALDAV_URL", DEFAULT_ICLOUD_CALDAV_URL)

    if not username or not password:
        raise RuntimeError(
            "Missing iCloud CalDAV credentials. Set ICLOUD_USERNAME (your Apple ID email) "
            "and ICLOUD_APP_PASSWORD (an Apple App-Specific Password)."
        )

    with caldav.DAVClient(
        url=caldav_url,
        username=username,
        password=password,
        features="icloud",
    ) as client:
        principal = client.principal()
        calendar = _find_calendar(principal, calendar_name)
        print(f"Connected to iCloud calendar: {calendar.name}")
        return sync_events_to_calendar(
            calendar,
            events,
            dry_run=dry_run,
            now=now,
            scraped_season=scraped_season,
            scraped_teams=scraped_teams,
            prune_stale=prune_stale,
        )


def _escape_applescript_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def create_apple_calendar_event(summary, location, start_time, end_time, calendar_name="Calendar", dry_run=False):
    """
    Creates an event in local Apple Calendar via AppleScript (macOS only),
    skipping if an event with the same summary and start date already exists.
    start_time and end_time should be datetime objects.
    """
    full_location = resolve_location(location)

    # AppleScript date format: "May 8, 2026 at 10:00:00 AM"
    start_str = start_time.strftime("%B %d, %Y at %I:%M:%S %p")
    end_str = end_time.strftime("%B %d, %Y at %I:%M:%S %p")

    esc_calendar = _escape_applescript_str(calendar_name)
    esc_summary = _escape_applescript_str(summary)
    esc_location = _escape_applescript_str(full_location)

    if dry_run:
        print(f"[DRY RUN] Would add via AppleScript: {summary} at {full_location}")
        return "added"

    script = f'''
    tell application "Calendar"
        tell calendar "{esc_calendar}"
            set targetStart to date "{start_str}"
            set existingEvents to (every event whose summary is "{esc_summary}" and start date is targetStart)
            if (count of existingEvents) > 0 then
                return "skipped"
            end if
            make new event with properties {{summary:"{esc_summary}", location:"{esc_location}", start date:targetStart, end date:date "{end_str}"}}
            return "added"
        end tell
    end tell
    '''

    try:
        result = subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        status = result.stdout.decode().strip()
        if status == "skipped":
            print(f"Skipped (already exists): {summary} at {location}")
            return "skipped"
        print(f"Successfully added: {summary} at {location}")
        return "added"
    except subprocess.CalledProcessError as e:
        print(f"Error adding event to Apple Calendar: {e.stderr.decode()}")
        return "failed"


if __name__ == "__main__":
    # Test
    test_start = datetime(2026, 5, 8, 19, 0, tzinfo=NY_TZ)
    test_end = datetime(2026, 5, 8, 20, 15, tzinfo=NY_TZ)
    create_apple_calendar_event("Test Game vs Opponent", "Beacon HS", test_start, test_end, dry_run=True)
