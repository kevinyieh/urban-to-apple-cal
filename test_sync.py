import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Alarm, Calendar

from calendar_manager import build_ical_event, sync_events_to_calendar
from main import filter_upcoming_games, parse_game_datetime
from scraper import Game, parse_schedule_table

NY_TZ = ZoneInfo("America/New_York")


class FakeCalDAVEvent:
    """Minimal stand-in for caldav.Event that mimics _data / icalendar_instance behavior."""

    def __init__(self, ical_bytes: bytes):
        self._data = ical_bytes.decode("utf-8") if isinstance(ical_bytes, bytes) else ical_bytes
        self._icalendar_instance = None
        self.save_count = 0

    @property
    def icalendar_instance(self):
        if self._icalendar_instance is None:
            self._icalendar_instance = Calendar.from_ical(self._data)
        return self._icalendar_instance

    @icalendar_instance.setter
    def icalendar_instance(self, inst):
        self._icalendar_instance = inst
        self._data = None

    @property
    def icalendar_component(self):
        return self.icalendar_instance.walk("VEVENT")[0]

    def save(self):
        self.save_count += 1
        if self._data is None and self._icalendar_instance is not None:
            self._data = self._icalendar_instance.to_ical().decode("utf-8")
        return self


class FakeCalDAVCalendar:
    def __init__(self, initial_events=None):
        self.name = "Em + Kev"
        self.stored_events = list(initial_events or [])
        self.save_event_calls = 0

    def search(self, start=None, end=None, event=True):
        return list(self.stored_events)

    def events(self):
        return list(self.stored_events)

    def save_event(self, ical_bytes):
        self.save_event_calls += 1
        ev = FakeCalDAVEvent(ical_bytes)
        self.stored_events.append(ev)
        return ev


class TestScraperUIDAndParsing(unittest.TestCase):
    SAMPLE_HTML_V1 = """
    <table>
      <tr><th>Date</th><th>Location</th><th>Time</th><th>Opponent</th><th>Results</th></tr>
      <tr><td>Thu 11/19</td><td>BEC-N</td><td>7:00</td><td>Old Team</td><td>W 2-1</td></tr>
      <tr><td>Thu 11/26</td><td>No Game</td><td></td><td>Thanksgiving</td><td></td></tr>
      <tr><td>Thu 12/03</td><td>LAG-N</td><td>7:30</td><td>Spikers</td><td></td></tr>
      <tr><td>Thu 12/10</td><td>JJC-A</td><td>8:15</td><td>Block Party</td><td></td></tr>
    </table>
    """

    SAMPLE_HTML_V2_RESCHEDULED = """
    <table>
      <tr><th>Date</th><th>Location</th><th>Time</th><th>Opponent</th><th>Results</th></tr>
      <tr><td>Thu 11/19</td><td>BEC-N</td><td>7:00</td><td>Old Team</td><td>W 2-1</td></tr>
      <tr><td>Thu 11/26</td><td>No Game</td><td></td><td>Thanksgiving</td><td></td></tr>
      <tr><td>Thu 12/03</td><td>BEC-F</td><td>8:30</td><td>Spikers</td><td></td></tr>
      <tr><td>Thu 12/10</td><td>JJC-A</td><td>8:15</td><td>Block Party</td><td></td></tr>
    </table>
    """

    def test_deterministic_uid_by_team_season_and_row(self):
        g1 = parse_schedule_table(self.SAMPLE_HTML_V1, "Freaks in the Seams", season="Fall Volleyball 2026")
        g2 = parse_schedule_table(self.SAMPLE_HTML_V2_RESCHEDULED, "Freaks in the Seams", season="Fall Volleyball 2026")
        g_other_team = parse_schedule_table(self.SAMPLE_HTML_V1, "neugenes", season="Fall Volleyball 2026")
        g_other_season = parse_schedule_table(self.SAMPLE_HTML_V1, "Freaks in the Seams", season="Winter Volleyball 2027")

        # 3 valid games (row 2 is No Game, skipped)
        self.assertEqual(len(g1), 3)
        self.assertEqual([g.row_index for g in g1], [1, 3, 4])

        # Same team + season + row produces the exact same UID even after time & location changed
        self.assertEqual(g1[1].uid, g2[1].uid)

        # Different rows produce different UIDs
        self.assertNotEqual(g1[0].uid, g1[1].uid)
        self.assertNotEqual(g1[1].uid, g1[2].uid)

        # Different team or season produces different UIDs for the same row
        self.assertNotEqual(g1[1].uid, g_other_team[1].uid)
        self.assertNotEqual(g1[1].uid, g_other_season[1].uid)

    def test_filter_upcoming_games_excludes_past(self):
        games = parse_schedule_table(self.SAMPLE_HTML_V1, "Freaks in the Seams", season="Fall Volleyball 2026")
        # Add an unparseable TBA game
        games.append(Game(date="Thu 12/17", time="TBA", location="TBA", opponent="TBD", summary="Freaks vs TBD", team_name="Freaks in the Seams", season="Fall Volleyball 2026", row_index=5, uid="uid-tba"))

        # Simulate GitHub Actions running in UTC at 2026-11-26 19:00 UTC (2:00 PM EST)
        now_utc = datetime(2026, 11, 26, 19, 0, tzinfo=timezone.utc)
        upcoming, past_count, unparsed_count = filter_upcoming_games(games, now=now_utc)

        self.assertEqual(past_count, 1)  # Thu 11/19 already occurred
        self.assertEqual(unparsed_count, 1)  # TBA
        self.assertEqual(len(upcoming), 2)
        self.assertEqual(upcoming[0][0].date, "Thu 12/03")
        self.assertEqual(upcoming[1][0].date, "Thu 12/10")
        self.assertEqual(upcoming[0][1], datetime(2026, 12, 3, 19, 30, tzinfo=NY_TZ))

    def test_parse_game_datetime_formats(self):
        now_ny = datetime(2026, 11, 26, 14, 0, tzinfo=NY_TZ)
        self.assertEqual(
            parse_game_datetime("Mon, Dec 7", "7:00 PM", now=now_ny),
            datetime(2026, 12, 7, 19, 0, tzinfo=NY_TZ),
        )
        self.assertEqual(
            parse_game_datetime("Thu 01/07", "8:15", now=now_ny),
            datetime(2027, 1, 7, 20, 15, tzinfo=NY_TZ),
        )


class TestCalDAVSyncDedupe(unittest.TestCase):
    def _make_payload(self, uid, summary, location, start_ny, description="test"):
        return {
            "uid": uid,
            "summary": summary,
            "location": location,
            "start_time": start_ny,
            "end_time": start_ny + timedelta(minutes=75),
            "description": description,
        }

    def test_add_skip_update_and_legacy_fallback(self):
        # Pre-existing legacy AppleScript event (random Apple UID, no deterministic UID)
        legacy_start = datetime(2026, 12, 10, 20, 15, tzinfo=NY_TZ)
        legacy_ical = build_ical_event(
            uid="APPLE-RANDOM-UUID-9999",
            summary="Freaks in the Seams vs Block Party",
            location="524 W 59th St, New York, NY",
            start_time=legacy_start,
            end_time=legacy_start + timedelta(minutes=75),
        )
        fake_cal = FakeCalDAVCalendar(initial_events=[FakeCalDAVEvent(legacy_ical)])

        game1_start = datetime(2026, 12, 3, 19, 30, tzinfo=NY_TZ)
        payloads = [
            self._make_payload("nyurban-row3@urban-scraper", "Freaks in the Seams vs Spikers", "LAG-N", game1_start),
            self._make_payload("nyurban-row4@urban-scraper", "Freaks in the Seams vs Block Party", "JJC-A", legacy_start),
        ]

        # Run 1: dry run should NOT write anything
        dry_stats = sync_events_to_calendar(fake_cal, payloads, dry_run=True)
        self.assertEqual(dry_stats, {"added": 1, "updated": 0, "skipped": 1, "failed": 0})
        self.assertEqual(fake_cal.save_event_calls, 0)

        # Run 2: real run adds row3, skips row4 (matched legacy AppleScript event)
        stats1 = sync_events_to_calendar(fake_cal, payloads, dry_run=False)
        self.assertEqual(stats1, {"added": 1, "updated": 0, "skipped": 1, "failed": 0})
        self.assertEqual(len(fake_cal.stored_events), 2)

        # Attach a user alarm to the stored event to ensure updates preserve user reminders
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("trigger", timedelta(minutes=-30))
        stored_row3 = fake_cal.stored_events[1]
        stored_row3.icalendar_component.add_component(alarm)
        stored_row3.icalendar_instance = stored_row3.icalendar_instance
        stored_row3.save()

        # Run 3: re-running with identical data skips both events
        stats2 = sync_events_to_calendar(fake_cal, payloads, dry_run=False)
        self.assertEqual(stats2, {"added": 0, "updated": 0, "skipped": 2, "failed": 0})

        # Run 4: game on row3 is rescheduled to 8:30 PM at BEC-F (same UID!)
        rescheduled_start = datetime(2026, 12, 3, 20, 30, tzinfo=NY_TZ)
        payloads_updated = [
            self._make_payload("nyurban-row3@urban-scraper", "Freaks in the Seams vs Spikers", "BEC-F", rescheduled_start),
            self._make_payload("nyurban-row4@urban-scraper", "Freaks in the Seams vs Block Party", "JJC-A", legacy_start),
        ]
        stats3 = sync_events_to_calendar(fake_cal, payloads_updated, dry_run=False)
        self.assertEqual(stats3, {"added": 0, "updated": 1, "skipped": 1, "failed": 0})
        self.assertEqual(len(fake_cal.stored_events), 2)

        # Verify serialized iCalendar reflects the updated time & location and kept the VALARM
        updated_cal = Calendar.from_ical(stored_row3._data)
        updated_vevent = updated_cal.walk("VEVENT")[0]
        self.assertEqual(str(updated_vevent.get("location")), "522 W 44th St, New York, NY")
        self.assertEqual(updated_vevent.get("dtstart").dt, rescheduled_start.astimezone(timezone.utc))
        self.assertEqual(len(updated_vevent.walk("VALARM")), 1)


if __name__ == "__main__":
    unittest.main()
