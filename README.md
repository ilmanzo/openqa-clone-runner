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
2. **OpenQA Client Tools**: The script relies on `openqa-clone-job` and `openqa-cli`. Ensure they are installed and available in your system `PATH`. Most likely you'll want to install the `openQA-client` package. 
3. **Python Dependencies**:
   ```bash
   pip install PyYAML
   ```
   or
   ```bash
   zypper install python3-PyYAML
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

when the `jobs_to_clone` entry is missing, the script switches to `openqa-cli api -X post isos` mode. In this mode some variables are mandatory:

```yaml
host: 'openqa.opensuse.org'

variables:
  DISTRI: "sle"
  VERSION: "16.1"
  BUILD: ["73.2", "73.3", "73.4"] # Expands to 3 builds
  FLAVOR: ["Full", "Online"] # Expands to 2 flavors
  ARCH: ["x86_64", "aarch64", "s390x", "ppc64le"] # Expands to 4 architectures  
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

Upon success, the script generates a text file containing the URLs of the newly created jobs. You can feed this directly into monitoring tools:

```bash
openqa-mon -i my_config.urls.txt
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (git checkout -b feature/your-feature).
3. Commit your changes. 
4. Push to the branch and open a Pull Request. 

Please ensure that you run the tests before submitting: 

```bash
python3 -m unittest test_clone_runner.py
```