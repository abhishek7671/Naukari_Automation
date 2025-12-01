# login_test.py
import pickle
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

print("➡️ Opening Naukri Login Page...")
driver.get("https://www.naukri.com/nlogin/login")

# Give you time to manually login (handle OTP/CAPTCHA manually here)
print("⚠️ PLEASE LOGIN MANUALLY IN THE BROWSER WINDOW.")
input("➡️ After login completes, press ENTER here to save cookies...")

pickle.dump(driver.get_cookies(), open("naukri_cookies.pkl", "wb"))
print("✅ Cookies saved successfully as naukri_cookies.pkl")

driver.quit()
