import unittest
from unittest.mock import patch, mock_open
from io import StringIO
import os
import re
import logging

# Import the function to be tested
from vm_process import setup_environment_variables

class TestSetupEnvironmentVariables(unittest.TestCase):
    @patch('builtins.input', side_effect=['value1', 'value2'])  # Mock user input
    @patch('vm_process.open', new_callable=mock_open)  # Patch open() within the module where setup_environment_variables() is defined
    @patch('os.path.exists', return_value=False)  # Ensure that the .env file doesn't exist initially
    def test_setup_environment_variables(self, mock_exists, mock_open, mock_input):
        # Call the function to be tested
        setup_environment_variables()

        # Assert that the file is written with the expected content
        mock_open.assert_called_once_with('.env', 'w')  # Assert the open() call for writing
        mock_open.return_value.write.assert_called_with("ENV_VAR1='value1'\nENV_VAR2='value2'\n")  # Assert the write() call

if __name__ == '__main__':
    unittest.main()