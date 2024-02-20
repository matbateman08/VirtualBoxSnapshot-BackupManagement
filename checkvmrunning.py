import subprocess
import re
import os
import configparser
import logging
import datetime
import smtplib
from enum import Enum
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

class VM(Enum):
    VBOX_MANAGE = "VBoxManage"

def read_config(section_name):
    try:
        config = configparser.ConfigParser()

        # Get the absolute path of the script
        script_directory = os.path.dirname(os.path.abspath(__file__))

        # Use a relative path to the config file
        config_file_path = os.path.join(script_directory, 'config.ini')

        # Check if the file exists
        if not os.path.exists(config_file_path):
            logging.critical(f"Error: Config file does not exist at {config_file_path}")
            return None

        # Attempt to read the configuration file
        read_files = config.read(config_file_path)

        if not read_files:
            logging.critical(f"Error: Config file does not exist at {config_file_path}")
            return None

        # Check if the specified section exists
        if section_name not in config:
            logging.critical(f"Error: Section {section_name} does not exist in the config file")
            return None

        section = config[section_name]

        # logging.info(f"{section_name} Section:")
        # for key, value in section.items():
        #     logging.info(f"  {key}: {value}")

        # logging.info("")

        return section
    except Exception as e:
        logging.error(f"Error in read_config: {str(e)}")
        return None

def configure_logging():
    try:
        # Get the absolute path of the script
        script_directory = os.path.dirname(os.path.abspath(__file__))

        # Generate a log file path based on the current date, VM name, and title
        today_date = datetime.date.today().strftime("%Y-%m-%d")
        # Create a subfolder named 'logs' if it doesn't exist
        logs_folder = os.path.join(script_directory, 'logs', 'vmrunninglogs')        
        os.makedirs(logs_folder, exist_ok=True)
        log_file_path = os.path.join(logs_folder, f'{today_date}_vm_running.log')

        # Configure logging first
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s]: %(message)s',
            handlers=[logging.StreamHandler(), logging.FileHandler(log_file_path)]
        )

        # Log the configuration settings
        logging.info(f"Log level: {logging.getLevelName(logging.getLogger().getEffectiveLevel())}")
        logging.info(f"Script File Path: {script_directory}")
        logging.info(f"Log File Path: {log_file_path}")
    except Exception as e:
        logging.error(f"Error in configure_logging: {str(e)}")

def list_vms():
    try:
        result = subprocess.run([VM.VBOX_MANAGE.value, 'list', 'vms'], capture_output=True, text=True)
        vm_list = result.stdout.split('\n')

        for line in vm_list:
            if not line:
                continue

            # vm_name_match = re.search(r'"(.+)"', line)
            # if vm_name_match:
            #     print(f"VMName: {vm_name_match.group(1)}")

        return re.findall(r'"([^"]*)"', result.stdout)
    except Exception as e:
        logging.error(f"Error in list_vms: {str(e)}")
        return []

def start_vm(vm_name):
    try:
        result = subprocess.run([VM.VBOX_MANAGE.value, 'startvm', vm_name, '--type', 'headless'], capture_output=True,
                                text=True, check=True)
        if "has been successfully started" in result.stdout:
            logging.info(f"VM '{vm_name}' started successfully.")
            return True
        elif "VBOX_E_INVALID_OBJECT_STATE" in result.stderr:
            logging.info(f"VM '{vm_name}' is already running.")
            return True
        else:
            logging.info(f"Failed to start VM '{vm_name}'.")
            logging.info("Error:", result.stderr)
            return False

    except subprocess.CalledProcessError as e:
        if "returned non-zero exit status 1" in str(e):
            logging.info(f"VM '{vm_name}' is already turned on.")
        elif "VBOX_E_INVALID_OBJECT_STATE" in e.stderr:
            logging.info(f"VM '{vm_name}' is already running.")
        else:
            logging.info(f"Failed to start/stop VM '{vm_name}'.")
            logging.info(f"Error: {e.stderr}")

def send_outlook_email(vm_name):
    try:
        SMTP = read_config("SMTP")
        smtp_server = SMTP["server"]
        smtp_username = os.getenv("email_username")
        smtp_password = os.getenv("email_password")
        from_email = os.getenv("email_from")
        to_email = os.getenv("email_to")
        smtp_port = int(os.getenv("email_port"))

        subject = f"VM '{vm_name}' Restarted"
        body = f"VM '{vm_name}' had stopped working and has been restarted."

        # Prepare email
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to SMTP server and send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

        logging.info(f"Email sent successfully to {to_email} for VM '{vm_name}' restart.")
    except Exception as e:
        logging.error(f"Failed to send email for VM '{vm_name}' restart. Error: {str(e)}")

def main():
    try:
        configure_logging()
        virtual_box_path = read_config("Paths")
        os.chdir(virtual_box_path['virtual_box_path'])
        vm_names = list_vms()

        not_running_counter = 0  # Initialize the counter
        
        VMDetails = read_config("VMDetails")
        vm_names_section = VMDetails['vm_names']
        for vm_name in vm_names_section.split(','):
            if start_vm(vm_name):
                send_outlook_email(vm_name)
                logging.info(f"VM: {vm_name} is already running, so incrementing counter: {not_running_counter}")
                not_running_counter += 1  # Increment the counter for each VM not running

        #for vm_name in vm_names:
        #    if start_vm(vm_name):
        #        send_outlook_email(vm_name)
        #        logging.info(f"VM: {vm_name} is already running, so incrementing counter: {not_running_counter}")
        #        not_running_counter += 1  # Increment the counter for each VM not running
        
        if not_running_counter == 0:
            # All VMs are running, send an email
            logging.info("All VM's are running.")
            #send_outlook_email("All VMs are running.")

    except Exception as e:
        logging.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
