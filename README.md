# Naukri Automation

Automates resume updates and job searching/applying on Naukri.com using Selenium.

**Purpose**
- **Description**: A lightweight automation tool that logs into Naukri, re-uploads a resume periodically, searches for jobs by keywords and locations, attempts quick/one-click applies where available, and records job links for manual follow-up.

**Features**
- **Cookie reuse**: Saves and loads browser cookies to avoid repeated logins.
- **Resume update**: Uploads resume to profile on a schedule to keep it current.
- **Job search & collect**: Searches per keyword/location and stores job links in a CSV.
- **Auto-apply attempt**: Tries to click quick-apply buttons when detected.
- **OTP support**: Optional IMAP-based OTP fetch (when configured) to automate OTP entry.
- **Error snapshots & logs**: Saves HTML snapshots into `snapshots/` and writes logs to `naukri_bot.log`.

**Key files**
- [naukari_automation.py](naukari_automation.py): Main scheduler and automation logic.
- [login_test.py](login_test.py): Quick helper to open the login page and save cookies after manual sign-in.
- [read_otp_email.py](read_otp_email.py): Small utility to fetch OTPs from an IMAP mailbox.
- [requirements.txt](requirements.txt): Python dependencies.
- [.env](.env): Environment variables (not included—create locally).
- [naukri_jobs_applied.csv](naukri_jobs_applied.csv): CSV where discovered/applied job links are stored.
- [snapshots/](snapshots): Directory with HTML snapshots captured on errors.

**Prerequisites**
- **Python**: 3.8+ recommended.
- **Chrome Browser**: The script uses Chrome; `webdriver-manager` installs matching chromedriver automatically.

**Install**
```bash
python -m pip install -r requirements.txt
```

**Environment configuration (.env)**
Create a `.env` file in the project root with these variables (example values shown):

```
NAUKRI_EMAIL=you@example.com
NAUKRI_PASSWORD=yourpassword
NAUKRI_RESUME_PATH=C:\full\path\to\resume.pdf
JOB_KEYWORDS=Python Developer,Backend Engineer
LOCATIONS=Bangalore,Hyderabad
EXPERIENCE=3
APPLY_KEYWORDS=Python,Docker,AWS
IMAP_HOST=imap.example.com      # optional for OTP fetch
IMAP_EMAIL=imap_user@example.com
IMAP_PASSWORD=imap_password
RESUME_UPDATE_MINUTES=30
JOB_SEARCH_HOURS=6
HEADLESS=false
USER_AGENT=optional custom UA string
```

Security note: Do not commit your `.env` — keep credentials private.

**Usage**
- Save cookies after a manual login (recommended first step):

```bash
python login_test.py
```

- Run the main automation script (runs scheduled tasks and a small scheduler loop):

```bash
python naukari_automation.py
```

- Optional: run `read_otp_email.py` standalone to test IMAP OTP fetching.

**Behavior & Notes**
- The script tries cookie reuse via `naukri_cookies.pkl`. If cookies are invalid/expired it falls back to login flow.
- If OTP or CAPTCHA appears the script will either attempt IMAP OTP fetch (if configured) or prompt for manual intervention.
- HTML snapshots for failures are saved under `snapshots/` with descriptive filenames (e.g., `login_failed_*.html`).
- Logs are written to `naukri_bot.log` in the project root.

**Troubleshooting**
- If uploads or search selectors stop working, site layout likely changed—inspect the saved snapshot in `snapshots/` and adjust selectors in `naukari_automation.py`.
- If Chrome driver errors appear, update `webdriver-manager` and ensure Chrome is up-to-date.

**Contributing / Extending**
- You can add more robust filters or safer apply heuristics in `naukari_automation.py`.
- Consider adding headless-run CI-safe flags or Docker wrapper if you want remote runs.

**License**
- No license specified. Add a `LICENSE` file if you want to apply one.

----

## Quick start commands

Follow these commands to create a virtual environment, install dependencies, and run the scripts.

Windows (Command Prompt):

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Save cookies after manual login (recommended):
python login_test.py

# Run the automation (scheduler + tasks):
python naukari_automation.py
```

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python login_test.py
python naukari_automation.py
```

Linux / macOS (bash):

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python login_test.py
python naukari_automation.py
```

Generated from repository inspection on 2026-07-28.
