import os
import subprocess
import logging
from vm_process import read_config, disconnect_all_active_connections, map_network_drive, execute_subprocess_command

def main():
    Paths = read_config("Paths")
    disconnect_all_active_connections(Paths['nas_path'])
    map_network_drive(Paths['nas_path'])
    os.chdir(Paths['virtual_box_path'])
    folder_copy_subprocess(src=r"C:\VM_Management", dest=r"\\OFFICE-NAS\VM_Backups\Misc")

def remove_hidden_attribute(file_path):
    """
    Remove the hidden attribute from a file.

    Parameters:
        file_path (str): The path to the file.

    Returns:
        None
    """
    try:
        subprocess.run(['attrib', '-h', file_path], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error removing hidden attribute from {file_path}: {e}")

def folder_copy_subprocess(src, dest):
    """
    Copy the entire contents of a folder from the source path to the destination path using xcopy via subprocess.

    Parameters:
        src (str): The path to the source directory to be copied.
        dest (str): The path to the destination directory where the contents will be copied.

    Returns:
        None

    Raises:
        Exception: For unexpected errors during the copying process.

    Note:
        This function uses the xcopy command via subprocess to copy the entire folder tree from
        the source to the destination. If the destination folder does not exist, it will be created.

    Example:
        Copy the contents of '/path/to/source_folder' to '/path/to/destination_folder':
        >>> xcopy_copy_folder('/path/to/source_folder', '/path/to/destination_folder')
    """
    try:

        # List files in the source directory
        src_files = os.listdir(src)
        
        # Print each file being copied
        for file in src_files:
            logging.info(f"Copying {file} from: {src} to Destination: {dest}...")
            file_path = os.path.join(src, file)
            remove_hidden_attribute(file_path)
            
        command = ['xcopy', src, dest, '/E', '/I', '/Y', '/H', '/C', '/F']
        log_message = f"Copying from: {src} Destination: {dest}..."
        execute_subprocess_command(command, log_message)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()