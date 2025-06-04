import smtplib
from email.message import EmailMessage
import os

EMAIL_ADDRESS = os.environ.get("REMINDER_EMAIL")
EMAIL_PASSWORD = os.environ.get("REMINDER_PASS")
TO_EMAIL = os.environ.get("TO_EMAIL")

def send_reminder():
    msg = EmailMessage()
    msg["Subject"] = "🕒 Daily Reminder: Log Your Hours"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL
    msg.set_content("Hey Dhiraj,\n\nDon't forget to log your work hours today in your Biweekly Pay Tracker app!\n\n✅ Visit your app and stay on track!")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

if __name__ == "__main__":
    send_reminder()
