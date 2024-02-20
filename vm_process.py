import subprocess
import shutil
import os
import re
import configparser
import logging
import string
import datetime
import smtplib
import time
from enum import Enum
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

class VM(Enum):
    VBOX_MANAGE = "VBoxManage"

class VMAction(Enum):
    POWER_OFF = "poweroff"
    START_HEADLESS = "headless"

class SnapshotAction(Enum):
    LIST = "list"
    TAKE = "take"
    DELETE = "delete"
    SNAPSHOT_PATTERN = r'Snapshot-\d{6}'

class BackupType(Enum):
    DAILY_LOCAL = "daily_backup_path"
    MONTHLY_LOCAL = "monthly_backup_path"
    DAILY_OFFICE365 = "office365_daily_path"
    MONTHLY_OFFICE365 = "office365_monthly_path"
    DAILY_NAS = "nas_daily_path"
    MONTHLY_NAS = "nas_monthly_path"

def main():
    generate_config_from_script()
    setup_environment_variables()
    log_file_path = configure_logging()
    try:
        if is_execution_day():
            Paths = read_config("Paths")
            disconnect_all_active_connections(Paths['nas_path'])
            drive_letter = find_available_drive_letter()
            map_network_drive(Paths['nas_path'], drive_letter)
            os.chdir(Paths['virtual_box_path'])
            VMDetails = read_config("VMDetails")
            vm_names_section = VMDetails['vm_names']
            for vm_name in vm_names_section.split(','):
                manage_vm_power(vm_name, VMAction.POWER_OFF)
                create_snapshot(vm_name)
                backup_management(Paths, vm_name, "Create")
                manage_vm_power(vm_name, VMAction.START_HEADLESS)
            backup_management(Paths, vm_name, "Backup")                
            send_log_email(log_file_path)
            disconnect_all_active_connections(Paths['nas_path'])
        else:
            logging.info("Not running the script today.")
    except Exception as e:
        logging.critical(f"Error encountered: {e}")

def setup_environment_variables():
    env_file = '.env'
    if not os.path.exists(env_file):
        logging.info("No .env file found. Let's set it up.")
        used_env_vars = set()
        script_path = os.path.abspath(__file__)

        # Search the script for os.getenv() calls
        with open(script_path, 'r') as script_file:
            script_content = script_file.read()

            # Find all occurrences of os.getenv()
            env_vars_used_in_script = re.findall(r"os\.getenv\(['\"]([^'\"]+)['\"]\)", script_content)
            used_env_vars.update(env_vars_used_in_script)

        # Ask the user for values of the detected environment variables
        with open(env_file, 'w') as f:
            logging.info("Please provide values for the following environment variables:")
            for env_var in used_env_vars:
                value = input(f"{env_var}: ")
                # Encapsulate the value in single quotes if it contains special characters
                value_to_write = value if not re.search(r"[^\w\-]", value) else f"'{value}'"
                f.write(f"{env_var}={value_to_write}\n")

def generate_config_from_script():
    def parse_config_from_script():
        script_path = os.path.abspath(__file__)
        try:
            with open(script_path, 'r') as file:
                script_lines = file.readlines()
                section_paths = {}
                for line in script_lines:
                    matches = re.findall(r"([A-Z]\w+)\[['\"](.+?)['\"]\]", line)
                    for match in matches:
                        header, path = match
                        if header and path:
                            combined_key = header + "['" + path + "']"
                            section_paths[combined_key] = path
                return section_paths
        except FileNotFoundError:
            logging.info(f"File '{script_path}' not found.")
            return {}

    section_paths = parse_config_from_script()
    formatted_output = {}
    for key, value in section_paths.items():
        prefix = key.split("['")[0]
        if prefix not in formatted_output:
            formatted_output[prefix] = {}
        # Extracting the last part of the key for displaying
        location_key = key.split("['")[-1][:-2]
        formatted_output[prefix][location_key] = value

    config = configparser.ConfigParser()

    # Check if config file exists
    if not os.path.exists('config.ini'):
        for prefix, items in formatted_output.items():
            config[prefix] = {}  # Creating the section
            for key, value in items.items():
                input_location = input(f"Enter location for {key} (press enter to keep default value '{value}'): ")
                if input_location.strip():  # If user provided input
                    items[key] = input_location  # Use the input as the new value
                # Here you might want to add some validation or error handling for the user input
                config[prefix][key] = items[key]

        # Writing the config to a file
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
    else:
        logging.info("Config file 'config.ini' already exists. Skipping user input and file writing.")

def read_config(section_name):
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

    #logging.info(f"{section_name} Section:")
    #for key, value in section.items():
    #    logging.info(f"  {key}: {value}")

    #logging.info("")

    return section

def configure_logging():
    # Get the absolute path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Generate a log file path based on the current date
    today_date = datetime.date.today().strftime("%Y-%m-%d")
    logs_folder = os.path.join(script_directory, 'logs', 'vmmaintenancelogs')
    os.makedirs(logs_folder, exist_ok=True)
    log_file_path = os.path.join(logs_folder, f'{today_date}_vm_maintenance.log')

    # Configure logging first
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s]: %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file_path)]
    )

    # Log the configuration settings
    #logging.info("Logging configuration settings:")
    logging.info(f"Log level: {logging.getLevelName(logging.getLogger().getEffectiveLevel())}")

    #handlers = logging.getLogger().handlers
    #if handlers:
    #    logging.info("Handlers:")
    #    for handler in handlers:
    #        logging.info(f"- {handler}")
    #else:
    #    logging.info("No handlers configured.")

    # Now you can log additional messages
    logging.info(f"Script File Path: {script_directory}")
    logging.info(f"Log File Path: {log_file_path}")

    return log_file_path

def disconnect_all_active_connections(remote_path):
    try:
        # Get all active connections
        result = subprocess.run(['net', 'use'], capture_output=True, text=True)

        # Check the return code
        if result.returncode == 0:
            # Parse the output to get drive letters of active connections to the specified remote path
            active_connections = [line.split()[1] for line in result.stdout.splitlines() if line.strip() and remote_path in line and not line.strip().endswith('\\IPC$')]

            # Log information about all active connections
            if active_connections:
                for drive_letter in active_connections:
                    logging.info(f"Active connection: Drive {drive_letter} connected to {remote_path} before disconnection")
            else:
                logging.info("No active connections found.")

            # Disconnect each active connection
            for drive_letter in active_connections:
                disconnect_command = ['net', 'use', drive_letter, '/delete', '/yes']
                subprocess.run(disconnect_command, capture_output=True)
                logging.info(f"Disconnected drive {drive_letter}")

            return True  # Disconnected all active connections
        else:
            logging.info(f"Error getting active connections: {result.stderr}")
            return False  # An error occurred while getting active connections

    except subprocess.CalledProcessError as e:
        logging.info(f"Error disconnecting active connections: {e}")
        return False  # An exception occurred during the subprocess call

    except subprocess.TimeoutExpired:
        logging.info(f"Timeout occurred while disconnecting active connections for {remote_path}")
        return False  # Timeout occurred while disconnecting active connections

def map_network_drive(network_path, drive_letter):
    username = os.getenv("Username")
    password = os.getenv("Password")

    try:
            # Construct the net use command to map the network drive
            check_command = ['net', 'use', drive_letter + ':', network_path, '/user:' + username, password]

            # Run the net use command
            result = subprocess.run(check_command, capture_output=True, text=True)

            # Check the return code
            if result.returncode == 0:
                logging.info(f"Network drive {network_path} successfully mapped to {drive_letter}.")
            else:
                logging.info(f"Failed to map network drive {network_path} to {drive_letter}. Error: {result.stderr}")

    except Exception as e:
        logging.info(f"An error occurred while mapping network drive {network_path}. Exception: {e}")

def find_available_drive_letter():
    net_use_output = subprocess.run(['net', 'use'], capture_output=True, text=True).stdout
    #logging.info(f"Raw net use output:\n{net_use_output}")

    used_drive_letters = set()

    for line in net_use_output.split("\n")[2:]:
        drive_info = line.split()
        if len(drive_info) >= 2 and ':' in drive_info[1]:
            used_drive_letters.add(drive_info[1][0])

    for letter in reversed(string.ascii_uppercase):
        if letter not in used_drive_letters:
            return letter

    return None

def is_execution_day():
    Misc = read_config("Misc")
    executionday = int(Misc['weekday_end'])
    current_day = datetime.datetime.now().weekday()
    return current_day < executionday

def is_last_working_day_of_month():
    try:
        Misc = read_config("Misc")
        daysinmonth = int(Misc['days_in_month'])
        today = datetime.date.today()
        next_month = today.replace(day=daysinmonth) + datetime.timedelta(days=4)  # Jump to end of next month
        last_working_day = next_month - datetime.timedelta(days=next_month.day)  # Backtrack to last weekday

        logging.info(f"Today's date: {today}")
        logging.info(f"Next month's date: {next_month}")
        logging.info(f"Calculated last working day of the month: {last_working_day}")

        return today == last_working_day
    except Exception as e:
        logging.error(f"An error occurred during date calculations: {e}")
        return None

def execute_vbox_command(command, log_message):
    try:
        logging.info(log_message)
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logging.info(f"{log_message} completed successfully.")
        return result
    except Exception as e:
        raise  # Re-raise the exception to pass it back to the caller

def manage_vm_power(vm_name, action):
    try:
        if action == VMAction.POWER_OFF:
            command = [VM.VBOX_MANAGE.value, "controlvm", vm_name, VMAction.POWER_OFF.value]
            log_message = f"Powering off {vm_name}..."
        elif action == VMAction.START_HEADLESS:
            command = [VM.VBOX_MANAGE.value, 'startvm', vm_name, '--type', 'headless']
            log_message = f"Powering On {vm_name} in headless mode..."
        else:
            logging.critical(f"Error: Invalid action '{action}'. Supported actions are 'power_off' and 'start_headless'.")
            return

        execute_vbox_command(command, log_message)
    
    except subprocess.CalledProcessError as e:
        if "returned non-zero exit status 1" in str(e):
            logging.info(f"VM '{vm_name}' is already turned off.")
        elif "VBOX_E_INVALID_OBJECT_STATE" in e.stderr:
            logging.info(f"VM '{vm_name}' is already running.")
        else:
            logging.info(f"Failed to start/stop VM '{vm_name}'.")
            logging.info(f"Error: {e.stderr}")

def backup_management(Paths, vm_name, state):
    BackupDetails = read_config("BackupDetails")
    
    daily_retention = int(BackupDetails['daily_retention'])
    monthly_retention = int(BackupDetails['monthly_retention'])

    daily_backup_paths = {
        BackupType.DAILY_LOCAL: Paths['source_daily_backup_path'],
        BackupType.DAILY_OFFICE365: Paths['office365_daily_path'],
        BackupType.DAILY_NAS: Paths['nas_daily_path']
    }

    monthly_backup_paths = {
        BackupType.MONTHLY_LOCAL: Paths['source_monthly_backup_path'],
        BackupType.MONTHLY_OFFICE365: Paths['office365_monthly_path'],
        BackupType.MONTHLY_NAS: Paths['nas_monthly_path']
    }

    try:
        if state == "Create":
            logging.info("Create the backu")
            create_backup_directories(*daily_backup_paths.values())
            create_backup_directories(*monthly_backup_paths.values())

            logging.info(f"Backup Management - VM Name: {vm_name}")
            logging.info(f"Daily Retention: {daily_retention}")
            logging.info(f"Monthly Retention: {monthly_retention}")

            backup_vm(vm_name, daily_backup_paths[BackupType.DAILY_LOCAL])

        elif state == "Backup":
            logging.info("Copying Files to Office365 & NAS")
            for backup_type, backup_path in daily_backup_paths.items():
                if backup_type not in [BackupType.DAILY_LOCAL, BackupType.MONTHLY_LOCAL]:
                    copy_backups(Paths['source_daily_backup_path'], backup_path)

            if is_last_working_day_of_month():
                for backup_type, backup_path in monthly_backup_paths.items():
                    if backup_type not in [BackupType.DAILY_LOCAL, BackupType.MONTHLY_LOCAL]:
                        logging.info("It is the last day of the month, so copying this month's backup.")
                        copy_backups(Paths['source_daily_backup_path'], backup_path)

            for backup_type, backup_path in daily_backup_paths.items():
                cleanup_files(backup_path, daily_retention)

            if is_last_working_day_of_month():
                for backup_type, backup_path in monthly_backup_paths.items():
                    logging.info("It is the last day of the month, so performing the cleanup on the monthly backups.")
                    cleanup_files(backup_path, monthly_retention)

            log_location = Paths['logs_location']
            copy_vm_management(Paths)
            logging.info(f"Cleaning up: {log_location} with retention policy of: {daily_retention}")
            cleanup_files(log_location, daily_retention)

    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else e.output
        if "returned non-zero exit status 1." in error_message and "VM has already been exported" not in error_message:
            logging.info("The virtual machine has already been exported.")
    except Exception as e:
        logging.error(f"An error occurred during backup management: {e}")

def copy_backups(src_path, dest_path):
    logging.info(f"Creating and copying backups from '{src_path}' to '{dest_path}'.")
    try:
        for root, dirs, files in os.walk(src_path):
            for file in files:
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(dest_path, file)

                if not os.path.exists(dest_file_path):
                    shutil.copy2(src_file_path, dest_file_path)
                    logging.info(f"File '{file}' copied successfully.")
                else:
                    logging.warning(f"File '{file}' already exists in '{dest_path}', skipping.")

        logging.info(f"Backups copied successfully from '{src_path}' to '{dest_path}'.")
    except Exception as e:
        logging.error(f"Error copying backups: {e}")

def create_backup_directories(*paths):
    try:
        for path in paths:
            if not os.path.exists(path):
                os.makedirs(path)
                logging.info(f"Created directory: {path}")
    except Exception as e:
        logging.error(f"An error occurred during directory creation: {e}")

def backup_vm(vm_name, daily_backup_path, monthly_backup_path=None):
    try:
        logging.info(f"Initiating backup for VM '{vm_name}'.")
        base_filename = f"{vm_name}_{datetime.date.today().strftime('%Y-%m-%d')}"
        daily_output_path = os.path.join(daily_backup_path, f"{base_filename}.ova")

        daily_export_command = [VM.VBOX_MANAGE.value, "export", vm_name, f"--output={daily_output_path}", "--ovf20", "--options", "manifest", "--options", "nomacs"]

        execute_vbox_command(daily_export_command, f"Backing up VM '{vm_name}' to '{daily_output_path}'.")

        logging.info("Export process completed.")

    except Exception as e:
        raise

def cleanup_files(backup_path, max_age_days):
    try:
        logging.info(f"Cleaning up files in '{backup_path}' older than {max_age_days} days.")

        for root, dirs, files in os.walk(backup_path):
            for filename in files:
                try:
                    file_path = os.path.join(root, filename)
                    file_age = datetime.date.today() - datetime.date.fromtimestamp(os.path.getmtime(file_path))
                    logging.info(f"Checking file '{filename}' with age {file_age.days} days.")

                    if file_age.days >= max_age_days:
                        os.remove(file_path)
                        logging.info(f"Deleted file '{filename}'.")
                except Exception as e:
                    logging.error(f"An error occurred while processing file '{filename}': {str(e)}")

        logging.info("File cleanup process completed.")

    except Exception as e:
        logging.error(f"An error occurred during file cleanup: {str(e)}")

def create_snapshot(vm_name):
    current_date = datetime.datetime.now()
    new_snapshot_name = f"Snapshot-{current_date.strftime('%d%m%y')}"
    
    try:
        if not snapshot_exists(vm_name, new_snapshot_name):
            manage_snapshot(vm_name, new_snapshot_name, SnapshotAction.TAKE)
            snapshot_retention_management(vm_name)
        else:
            logging.info(f"Snapshot '{new_snapshot_name}' already exists for {vm_name}.")
    except:
        manage_snapshot(vm_name, new_snapshot_name, SnapshotAction.TAKE)
        logging.info(f"There is no Snapshot for {vm_name}. We've just created one.")

def snapshot_exists(vm_name, snapshot_name):
    try:
        result = manage_snapshot(vm_name, None, SnapshotAction.LIST)
        snapshot_lines = [line for line in result.split('\n') if re.search(f'"{snapshot_name}"', line)]
        logging.info(f"Was there a snapshot? {'Yes' if bool(snapshot_lines) else 'No'}")
        return bool(snapshot_lines)
    except subprocess.CalledProcessError as e:
        logging.critical(f"Error: {e}")
        return False
        
def snapshot_retention_management(vm_name):
    SnapshotDetails = read_config("SnapshotDetails")
    daily_retention = int(SnapshotDetails['daily_retention'])
    try:
        logging.info(f"Managing {vm_name} Snapshots retention...")
        snapshots_info = manage_snapshot(vm_name, None, SnapshotAction.LIST)
        if snapshots_info:
            lines = snapshots_info.split('\n')
            current_date = datetime.datetime.now()

            for line in lines:
                snapshot_name = re.search(SnapshotAction.SNAPSHOT_PATTERN.value, line)
                if snapshot_name:
                    snapshot_date_str = snapshot_name.group().split('-')[1]
                    try:
                        snapshot_date = datetime.datetime.strptime(snapshot_date_str, '%d%m%y')
                        days_difference = (current_date - snapshot_date).days
                        logging.info(f"Snapshot: {snapshot_name.group()}, Age: {days_difference} days")
                        if days_difference > daily_retention:
                            manage_snapshot(vm_name, snapshot_name.group(), SnapshotAction.DELETE)
                            logging.info(f"Deleted snapshot: {snapshot_name}")
                    except ValueError:
                        logging.critical(f"Issue parsing date from Snapshot name: {snapshot_name.group()}")
                        continue
        logging.info(f"{vm_name}'s Snapshot retention management completed.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}")
       
def manage_snapshot(vm_name, snapshot_name, action):
    try:
        if action == SnapshotAction.LIST:
            command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.LIST.value, "--machinereadable"]
            log_message = f"Checking snapshots for {vm_name}..."
            result = execute_vbox_command(command, log_message)
            lines = result.stdout.split('\n')
            snapshot_lines = [line for line in lines if re.search(SnapshotAction.SNAPSHOT_PATTERN.value, line)]
            return '\n'.join(snapshot_lines)
        elif action == SnapshotAction.TAKE:
            command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.TAKE.value, snapshot_name]
            log_message = f"Taking {vm_name} snapshot '{snapshot_name}'..."
            execute_vbox_command(command, log_message)
        elif action == SnapshotAction.DELETE:
            command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.DELETE.value, snapshot_name]
            log_message = f"Deleting snapshot '{snapshot_name}'..."
            execute_vbox_command(command, log_message)
        else:
            logging.critical(f"Unsupported action: {action}")
    except subprocess.CalledProcessError as e:
        logging.critical(f"Error during snapshot operation: {e}")

def copy_vm_management(Paths):
    try:
        source_path = Paths['vm_management_source_path']
        destination_nas_path = Paths['nas_misc_path']
        destination_office365_path = Paths['office365_misc_path']

        # Create backup directories
        create_backup_directories(destination_nas_path)
        create_backup_directories(destination_office365_path)

        # Copy the entire directory to NAS destination
        shutil.copytree(source_path, os.path.join(destination_nas_path, os.path.basename(source_path)))
        logging.info(f'Successfully copied {source_path} to NAS: {destination_nas_path}')

        # Copy the entire directory to Office 365 destination
        shutil.copytree(source_path, os.path.join(destination_office365_path, os.path.basename(source_path)))
        logging.info(f'Successfully copied {source_path} to Office 365: {destination_office365_path}')

    except FileNotFoundError:
        logging.error(f'Error: Source directory not found - {source_path}')
    except Exception as e:
        logging.error(f'Error: {e}')

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

        # Read the content of the log file
        try:
            with open(log_file_path, 'r') as log_file:
                log_content = log_file.read()
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

if __name__ == "__main__":
    main()