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

from vm_process import VM, read_config, create_directories, configure_logging, is_last_working_day_of_month, execute_subprocess_command, copy_backups

def main():
    """
    Main function to orchestrate backup and cleanup operations.
    """
    configure_logging("vmmaintenance")
    paths = read_config("Paths")
    os.chdir(paths['virtual_box_path'])

    daily_backup_paths, monthly_backup_paths = get_backup_paths()
    VMDetails = read_config("VMDetails")
    vm_names_section = VMDetails['vm_names']

    copy_backups_based_on_date(is_last_working_day_of_month(), daily_backup_paths['DAILY_LOCAL'], daily_backup_paths, monthly_backup_paths)
    perform_cleanup_operations(is_last_working_day_of_month(), daily_backup_paths['DAILY_LOCAL'], daily_backup_paths, monthly_backup_paths)
    
    copy_vm_management(paths)  # Call the new function here

def get_retention_periods(section_header):
    """
    Parses retention periods from configuration data.

    Args:
        section_header (str): The header of the section to retrieve.

    Returns:
        dict: A dictionary containing all items within the specified section.
    """
    BackupDetails = read_config(section_header)
    section_data = BackupDetails.get(section_header, {})
    return section_data

def get_backup_paths():
    """
    Parses backup paths from paths data and creates directories if they don't exist.

    Returns:
        tuple: A tuple containing dictionaries for daily backup paths and monthly backup paths.
    """
    Paths = read_config("Paths")

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

    for path in daily_backup_paths.values():
        create_directories(path)
    
    for path in monthly_backup_paths.values():
        create_directories(path)

    return daily_backup_paths, monthly_backup_paths

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
    except Exception as e:
        raise

def copy_backups_based_on_date(is_last_day, source_path, daily_paths, monthly_paths):
    """
    Copy backups based on the date condition.

    Parameters:
        is_last_day (bool): Whether it's the last day of the month.
        source_path (str): Source path for backup.
        daily_paths (dict): Dictionary containing daily destination paths.
        monthly_paths (dict): Dictionary containing monthly destination paths.
    """
    if not is_last_day:
        copy_backups(source_path, daily_paths)
    else:
        copy_backups(source_path, daily_paths)
        copy_backups(source_path, monthly_paths)

def copy_backups(source_path, paths):
    """
    Copy backups from source path to destination paths.

    Parameters:
        source_path (str): Source path for backup.
        paths (dict): Dictionary containing destination paths for different backup types.
    """
    for destination_key, destination_value in paths.items():
        if source_path == destination_value:
            logging.info(f"Source path {source_path} is the same as destination path {destination_value}. Skipping copying.")
            continue
        file_copy(source_path, destination_value)
        logging.info(f"Files copied from {source_path} to {destination_value}.")

def perform_cleanup_operations(is_last_day, source_path, daily_paths, monthly_paths):
    """
    Perform cleanup operations based on the date condition.

    Parameters:
        is_last_day (bool): Whether it's the last day of the month.
        source_path (str): Source path for cleanup.
        daily_paths (dict): Dictionary containing daily destination paths.
        monthly_paths (dict): Dictionary containing monthly destination paths.
    """
    daily_retention, monthly_retention = get_retention_periods("BackupDetails")
    daily_retention = 0
    monthly_retention = 0
    if not is_last_day:
        cleanup_files_in_paths(daily_paths, daily_retention)
    else:
        cleanup_files_in_paths(daily_paths, daily_retention)
        cleanup_files_in_paths(monthly_paths, monthly_retention)

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
                for file_name in files:
                    try:
                        cleanup_file_path = file_path(root, file_name)
                        cleanup_file_age = file_age(cleanup_file_path, file_name)
                        if cleanup_file_age.days >= max_age_days:
                            file_remove(cleanup_file_path, file_name)
                    except Exception as e:
                        logging.error(f"An error occurred while processing file '{file_name}': {str(e)}")
        logging.info("File cleanup process completed.")
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

def file_age(file_path, filename):
    """
    Calculate the age of the file in days.

    Parameters:
        file_path (str): Path to the file.
        filename (str): Name of the file.

    Returns:
        datetime.timedelta: Age of the file.
    """
    file_age = datetime.date.today() - datetime.date.fromtimestamp(os.path.getmtime(file_path))
    logging.info(f"Checking file '{filename}' with age {file_age.days} days.")
    return file_age

def file_copy(source_path, destination_path):
    """
    Copy files from source_path to destination_path.

    Parameters:
        source_path (str): Path to the source directory.
        destination_path (str): Path to the destination directory.
    """
    try:
        shutil.copytree(source_path, os.path.join(destination_path, os.path.basename(source_path)))
        logging.info(f"Directory copied from {source_path} to {destination_path}.")
    except Exception as e:
        logging.error(f"Error copying directory: {e}")

def file_remove(file_path, file_name):
    """
    Remove the specified file.

    Parameters:
        file_path (str): Path to the file.
        file_name (str): Name of the file.
    """
    os.remove(file_path)
    logging.info(f"Deleted file '{file_name}'.")

def copy_vm_management():
    """
    Copy VM management files to NAS and Office 365 destinations and perform cleanup.

    """
    try:
        Paths = read_config("Paths")
        source_path = Paths['vm_management_source_path']
        destination_nas_path = Paths['nas_misc_path']
        destination_office365_path = Paths['office365_misc_path']

        # Copy files to NAS
        file_copy(source_path, destination_nas_path)
        logging.info(f'Successfully copied {source_path} to NAS: {destination_nas_path}')

        # Copy files to Office 365
        file_copy(source_path, destination_office365_path)
        logging.info(f'Successfully copied {source_path} to Office 365: {destination_office365_path}')

        # Perform cleanup
        perform_cleanup_operations(is_last_working_day_of_month(), source_path, {'NAS': destination_nas_path}, {'Office365': destination_office365_path})

    except FileNotFoundError:
        logging.error(f'Error: Source directory not found - {source_path}')
    except Exception as e:
        logging.error(f'Error: {e}')

if __name__ == "__main__":
    main()
