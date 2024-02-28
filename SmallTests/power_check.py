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
from vm_process import configure_logging, generate_config_from_script, setup_environment_variables, is_execution_day, read_config, disconnect_all_active_connections, map_network_drive, get_backup_paths, VM, VMAction, execute_subprocess_command
load_dotenv()


def main():
    log_file_path = configure_logging("vmmaintenance")
    generate_config_from_script()
    setup_environment_variables()
    try:
        if is_execution_day():
            Paths = read_config("Paths")
            disconnect_all_active_connections(Paths['nas_path'])
            map_network_drive(Paths['nas_path'])
            os.chdir(Paths['virtual_box_path'])
            configure_logging("vmmaintenance")

            vm_names_section = "Windows11 Clone"
            for vm_name in vm_names_section.split(','):
                vm_name = vm_name.strip()
                logging.info(f"Processing VM: '{vm_name}'")
                #manage_vm_action(vm_name, VMAction.POWER_OFF)
                time.sleep(5)
                manage_vm_action(vm_name, VMAction.START_HEADLESS)
            disconnect_all_active_connections(Paths['nas_path'])
        else:
            logging.info("Not running the script today.")       
    except Exception as e:
        logging.critical(f"Error encountered: {e}")



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
        success = execute_subprocess_command(command, log_message)  # Capture both return values
        if success:
            vm_state = extract_vm_state(success.stdout)
            return vm_state
        else:
            logging.error(f"Error while getting state of VM '{vm_name}': {success.stdout}")
            return "UNKNOWN"
    except Exception as e:
        logging.error(f"Error while getting state of VM '{vm_name}': {e}")
        return "UNKNOWN"

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
    return "UNKNOWN"

if __name__ == "__main__":
    main()