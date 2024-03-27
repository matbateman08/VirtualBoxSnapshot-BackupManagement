import os
import logging
from vm_process import VMAction, read_config, manage_vm_action, configure_logging, generate_config_from_script, send_log_email

def main():
    log_file_path = configure_logging("osrestart")
    generate_config_from_script()
    Paths = read_config("Paths")
    os.chdir(Paths['virtual_box_path'])
    VMDetails = read_config("VMDetails")
    vm_names_section = VMDetails['vm_names']
    for vm_name in vm_names_section.split(','):
        vm_name = vm_name.strip()
        manage_vm_action(vm_name, VMAction.POWER_OFF)
    logging.info(f"All VM's powered off. Host PC about to restart")
    restart_computer(log_file_path)

def restart_computer(log_file_path):
    try:
        logging.info(f"Restart about to be initiated")
        send_log_email(log_file_path)
        os.system("shutdown /r /t 0")
    except Exception as e:
        logging.info(f"An error occurred executing the restart: {e}")

if __name__ == "__main__":
    main()