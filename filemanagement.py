import logging
import subprocess
import os
import shutil
import datetime
from enum import Enum
from config_and_env import read_config
from execution_days import is_last_working_day_of_month
from vboxcontrols import VM, execute_vbox_command

class BackupType(Enum):
    DAILY_LOCAL = "daily_backup_path"
    MONTHLY_LOCAL = "monthly_backup_path"
    DAILY_OFFICE365 = "office365_daily_path"
    MONTHLY_OFFICE365 = "office365_monthly_path"
    DAILY_NAS = "nas_daily_path"
    MONTHLY_NAS = "nas_monthly_path"

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