import datetime
import os
import smtplib
import logging
from config_and_env import read_config
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

def send_log_email(log_file_path):
    try:
        SMTP = read_config("SMTP")
        smtp_server = SMTP["server"]
        smtp_username = os.getenv("email_username")
        smtp_password = os.getenv("email_password")
        from_email = os.getenv("email_from")
        to_email = os.getenv("email_to")
        smtp_port = int(os.getenv("email_port"))

        subject = f"Log file for {datetime.date.today().strftime('%Y-%m-%d')}"

        # Read the content of the log file with the latest entries at the top
        try:
            with open(log_file_path, 'r') as log_file:
                log_content = reversed(log_file.readlines())
                log_content = ''.join(log_content)
        except FileNotFoundError as e:
            logging.error(f"File not found error: {e}")
            return  # Stop further execution if file not found

        # Prepare email
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        # Attach log content
        msg.attach(MIMEText(log_content, 'plain'))

        # Connect to SMTP server and send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
