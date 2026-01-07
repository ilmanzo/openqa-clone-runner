# OpenQA Clone Runner

A Python utility to automate the cloning of OpenQA jobs in bulk using YAML configuration files. This wrapper around `openqa-clone-job` allows you to define job sources, variable overrides, and flags in a structured way.

## Prerequisites

1. **Python 3**: Ensure you have Python 3 installed.
2. **OpenQA Client Tools**: The script relies on the `openqa-clone-job` command line tool. Ensure it is installed and available in your system `PATH`.
3. **Python Dependencies**:
   ```bash
   pip install PyYAML
   ```

## Usage

Make the script executable (optional) and run it with a configuration file:

```bash
chmod +x clone_runner.py
./clone_runner.py -c my_config.yaml
```

### Arguments

*   `-c`, `--config` (Required): Path to the YAML configuration file.
*   `-o`, `--output` (Optional): Custom path for the output file containing new job URLs. If omitted, it defaults to `<config_filename>.urls.txt`.
*   `--dry-run`: Print the commands that would be executed without actually running them.

## Configuration File Format

Create a YAML file to define your cloning batch.

**Example `smoke_tests.yaml`:**

```yaml
jobs_to_clone:
  - https://openqa.opensuse.org/tests/123456
  - https://openqa.opensuse.org/tests/789012

flags:
  - --skip-chained-deps

variables:
  TEST: "custom_test_suite"
  CASEDIR: "https://github.com/os-autoinst/os-autoinst-distri-opensuse.git"
```

## Output

Upon success, the script generates a text file containing the URLs of the newly created jobs. You can feed this directly into monitoring tools:

```bash
openqa-mon -i my_config.urls.txt
```