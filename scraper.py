import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

from dataclasses import dataclass
from bs4 import BeautifulSoup

@dataclass
class Game:
    date: str
    time: str
    location: str
    opponent: str
    summary: str
    team_name: str

def parse_schedule_table(html, team_name):
    soup = BeautifulSoup(html, 'html.parser')
    games = []
    
    # Look for tables. NY Urban schedules are usually in a <table>
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        if not rows: continue
        
        # Check if this table has schedule headers
        header_row = rows[0].find_all(['td', 'th'])
        header_text = [c.get_text(strip=True) for c in header_row]
        
        # New format headers: ['Date', 'Location', 'Time', 'Opponent', 'Results']
        if len(header_text) >= 4 and "Date" in header_text[0] and "Time" in header_text[2]:
            # This is a schedule table
            for row in rows[1:]:
                cols = row.find_all(['td', 'th'], recursive=False)
                # Only process rows that have 5 columns (Date, Location, Time, Opponent, Results)
                if len(cols) == 5:
                    text_cols = []
                    for c in cols:
                        raw_text = c.get_text(separator=' ', strip=True)
                        clean_text = raw_text.split('arrow')[0].strip()
                        text_cols.append(clean_text)
                    
                    date_val = text_cols[0]
                    # Filter out headers that might be repeated or nested
                    if date_val == "Date" or not any(char.isdigit() for char in date_val):
                        continue
                        
                    if "No Game" in "".join(text_cols) or "***" in date_val:
                        continue

                    game = Game(
                        date=text_cols[0],
                        location=text_cols[1],
                        time=text_cols[2],
                        opponent=text_cols[3],
                        team_name=team_name,
                        summary=f"{team_name} vs {text_cols[3]}"
                    )
                    games.append(game)
    return games

def login_and_get_schedule():
    username = os.getenv("NY_URBAN_USERNAME")
    password = os.getenv("NY_URBAN_PASSWORD")
    
    if not username or not password or username == "your_username":
        print("Please set NY_URBAN_USERNAME and NY_URBAN_PASSWORD in .env file")
        return []

    with sync_playwright() as p:
        # Launching with headless=True
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        print("Navigating to NY Urban Login...")
        page.goto("https://www.nyurban.com/volleyball/")
        
        print("Logging in...")
        # Correct selectors based on actual HTML
        page.fill('input[name="ny_username"]', username)
        page.fill('input[name="ny_password"]', password)
        
        # Press Enter to submit the form since the button is hidden
        print("Submitting login form...")
        page.keyboard.press("Enter")
        
        page.wait_for_load_state("networkidle")
        
        if "Logout" not in page.content():
            print("Login failed or 'Logout' link not found.")
            browser.close()
            return []
        
        print("Login successful! Navigating to Waiver Team Listing...")
        page.goto("https://www.nyurban.com/waiver-team-listing/")
        page.wait_for_load_state("networkidle")
        
        # Parse the team listing to find the latest season
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find the team table
        team_table = soup.find('table', {'width': '767'})
        if not team_table:
            print("Could not find team table.")
            browser.close()
            return []
            
        rows = team_table.find_all('tr')[1:] # Skip header
        
        teams = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                name_col = cols[0]
                season_col = cols[1]
                
                team_name = name_col.get_text(strip=True)
                season = season_col.get_text(strip=True)
                link_tag = name_col.find('a')
                if link_tag and link_tag.get('href'):
                    teams.append({
                        'name': team_name,
                        'season': season,
                        'href': link_tag.get('href')
                    })
        
        if not teams:
            print("No teams found in listing.")
            browser.close()
            return []
            
        # Determine latest season (heuristic: the one at the top is usually latest)
        # or we can just pick the first unique season name we see
        latest_season = teams[0]['season']
        print(f"Detected latest season: {latest_season}")
        
        # Filter teams for only the latest season
        latest_teams = [t for t in teams if t['season'] == latest_season]
        print(f"Found {len(latest_teams)} teams for {latest_season}: {[t['name'] for t in latest_teams]}")
        
        all_games = []
        # Visit each latest team page and parse the table
        for team in latest_teams:
            href = team['href']
            full_url = href if href.startswith("http") else f"https://www.nyurban.com{href}"
            print(f"Checking team: {team['name']} ({full_url})")
            page.goto(full_url)
            page.wait_for_load_state("networkidle")
            
            html = page.content()
            team_games = parse_schedule_table(html, team['name'])
            print(f"  - Extracted {len(team_games)} games from this team.")
            all_games.extend(team_games)
            
        browser.close()
        
        # Deduplicate games based on date and time to be safe
        unique_games = []
        seen = set()
        for g in all_games:
            key = (g.date, g.time, g.opponent)
            if key not in seen:
                unique_games.append(g)
                seen.add(key)
                
        return unique_games

if __name__ == "__main__":
    login_and_get_schedule()
