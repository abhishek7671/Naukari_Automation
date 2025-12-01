# read_otp_email.py
import imaplib
import email
import re
import time
from dotenv import load_dotenv
import os

load_dotenv()

IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_EMAIL = os.getenv("IMAP_EMAIL")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

def fetch_otp(subject_keyword="Naukri", timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        try:
            imap = imaplib.IMAP4_SSL(IMAP_HOST)
            imap.login(IMAP_EMAIL, IMAP_PASSWORD)
            imap.select("INBOX")
            status, data = imap.search(None, f'(UNSEEN SUBJECT "{subject_keyword}")')
            ids = data[0].split()
            if ids:
                email_id = ids[-1]
                typ, msg_data = imap.fetch(email_id, "(RFC822)")
                message = email.message_from_bytes(msg_data[0][1])
                body = ""
                if message.is_multipart():
                    for part in message.walk():
                        if part.get_content_type() == "text/plain":
                            body += part.get_payload(decode=True).decode(errors='ignore')
                else:
                    body = message.get_payload(decode=True).decode(errors='ignore')
                match = re.search(r"\b(\d{4,8})\b", body)
                imap.logout()
                if match:
                    return match.group(1)
            imap.logout()
        except Exception as e:
            print("IMAP error:", e)
        time.sleep(5)
    return None

if __name__ == "__main__":
    otp = fetch_otp()
    print("OTP:", otp)
