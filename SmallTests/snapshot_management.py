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
from vm_process import VM, VMAction, SnapshotAction, configure_logging, read_config, execute_subprocess_command

def main():
    """
    Main function to orchestrate backup and cleanup operations.
    """
    configure_logging("vmmaintenance")
    paths = read_config("Paths")
    os.chdir(paths['virtual_box_path'])
    vm_name = "Windows11 Clone"

    create_snapshot(vm_name)

def create_snapshot(vm_name):
    """
    Creates a snapshot for the specified virtual machine.

    Parameters:
        vm_name (str): The name of the virtual machine.

    Returns:
        None
    """
    current_date = datetime.datetime.now()
    new_snapshot_name = f"Snapshot-{current_date.strftime('%d%m%y')}"

    try:
        print(snapshot_exists(vm_name, new_snapshot_name))
        print(list_snapshots(vm_name))
        if snapshot_exists(vm_name, new_snapshot_name):
            logging.info(f"Snapshot '{new_snapshot_name}' already existed for {vm_name}.")
        else:
            logging.info(f"Snapshot '{new_snapshot_name}' didn't exist, so taking one for {new_snapshot_name} for {vm_name}.") 
            manage_snapshot(vm_name, new_snapshot_name, SnapshotAction.TAKE)
        snapshot_retention_management(vm_name)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred while creating snapshot for {vm_name}: {e}")

def snapshot_exists(vm_name, snapshot_name):
    """
    Checks if a snapshot with the given name exists for the specified virtual machine.

    Parameters:
        vm_name (str): The name of the virtual machine.
        snapshot_name (str): The name of the snapshot to check for.

    Returns:
        bool: True if the snapshot exists, False otherwise.
    """
    try:
        snapshot_names = list_snapshots(vm_name)
        return snapshot_name in snapshot_names
    except subprocess.CalledProcessError as e:
        logging.critical(f"Error: {e}")
        return False

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
    for line in lines:
        match = re.search(r'SnapshotName="([^"]+)"', line)
        if match:
            snapshot_lines.append(match.group(1))
    return snapshot_lines

def take_snapshot(vm_name, snapshot_name):
    command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.TAKE.value, snapshot_name]
    log_message = f"Taking snapshot '{snapshot_name}' for {vm_name}..."
    execute_subprocess_command(command, log_message)

def delete_snapshot(vm_name, snapshot_name):
    command = [VM.VBOX_MANAGE.value, "snapshot", vm_name, SnapshotAction.DELETE.value, snapshot_name]
    log_message = f"Deleting snapshot '{snapshot_name}' for {vm_name}..."
    execute_subprocess_command(command, log_message)

def snapshot_retention_management(vm_name):
    """
    Manages snapshot retention for the specified virtual machine.

    This function retrieves a list of snapshot names for the specified virtual machine
    and checks their ages. If a snapshot's age exceeds the daily retention period
    specified in the configuration, it is deleted.

    Parameters:
        vm_name (str): The name of the virtual machine.

    Returns:
        None
    """
    try:
        logging.info(f"Managing {vm_name} Snapshots retention...")
        
        # Retrieve list of snapshot names for the VM
        snapshot_names = list_snapshots(vm_name)
        
        if snapshot_names:
            current_date = datetime.datetime.now()
            for snapshot_name in snapshot_names:
                # Extract date from snapshot name using regular expression
                match = re.search(r'Snapshot-\d{6}', snapshot_name)
                if match:
                    snapshot_date_str = match.group().split('-')[1]
                    try:
                        snapshot_date = datetime.datetime.strptime(snapshot_date_str, '%d%m%y')
                        days_difference = (current_date - snapshot_date).days
                        logging.info(f"Snapshot: {snapshot_name}, Age: {days_difference} days")
                        
                        # Check if snapshot age exceeds daily retention period
                        if days_difference > int(read_config("SnapshotDetails")['daily_retention']):
                            # Delete the snapshot
                            manage_snapshot(vm_name, snapshot_name, SnapshotAction.DELETE)
                            logging.info(f"Deleted snapshot: {snapshot_name}")
                            
                    except ValueError:
                        logging.critical(f"Issue parsing date from Snapshot name: {snapshot_name}")
                        continue
        
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