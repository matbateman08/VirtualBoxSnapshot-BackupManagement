### VirtualBox VM Maintenance Script

This Python script automates various maintenance tasks for virtual machines (VMs) managed through VirtualBox. It performs actions such as creating snapshots, managing backups, and sending log emails. 

#### Dependencies
- subprocess
- shutil
- os
- re
- configparser
- logging
- string
- datetime
- smtplib
- enum
- dotenv
- email.mime.text
- email.mime.multipart

#### Usage
1. Ensure all dependencies are installed.
2. Configure the config.ini, file with relevant paths and settings.
3. Set environment variables (email_username, email_password, email_from, email_to, Username, Password).
4. Run the script. (python script.py)

#### Functionality
- **Backup Management**: Handles creation, copying, and cleanup of backups to various destinations.
- **Snapshot Management**: Creates snapshots for VMs with specified retention policies.
- **Log Email**: Sends a daily log email containing script execution details.
- **Network Drive Mapping**: Maps network drives for backup purposes.
- **Error Handling**: Captures and logs errors for troubleshooting.