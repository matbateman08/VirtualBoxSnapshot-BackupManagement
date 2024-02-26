import smtplib
import os
import logging
import datetime
import configparser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from vm_process import configure_logging, get_script_directory, file_exists

def main():
    log_file_path = configure_logging("vmmaintenance")
    Paths = read_config("Paths")
    #print(Paths)

    retention = read_config("BackupDetails")
    print(retention.get('daily_retention'))
    print(retention.get('monthly_retention'))

    daily_retention = retention.get('daily_retention', 0)
    monthly_retention = retention.get('monthly_retention', 0)
    print(daily_retention)
    print(monthly_retention)


def print_config(config):
    for section in config.sections():
        print(f"[{section}]")
        for key, value in config[section].items():
            print(f"{key} = {value}")
        print()

def read_config(section_name):
    config_file_path = os.path.join(get_script_directory(), 'config.ini')
    print(f"Config file path: {config_file_path}")
    if not file_exists(config_file_path):
        logging.critical(f"Error: Config file does not exist at {config_file_path}")
        return None
    try:
        config = configparser.ConfigParser()
        config.read(config_file_path)
        if section_name not in config:
            logging.error(f"Error: Section '{section_name}' not found in config file.")
            return None

        section_data = dict(config[section_name])
        return section_data
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
        return None

if __name__ == "__main__":
    main()
