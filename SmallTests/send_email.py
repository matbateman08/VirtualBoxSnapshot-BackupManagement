import smtplib
import os
import logging
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from vm_process import read_config, configure_logging

def main():
    configure_logging("vmmaintenance")
    paths = read_config("Paths")
    os.chdir(paths['virtual_box_path'])
    send_log_email(r"C:\VM_Management\logs\vmmaintenance\2024-02-22_vmmaintenance.log")

def get_log_content(log_file_path):
    """
    Read the content of a log file.
    Args:
        log_file_path (str): The path to the log file.

    Returns:
        str: The content of the log file.
    """
    try:
        with open(log_file_path, 'r') as log_file:
            return ''.join(reversed(log_file.readlines()))
    except FileNotFoundError as e:
        logging.error(f"File not found error: {e}")
        return None

def send_email(subject, from_email, to_email, body, smtp_server, smtp_port, smtp_username, smtp_password):
    """
    Send an email.
    Args:
        subject (str): The subject of the email.
        from_email (str): The sender's email address.
        to_email (str): The recipient's email address.
        body (str): The body/content of the email.
        smtp_server (str): The SMTP server address.
        smtp_port (int): The SMTP server port.
        smtp_username (str): The SMTP username for authentication.
        smtp_password (str): The SMTP password for authentication.
    """
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending email: {e}")

def send_log_email(log_file_path):
    """
    Send log file content via email.
    Args:
        log_file_path (str): The path to the log file.
    """
    try:
        SMTP = read_config("SMTP")
        smtp_server = SMTP["server"]
        smtp_username = os.getenv("email_username")
        smtp_password = os.getenv("email_password")
        from_email = os.getenv("email_from")
        to_email = os.getenv("email_to")
        smtp_port = os.getenv("email_port")

        print(smtp_server, smtp_username, smtp_password, from_email, to_email, smtp_port)
        subject = f"Log file for {datetime.date.today().strftime('%Y-%m-%d')}"

        log_content = get_log_content(log_file_path)
        if log_content is not None:
            send_email(subject, from_email, to_email, log_content, smtp_server, smtp_port, smtp_username, smtp_password)
    
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
