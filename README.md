# NY Urban Volleyball Calendar Sync

Automatically sync your NY Urban volleyball schedule directly to your Apple Calendar (iCloud) with full gym street addresses, team names, deduplication, in-place reschedule updates, and automatic removal of cancelled games—all running on a daily GitHub Actions schedule with no local setup required.

## Features

- **Hands-Free Daily Sync**: Runs automatically every day at **8:00 AM EST / 9:00 AM EDT** (`13:00 UTC`) via GitHub Actions, with one-click manual runs anytime.
- **Latest Season Detection**: Logs into `nyurban.com` and automatically discovers all of your teams for the latest season.
- **Upcoming Games Only**: Only syncs games that haven't occurred yet (evaluated in `America/New_York` time).
- **Deduplication & In-Place Updates**: Assigns each game a deterministic `UID` based on `team + season + table row`, so re-running never creates duplicates and automatically updates existing events if a time, gym, or opponent changes.
- **Cancelled / Rescheduled Cleanup**: Scans future NY Urban events on your calendar and removes any that are no longer on the NY Urban website—while leaving past games, other seasons, and all personal events untouched.
- **Gym Address Mapping**: Converts NY Urban gym codes (like `SOA`, `LAG-N`, `JJC-A`, `BEC-F`) into full physical addresses.

---

## Setup (Recommended: Automated via GitHub Actions)

You don't need to install anything locally—just fork this repository and add your credentials in GitHub.

### 1. Fork this Repository
Click **Fork** at the top right of this repository to create your own copy in your GitHub account.

### 2. Create an Apple App-Specific Password
To let GitHub Actions sync directly with your iCloud Apple Calendar without using your main Apple ID password:
1. Sign in to [account.apple.com](https://account.apple.com).
2. Go to **Sign-In and Security → App-Specific Passwords**.
3. Click **Generate an app-specific password**, give it a label (e.g., `ny-urban-sync`), and copy the generated `xxxx-xxxx-xxxx-xxxx` password.

### 3. Configure Repository Secrets & Variables
In your forked repo, go to **Settings → Secrets and variables → Actions** and add the following under **Repository secrets** and **Repository variables** *(not Environment secrets)*:

- **Repository secrets** (required):
  | Secret | Description |
  | --- | --- |
  | `NY_URBAN_USERNAME` | Your NY Urban login email/username |
  | `NY_URBAN_PASSWORD` | Your NY Urban login password |
  | `ICLOUD_USERNAME` | Your Apple ID email address |
  | `ICLOUD_APP_PASSWORD` | The App-Specific Password from Step 2 |

- **Repository variables** (recommended):
  | Variable | Description |
  | --- | --- |
  | `CALENDAR_NAME` | The exact name of your target Apple Calendar in iCloud (e.g., `Personal`, `Volleyball`, `Home`). Works with shared iCloud calendars too. |

> **Tip:** You can change `CALENDAR_NAME` anytime in **Repository variables** without editing any code. If you aren't sure what iCloud calls your calendar, run a dry run (Step 5) and if it doesn't match, the error log will print all available calendar names in your iCloud account.

### 4. Enable GitHub Actions on Your Fork
GitHub disables scheduled workflows on newly forked repos by default:
1. Open the **Actions** tab in your forked repo.
2. Click **"I understand my workflows, go ahead and enable them"**.

### 5. Test with a Dry Run
1. Go to **Actions → Sync NY Urban Volleyball Schedule**.
2. Click **Run workflow**, check **`dry_run`**, and click **Run workflow**.
3. Inspect the job log to confirm your teams, upcoming games, and target calendar look right.
4. Run it once more with **`dry_run` unchecked** to perform your initial sync.

From then on, [`.github/workflows/sync-schedule.yml`](.github/workflows/sync-schedule.yml) will automatically run every day with `dry_run` off.

> **Note for public forks:** GitHub automatically pauses scheduled (`cron`) workflows on public repositories after 60 days without any commits. If that happens, GitHub will email you with a one-click link to re-enable it in the Actions tab.

---

## Optional: Running Locally

If you want to run or test the script on your own machine (requires **Python 3.12+**):

1. **Install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Create your `.env` file**:
   ```bash
   cp .env.example .env
   ```
   Fill in `NY_URBAN_USERNAME`, `NY_URBAN_PASSWORD`, `CALENDAR_NAME`, and (for iCloud CalDAV sync) `ICLOUD_USERNAME` and `ICLOUD_APP_PASSWORD`.
   *(On macOS, if `ICLOUD_USERNAME` / `ICLOUD_APP_PASSWORD` are omitted, the script automatically falls back to local AppleScript via the Calendar app.)*

3. **Run the sync**:
   ```bash
   # Interactive sync
   python3 main.py

   # Preview changes without modifying your calendar
   python3 main.py --dry-run

   # Non-interactive sync with a calendar override
   python3 main.py --yes --calendar "Volleyball"
   ```

4. **Run unit tests**:
   ```bash
   python3 -m unittest test_sync.py -v
   ```

---

## Security Note

- **Never** commit your `.env` file or hardcode credentials in the repository.
- Always use an Apple **App-Specific Password** (never your primary Apple ID password) for `ICLOUD_APP_PASSWORD`, and revoke it anytime at [account.apple.com](https://account.apple.com).
