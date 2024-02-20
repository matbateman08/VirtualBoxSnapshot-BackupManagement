import subprocess
import logging
from enum import Enum


class VM(Enum):
    VBOX_MANAGE = "VBoxManage"

class VMAction(Enum):
    POWER_OFF = "poweroff"
    START_HEADLESS = "headless"

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
            return False

        execute_vbox_command(command, log_message)
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

def get_vm_state(vm_name):
    try:
        command = ["VBoxManage", "showvminfo", vm_name, "--machinereadable"]
        result = execute_vbox_command(command, f"Getting state of VM '{vm_name}'...")
        vm_state = result.stdout.splitlines()
        for line in vm_state:
            if line.startswith("VMState="):
                state = line.split("=")[1].strip('"')
                return state
    except Exception as e:
        logging.error(f"Error while getting state of VM '{vm_name}': {e}")
    return "UNKNOWN"

