# OpenQA Clone Runner

A Python utility to automate the cloning of OpenQA jobs in bulk or posting new ISO assets using YAML configuration files. This wrapper around `openqa-clone-job` and `openqa-cli` allows you to define job sources, variable overrides, and flags in a structured way.

## Table of Contents

- Prerequisites
- Usage
  - Arguments
- Configuration File Format
  - Variable Expansion
- Output
- Running Tests
- Contributing

## Prerequisites

1. **Python 3**: Ensure you have Python 3 installed.
2. **OpenQA Client Tools**: The script relies on `openqa-clone-job` and `openqa-cli`. Ensure they are installed and available in your system `PATH`. Most likely you'll want to install the `openQA-client` package. `openqa-mon` is also required if you use `--watch`.
3. **Python Dependencies**:
   ```bash
   pip install PyYAML
   ```
   or
   ```bash
   zypper install python3-PyYAML
   ```
  

## Usage

Make the script executable (optional) and run it with one or more configuration files:

```bash
chmod +x clone_runner.py
./clone_runner.py my_config.yaml
./clone_runner.py config_a.yaml config_b.yaml   # multiple files, each runs independently
```

### Arguments

*   `config_files` (Required): One or more paths to YAML configuration files (positional, repeatable).
*   `-o`, `--output` (Optional): Custom output path for the new-job-URL file. Ignored when more than one config file is given. If omitted, output is named `<config_stem>.<timestamp>.urls.txt` next to the config file.
*   `--dry-run`: Print the commands that would be executed without running them.
*   `--validate`: Print a summary of what each config would do, then exit without running anything.
*   `--watch`: After writing the URL file, launch `openqa-mon -i <file>` automatically.
*   `-h`, `--help`: Show the built-in help page and exit.

## Configuration File Format

The script supports two modes. 
1) for **jobs cloning** , create a YAML file to define your cloning batch.

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

2) post isos

when the `jobs_to_clone` entry is missing, the script switches to `openqa-cli api -X post isos` mode. In this mode some variables are mandatory.

The optional `host:` field selects the target openQA server (scheme defaults to `https://` if omitted). It is mutually exclusive with the `--osd` and `--o3` shorthand flags, which target `openqa.suse.de` and `openqa.opensuse.org` respectively.

```yaml
host: 'openqa.opensuse.org'

variables:
  DISTRI: "sle"
  VERSION: "16.1"
  BUILD: ["73.2", "73.3", "73.4"] # Expands to 3 builds
  FLAVOR: ["Full", "Online"] # Expands to 2 flavors
  ARCH: ["x86_64", "aarch64", "s390x", "ppc64le"] # Expands to 4 architectures  
  _GROUP_ID: 100
  ISO: "SLE-%VERSION%-%ARCH%-Build%BUILD%-Media1.iso"
```

running with this configuration, it will result to a total of 3*2*4 = 24 ISO post API calls, which, depending on the job template, can result in tens or hundreds of job spawned. **Take care!**


### Variable Expansion

You can reference other variables within variable values using the `%VAR%` syntax. This is particularly useful for constructing dynamic strings like ISO filenames.

**Example:**

```yaml
variables:
  VERSION: "15-SP5"
  ARCH: "x86_64"
  ISO: "SLE-%VERSION%-%ARCH%-Media1.iso" 
  # ISO becomes "SLE-15-SP5-x86_64-Media1.iso"
```

## Output

Upon success, the script generates a text file named `<config_stem>.<timestamp>.urls.txt` containing the URLs of the newly created jobs. You can feed this into monitoring tools, or use `--watch` to launch the monitor automatically:

```bash
openqa-mon -i my_config.20240624-1430.urls.txt
# or just:
./clone_runner.py my_config.yaml --watch
```

## Running Tests

```bash
python3 -m unittest test_clone_runner.py
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (git checkout -b feature/your-feature).
3. Commit your changes. 
4. Push to the branch and open a Pull Request. 

Please run the tests before submitting (see [Running Tests](#running-tests)).