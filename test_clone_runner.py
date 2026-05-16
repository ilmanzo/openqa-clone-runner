#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys
import clone_runner

WHICH_FOUND = patch('clone_runner.shutil.which', return_value='/usr/bin/tool')

class TestValidateVariables(unittest.TestCase):

    def test_valid_variables(self):
        variables = {
            'ARCH': 'x86_64',
            'VERSION': '15-SP4',
            'FLAVORS': ['DVD', 'NET'],
            'BUILD': 123
        }
        try:
            clone_runner.validate_variables(variables)
        except ValueError:
            self.fail("validate_variables() raised ValueError unexpectedly with valid input!")

    def test_empty_variables(self):
        clone_runner.validate_variables({})

    def test_lowercase_key(self):
        variables = {'arch': 'x86_64'}
        with self.assertRaises(ValueError) as cm:
            clone_runner.validate_variables(variables)
        self.assertEqual(str(cm.exception), "Error: Variable 'arch' must be uppercase.")

    def test_empty_string_value(self):
        variables = {'ARCH': ''}
        with self.assertRaises(ValueError) as cm:
            clone_runner.validate_variables(variables)
        self.assertEqual(str(cm.exception), "Error: Variable 'ARCH' cannot be an empty string.")

    def test_empty_string_in_list(self):
        variables = {'FLAVORS': ['DVD', '']}
        with self.assertRaises(ValueError) as cm:
            clone_runner.validate_variables(variables)
        self.assertEqual(str(cm.exception), "Error: Variable 'FLAVORS' contains an empty string in the list.")

    def test_non_string_values(self):
        variables = {
            'BUILD_ID': 12345,
            'ENABLE_FEATURE': True,
            'TIMEOUT': 30.5
        }
        try:
            clone_runner.validate_variables(variables)
        except ValueError:
            self.fail("validate_variables() raised ValueError unexpectedly with non-string input!")

    def test_list_with_non_strings(self):
        variables = {
            'BUILD_NUMBERS': [1001, 1002, 1003],
            'ENABLED': [True, False]
        }
        try:
            clone_runner.validate_variables(variables)
        except ValueError:
            self.fail("validate_variables() raised ValueError unexpectedly with list of non-strings!")

class TestExpandVariables(unittest.TestCase):

    def test_simple_expansion(self):
        variables = {'VERSION': '15', 'ISO': 'SLES-%VERSION%.iso'}
        expanded = clone_runner.expand_variables(variables)
        self.assertEqual(expanded['ISO'], 'SLES-15.iso')

    def test_nested_expansion(self):
        variables = {'A': 'start', 'B': '%A%-mid', 'C': '%B%-end'}
        expanded = clone_runner.expand_variables(variables)
        self.assertEqual(expanded['C'], 'start-mid-end')

    def test_undefined_variable_raises_error(self):
        variables = {'ISO': 'SLES-%MISSING%.iso'}
        with self.assertRaises(ValueError) as cm:
            clone_runner.expand_variables(variables)
        self.assertIn("MISSING", str(cm.exception))

    @patch('sys.stdout', new_callable=StringIO)
    def test_circular_dependency_limit(self, mock_stdout: StringIO):
        variables = {'A': 'recurse-%A%'}
        expanded = clone_runner.expand_variables(variables)
        self.assertIn('%A%', expanded['A'])
        self.assertIn("Warning: Variable expansion hit the iteration limit (5).", mock_stdout.getvalue())

class TestCloneRunnerCLI(unittest.TestCase):

    @patch('sys.stdout', new_callable=StringIO)
    def test_missing_config_file(self, mock_stdout: StringIO):
        with patch('sys.argv', ['clone_runner.py', 'non_existent.yaml']):
            with self.assertRaises(SystemExit) as cm:
                clone_runner.main()
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Error: Config file 'non_existent.yaml' not found.", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=StringIO)
    def test_malformed_yaml(self, mock_stdout: StringIO):
        malformed_yaml = "key: - value\n  - another_value: oops"

        with patch('sys.argv', ['clone_runner.py', 'malformed.yaml']):
            with patch('pathlib.Path.is_file', return_value=True):
                with patch('pathlib.Path.open', unittest.mock.mock_open(read_data=malformed_yaml)):
                    with self.assertRaises(SystemExit) as cm:
                        clone_runner.main()
                    self.assertEqual(cm.exception.code, 1)
                    self.assertIn("Error parsing YAML file 'malformed.yaml'", mock_stdout.getvalue())

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_dry_run_flag(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'jobs_to_clone': ['https://example.com/t1'],
            'variables': {'ARCH': 'x86_64'}
        }]

        with patch('sys.argv', ['clone_runner.py', 'dummy.yaml', '--dry-run']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("[DRY RUN] Would execute:", output)
        self.assertIn("openqa-clone-job", output)
        self.assertNotIn("No new job URLs found in output.", output)
        mock_subprocess.assert_not_called()

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_iso_post_dry_run(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'variables': {
                'DISTRI': 'sle', 'VERSION': '15-SP5', 'FLAVOR': 'Online',
                'ARCH': 'x86_64', '_GROUP_ID': 100, 'ISO': 'dummy.iso'
            }
        }]

        with patch('sys.argv', ['clone_runner.py', 'iso_config.yaml', '--dry-run']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("[DRY RUN] Would execute:", output)
        self.assertIn("openqa-cli api -X post isos", output)
        mock_subprocess.assert_not_called()

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_iso_post_missing_iso(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'variables': {
                'DISTRI': 'sle', 'VERSION': '15-SP5', 'FLAVOR': 'Online',
                'ARCH': 'x86_64', '_GROUP_ID': 100
            }
        }]

        with patch('sys.argv', ['clone_runner.py', 'iso_config.yaml']):
            with self.assertRaises(SystemExit) as cm:
                clone_runner.main()
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Error: Missing required variables for ISO post: ISO", mock_stdout.getvalue())

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_iso_post_variable_expansion(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'variables': {
                'DISTRI': 'sle', 'VERSION': '15-SP5', 'FLAVOR': 'Online',
                'ARCH': 'x86_64', '_GROUP_ID': 100,
                'ISO': 'SLE-%VERSION%-%FLAVOR%-%ARCH%.iso'
            }
        }]

        with patch('sys.argv', ['clone_runner.py', 'iso_config.yaml', '--dry-run']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("[DRY RUN] Would execute:", output)
        self.assertIn("ISO=SLE-15-SP5-Online-x86_64.iso", output)
        self.assertNotIn("%VERSION%", output)
        mock_subprocess.assert_not_called()

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_nested_variable_expansion(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'variables': {
                'DISTRI': 'sle', 'VERSION': '15-SP5', 'FLAVOR': 'Online',
                'ARCH': 'x86_64', '_GROUP_ID': 100,
                'ISO': 'dummy.iso',
                'PART1': 'Start',
                'PART2': '%PART1%-Middle',
                'FULL': '%PART2%-End'
            }
        }]

        with patch('sys.argv', ['clone_runner.py', 'iso_config.yaml', '--dry-run']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("FULL=Start-Middle-End", output)

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_circular_dependency(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'variables': {
                'DISTRI': 'sle', 'VERSION': '15-SP5', 'FLAVOR': 'Online',
                'ARCH': 'x86_64', '_GROUP_ID': 100,
                'ISO': 'dummy.iso',
                'VAR_A': '%VAR_B%',
                'VAR_B': '%VAR_A%'
            }
        }]

        with patch('sys.argv', ['clone_runner.py', 'iso_config.yaml', '--dry-run']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("[DRY RUN] Would execute:", output)
        self.assertIn("VAR_A=", output)
        self.assertIn("VAR_B=", output)

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_conflicting_host_and_flag(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'host': 'https://openqa.opensuse.org',
            'variables': {'DISTRI': 'sle', 'VERSION': '15', 'FLAVOR': 'Online', 'ARCH': 'x86_64', '_GROUP_ID': 100, 'ISO': 'dummy.iso'},
            'flags': ['--osd']
        }]

        with patch('sys.argv', ['clone_runner.py', 'conflict.yaml', '--dry-run']):
            with self.assertRaises(SystemExit) as cm:
                clone_runner.main()
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Error: Conflicting options: 'host' set to 'https://openqa.opensuse.org' but '--osd' flag provided.", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=StringIO)
    def test_duplicate_keys_yaml(self, mock_stdout: StringIO):
        duplicate_yaml = "variables:\n  ARCH: x86_64\n  ARCH: i586"

        with patch('sys.argv', ['clone_runner.py', 'duplicate.yaml']):
            with patch('pathlib.Path.is_file', return_value=True):
                with patch('pathlib.Path.open', unittest.mock.mock_open(read_data=duplicate_yaml)):
                    with self.assertRaises(SystemExit) as cm:
                        clone_runner.main()
                    self.assertEqual(cm.exception.code, 1)
                    self.assertIn("Duplicate key 'ARCH' found in YAML", mock_stdout.getvalue())

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_multiple_configs_separate_outputs(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.side_effect = [
            [{'jobs_to_clone': ['https://example.com/t1'], 'variables': {}}],
            [{'jobs_to_clone': ['https://example.com/t2'], 'variables': {}}]
        ]
        mock_subprocess.return_value.stdout = "-> https://new/job"

        mock_file = unittest.mock.mock_open()

        with patch('sys.argv', ['clone_runner.py', 'config1.yaml', 'config2.yaml']):
            with patch('pathlib.Path.open', mock_file):
                clone_runner.main()

        self.assertEqual(mock_load_configs.call_count, 2)
        open_calls = mock_file.call_args_list
        self.assertEqual(len(open_calls), 2)

        output = mock_stdout.getvalue()
        self.assertRegex(output, r"Success! 1 URLs saved to 'config1\.\d{8}-\d{4}\.urls\.txt'")
        self.assertRegex(output, r"Success! 1 URLs saved to 'config2\.\d{8}-\d{4}\.urls\.txt'")

    @patch('clone_runner.run_clone_jobs')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_multidoc_isolation(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_run_clone):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [
            {'jobs_to_clone': ['j1'], 'variables': {'A': '1'}},
            {'jobs_to_clone': ['j2'], 'variables': {'B': '2'}}
        ]
        mock_run_clone.return_value = []

        with patch('sys.argv', ['clone_runner.py', 'multidoc.yaml']):
            clone_runner.main()

        vars1 = mock_run_clone.call_args_list[0][0][2]
        vars2 = mock_run_clone.call_args_list[1][0][2]

        self.assertIn('A', vars1)
        self.assertNotIn('B', vars1)
        self.assertIn('B', vars2)
        self.assertNotIn('A', vars2)

    @patch('clone_runner.run_clone_jobs')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_multiple_files_variable_isolation(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_run_clone):
        mock_is_file.return_value = True
        mock_load_configs.side_effect = [
            [{'jobs_to_clone': ['j1'], 'variables': {'VAR_FILE1': '1'}}],
            [{'jobs_to_clone': ['j2'], 'variables': {'VAR_FILE2': '2'}}]
        ]
        mock_run_clone.return_value = []

        with patch('sys.argv', ['clone_runner.py', 'file1.yaml', 'file2.yaml']):
            clone_runner.main()

        self.assertEqual(mock_run_clone.call_count, 2)
        vars1 = mock_run_clone.call_args_list[0][0][2]
        self.assertIn('VAR_FILE1', vars1)
        self.assertNotIn('VAR_FILE2', vars1)

        vars2 = mock_run_clone.call_args_list[1][0][2]
        self.assertIn('VAR_FILE2', vars2)
        self.assertNotIn('VAR_FILE1', vars2)

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_multiple_configs_one_missing(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_subprocess.return_value.stdout = ""
        mock_is_file.side_effect = [True, False]
        mock_load_configs.return_value = [{'jobs_to_clone': ['j1'], 'variables': {}}]

        with patch('sys.argv', ['clone_runner.py', 'exist.yaml', 'missing.yaml']):
            with self.assertRaises(SystemExit) as cm:
                clone_runner.main()
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Error: Config file 'missing.yaml' not found.", mock_stdout.getvalue())

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_multiple_configs_one_invalid(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_subprocess.return_value.stdout = ""
        mock_is_file.return_value = True
        mock_load_configs.side_effect = [
            [{'jobs_to_clone': ['j1'], 'variables': {}}],
            ValueError("Invalid YAML")
        ]

        with patch('sys.argv', ['clone_runner.py', 'valid.yaml', 'invalid.yaml']):
            with self.assertRaises(SystemExit) as cm:
                clone_runner.main()
            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Invalid YAML", mock_stdout.getvalue())

    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_validate_flag_clone_mode(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'jobs_to_clone': ['https://openqa.suse.de/tests/1', 'https://openqa.suse.de/tests/2'],
            'variables': {'ARCH': 'x86_64', 'BUILD': '150'},
            'flags': ['--skip-chained-deps']
        }]

        with patch('sys.argv', ['clone_runner.py', '--validate', 'config.yaml']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("Clone jobs mode", output)
        self.assertIn("Jobs to clone", output)
        self.assertIn("Commands", output)
        self.assertIn("ARCH=x86_64", output)

    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_validate_flag_iso_mode(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'variables': {
                'DISTRI': 'sle', 'VERSION': '15-SP5', 'FLAVOR': ['Online', 'Full'],
                'ARCH': 'x86_64', '_GROUP_ID': 100, 'ISO': 'dummy.iso'
            }
        }]

        with patch('sys.argv', ['clone_runner.py', '--validate', 'config.yaml']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("ISO post mode", output)
        self.assertIn("Combinations  : 2", output)
        self.assertIn("Commands      : 2", output)

    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_validate_flag_iso_mode_missing_vars(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock):
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'variables': {
                'DISTRI': 'sle', 'VERSION': '15-SP5'
            }
        }]

        with patch('sys.argv', ['clone_runner.py', '--validate', 'config.yaml']):
            clone_runner.main()

        output = mock_stdout.getvalue()
        self.assertIn("Missing", output)
        self.assertIn("FLAVOR", output)
        self.assertIn("ISO", output)

    @WHICH_FOUND
    @patch('subprocess.run')
    @patch('clone_runner.load_configs')
    @patch('pathlib.Path.is_file')
    @patch('sys.stdout', new_callable=StringIO)
    def test_tool_not_in_path(self, mock_stdout: StringIO, mock_is_file: MagicMock, mock_load_configs: MagicMock, mock_subprocess: MagicMock, mock_which: MagicMock):
        mock_which.return_value = None
        mock_is_file.return_value = True
        mock_load_configs.return_value = [{
            'jobs_to_clone': ['https://example.com/t1'],
            'variables': {}
        }]

        with patch('sys.argv', ['clone_runner.py', 'dummy.yaml']):
            with self.assertRaises(SystemExit) as cm:
                clone_runner.main()
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("not found in PATH", mock_stdout.getvalue())

if __name__ == '__main__':
    unittest.main()
