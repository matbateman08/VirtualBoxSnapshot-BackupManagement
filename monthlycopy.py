import logging
import os
import shutil
from vm_process import configure_logging, read_config, copy_last_day_of_month, file_directory_list

def main():
    try:
        configure_logging("vmrunninglogs")
        Paths = read_config("Paths")

        files = file_directory_list(Paths['source_daily_backup_path'])
        copy_last_day_of_month(files, Paths['source_monthly_backup_path'])
        print("Completed")
            
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main()
