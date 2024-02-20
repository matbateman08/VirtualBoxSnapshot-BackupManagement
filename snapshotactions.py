import re
import datetime
import logging
import subprocess
from enum import Enum
from config_and_env import read_config
from vboxcontrols import VM, execute_vbox_command

class SnapshotAction(Enum):
    LIST = "list"
    TAKE = "take"
    DELETE = "delete"
    SNAPSHOT_PATTERN = r'Snapshot-\d{6}'

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
