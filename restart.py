import subprocess
import os
import configparser
import logging
from enum import Enum

class VM(Enum):
    VBOX_MANAGE = "VBoxManage"

class VMAction(Enum):
    POWER_OFF = "poweroff"
    START_HEADLESS = "headless"

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

    logging.info(f"{section_name} Section:")
    for key, value in section.items():
        logging.info(f"  {key}: {value}")

    logging.info("")

    return section

def main():
    paths_section = read_config("Paths")
    vm_details = read_config("VMDetails")
    os.chdir(paths_section['virtual_box_path'])
    
    vm_names = vm_details.get('vm_names').split(', ')

    for vm_name in vm_names:
        manage_vm_power(vm_name, VMAction.POWER_OFF)

    restart_computer()

def execute_vbox_command(command, log_message):
    try:
        logging.info(log_message)
        subprocess.run(command, check=True)
        logging.info(f"{log_message} completed successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during {log_message}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during {log_message}: {e}")

def manage_vm_power(vm_name, action):
    try:
        if action == VMAction.POWER_OFF:
            command = [VM.VBOX_MANAGE.value, "controlvm", vm_name, VMAction.POWER_OFF.value]
            log_message = f"Powering off {vm_name}..."
        elif action == VMAction.START_HEADLESS:
            command = [VM.VBOX_MANAGE.value, "startvm", vm_name, "--type", VMAction.START_HEADLESS.value]
            log_message = f"Powering On {vm_name} in headless mode..."
        else:
            logging.critical(f"Error: Invalid action '{action}'. Supported actions are 'power_off' and 'start_headless'.")
            return

        execute_vbox_command(command, log_message)

    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            logging.error(f"Error: Virtual Machine '{vm_name}' is not currently running.")
        else:
            logging.critical(f"Error: {e}")

    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}")

def restart_computer():
    try:
        os.system("shutdown /r /t 0")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()