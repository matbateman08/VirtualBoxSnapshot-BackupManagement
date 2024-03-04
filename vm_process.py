import subprocess
import shutil
import os
import re
import configparser
import logging
import string
import datetime
import smtplib
from enum import Enum
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class VM(Enum):
    VBOX_MANAGE = "VBoxManage"

class VMAction(Enum):
    POWER_OFF = "poweroff"
    START_HEADLESS = "headless"
    SHOW_STATE = "showvminfo"

class SnapshotAction(Enum):
    LIST = "list"
    TAKE = "take"
    DELETE = "delete"
    SNAPSHOT_PATTERN = r'Snapshot-\d{6}'

def main():
    log_file_path = configure_logging("vmmaintenance")
    generate_config_from_script()
    setup_environment_variables()
    try:
        if is_execution_day():
            Paths = read_config("Paths")
            disconnect_all_active_connections(Paths['nas_path'])
            network_drive = map_network_drive(Paths['nas_path'])
            daily_backup_paths, monthly_backup_paths = get_backup_paths(Paths, network_drive)
            os.chdir(Paths['virtual_box_path'])
            configure_logging("vmmaintenance")
            VMDetails = read_config("VMDetails")
            vm_names_section = VMDetails['vm_names']
            for vm_name in vm_names_section.split(','):
                vm_name = vm_name.strip()
                logging.info(f"Processing VM: '{vm_name}'")
                manage_vm_action(vm_name, VMAction.POWER_OFF)
                create_snapshot(vm_name)
                export_vm(vm_name, daily_backup_paths['DAILY_LOCAL'])
                manage_snapshot_retention(vm_name)
                manage_vm_action(vm_name, VMAction.START_HEADLESS)
            file_management(Paths, daily_backup_paths, monthly_backup_paths)
            disconnect_all_active_connections(Paths['nas_path'])
            send_log_email(log_file_path) 
        else:
            logging.info("Not running the script today.")       
    except Exception as e:
        logging.critical(f"Error encountered: {e}")

####### execute_subprocess_command
def execute_subprocess_command(command, log_message):
    """
    Execute a subprocess command.

    Parameters:
        command (list): List containing the command and its arguments.
        log_message (str): Message to log before executing the command.

    Returns:
        CompletedProcess: An object representing the completed process.

    Raises:
        subprocess.CalledProcessError: If the subprocess exits with a non-zero return code.
    """
    try:
        logging.info(log_message)
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logging.info(f"{log_message} completed successfully.")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"{log_message} failed with return code {e.returncode}.")
        raise
    except Exception as e:
        logging.exception(f"An error occurred during execution: {e}")
        raise

####### These two functions are used across setup_environment_variables and generate_log_file_path
def get_script():
    """
    Get the absolute path of the current script.

    Returns:
        str: The absolute path of the current script.
    """
    return os.path.abspath(__file__) 

def get_script_directory():
    """
    Get the directory of the current script.

    Returns:
        str: The directory path of the current script.
    """
    return os.path.dirname(os.path.abspath(__file__))

def create_directories(directory):
    """
    Create directories if they don't exist.

    Args:
        directory (str): The directory path to be created.
    """
    os.makedirs(directory, exist_ok=True)

def file_exists(file):
    """
    Check if a file exists in the script directory.

    Args:
        file (str): The name of the file to check.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    script_dir = get_script_directory()
    file_path = os.path.join(script_dir, file)
    return os.path.exists(file_path)

####### Setup_environment_variables & Helper Functions 
def find_used_env_vars(script_content):
    """
    Find used environment variables in the script content.

    Args:
        script_content (str): The content of the script.

    Returns:
        set: A set containing the names of environment variables used in the script.
    """
    return set(re.findall(r"os\.getenv\(['\"]([^'\"]+)['\"]\)", script_content))

def get_env_values(used_env_vars):
    """
    Prompt the user to provide values for the given environment variables.

    Args:
        used_env_vars (set): A set containing the names of environment variables.

    Returns:
        dict: A dictionary containing environment variable names as keys and their corresponding values.
    """
    env_values = {}
    logging.info("Please provide values for the following environment variables:")
    for env_var in used_env_vars:
        value = input(f"{env_var}: ")
        env_values[env_var] = value if not re.search(r"[^\w\-]", value) else f"'{value}'"
    return env_values

def write_env_file(env_file, env_values):
    """
    Write environment variables and their values to a file.

    Args:
        env_file (str): The path to the environment file.
        env_values (dict): A dictionary containing environment variable names and their values.

    Returns:
        bool: True if writing to the file was successful, False otherwise.
    """
    try:
        with open(env_file, 'w') as f:
            for env_var, value in env_values.items():
                f.write(f"{env_var}={value}\n")
        return True
    except Exception as e:
        logging.error(f"Error writing to {env_file}: {e}")
        return False
    
def setup_environment_variables():
    """
    Setup environment variables based on the script content.

    This function checks for the existence of a .env file. If found, it outputs a message saying it exists.
    If not found, it prompts the user to provide values for environment variables used in the script content,
    then creates a .env file.
    """
    env_file = '.env'
    if file_exists(env_file):
        logging.info(f"The .env file '{env_file}' already exists. Skipping user input and file writing.")
    else:
        logging.info("No .env file found. Let's set it up.")
        script_path = get_script()
        with open(script_path, 'r') as script_file:
            script_content = script_file.read()
        used_env_vars = find_used_env_vars(script_content)
        env_values = get_env_values(used_env_vars)
        success = write_env_file(env_file, env_values)
        if success:
            logging.info(f".env file created successfully at {env_file}")
        else:
            logging.error("Failed to create .env file.")

####### Generate_Config_from_Script & Helper Functions 
def parse_config_from_script(script_path):
    """
    Parse configuration settings from a script.

    Args:
        script_path (str): The path to the script containing configuration settings.

    Returns:
        dict: A dictionary containing parsed configuration settings.
    """
    try:
        script = get_script()
        with open(script, 'r') as file:
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
    except Exception as e:
        logging.error(f"Error occurred while parsing script: {e}")
        return {}

def format_section_paths(section_paths):
    """
    Format parsed section paths.

    Args:
        section_paths (dict): Parsed section paths.

    Returns:
        dict: Formatted section paths.
    """
    formatted_output = {}
    for key, value in section_paths.items():
        prefix = key.split("['")[0]
        if prefix not in formatted_output:
            formatted_output[prefix] = {}
        location_key = key.split("['")[-1][:-2]
        formatted_output[prefix][location_key] = value
    return formatted_output

def get_user_input(formatted_output):
    """
    Get user input for configuration settings.

    Args:
        formatted_output (dict): Formatted section paths.

    Returns:
        configparser.ConfigParser or None: Configuration settings obtained from user input.
    """
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        for prefix, items in formatted_output.items():
            config[prefix] = {}
            for key, value in items.items():
                input_location = input(f"Enter location for {key} (press enter to keep default value '{value}'): ")
                if input_location.strip():
                    items[key] = input_location
                config[prefix][key] = items[key]
        return config
    else:
        logging.info("Config file 'config.ini' already exists. Skipping user input and file writing.")
        return None

def write_config_to_file(config):
    """
    Write configuration settings to a file.

    Args:
        config (configparser.ConfigParser): Configuration settings to be written to file.
    """
    if config:
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

def generate_config_from_script():
    """
    Generate configuration settings from a script.
    """
    script_path = get_script_directory()
    section_paths = parse_config_from_script(script_path)
    formatted_output = format_section_paths(section_paths)
    config = get_user_input(formatted_output)
    write_config_to_file(config)

####### read_config & Helper Functions
def read_config_section(config, section_name):
    """
    Read a specific section from the configuration.

    Args:
        config (configparser.ConfigParser): Configuration object.
        section_name (str): Name of the section to read.

    Returns:
        dict or None: Contents of the specified section if found, else None.
    """
    if section_name not in config:
        logging.critical(f"Error: Section {section_name} does not exist in the config file")
        return None
    return config[section_name]

def read_config(section_name):
    """
    Read configuration settings from a file.

    Args:
        section_name (str): Name of the section to read from the config file.

    Returns:
        dict or None: Configuration settings from the specified section if found, else None.
    """
    config_file_path = os.path.join(get_script_directory(), 'config.ini')
    if not os.path.exists(config_file_path):
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

####### configure_logging & Helper Functions 
def generate_log_file_path(script_directory, logfile):
    """
    Generate the path for the log file.

    Args:
        script_directory (str): Path to the script directory.
        logfile (str): Name of the log file.

    Returns:
        str: Path to the log file.
    """
    today_date = datetime.date.today().strftime("%Y-%m-%d")
    logs_folder = os.path.join(script_directory, 'logs', logfile)
    create_directories(logs_folder)
    create_directories(logs_folder)
    return os.path.join(logs_folder, f'{today_date}_{logfile}.log')

def setup_logging(log_file_path):
    """
    Setup logging configuration.

    Args:
        log_file_path (str): Path to the log file.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s]: %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file_path)]
    )

def log_configuration_settings():
    """Log configuration settings."""
    logging.info(f"Log level: {logging.getLevelName(logging.getLogger().getEffectiveLevel())}")
    logging.info(f"Script File Path: {get_script_directory()}")

def configure_logging(logfile):
    """
    Configure logging.

    Args:
        logfile (str): Name of the log file.

    Returns:
        str: Path to the log file.
    """
    script_directory = get_script_directory()
    log_file_path = generate_log_file_path(script_directory, logfile)
    setup_logging(log_file_path)
    log_configuration_settings()
    return log_file_path

####### disconnect_all_active_connections & Helper functions
def disconnect_all_active_connections(remote_path):
    """
    Disconnect all active connections to a remote path.

    Args:
        remote_path (str): The remote path to disconnect active connections from.

    Returns:
        bool: True if disconnection was successful, False otherwise.
    """
    try:
        result = execute_subprocess_command(['net', 'use'], "Getting active connections")
        if result.returncode == 0:
            active_connections = parse_active_connections(result.stdout, remote_path)
            log_active_connections(remote_path, active_connections)
            disconnect_active_connections(active_connections)
            return True
        else:
            logging.info(f"Error getting active connections: {result.stderr}")
            return False

    except subprocess.CalledProcessError as e:
        logging.info(f"Error disconnecting active connections: {e}")
        return False

    except subprocess.TimeoutExpired:
        logging.info(f"Timeout occurred while disconnecting active connections for {remote_path}")
        return False

def parse_active_connections(output, remote_path):
    """
    Parse active connections from the output of 'net use' command.

    Args:
        output (str): Output of the 'net use' command.
        remote_path (str): The remote path to filter active connections.

    Returns:
        list: List of active connections matching the remote path.
    """
    return [line.split()[1] for line in output.splitlines() if line.strip() and remote_path in line and not line.strip().endswith('\\IPC$')]

def log_active_connections(remote_path, active_connections):
    """
    Log active connections.

    Args:
        remote_path (str): The remote path.
        active_connections (list): List of active connections.
    """
    if active_connections:
        for drive_letter in active_connections:
            logging.info(f"Active connection: Drive {drive_letter} connected to {remote_path} before disconnection")
    else:
        logging.info("No active connections found.")

def disconnect_active_connections(active_connections):
    """
    Disconnect active connections.

    Args:
        active_connections (list): List of active connections to disconnect.
    """
    for drive_letter in active_connections:
        execute_subprocess_command(['net', 'use', drive_letter, '/delete', '/yes'], f"Disconnecting drive {drive_letter}")

####### map_network_drive 
def map_network_drive(network_path):
    """
    Map a network drive.

    Args:
        network_path (str): The network path to map.

    Raises:
        Exception: If an error occurs during the process.
    """
    load_dotenv()
    username = os.getenv("NASUsername")
    password = os.getenv("NASPassword")
    try:
        # Construct the net use command to map the network drive
        drive_letter = find_available_drive_letter()
        drive_letter = drive_letter + ':'
        command = ['net', 'use', drive_letter, network_path, '/user:' + username, password]
        result = execute_subprocess_command(command, f"Mapping network drive {network_path} to {drive_letter}")
        # Check the return code
        if result.returncode == 0:
            logging.info(f"Network drive {network_path} successfully mapped to {drive_letter}.")
            return True
    except Exception as e:
        logging.info(f"ERROR Failed to map network drive {network_path} to {drive_letter}. Error: {e}")
        return False

####### find_available_drive_letter 
def find_available_drive_letter():
    """
    Find an available drive letter.

    Returns:
        str: Available drive letter.
    """
    try:
        net_use_output = execute_subprocess_command(['net', 'use'], "Finding available drive letters").stdout
        used_drive_letters = set()
        for line in net_use_output.split("\n")[2:]:
            drive_info = line.split()
            if len(drive_info) >= 2 and ':' in drive_info[1]:
                used_drive_letters.add(drive_info[1][0])
        for letter in reversed(string.ascii_uppercase):
            if letter not in used_drive_letters:
                logging.info(f"Drive Letter avaliable to be used: {letter}")
                return letter
        return None
    except Exception as e:
        logging.info(f"An error occurred while finding available drive letter. Exception: {e}")
        
####### is_execution_day & is_last_working_day_of_month functions with helper functions
def get_days_in_month():
    """
    Get the number of days in the month from the configuration.

    Returns:
        int or None: Number of days in the month if available, None otherwise.
    """
    Misc = read_config('Misc')
    days_in_month = Misc['days_in_month']
    if days_in_month is not None:
        return int(days_in_month)
    else:
        logging.error("Missing 'days_in_month' key in Misc config.")
        return None

def calculate_last_working_day_of_month():
    """
    Calculate the last working day of the month.

    Returns:
        datetime.date or None: Last working day of the month if available, None otherwise.
    """
    days_in_month = get_days_in_month()
    if days_in_month is not None:
        today = datetime.date.today()
        next_month = today.replace(day=days_in_month) + datetime.timedelta(days=4)  # Jump to end of next month
        return next_month - datetime.timedelta(days=next_month.day)  # Backtrack to last weekday
    else:
        return None

def is_last_working_day_of_month():
    """
    Check if today is the last working day of the month.

    Returns:
        bool or None: True if today is the last working day of the month, False if not, None if unable to determine.
    """
    try:
        last_working_day = calculate_last_working_day_of_month()
        if last_working_day:
            logging.info(f"Calculated last working day of the month: {last_working_day}")
            return datetime.date.today() == last_working_day
        else:
            return None
    except Exception as e:
        logging.error(f"An error occurred during date calculations: {e}")
        return None
    
def is_execution_day():
    """
    Check if today is an execution day based on configuration.

    Returns:
        bool or None: True if today is an execution day, False if not, None if unable to determine.
    """
    Misc = read_config('Misc')
    weekday_end = int(Misc['weekday_end'])
    if weekday_end is not None:
        current_day = datetime.datetime.now().weekday()
        return current_day < weekday_end
    return None

####### manage_vm_action & get_vm_state & helper functions
def manage_vm_action(vm_name, action):
    """
    Perform an action on a virtual machine.

    Args:
        vm_name (str): The name of the virtual machine.
        action (str): The action to perform on the virtual machine.

    Returns:
        bool: True if the action was successful, False otherwise.
    """
    try:
        vm_state = get_vm_state(vm_name)  # Get the current state of the VM

        # Check if the VM is already in the desired state
        if action == VMAction.POWER_OFF and vm_state == "powered off":
            logging.info(f"VM '{vm_name}' is already powered off.")
            return True

        if action == VMAction.START_HEADLESS and vm_state == "running":
            logging.info(f"VM '{vm_name}' is already running.")
            return True

        # If the VM is not in the desired state, proceed to execute the command
        if action == VMAction.POWER_OFF:
            command, log_message = build_command_and_log_message(vm_name, action)
            execute_subprocess_command(command, log_message)
            return True

        if action == VMAction.START_HEADLESS:
            command, log_message = build_command_and_log_message(vm_name, action)
            execute_subprocess_command(command, log_message)
            return True

        # Handle unsupported actions
        logging.error(f"Unsupported action: {action}")
        return False
    
    except subprocess.CalledProcessError as e:
        if "returned non-zero exit status 1" in str(e):
            vm_state = get_vm_state(vm_name)
            logging.info(f"VM '{vm_name}' Current state: {vm_state}")
        elif "VBOX_E_INVALID_OBJECT_STATE" in e.stderr:
            vm_state = get_vm_state(vm_name)
            logging.info(f"VM '{vm_name}' Current state: {vm_state}")
        else:
            logging.info(f"Failed to start/stop VM '{vm_name}'.")
            logging.info(f"Error: {e.stderr}")
        return False

def build_command_and_log_message(vm_name, action=None):
    """
    Build command and log message for managing VM action.

    Args:
        vm_name (str): The name of the virtual machine.
        action (str): The action to perform on the virtual machine.

    Returns:
        tuple: A tuple containing the command and log message.
    """
    if action == VMAction.POWER_OFF:
        command = [VM.VBOX_MANAGE.value, "controlvm", vm_name, "poweroff"]
        log_message = f"Powering off {vm_name}..."
    elif action == VMAction.START_HEADLESS:
        command = [VM.VBOX_MANAGE.value, "startvm", vm_name, '--type', 'headless']
        log_message = f"Powering On {vm_name} in headless mode..."
    elif action == VMAction.SHOW_STATE:
        command = [VM.VBOX_MANAGE.value, "showvminfo", vm_name, "--machinereadable"]
        log_message = f"Getting state of VM '{vm_name}'..."
    else:
        handle_invalid_action(action)
    return command, log_message

def handle_invalid_action(action):
    """
    Handle invalid action.

    Args:
        action (str): The invalid action.

    Raises:
        ValueError: If the action is invalid.
    """
    logging.critical(f"Error: Invalid action '{action}'. Supported actions are 'power_off' and 'start_headless'.")
    raise ValueError("Invalid action")

def get_vm_state(vm_name):
    """
    Get the state of a virtual machine.

    Args:
        vm_name (str): The name of the virtual machine.

    Returns:
        str: The state of the virtual machine.
    """
    try:
        command, log_message = build_command_and_log_message(vm_name, VMAction.SHOW_STATE)
        result = execute_subprocess_command(command, log_message)  
        if result:
            vm_state = extract_vm_state(result.stdout)
            return vm_state
        else:
            logging.error(f"Error while getting state of VM '{vm_name}': {result.stdout}")
            return "VM State: Unknown"
    except Exception as e:
        logging.error(f"Error while getting state of VM '{vm_name}': {e}")
        return "Error: Unknown"

def extract_vm_state(stdout):
    """
    Extract the state of a virtual machine from the command output.

    Args:
        stdout (str): The command output.

    Returns:
        str: The state of the virtual machine.
    """
    vm_state_lines = stdout.splitlines()
    for line in vm_state_lines:
        if line.startswith("VMState="):
            return line.split("=")[1].strip('"')
    return "VMState: Could not be found"

########## Get backup paths
def get_backup_paths(Paths, network_drive):
    """
    Parses backup paths from paths data and creates directories if they don't exist.

    Returns:
        tuple: A tuple containing dictionaries for daily backup paths and monthly backup paths.
    """
    daily_backup_paths = {
        'DAILY_LOCAL': Paths.get('source_daily_backup_path', ''),
        'DAILY_OFFICE365': Paths.get('office365_daily_path', ''),
        'DAILY_NAS': Paths.get('nas_daily_path', '') 
    }

    monthly_backup_paths = {
        'MONTHLY_LOCAL': Paths.get('source_monthly_backup_path', ''),
        'MONTHLY_OFFICE365': Paths.get('office365_monthly_path', ''),
        'MONTHLY_NAS': Paths.get('nas_monthly_path', '') 
    }

    if not network_drive:  # Assuming network_drive is the result of map_network_drive
        # Remove NAS paths if network drive mapping failed
        daily_backup_paths.pop('DAILY_NAS', None)
        monthly_backup_paths.pop('MONTHLY_NAS', None)

    for path in daily_backup_paths.values():
        create_directories(path)
    
    for path in monthly_backup_paths.values():
        create_directories(path)

    return daily_backup_paths, monthly_backup_paths

########## Export VM
def export_vm(vm_name, daily_backup_path):
    """
    Export a Virtual Machine to the specified daily backup path.

    Parameters:
        vm_name (str): Name of the Virtual Machine to export.
        daily_backup_path (str): Path to the daily backup destination.
    """
    try:
        logging.info(f"Initiating backup for VM '{vm_name}'.")
        base_filename = f"{vm_name}_{datetime.date.today().strftime('%Y-%m-%d')}"
        daily_output_path = os.path.join(daily_backup_path, f"{base_filename}.ova")
        daily_export_command = [VM.VBOX_MANAGE.value, "export", vm_name, f"--output={daily_output_path}", "--ovf20", "--options", "manifest", "--options", "nomacs"]
        execute_subprocess_command(daily_export_command, f"Backing up VM '{vm_name}' to '{daily_output_path}'.")
        logging.info("Export process completed.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing command: {e}")
        return False

########## Copying files based on dates
def copy_backups_based_on_date(is_last_day, Paths):
    """
    Copy backups based on the date condition.

    Parameters:
        is_last_day (bool): Whether it's the last day of the month.
        Paths (dict): Dictionary containing source and destination paths.
            Example:
                {
                    'source_daily_backup_path': str,
                    'office365_daily_path': str,
                    'nas_daily_path': str,
                    'source_monthly_backup_path': str,
                    'office365_monthly_path': str,
                    'nas_monthly_path': str
                }
            where:
                - 'source_daily_backup_path': Source path for daily backup.
                - 'office365_daily_path': Destination path for daily backup (Office 365).
                - 'nas_daily_path': Destination path for daily backup (NAS).
                - 'source_monthly_backup_path': Source path for monthly backup.
                - 'office365_monthly_path': Destination path for monthly backup (Office 365).
                - 'nas_monthly_path': Destination path for monthly backup (NAS).
    """
    folder_copy_subprocess(Paths['source_daily_backup_path'], Paths['office365_daily_path'])
    folder_copy_subprocess(Paths['source_daily_backup_path'], Paths['nas_daily_path'])
    folder_copy_subprocess(Paths['vm_management_source_path'], Paths['nas_misc_path'])
    folder_copy_subprocess(Paths['vm_management_source_path'], Paths['office365_misc_path'])

    if is_last_day:
        copy_last_day_of_month(list_snapshot_files(Paths['source_daily_backup_path']), Paths['source_monthly_backup_path'])
        folder_copy_subprocess(Paths['source_monthly_backup_path'], Paths['office365_monthly_path'])
        folder_copy_subprocess(Paths['source_monthly_backup_path'], Paths['nas_monthly_path'])

def copy_backups(source_path, paths):
    """
    Copy backups from source path to destination paths.

    Parameters:
        source_path (str): Source path for backup.
        paths (dict): Dictionary containing destination paths for different backup types.
    """
    if isinstance(paths, str):  # If paths is a string, convert it into a dictionary with a single entry
        paths = {'default': paths}

    for destination_key, destination_value in paths.items():
        if source_path == destination_value:
            logging.info(f"Source path {source_path} is the same as destination path {destination_value}. Skipping copying.")
            continue
        file_copy(source_path, destination_value)
        logging.info(f"Files copied from {source_path} to {destination_value}.")
 
def file_copy(source_path, destination_path):
    """
    Copy files from source_path to destination_path.

    Parameters:
        source_path (str): Path to the source directory.
        destination_path (str): Path to the destination directory.
    """
    try:
        files = os.listdir(source_path)
        for file in files:
            source_file = os.path.join(source_path, file)
            destination_file = os.path.join(destination_path, file)
            shutil.copy(source_file, destination_file)
        logging.info(f"Files copied from {source_path} to {destination_path}.")
    except FileNotFoundError:
        logging.error(f"Source directory {source_path} not found.")
    except PermissionError:
        logging.error(f"Permission denied while copying files from {source_path}. Check permissions.")
    except Exception as e:
        logging.error(f"Error copying files: {e}")

def folder_copy(src, dest):
    """
    Copy the entire contents of a folder from the source path to the destination path.

    Parameters:
        src (str): The path to the source folder to be copied.
        dest (str): The path to the destination folder where the contents will be copied.

    Returns:
        None

    Raises:
        shutil.Error: If an error occurs during the copying process.
        Exception: For unexpected errors during the copying process.

    Note:
        This function uses shutil.copytree() to copy the entire folder tree from
        the source to the destination. If the destination folder already exists,
        its contents will be merged with the contents of the source folder.

    Example:
        copy_folder('/path/to/source_folder', '/path/to/destination_folder')
    """
    try:
        shutil.copytree(src, dest, dirs_exist_ok=True)
        logging.info(f"Folder '{src}' copied to '{dest}' successfully.")
    except shutil.Error as e:
        logging.error(f"Folder '{src}' could not be copied. Error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

def folder_copy_subprocess(src, dest):
    """
    Copy the entire contents of a folder from the source path to the destination path using xcopy via subprocess.

    Parameters:
        src (str): The path to the source directory to be copied.
        dest (str): The path to the destination directory where the contents will be copied.

    Returns:
        None

    Raises:
        Exception: For unexpected errors during the copying process.

    Note:
        This function uses the xcopy command via subprocess to copy the entire folder tree from
        the source to the destination. If the destination folder does not exist, it will be created.

    Example:
        Copy the contents of '/path/to/source_folder' to '/path/to/destination_folder':
        >>> xcopy_copy_folder('/path/to/source_folder', '/path/to/destination_folder')
    """
    try:
        # List files in the source directory
        src_files = os.listdir(src)
        
        # Print each file being copied
        for file in src_files:
            logging.info(f"Copying {file} from: {src} to Destination: {dest}...")
        command = ['xcopy', src, dest, '/E', '/I', '/Y']
        log_message = f"Copying from: {src} Destination: {dest}..."
        execute_subprocess_command(command, log_message)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

def file_management(Paths,daily_backup_paths, monthly_backup_paths):
    """
    This function performs file management tasks including creating directories,
    copying backups based on date, and performing cleanup operations.

    Args:
        Paths (dict): A dictionary containing various file paths used by the program.
            * Paths['nas_misc_path']: Path to the NAS miscellaneous directory.
            * Paths['office365_misc_path']: Path to the Office 365 miscellaneous directory.
            * (Other paths can be added to the Paths dictionary as needed)
        daily_backup_paths (list): A list containing paths to directories that require daily backups.
        monthly_backup_paths (list): A list containing paths to directories that require monthly backups.

    Returns:
        None
    """
    try:
        create_directories(Paths['nas_misc_path'])
        create_directories(Paths['office365_misc_path'])
        copy_backups_based_on_date(is_last_working_day_of_month(), Paths)
        daily_backup_paths.update({'logs_nas': Paths['logs_nas'],'logs_office365': Paths['logs_office365'],'logs_location': Paths['logs_location']})
        daily_backup_paths.pop('DAILY_NAS', None)
        monthly_backup_paths.pop('MONTHLY_NAS', None)
        perform_cleanup_operations(is_last_working_day_of_month(), daily_backup_paths, monthly_backup_paths)
    except Exception as e:
        logging.error(f"An unexpected error occurred:{e}")

########### File cleanup & helper functions
def perform_cleanup_operations(is_last_day, daily_paths, monthly_paths):
    """
    Perform cleanup operations based on the date condition.

    Parameters:
        is_last_day (bool): Whether it's the last day of the month.
        source_path (str): Source path for cleanup.
        daily_paths (dict): Dictionary containing daily destination paths.
        monthly_paths (dict): Dictionary containing monthly destination paths.
    """
    retention = read_config("BackupDetails")
    if not is_last_day:  
        cleanup_files_in_paths(daily_paths, int(retention.get('daily_retention', 0)))
    else:
        cleanup_files_in_paths(daily_paths, int(retention.get('daily_retention', 0)))
        cleanup_files_in_paths(monthly_paths, int(retention.get('monthly_retention', 0)))

def cleanup_files_in_paths(paths, max_age_days):
    """
    Cleanup files in specified paths older than the given maximum age.

    Parameters:
        paths (dict): Dictionary containing paths for cleanup.
        max_age_days (int): Maximum age (in days) of files to retain.
    """
    try:
        for destination_path in paths.values():
            logging.info(f"Cleaning up files in '{destination_path}' older than {max_age_days} days.")
            for root, dirs, files in os.walk(destination_path):
                logging.info(f"Entered subdirectory: {root}")  # Log change to subdirectory
                for file_name in files:
                    try:
                        cleanup_file_path = file_path(root, file_name)
                        cleanup_file_age = file_age(cleanup_file_path, file_name, max_age_days)
                        if cleanup_file_age.days >= max_age_days:
                            file_remove(cleanup_file_path, file_name)
                    except Exception as e:
                        logging.error(f"An error occurred while processing file '{file_name}': {str(e)}")
        logging.info("Finished cleaning up subdirectories in: " + destination_path)
    except Exception as e:
        logging.error(f"An error occurred during file cleanup: {str(e)}")

def file_path(root, file_name):
    """
    Concatenate root directory and file name to get the full file path.

    Parameters:
        root (str): Root directory.
        file_name (str): File name.

    Returns:
        str: Full file path.
    """
    return os.path.join(root, file_name)

def file_age(file_path, filename, max_age_days):
    """
    Calculate the age of the file in days.

    Parameters:
        file_path (str): Path to the file.
        filename (str): Name of the file.
        max_age_days (int): Maximum allowed age of the file in days.

    Returns:
        datetime.timedelta: Age of the file.
    """
    file_mtime = datetime.date.fromtimestamp(os.path.getmtime(file_path))
    file_age = datetime.date.today() - file_mtime
    remaining_days = max_age_days - file_age.days
    logging.info(f"Checking file '{filename}' with age {file_age.days} days. Days Remaining: {remaining_days}")
    return file_age

def file_remove(file_path, file_name):
    """
    Remove the specified file.

    Parameters:
        file_path (str): Path to the file.
        file_name (str): Name of the file.
    """
    os.remove(file_path)
    logging.info(f"Deleted file '{file_name}'.")

def get_date_from_filename(filename):
    """
    Extract the date from the filename.

    Args:
        filename (str): The filename from which to extract the date.

    Returns:
        datetime: The extracted date as a datetime object.
    """
    return datetime.strptime(filename.split('-')[-1], '%d%m%y')

def list_snapshot_files(backup_directory):
    """
    List and filter snapshot files in the given directory.

    Args:
        backup_directory (str): The directory containing backup files.

    Returns:
        list: List of snapshot file paths.
    """
    # List all files in the directory
    files = [os.path.join(backup_directory, f) for f in os.listdir(backup_directory) if os.path.isfile(os.path.join(backup_directory, f))]
    # Filter files to match the format "Snapshot-DDMMYY"
    files = [f for f in files if f.startswith("Snapshot-")]
    return files

def copy_last_day_of_month(files, destination_folder):
    """
    Copy the last day of the month file from each month to the destination folder.

    Args:
        files (list): List of filenames to process.
        destination_folder (str): The folder where the last day of the month files will be copied.
    """
    # Group files by month
    files_by_month = {}
    for file in files:
        month_year = file.split('-')[-1][:4]
        if month_year not in files_by_month:
            files_by_month[month_year] = []
        files_by_month[month_year].append(file)

    # Copy last day of the month file to destination folder
    for month_files in files_by_month.values():
        month_files.sort(key=get_date_from_filename)
        last_file = month_files[-1]
        shutil.copy(last_file, destination_folder)
        print(f"Copied {last_file} to {destination_folder}")


############## Function that gets the log contents, loads it into an email and then sends the email
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

        subject = f"Log file for {datetime.date.today().strftime('%Y-%m-%d')}"

        log_content = get_log_content(log_file_path)
        if log_content is not None:
            send_email(subject, from_email, to_email, log_content, smtp_server, smtp_port, smtp_username, smtp_password)
    
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

############## Snapshot Management 
def create_snapshot(vm_name):
    """
    Creates a snapshot for the specified virtual machine.

    Parameters:
        vm_name (str): The name of the virtual machine.

    Returns:
        None
    """
    new_snapshot_name = get_snapshot_name()
    try:
        if snapshot_exists(vm_name, new_snapshot_name):
            logging.info(f"Snapshot '{new_snapshot_name}' already existed for {vm_name}.")
        else:
            manage_snapshot(vm_name, new_snapshot_name, SnapshotAction.TAKE)
    except subprocess.CalledProcessError as e:
        logging.info(f"No snapshots found for {vm_name}. Creating Snapshot 0.")
        manage_snapshot(vm_name, "Snapshot 0", SnapshotAction.TAKE)

def snapshot_exists(vm_name, snapshot_name):
    """
    Checks if a snapshot with the given name exists for the specified virtual machine.

    Parameters:
        vm_name (str): The name of the virtual machine.
        snapshot_name (str): The name of the snapshot to check for.

    Returns:
        bool: True if the snapshot exists, False otherwise.
    """

    snapshot_names = list_snapshots(vm_name)
    return snapshot_name in snapshot_names

def manage_snapshot(vm_name, snapshot_name, action):
    """
    Manages snapshots for the specified virtual machine.

    Parameters:
        vm_name (str): The name of the virtual machine.
        snapshot_name (str): The name of the snapshot (required for actions like TAKE or DELETE).
        action (SnapshotAction): The action to perform on the snapshot.

    Returns:
        str or None: If action is LIST, returns a string containing information about snapshots.
                     Otherwise, returns None.
    """
    try:
        if action == SnapshotAction.LIST:
            return list_snapshots(vm_name)
        elif action in (SnapshotAction.TAKE, SnapshotAction.DELETE):
            command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, action.value, snapshot_name]
            log_message = f"{action.value.capitalize()}ing snapshot '{snapshot_name}' for {vm_name}..."
            execute_subprocess_command(command, log_message)
        else:
            logging.critical(f"Unsupported action: {action}")
    except subprocess.CalledProcessError as e:
        logging.critical(f"Error during snapshot operation: {e}")
        
    return None

def list_snapshots(vm_name):
    """
    Retrieves a list of snapshot names for the specified virtual machine.

    Parameters:
        vm_name (str): The name of the virtual machine.

    Returns:
        list or None: A list containing names of snapshots if successful,
                      otherwise None.
    """
    command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.LIST.value, "--machinereadable"]
    log_message = f"Checking snapshots for {vm_name}..."
    result = execute_subprocess_command(command, log_message)
    lines = result.stdout.split('\n')
    snapshot_lines = []
    existing_snapshots = set()  # To keep track of existing snapshot names

    for line in lines:
        match = re.search(SnapshotAction.SNAPSHOT_PATTERN.value, line)
        if match:
            snapshot_name = match.group(0)
            # Check if the snapshot name is not already in the list
            if snapshot_name not in existing_snapshots:
                snapshot_lines.append(snapshot_name)
                existing_snapshots.add(snapshot_name)  # Add to the set to mark it as seen

    # Sort snapshot names based on their dates in descending order
    snapshot_lines = sorted(snapshot_lines, key=lambda x: x.split("-")[1], reverse=True)
    return snapshot_lines

def take_snapshot(vm_name, snapshot_name):
    command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.TAKE.value, snapshot_name]
    log_message = f"Taking snapshot '{snapshot_name}' for {vm_name}..."
    execute_subprocess_command(command, log_message)

def delete_snapshot(vm_name, snapshot_name):
    command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.DELETE.value, snapshot_name]
    log_message = f"Deleting snapshot '{snapshot_name}' for {vm_name}..."
    execute_subprocess_command(command, log_message)

def get_snapshot_date(snapshot_name):
    """
    Extracts date from snapshot name.

    Parameters:
        snapshot_name (str): Name of the snapshot.

    Returns:
        datetime.datetime: Date extracted from the snapshot name.
    """
    match = re.search(SnapshotAction.SNAPSHOT_PATTERN.value, snapshot_name)
    if match:
        snapshot_date_str = match.group().split('-')[1]
        try:
            return datetime.datetime.strptime(snapshot_date_str, '%d%m%y')
        except ValueError:
            logging.critical(f"Issue parsing date from Snapshot name: {snapshot_name}")
    return None

def get_snapshot_name():
    """
    Generates a name for a snapshot based on the current date and time.

    Returns:
        str: A string representing the snapshot name formatted as "Snapshot-DDMMYY".
    """
    current_date = datetime.datetime.now()
    new_snapshot_name = f"Snapshot-{current_date.strftime('%d%m%y')}"
    return new_snapshot_name

def manage_snapshot_retention(vm_name):
    """
    Manages snapshot retention for the specified virtual machine.

    Parameters:
        vm_name (str): The name of the virtual machine.
        snapshot_names (list): List of snapshot names for the VM.

    Returns:
        None
    """
    snapshot_names = list_snapshots(vm_name)
    try:
        logging.info(f"Managing {vm_name} Snapshots retention...")
        if snapshot_names:
            current_date = datetime.datetime.now()
            for snapshot_name in snapshot_names:
                snapshot_date = get_snapshot_date(snapshot_name)
                if snapshot_date:
                    days_difference = (current_date - snapshot_date).days
                    daily_retention = int(read_config("SnapshotDetails")['daily_retention'])
                    logging.info(f"Snapshot: {snapshot_name}, Current Age: {days_difference} days, Max Age {daily_retention} days, Days Remaining: {daily_retention - days_difference}")
                    if days_difference > daily_retention:
                        manage_snapshot(vm_name, snapshot_name, SnapshotAction.DELETE)
                        logging.info(f"Deleted snapshot: {snapshot_name}")
        logging.info(f"{vm_name}'s Snapshot retention management completed.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}")

def manage_snapshot(vm_name, snapshot_name, action):
    if action == SnapshotAction.LIST:
        return list_snapshots(vm_name)
    elif action == SnapshotAction.TAKE:
        take_snapshot(vm_name, snapshot_name)
    elif action == SnapshotAction.DELETE:
        delete_snapshot(vm_name, snapshot_name)
    else:
        logging.error(f"Unsupported action: {action}")

if __name__ == "__main__":
    main()