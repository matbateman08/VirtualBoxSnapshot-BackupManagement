import unittest
from unittest.mock import patch, MagicMock
from vm_process import read_config  

class TestReadConfig(unittest.TestCase):

    @patch('configparser.ConfigParser')
    @patch('os.path.exists', return_value=True)
    def test_read_config_success(self, mock_exists, mock_config_parser):
        # Mock the behavior of the ConfigParser object
        mock_parser_instance = MagicMock()
        mock_parser_instance.__contains__.return_value = True
        mock_parser_instance.__getitem__.return_value = {'key': 'value'}
        mock_config_parser.return_value = mock_parser_instance

        # Call the function
        result = read_config('example_section')

        # Assert that the result is as expected
        self.assertEqual(result, {'key': 'value'})

    @patch('builtins.open', new_callable=MagicMock)
    @patch('os.path.exists', return_value=False)
    def test_read_config_file_not_exists(self, mock_exists, mock_open):
        # Call the function
        result = read_config('example_section')

        # Assert that the result is None
        self.assertIsNone(result)

    @patch('builtins.open', new_callable=MagicMock)
    @patch('os.path.exists', return_value=True)
    def test_read_config_section_not_exists(self, mock_exists, mock_open):
        # Mock the ConfigParser object
        mock_parser = MagicMock()
        mock_parser.__contains__.return_value = False
        mock_open.return_value.__enter__.return_value = mock_parser

        # Call the function
        result = read_config('nonexistent_section')

        # Assert that the result is None
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()