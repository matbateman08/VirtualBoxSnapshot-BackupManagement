import os
import logging
import shutil
from vm_process import configure_logging, generate_config_from_script, setup_environment_variables, create_directories, read_config, disconnect_all_active_connections, map_network_drive, get_backup_paths

def main():
    log_file_path = configure_logging("vmmaintenance")
    generate_config_from_script()
    setup_environment_variables()
    try:
        Paths = read_config("Paths")
        disconnect_all_active_connections(Paths['nas_path'])
        network_drive = map_network_drive(Paths['nas_path'])
        #copy_backups(Paths['vm_management_source_path'], Paths['nas_misc_path'])
        #copy_backups(Paths['vm_management_source_path'], Paths['office365_misc_path'])
        #daily_backup_paths, monthly_backup_paths = get_backup_paths(Paths, network_drive)
        
        source_path = Paths['vm_management_source_path']
        destination_path = Paths['nas_misc_path']

        copy_folder(source_path, destination_path)

    except Exception as e:
        logging.critical(f"Error encountered: {e}")

def copy_folder(src, dest):
    try:
        shutil.copytree(src, dest)
        print(f"Folder '{src}' copied to '{dest}' successfully.")
    except shutil.Error as e:
        print(f"Folder '{src}' could not be copied. Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

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

def file_copy(source_path, destination_path, retry=2):
    """
    Copy files from source_path to destination_path with retry attempts.

    Parameters:
        source_path (str): Path to the source directory.
        destination_path (str): Path to the destination directory.
        retry (int): Number of retry attempts (default is 2).
    """
    try:
        files = os.listdir(source_path)
        for file in files:
            source_file = os.path.join(source_path, file)
            destination_file = os.path.join(destination_path, file)
            attempt = 0
            while attempt < retry:
                try:
                    shutil.copy(source_file, destination_file)
                    logging.info(f"File {file} copied from {source_path} to {destination_path}.")
                    break  # Break out of the retry loop if successful
                except FileNotFoundError:
                    logging.error(f"Source file {source_file} not found. Skipping.")
                    break  # Break out of the retry loop if file not found
                except PermissionError:
                    logging.error(f"Permission denied while copying file {source_file}. Check permissions. Skipping.")
                    break  # Break out of the retry loop if permission denied
                except Exception as e:
                    logging.warning(f"Error copying file {source_file}: {e}. Retrying...")
                    attempt += 1
                    if attempt == retry:
                        logging.error(f"Failed to copy file {source_file} after {retry} attempts. Skipping.")
    except FileNotFoundError:
        logging.error(f"Source directory {source_path} not found.")
    except PermissionError:
        logging.error(f"Permission denied while copying files from {source_path}. Check permissions.")
    except Exception as e:
        logging.error(f"Error copying files: {e}")

if __name__ == "__main__":
    main()
