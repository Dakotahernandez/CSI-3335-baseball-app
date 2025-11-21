# CSI 3335 Baseball Flask Application

This repository contains a ready-to-run Flask + MariaDB project for the CSI 3335 baseball database. The backend connects to the existing `baseball` schema and only manages an additional `users` table for application authentication.

## Prerequisites
- Python 3.12 or newer ive tested with Python 3.13.9 
- MariaDB server 
- Existing `baseball` database loaded via the provided `baseball.sql`

## Database Startup
- Run `SQLStart.bat` followed by `SQL.bat` from the course ZIP to start MariaDB.
- Connect using the provided shell and run:
  ```sql
  use baseball;
  SELECT @@sql_mode;
  \. user.sql
  ```
  This command recreates **only** the `users` table required by the web application and seeds the administrator account.

## Configuration
1. Open `csi3335f2025.py` and confirm the credentials match your MariaDB setup. Default values (adjust if your DB uses something else):
   ```python
   mysql = {
       'host': 'localhost',
       'user': 'web',
       'password': 'csi3335rocks',
       'database': 'baseball'
   }
   ```
2. If your credentials differ, update the  accordingly. The application reads this file at startup, per the 2025 project spec.

## Python Environment
1. From the project root, create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
2. Activate it:
   - Windows (PowerShell): `venv\Scripts\Activate.ps1`
3. Install dependencies 
   ```bash
   pip install -r requirements.txt
   ```


## Running the Application
1. Ensure MariaDB is running and that `user.sql` has been applied to the `baseball` database.
2. Activate the virtual environment.
3. Export `FLASK_APP=run.py` if `.flaskenv` is not respected by your shell.
4. Start the development server:
   ```bash
   flask run
   ```
5. Visit `http://127.0.0.1:5000/` in your browser. All core pages require sign-in; you will be redirected to the login page if not authenticated.

## Application Routes
- `/` – Home page with season + team lookup (requires login).
- `/team/<team_id>/<year>` – Displays batting statistics for the selected team and season.
- `/team/<team_id>/<year>/download` – Exports the enriched batting table as a CSV file.
- `/team/<team_id>/<year>/compare` – Lets you select two players from the roster and view a side-by-side stat breakdown.
- `/teams/compare` – Compare two teams from the same season side by side.
- `/game` – kahootish multiple choice trivia game with random player/team questions drawn from the database (three lives).
- `/auth/register` – Create an account (stored in `baseball.users`).
- `/auth/login` – Sign in.
- `/auth/logout` – Sign out.

Routes other than `/auth/*` require an authenticated session.

## Administrator Account
- Default administrator username: `admin`
- Default password: `AdminPass123!`
- The credentials are stored in `user.sql` as a PBKDF2-SHA256 hash. To change it, replace the seeded hash with a new one generated via Python:
  ```bash
  python - <<'PY'
  from werkzeug.security import generate_password_hash
  print(generate_password_hash('YourNewAdminPassword'))
  PY
  ```
  Then update the `pw_hash` value in `user.sql` and re-run it against the database.

## User Accounts and Password Policy
- Users sign up through `/auth/register`; passwords are never stored in plaintext and are hashed with PBKDF2-SHA256.
- No complexity rules are enforced beyond providing a password, password strength is your choice
- You must be logged in to access team lookup, CSV download, player comparison, and trivia pages.

## Data Handling Notes
- All baseball tables except `users` remain read-only.
- The team lookup form enforces year bounds (1871–2024) and requires selecting a team ID available in the chosen season.
- Queries are parameterized and never echo raw SQL.

## Calculations Included
- Player age: `season_year - birthYear` when available.
- Singles/total bases: singles = hits − doubles − triples − HR; total bases = 1B + 2×2B + 3×3B + 4×HR.
- Plate appearances: AB + BB + HBP + SF + SH.
- Slash line: AVG = H/AB; OBP = (H + BB + HBP) / PA; SLG = TB/AB; OPS = OBP + SLG.
- SB%: SB / (SB + CS) when attempts > 0.
- Team totals added as the last row in exports; leaders (HR, AVG, OPS, SB) and badges (Hall of Fame/All-Star) surface where data exists.

## EXTRAS
- Hall of Fame and All-Star badges appear next to qualified players, powered by the `halloffame` and `allstarfull` tables.
- Core batting stats (AVG/OBP/SLG/OPS) are calculated on the server and rendered alongside traditional counting stats.
- Team totals are appended to the stat table, and a slash-line summary panel highlights overall production plus season leaders.
- Additional metrics surface player ages and stolen-base success rate; league comparison card shows AVG/OBP/SLG/OPS context.
- CSV export lets viewers download the enriched table for further analysis with a single click.


## Shutdown
When finished, stop MariaDB using the provided shutdown scripts from the course ZIP.
