import unittest
from unittest.mock import patch, MagicMock
import subprocess
import os
from vm_process import execute_subprocess_command, get_script_directory, get_script, create_directories, file_exists, find_used_env_vars, get_env_values, write_env_file, setup_environment_variables

class TestYourFunctions(unittest.TestCase):

    @patch('subprocess.run')
    @patch('logging.info')
    def test_execute_subprocess_command(self, mock_logging_info, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(returncode=0, output="Output")
        command = ["ls", "-l"]
        log_message = "Testing subprocess"
        result = execute_subprocess_command(command, log_message)
        mock_logging_info.assert_called_with(log_message)
        mock_subprocess_run.assert_called_with(command, capture_output=True, text=True, check=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.output, "Output")



if __name__ == '__main__':
    unittest.main()
