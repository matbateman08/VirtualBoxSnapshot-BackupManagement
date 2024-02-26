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

    @patch('os.path.abspath')
    def test_get_script_directory(self, mock_abspath):
        mock_abspath.return_value = r"C:\VM_Management\unittesting.py"
        result = get_script_directory()
        mock_abspath.assert_called_once()
        self.assertEqual(result, "/path/to")

    @patch('os.path.abspath')
    def test_get_script(self, mock_abspath):
        mock_abspath.return_value = "/path/to/script.py"
        result = get_script()
        mock_abspath.assert_called_once()
        self.assertEqual(result, "/path/to/script.py")

    @patch('os.makedirs')
    def test_create_directories(self, mock_makedirs):
        directory = "/path/to/directory"
        create_directories(directory)
        mock_makedirs.assert_called_once_with(directory, exist_ok=True)

    @patch('os.path.exists')
    @patch('os.path.join')
    def test_file_exists(self, mock_join, mock_exists):
        mock_join.return_value = "/path/to/script.py"
        mock_exists.return_value = True
        result = file_exists("script.py")
        mock_join.assert_called_once_with("/path/to", "script.py")
        mock_exists.assert_called_once_with("/path/to/script.py")
        self.assertTrue(result)

    def test_find_used_env_vars(self):
        script_content = 'os.getenv("VAR1")\nos.getenv("VAR2")'
        result = find_used_env_vars(script_content)
        self.assertEqual(result, {"VAR1", "VAR2"})

    @patch('builtins.input')
    def test_get_env_values(self, mock_input):
        mock_input.side_effect = ["value1", "value2"]
        used_env_vars = {"VAR1", "VAR2"}
        result = get_env_values(used_env_vars)
        mock_input.assert_has_calls([unittest.mock.call('VAR1: '), unittest.mock.call('VAR2: ')])
        self.assertEqual(result, {"VAR1": "value1", "VAR2": "value2"})

    @patch('builtins.open', create=True)
    def test_write_env_file(self, mock_open):
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        env_values = {"VAR1": "value1", "VAR2": "value2"}
        result = write_env_file(".env", env_values)
        mock_open.assert_called_once_with(".env", 'w')
        mock_file.write.assert_has_calls([unittest.mock.call("VAR1=value1\n"), unittest.mock.call("VAR2=value2\n")])
        self.assertTrue(result)

    @patch('vm_process.file_exists')
    @patch('vm_process.find_used_env_vars')
    @patch('vm_process.get_script')
    @patch('builtins.open', create=True)
    @patch('vm_process.get_env_values')
    def test_setup_environment_variables(self, mock_get_env_values, mock_open, mock_get_script, mock_find_used_env_vars, mock_file_exists):
        mock_file_exists.return_value = False
        mock_get_script.return_value = "/path/to/script.py"
        mock_find_used_env_vars.return_value = {"VAR1", "VAR2"}
        mock_get_env_values.return_value = {"VAR1": "value1", "VAR2": "value2"}
        setup_environment_variables()
        mock_file_exists.assert_called_once_with('.env')
        mock_get_script.assert_called_once()
        mock_find_used_env_vars.assert_called_once()
        mock_get_env_values.assert_called_once_with({"VAR1", "VAR2"})
        mock_open.assert_called_once_with('.env', 'w')
        mock_open.return_value.__enter__.return_value.write.assert_has_calls([
            unittest.mock.call('VAR1=value1\n'),
            unittest.mock.call('VAR2=value2\n')
        ])

if __name__ == '__main__':
    unittest.main()
