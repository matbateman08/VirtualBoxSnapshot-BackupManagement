import os
import logging
from vm_process import VMAction, send_log_email, setup_environment_variables, generate_config_from_script, read_config, configure_logging, manage_vm_power

def main():
    try:
        log_file_path = configure_logging("vmrunninglogs")
        generate_config_from_script()
        setup_environment_variables()
        Paths = read_config("Paths")
        os.chdir(Paths['virtual_box_path'])
        already_running = 0  
        VMDetails = read_config("VMDetails")
        vm_names_section = VMDetails['vm_names']
        for vm_name in vm_names_section.split(','):
            vm_name = vm_name.strip()
            if manage_vm_power(vm_name, VMAction.START_HEADLESS):
                already_running += 1  # Increment the counter for each failed VM start
        if already_running > 0:
            logging.info("Certain VM's weren't running. Sending Email to summarise.")
            send_log_email(log_file_path)

    except Exception as e:
        logging.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
