"""
Main Naukri automation script.

- Loads credentials/config from .env
- Uses cookie reuse to avoid OTP/CAPTCHA after manual login
- Uploads resume to profile
- Searches jobs and attempts "quick apply" when safe
- Saves job links to CSV, logs activity, and creates HTML snapshots on errors
- Scheduler runs resume update and job search tasks

Install required packages:
    pip install selenium webdriver-manager pandas python-dotenv schedule imapclient
"""
import os
import time
import pickle
import random
import logging
import schedule
import pandas as pd
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Optional IMAP for OTP (only used if configured)
try:
    import imaplib, email, re
except Exception:
    imaplib = None

# ---------------- CONFIG & LOGGING ----------------
load_dotenv()

NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD")
RESUME_PATH = os.getenv("NAUKRI_RESUME_PATH")
COOKIE_FILE = Path("naukri_cookies.pkl")
JOB_LINKS_CSV = Path("naukri_jobs_applied.csv")
SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

JOB_KEYWORDS = [k.strip() for k in os.getenv("JOB_KEYWORDS", "Python Developer,Python AWS Docker SQL").split(",")]
LOCATIONS = [l.strip() for l in os.getenv("LOCATIONS", "Bangalore,Hyderabad,Chennai,Pune").split(",")]
EXPERIENCE = os.getenv("EXPERIENCE", "3")
APPLY_KEYWORDS = [k.strip().lower() for k in os.getenv("APPLY_KEYWORDS", "AWS,Docker,SQL,Microservices,MongoDB,Python,Django,RestAPIs,Fastapi,Flask").split(",")]

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_EMAIL = os.getenv("IMAP_EMAIL")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

RESUME_UPDATE_MINUTES = int(os.getenv("RESUME_UPDATE_MINUTES", "30"))
JOB_SEARCH_HOURS = int(os.getenv("JOB_SEARCH_HOURS", "6"))
HEADLESS = os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes")
MAX_JOB_PER_KEYWORD = int(os.getenv("MAX_JOB_PER_KEYWORD", "10"))

logging.basicConfig(filename='naukri_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

# ---------------- Helpers ----------------
def setup_driver(headless=HEADLESS):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    ua = os.getenv("USER_AGENT")
    if ua:
        options.add_argument(f"--user-agent={ua}")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(30)
    return driver

def wait_for(driver, by, locator, timeout=15):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, locator)))

def normalize(text):
    return (text or "").strip().lower()

def snapshot_page(driver, name_prefix="snapshot"):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_file = SNAPSHOT_DIR / f"{name_prefix}_{ts}.html"
    try:
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logging.info(f"Saved snapshot: {html_file}")
    except Exception as e:
        logging.error(f"Failed to save snapshot: {e}")
    return html_file

# ---------------- Cookie management ----------------
def save_cookies(driver, path=COOKIE_FILE):
    try:
        pickle.dump(driver.get_cookies(), open(path, 'wb'))
        logging.info(f"Saved cookies to {path}")
    except Exception as e:
        logging.error(f"Failed to save cookies: {e}")

def load_cookies(driver, path=COOKIE_FILE):
    if not path.exists():
        return False
    try:
        cookies = pickle.load(open(path, 'rb'))
        driver.get("https://www.naukri.com")
        for c in cookies:
            c.pop('sameSite', None)
            try:
                driver.add_cookie(c)
            except Exception:
                pass
        driver.refresh()
        logging.info("Loaded cookies and refreshed.")
        return True
    except Exception as e:
        logging.error(f"Failed to load cookies: {e}")
        return False

# ---------------- Optional IMAP OTP fetch ----------------
def fetch_latest_otp(subject_keyword="Naukri", timeout=60):
    if not imaplib or not IMAP_HOST or not IMAP_EMAIL or not IMAP_PASSWORD:
        logging.info("IMAP not configured; skipping OTP fetch.")
        return None

    end = time.time() + timeout
    while time.time() < end:
        try:
            imap = imaplib.IMAP4_SSL(IMAP_HOST)
            imap.login(IMAP_EMAIL, IMAP_PASSWORD)
            imap.select('INBOX')
            typ, data = imap.search(None, f'(UNSEEN SUBJECT "{subject_keyword}")')
            ids = data[0].split()
            if ids:
                latest = ids[-1]
                typ, msg_data = imap.fetch(latest, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            body += part.get_payload(decode=True).decode(errors='ignore')
                else:
                    body = msg.get_payload(decode=True).decode(errors='ignore')
                m = re.search(r"\b(\d{4,8})\b", body)
                imap.logout()
                if m:
                    logging.info("Fetched OTP from email")
                    return m.group(1)
            imap.logout()
        except Exception as e:
            logging.error(f"IMAP check failed: {e}")
        time.sleep(5)
    return None

# ---------------- Login ----------------
def login_naukri(driver, allow_manual_otp=True):
    if not NAUKRI_EMAIL or not NAUKRI_PASSWORD:
        raise RuntimeError("NAUKRI_EMAIL or NAUKRI_PASSWORD missing in environment")

    driver.get("https://www.naukri.com/nlogin/login")
    try:
        if COOKIE_FILE.exists():
            loaded = load_cookies(driver)
            if loaded:
                time.sleep(2)
                # quick heuristic to check if logged in
                if "mnjuser" in driver.current_url or "profile" in driver.current_url:
                    logging.info("Already logged in via cookies")
                    return True

        # Fill form
        try:
            email_el = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'usernameField')))
            pwd_el = driver.find_element(By.ID, 'passwordField')
            email_el.clear(); email_el.send_keys(NAUKRI_EMAIL)
            pwd_el.clear(); pwd_el.send_keys(NAUKRI_PASSWORD)
            login_btn = driver.find_element(By.CLASS_NAME, 'loginButton')
            login_btn.click()
        except TimeoutException:
            logging.warning("Login fields not found; page layout may have changed")

        # detect OTP or captcha
        try:
            otp_input = WebDriverWait(driver, 6).until(EC.presence_of_element_located(
                (By.XPATH, "//input[contains(@name,'otp') or contains(@placeholder,'OTP')]")))
            logging.info("OTP input detected on page")
            if IMAP_HOST:
                otp = fetch_latest_otp(timeout=40)
                if otp:
                    otp_input.send_keys(otp)
                    try:
                        otp_submit = driver.find_element(By.XPATH, "//button[contains(.,'Verify') or contains(.,'Submit')]")
                        otp_submit.click()
                    except Exception:
                        pass
                else:
                    logging.info("Could not fetch OTP automatically; please enter OTP manually in browser")
            else:
                if allow_manual_otp:
                    input("Please solve OTP/CAPTCHA in browser and press Enter here to continue...")
                else:
                    logging.error("OTP present and manual intervention disallowed")
                    return False
        except TimeoutException:
            pass

        page_text = driver.page_source.lower()
        if 'captcha' in page_text or 'recaptcha' in page_text:
            logging.warning('CAPTCHA detected. Please solve it manually in the opened browser window.')
            input('Solve the CAPTCHA in the browser and press Enter here to continue...')

        try:
            WebDriverWait(driver, 20).until(EC.url_contains('naukri.com'))
        except Exception:
            logging.warning('Login may not have completed automatically; check browser manually')

        save_cookies(driver)
        return True

    except Exception as e:
        logging.error(f"Login failed: {e}")
        snapshot_page(driver, "login_failed")
        return False

# ---------------- Resume upload ----------------
def upload_resume_to_profile(driver):
    try:
        driver.get('https://www.naukri.com/mnjuser/profile')
        WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
        if not file_inputs:
            # try searching inside iframes
            iframes = driver.find_elements(By.TAG_NAME, 'iframe')
            for fr in iframes:
                try:
                    driver.switch_to.frame(fr)
                    file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
                    if file_inputs:
                        break
                    driver.switch_to.default_content()
                except Exception:
                    driver.switch_to.default_content()

        if not file_inputs:
            try:
                el = driver.find_element(By.XPATH, "//input[@type='file']")
                driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility='visible';", el)
                file_inputs = [el]
            except Exception:
                pass

        if file_inputs:
            input_el = file_inputs[0]
            if not RESUME_PATH or not Path(RESUME_PATH).exists():
                logging.error('RESUME_PATH missing or file does not exist in environment')
                return False
            input_el.send_keys(str(RESUME_PATH))
            logging.info('Sent resume file path to file input. Waiting for upload to complete...')
            time.sleep(3 + random.uniform(0.5, 2.0))
            logging.info('Resume upload attempted')
            driver.switch_to.default_content()
            return True
        else:
            logging.error('No file input found for resume upload')
            snapshot_page(driver, 'resume_input_notfound')
            return False

    except Exception as e:
        logging.error(f"Resume upload failed: {e}")
        snapshot_page(driver, 'resume_upload_error')
        return False

# ---------------- Search & Apply ----------------
def search_and_apply_jobs_once():
    logging.info('Starting search_and_apply_jobs')
    driver = None
    job_links = []
    try:
        driver = setup_driver()
        logged = login_naukri(driver)
        if not logged:
            logging.error('Cannot proceed without login')
            return

        for keyword in JOB_KEYWORDS:
            try:
                logging.info(f"Searching for: {keyword}")
                driver.get('https://www.naukri.com')
                # find search box (tolerant)
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter skills / designations']"))
                    )
                except TimeoutException:
                    alt = driver.find_elements(By.XPATH, "//input[contains(@aria-label,'skills') or contains(@placeholder,'Search')]")
                    if alt:
                        search_box = alt[0]
                    else:
                        snapshot_page(driver, 'search_box_missing')
                        continue

                search_box.clear()
                search_box.send_keys(keyword)
                search_box.send_keys(Keys.RETURN)
                time.sleep(2 + random.uniform(0.5, 1.5))

                # Apply location filters heuristically
                for location in LOCATIONS:
                    try:
                        loc_xpath = f"//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{location.lower()}')]|//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{location.lower()}')]"
                        els = driver.find_elements(By.XPATH, loc_xpath)
                        if els:
                            try:
                                els[0].click()
                                time.sleep(1 + random.uniform(0.2, 0.8))
                            except Exception:
                                pass
                    except Exception:
                        continue

                # Experience filter (best-effort)
                try:
                    exp_xpath = f"//label[contains(., '{EXPERIENCE} Years') or contains(., '{EXPERIENCE} yrs')]"
                    exp_els = driver.find_elements(By.XPATH, exp_xpath)
                    if exp_els:
                        try:
                            exp_els[0].click()
                            time.sleep(1)
                        except Exception:
                            pass
                except Exception:
                    pass

                # Collect job cards (tolerant selectors)
                jobs = driver.find_elements(By.XPATH, "//a[contains(@class,'title') or contains(@class,'jobTuple') or contains(@class,'jobTitle')]")
                if not jobs:
                    jobs = driver.find_elements(By.XPATH, "//div[contains(@class,'jobTuple')]//a")

                for job in jobs[:MAX_JOB_PER_KEYWORD]:
                    try:
                        job_title = job.text
                        job_link = job.get_attribute('href')
                        job_links.append(job_link)

                        if any(kw in normalize(job_title) for kw in APPLY_KEYWORDS):
                            logging.info(f"Considering auto-apply for: {job_title}")
                            driver.get(job_link)
                            time.sleep(2 + random.uniform(0.5, 1.5))

                            apply_btns = driver.find_elements(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'quick apply') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'apply now') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'apply')]")
                            if apply_btns:
                                try:
                                    apply_btns[0].click()
                                    logging.info(f"Clicked apply for {job_title} (attempt)")
                                    time.sleep(2 + random.uniform(0.5, 1.2))
                                except Exception as e:
                                    logging.warning(f"Apply click failed: {e}")
                            else:
                                logging.info(f"No one-click apply found for {job_title}; saved link for manual apply")
                        else:
                            logging.info(f"Skipped auto-apply (keywords mismatch): {job_title}")
                    except Exception as e:
                        logging.error(f"Error handling job card: {e}")
                        snapshot_page(driver, 'job_card_error')

            except Exception as e:
                logging.error(f"Search loop error for keyword {keyword}: {e}")
                snapshot_page(driver, 'search_loop_error')

        df = pd.DataFrame({'Job Links': job_links})
        df.to_csv(JOB_LINKS_CSV, index=False)
        logging.info(f"Saved {len(job_links)} job links to {JOB_LINKS_CSV}")

    except Exception as e:
        logging.error(f"search_and_apply_jobs_once failed: {e}")
    finally:
        if driver:
            driver.quit()

# ---------------- Scheduled tasks ----------------
def task_update_resume():
    logging.info('Scheduled: update_resume')
    driver = None
    try:
        driver = setup_driver()
        logged = login_naukri(driver)
        if not logged:
            logging.error('Could not login; skipping resume update')
            return
        success = upload_resume_to_profile(driver)
        if success:
            logging.info('Resume update attempted successfully')
        else:
            logging.error('Resume update failed')
    except Exception as e:
        logging.error(f"task_update_resume failed: {e}")
    finally:
        if driver:
            driver.quit()

# ---------------- Scheduler start ----------------
schedule.every(RESUME_UPDATE_MINUTES).minutes.do(task_update_resume)
schedule.every(JOB_SEARCH_HOURS).hours.do(search_and_apply_jobs_once)

logging.info('Scheduler started. Press Ctrl+C to stop.')
try:
    while True:
        if datetime.today().weekday() < 5:
            schedule.run_pending()
        time.sleep(30)
except KeyboardInterrupt:
    logging.info('Script interrupted by user. Exiting.')
