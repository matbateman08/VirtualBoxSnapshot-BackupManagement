import os
import logging
import re
import configparser
import datetime

def setup_environment_variables():
    env_file = '.env'
    if not os.path.exists(env_file):
        logging.info("No .env file found. Let's set it up.")
        used_env_vars = set()
        script_path = os.path.abspath(__file__)

        # Search the script for os.getenv() calls
        with open(script_path, 'r') as script_file:
            script_content = script_file.read()

            # Find all occurrences of os.getenv()
            env_vars_used_in_script = re.findall(r"os\.getenv\(['\"]([^'\"]+)['\"]\)", script_content)
            used_env_vars.update(env_vars_used_in_script)

        # Ask the user for values of the detected environment variables
        with open(env_file, 'w') as f:
            logging.info("Please provide values for the following environment variables:")
            for env_var in used_env_vars:
                value = input(f"{env_var}: ")
                # Encapsulate the value in single quotes if it contains special characters
                value_to_write = value if not re.search(r"[^\w\-]", value) else f"'{value}'"
                f.write(f"{env_var}={value_to_write}\n")

def generate_config_from_script():
    def parse_config_from_script():
        script_path = os.path.abspath(__file__)
        try:
            with open(script_path, 'r') as file:
                script_lines = file.readlines()
                section_paths = {}
                for line in script_lines:
                    matches = re.findall(r"([A-Z]\w+)\[['\"](.+?)['\"]\]", line)
                    for match in matches:
                        header, path = match
                        if header and path:
                            combined_key = header + "['" + path + "']"
                            section_paths[combined_key] = path
                return section_paths
        except FileNotFoundError:
            logging.info(f"File '{script_path}' not found.")
            return {}

    section_paths = parse_config_from_script()
    formatted_output = {}
    for key, value in section_paths.items():
        prefix = key.split("['")[0]
        if prefix not in formatted_output:
            formatted_output[prefix] = {}
        # Extracting the last part of the key for displaying
        location_key = key.split("['")[-1][:-2]
        formatted_output[prefix][location_key] = value

    config = configparser.ConfigParser()

    # Check if config file exists
    if not os.path.exists('config.ini'):
        for prefix, items in formatted_output.items():
            config[prefix] = {}  # Creating the section
            for key, value in items.items():
                input_location = input(f"Enter location for {key} (press enter to keep default value '{value}'): ")
                if input_location.strip():  # If user provided input
                    items[key] = input_location  # Use the input as the new value
                # Here you might want to add some validation or error handling for the user input
                config[prefix][key] = items[key]

        # Writing the config to a file
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
    else:
        logging.info("Config file 'config.ini' already exists. Skipping user input and file writing.")

def read_config(section_name):
    config = configparser.ConfigParser()

    # Get the absolute path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Use a relative path to the config file
    config_file_path = os.path.join(script_directory, 'config.ini')

    # Check if the file exists
    if not os.path.exists(config_file_path):
        logging.critical(f"Error: Config file does not exist at {config_file_path}")
        return None

    # Attempt to read the configuration file
    read_files = config.read(config_file_path)

    if not read_files:
        logging.critical(f"Error: Config file does not exist at {config_file_path}")
        return None

    # Check if the specified section exists
    if section_name not in config:
        logging.critical(f"Error: Section {section_name} does not exist in the config file")
        return None

    section = config[section_name]

    #logging.info(f"{section_name} Section:")
    #for key, value in section.items():
    #    logging.info(f"  {key}: {value}")

    #logging.info("")

    return section

def configure_logging(logfile):
    # Get the absolute path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Generate a log file path based on the current date
    today_date = datetime.date.today().strftime("%Y-%m-%d")
    logs_folder = os.path.join(script_directory, 'logs', logfile)
    os.makedirs(logs_folder, exist_ok=True)
    log_file_path = os.path.join(logs_folder, f'{today_date}_{logfile}.log')

    # Configure logging first
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s]: %(message)s',
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file_path)]
    )

    # Log the configuration settings
    #logging.info("Logging configuration settings:")
    logging.info(f"Log level: {logging.getLevelName(logging.getLogger().getEffectiveLevel())}")

    #handlers = logging.getLogger().handlers
    #if handlers:
    #    logging.info("Handlers:")
    #    for handler in handlers:
    #        logging.info(f"- {handler}")
    #else:
    #    logging.info("No handlers configured.")

    # Now you can log additional messages
    logging.info(f"Script File Path: {script_directory}")
    logging.info(f"Log File Path: {log_file_path}")

    return log_file_path
