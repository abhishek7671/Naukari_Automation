# login_test.py
import pickle
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print("➡️ Opening Naukri Login Page...")
driver.get("https://www.naukri.com/nlogin/login")

# Give you time to manually login (handle OTP/CAPTCHA manually here)
print("⚠️ PLEASE LOGIN MANUALLY IN THE BROWSER WINDOW.")
input("➡️ After login completes, press ENTER here to save cookies...")

with open("naukri_cookies.pkl", "wb") as f:
    pickle.dump(driver.get_cookies(), f)
print("✅ Cookies saved successfully as naukri_cookies.pkl")

driver.quit()
