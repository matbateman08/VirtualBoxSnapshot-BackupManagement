import os
import logging
from config_and_env import generate_config_from_script, setup_environment_variables, configure_logging, read_config
from networkdrivemanagement import disconnect_all_active_connections, find_available_drive_letter, map_network_drive
from execution_days import is_execution_day
from filemanagement import backup_management
from sendemail import send_log_email
from snapshotactions import create_snapshot
from vboxcontrols import VMAction, manage_vm_power

def main():
    generate_config_from_script()
    setup_environment_variables()
    log_file_path = configure_logging("vmmaintenance")
    try:
        if is_execution_day():
            Paths = read_config("Paths")
            disconnect_all_active_connections(Paths['nas_path'])
            drive_letter = find_available_drive_letter()
            map_network_drive(Paths['nas_path'], drive_letter)
            os.chdir(Paths['virtual_box_path'])
            VMDetails = read_config("VMDetails")
            vm_names_section = VMDetails['vm_names']
            for vm_name in vm_names_section.split(','):
                vm_name = vm_name.strip()
                manage_vm_power(vm_name, VMAction.POWER_OFF)
                create_snapshot(vm_name)
                backup_management(Paths, vm_name, "Create")
                manage_vm_power(vm_name, VMAction.START_HEADLESS)
            backup_management(Paths, vm_name, "Backup")                
            send_log_email(log_file_path)
            disconnect_all_active_connections(Paths['nas_path'])
        else:
            logging.info("Not running the script today.")
    except Exception as e:
        logging.critical(f"Error encountered: {e}")

if __name__ == "__main__":
    main()