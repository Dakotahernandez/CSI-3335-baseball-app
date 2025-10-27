# CSI 3335 Baseball Flask Application

This repository contains a ready-to-run Flask + MariaDB project for the CSI 3335 baseball database. The backend connects to the existing `baseball` schema and only manages an additional `users` table for application authentication.

## Prerequisites
- Python 3.12 or newer
- MariaDB server from the CSI 3335 course bundle
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
1. Open `csi3335f2024.py` and confirm the credentials match your MariaDB setup. Default values:
   ```python
   mysql = {
       'location': 'localhost',
       'user': 'web',
       'password': 'mypass',
       'database': 'baseball'
   }
   ```
2. If your credentials differ, update the dictionary accordingly. No other configuration edits are needed.

## Python Environment
1. From the project root, create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
2. Activate it:
   - macOS/Linux: `source venv/bin/activate`
   - Windows (PowerShell): `venv\Scripts\Activate.ps1`
   - Windows (CMD): `venv\Scripts\activate.bat`
3. Install the allowed dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Database Migration Setup
Flask-Migrate is configured but not initialized by default. After activating your virtual environment and installing requirements, run within the project root:
```bash
flask db init
```
This creates migration scaffolding for future application-level metadata if needed. **Do not** autogenerate migrations that alter existing baseball tables; the project only manages the `users` table explicitly.

## Running the Application
1. Ensure MariaDB is running and that `user.sql` has been applied to the `baseball` database.
2. Activate the virtual environment.
3. Export `FLASK_APP=run.py` if `.flaskenv` is not respected by your shell.
4. Start the development server:
   ```bash
   flask run
   ```
5. Visit `http://127.0.0.1:5000/` in your browser.

## Application Routes
- `/` – Home page with season + team lookup.
- `/team/<team_id>/<year>` – Displays batting statistics for the selected team and season.
- `/auth/register` – Create an account (stored in `baseball.users`).
- `/auth/login` – Sign in.
- `/auth/logout` – Sign out.

## Administrator Account
- Default administrator username: `admin`
- Default password: `AdminPass123!`
- The credentials are stored in `user.sql` as a hashed password using Werkzeug's PBKDF2-SHA256 scheme. Change the password by updating `user.sql` with a new hashed value if desired.

## Data Handling Notes
- All baseball tables except `users` remain read-only.
- The team lookup form enforces year bounds (1871–2024) and requires selecting a team ID available in the chosen season.
- Queries are parameterized and never echo raw SQL.

## Shutdown
When finished, stop MariaDB using the provided shutdown scripts from the course ZIP.
