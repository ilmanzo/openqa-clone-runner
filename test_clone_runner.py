#!/usr/bin/env python3
import unittest
from unittest.mock import patch
from io import StringIO
import sys
import clone_runner

class TestValidateVariables(unittest.TestCase):

    def test_valid_variables(self):
        """Test that valid variables do not raise an error."""
        variables = {
            'ARCH': 'x86_64',
            'VERSION': '15-SP4',
            'FLAVORS': ['DVD', 'NET'],
            'BUILD': 123
        }
        try:
            clone_runner.validate_variables(variables)
        except SystemExit:
            self.fail("validate_variables() raised SystemExit unexpectedly with valid input!")

    def test_empty_variables(self):
        """Test that empty variables dictionary is handled gracefully."""
        clone_runner.validate_variables({})
        # If no exception is raised, the test passes

    @patch('sys.stdout', new_callable=StringIO)
    def test_lowercase_key(self, mock_stdout):
        """Test that a lowercase key triggers an error."""
        variables = {'arch': 'x86_64'}
        with self.assertRaises(SystemExit) as cm:
            clone_runner.validate_variables(variables)
        
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Error: Variable 'arch' must be uppercase.", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=StringIO)
    def test_empty_string_value(self, mock_stdout):
        """Test that an empty string value triggers an error."""
        variables = {'ARCH': ''}
        with self.assertRaises(SystemExit) as cm:
            clone_runner.validate_variables(variables)
            
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Error: Variable 'ARCH' cannot be an empty string.", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=StringIO)
    def test_empty_string_in_list(self, mock_stdout):
        """Test that an empty string inside a list triggers an error."""
        variables = {'FLAVORS': ['DVD', '']}
        with self.assertRaises(SystemExit) as cm:
            clone_runner.validate_variables(variables)
            
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Error: Variable 'FLAVORS' contains an empty string in the list.", mock_stdout.getvalue())

    def test_non_string_values(self):
        """Test that non-string values (integers, booleans) are accepted."""
        variables = {
            'BUILD_ID': 12345,
            'ENABLE_FEATURE': True,
            'TIMEOUT': 30.5
        }
        try:
            clone_runner.validate_variables(variables)
        except SystemExit:
            self.fail("validate_variables() raised SystemExit unexpectedly with non-string input!")

if __name__ == '__main__':
    unittest.main()