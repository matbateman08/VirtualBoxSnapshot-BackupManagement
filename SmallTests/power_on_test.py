import subprocess
import time
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

load_dotenv()

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

class BackupType(Enum):
    DAILY_LOCAL = "daily_backup_path"
    MONTHLY_LOCAL = "monthly_backup_path"
    DAILY_OFFICE365 = "office365_daily_path"
    MONTHLY_OFFICE365 = "office365_monthly_path"
    DAILY_NAS = "nas_daily_path"
    MONTHLY_NAS = "nas_monthly_path"

def main():
    log_file_path = configure_logging("vmmaintenance")
    generate_config_from_script()
    setup_environment_variables()
    try:
        Paths = read_config("Paths")
        os.chdir(Paths['virtual_box_path'])
        configure_logging("vmmaintenance")
        VMDetails = read_config("VMDetails")
        vm_names_section = VMDetails['vm_names']
        for vm_name in vm_names_section.split(','):
            vm_name = vm_name.strip()
            manage_vm_action(vm_name, VMAction.POWER_OFF)
            time.sleep(10)
            manage_vm_action(vm_name, VMAction.START_HEADLESS)
        else:
            logging.info("Not running the script today.")      
    except Exception as e:
        logging.critical(f"Error encountered: {e}")

####### execute_subprocess_command
def execute_subprocess_command(command, log_message):
    try:
        logging.info(log_message)
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logging.info(f"{log_message} completed successfully.")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"{log_message} failed with return code {e.returncode}.")
        logging.error(f"Command output: {e.output}")
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
        logging.info(f"The .env file '{env_file}' already exists.")
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
    try:
        script_path = get_script()
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
    except Exception as e:
        logging.error(f"Error occurred while parsing script: {e}")
        return {}

def format_section_paths(section_paths):
    formatted_output = {}
    for key, value in section_paths.items():
        prefix = key.split("['")[0]
        if prefix not in formatted_output:
            formatted_output[prefix] = {}
        location_key = key.split("['")[-1][:-2]
        formatted_output[prefix][location_key] = value
    return formatted_output

def get_user_input(formatted_output):
    config = configparser.ConfigParser()
    if not file_exists('config.ini'):
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
    if config:
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

def generate_config_from_script():
    script_path = get_script_directory()
    section_paths = parse_config_from_script(script_path)
    formatted_output = format_section_paths(section_paths)
    config = get_user_input(formatted_output)
    write_config_to_file(config)

####### read_config & Helper Functions
def read_config_section(config, section_name):
    if section_name not in config:
        logging.critical(f"Error: Section {section_name} does not exist in the config file")
        return None
    return config[section_name]

def read_config(section_name):
    config_file_path = os.path.join(get_script_directory(), 'config.ini')

    if not file_exists(config_file_path):
        logging.critical(f"Error: Config file does not exist at {config_file_path}")
        return None
    try:
        config = configparser.ConfigParser()
        config.read(config_file_path)
        section_data = dict(config[section_name])
        return section_data
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
        return None

####### configure_logging & Helper Functions 
def generate_log_file_path(script_directory, logfile):
    today_date = datetime.date.today().strftime("%Y-%m-%d")
    logs_folder = os.path.join(script_directory, 'logs', logfile)
    create_directories(logs_folder)
    return os.path.join(logs_folder, f'{today_date}_{logfile}.log')

def setup_logging(log_file_path):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s]: %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file_path)]
    )

def log_configuration_settings():
    logging.info(f"Log level: {logging.getLevelName(logging.getLogger().getEffectiveLevel())}")
    logging.info(f"Script File Path: {get_script_directory()}")

def configure_logging(logfile):
    script_directory = get_script_directory()
    log_file_path = generate_log_file_path(script_directory, logfile)
    setup_logging(log_file_path)
    log_configuration_settings()
    return log_file_path

####### manage_vm_action & get_vm_state & helper functions
def manage_vm_action(vm_name, action):
    try:
        command, log_message = build_command_and_log_message(vm_name, action)
        execute_subprocess_command(command, log_message)
        return True
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
    logging.critical(f"Error: Invalid action '{action}'. Supported actions are 'power_off' and 'start_headless'.")
    raise ValueError("Invalid action")

def get_vm_state(vm_name):
    try:
        command, log_message = build_command_and_log_message(vm_name, VMAction.SHOW_STATE)
        success, result = execute_subprocess_command(command, log_message)  # Capture both return values
        if success:
            vm_state = extract_vm_state(result)
            return vm_state
        else:
            logging.error(f"Error while getting state of VM '{vm_name}': {result}")
            return "UNKNOWN"
    except Exception as e:
        logging.error(f"Error while getting state of VM '{vm_name}': {e}")
        return "UNKNOWN"

def extract_vm_state(stdout):
    vm_state_lines = stdout.splitlines()
    for line in vm_state_lines:
        if line.startswith("VMState="):
            return line.split("=")[1].strip('"')
    return "UNKNOWN"

if __name__ == "__main__":
    main()