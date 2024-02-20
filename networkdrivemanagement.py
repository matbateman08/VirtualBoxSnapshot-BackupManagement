import logging
import subprocess
import os
import string 

def disconnect_all_active_connections(remote_path):
    try:
        # Get all active connections
        result = subprocess.run(['net', 'use'], capture_output=True, text=True)

        # Check the return code
        if result.returncode == 0:
            # Parse the output to get drive letters of active connections to the specified remote path
            active_connections = [line.split()[1] for line in result.stdout.splitlines() if line.strip() and remote_path in line and not line.strip().endswith('\\IPC$')]

            # Log information about all active connections
            if active_connections:
                for drive_letter in active_connections:
                    logging.info(f"Active connection: Drive {drive_letter} connected to {remote_path} before disconnection")
            else:
                logging.info("No active connections found.")

            # Disconnect each active connection
            for drive_letter in active_connections:
                disconnect_command = ['net', 'use', drive_letter, '/delete', '/yes']
                subprocess.run(disconnect_command, capture_output=True)
                logging.info(f"Disconnected drive {drive_letter}")

            return True  # Disconnected all active connections
        else:
            logging.info(f"Error getting active connections: {result.stderr}")
            return False  # An error occurred while getting active connections

    except subprocess.CalledProcessError as e:
        logging.info(f"Error disconnecting active connections: {e}")
        return False  # An exception occurred during the subprocess call

    except subprocess.TimeoutExpired:
        logging.info(f"Timeout occurred while disconnecting active connections for {remote_path}")
        return False  # Timeout occurred while disconnecting active connections

def map_network_drive(network_path, drive_letter):
    username = os.getenv("Username")
    password = os.getenv("Password")

    try:
            # Construct the net use command to map the network drive
            check_command = ['net', 'use', drive_letter + ':', network_path, '/user:' + username, password]

            # Run the net use command
            result = subprocess.run(check_command, capture_output=True, text=True)

            # Check the return code
            if result.returncode == 0:
                logging.info(f"Network drive {network_path} successfully mapped to {drive_letter}.")
            else:
                logging.info(f"Failed to map network drive {network_path} to {drive_letter}. Error: {result.stderr}")

    except Exception as e:
        logging.info(f"An error occurred while mapping network drive {network_path}. Exception: {e}")

def find_available_drive_letter():
    net_use_output = subprocess.run(['net', 'use'], capture_output=True, text=True).stdout
    #logging.info(f"Raw net use output:\n{net_use_output}")

    used_drive_letters = set()

    for line in net_use_output.split("\n")[2:]:
        drive_info = line.split()
        if len(drive_info) >= 2 and ':' in drive_info[1]:
            used_drive_letters.add(drive_info[1][0])

    for letter in reversed(string.ascii_uppercase):
        if letter not in used_drive_letters:
            return letter

    return None