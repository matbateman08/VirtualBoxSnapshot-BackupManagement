import os
import logging
import shutil
from vm_process import configure_logging, execute_subprocess_command ,generate_config_from_script, setup_environment_variables, folder_copy, create_directories, read_config, disconnect_all_active_connections, map_network_drive, get_backup_paths

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
        destination_path = r"C:\Users\MathewBateman\OneDrive - Axial Projects\Desktop"

        # Use rsync command to copy source directory to NAS directory
        # -a: archive mode (preserves permissions, ownership, timestamps, etc.)
        # -r: recursive (copy directories and their contents recursively)
        # --progress: show progress during transfer
        # --exclude: exclude certain files or directories (optional)
        command = ['xcopy', source_path, destination_path, '/E', '/I', '/Y']
        log_message = f"Copying from: {source_path} Destination: {destination_path}..."
        execute_subprocess_command(command, log_message)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


    except Exception as e:
        logging.critical(f"Error encountered: {e}")

if __name__ == "__main__":
    main()
