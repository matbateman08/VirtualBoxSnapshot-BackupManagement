import os
import logging
from vm_process import configure_logging, read_config, list_snapshots

def main():
    try:
        log_file_path = configure_logging("vmrunninglogs")
        Paths = read_config("Paths")
        os.chdir(Paths['virtual_box_path'])
        VMDetails = read_config("VMDetails")
        vm_names_section = VMDetails['vm_names']
        for vm_name in vm_names_section.split(','):
            print(list_snapshots(vm_name))
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
