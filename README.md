# NY Urban Volleyball Calendar Sync

Sync your NY Urban volleyball schedule directly to your Apple Calendar with physical gym addresses, team names, automatic deduplication, and periodic GitHub Actions runs.

## Features

- **Automated Login**: Logs into your `nyurban.com` account via Playwright.
- **Latest Season Detection**: Automatically finds your teams for the most recent season.
- **Upcoming Games Only**: Filters out games that have already occurred (evaluated in `America/New_York` time).
- **Deduplication, Updates & Cancellation Cleanup**: Assigns each game a deterministic `UID` based on `team + season + table row`, so re-running never duplicates games and updates events in place if a time, gym, or opponent changes. Also scans future NY Urban events on your calendar and removes any that are no longer on the NY Urban website (cancelled or rescheduled), while leaving past games, other seasons, and personal events untouched.
- **iCloud CalDAV & Local AppleScript Support**: Syncs directly to your iCloud Apple Calendar from GitHub Actions or any OS using CalDAV, with a local macOS AppleScript fallback.
- **Address Mapping**: Converts gym codes (like `SOA`, `LAG-N`, `JJC-A`) into full physical addresses.

## Prerequisites

- **Python 3.12+**
- **Apple Calendar via iCloud** (for GitHub Actions / CalDAV sync) or **macOS** (for local AppleScript fallback)

## Local Setup

1. **Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   Fill in `.env`:
   - `NY_URBAN_USERNAME`: Your NY Urban login email/username.
   - `NY_URBAN_PASSWORD`: Your NY Urban login password.
   - `CALENDAR_NAME`: Name of your target Apple Calendar (e.g., `Em + Kev`).
   - `ICLOUD_USERNAME` *(for iCloud CalDAV)*: Your Apple ID email.
   - `ICLOUD_APP_PASSWORD` *(for iCloud CalDAV)*: An Apple [App-Specific Password](https://account.apple.com) (`Sign-In and Security → App-Specific Passwords`).

## Usage

```bash
# Interactive sync (auto-uses iCloud CalDAV if configured, else AppleScript on macOS)
python3 main.py

# Preview changes without modifying your calendar
python3 main.py --dry-run

# Non-interactive sync (e.g., CI / cron) with optional calendar override
python3 main.py --yes --calendar "Em + Kev"
```

## Periodic Sync with GitHub Actions

This repo includes [`.github/workflows/sync-schedule.yml`](.github/workflows/sync-schedule.yml), which runs daily at **13:00 UTC** (8:00 AM EST / 9:00 AM EDT) and can also be triggered manually via **Actions → Sync NY Urban Volleyball Schedule → Run workflow** (including a `dry_run` toggle and `calendar_name` override).

### GitHub Repository Configuration

Go to your GitHub repo **Settings → Secrets and variables → Actions**:

1. **Repository Secrets** (required):
   - `NY_URBAN_USERNAME`
   - `NY_URBAN_PASSWORD`
   - `ICLOUD_USERNAME` (your Apple ID email)
   - `ICLOUD_APP_PASSWORD` (generated at `account.apple.com → Sign-In and Security → App-Specific Passwords`)

2. **Repository Variables** (optional, easy to change anytime):
   - `CALENDAR_NAME` — set to your target Apple Calendar name (defaults to `Em + Kev` if unset).

## Cleanup

If you ever need to remove synced events locally on macOS, see `cleanup_calendar.py`.

## Security Note

- **Never** commit your `.env` file to GitHub.
- Always use an **App-Specific Password** (never your primary Apple ID password) for `ICLOUD_APP_PASSWORD`.
