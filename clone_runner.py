#!/usr/bin/env python3.11
import json
import itertools
import yaml
import subprocess
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = set()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate key '{key}' found in YAML at line {key_node.start_mark.line + 1}")
            mapping.add(key)
        return super().construct_mapping(node, deep)

def load_configs(config_path: Path) -> List[Dict[str, Any]]:
    try:
        with config_path.open('r', encoding='utf-8') as file:
            return [doc for doc in yaml.load_all(file, Loader=UniqueKeyLoader) if doc is not None]
    except (yaml.YAMLError, ValueError) as e:
        raise ValueError(f"Error parsing YAML file '{config_path}': {e}") from e

def extract_urls(output_text: str) -> List[str]:
    """Parses output looking for: '- jobname -> https://url...' """
    url_pattern = re.compile(r"->\s+(https?://\S+)")
    return url_pattern.findall(output_text)

def validate_variables(variables: Dict[str, Any]) -> None:
    if not variables:
        return
    for key, value in variables.items():
        if key != key.upper():
            raise ValueError(f"Error: Variable '{key}' must be uppercase.")
        if isinstance(value, str) and not value:
            raise ValueError(f"Error: Variable '{key}' cannot be an empty string.")
        if isinstance(value, list):
            if any(isinstance(item, str) and not item for item in value):
                raise ValueError(f"Error: Variable '{key}' contains an empty string in the list.")

def expand_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Iteratively expands variables referencing other variables (e.g. %VAR%).
    Returns a new dictionary with expanded values.
    """
    expanded_vars = variables.copy()
    limit_hit = True
    for _ in range(5):
        changes = 0
        for key, val in expanded_vars.items():
            if isinstance(val, str) and '%' in val:
                new_val = re.sub(r'%(\w+)%', lambda m: str(expanded_vars.get(m.group(1), m.group(0))), val)
                if new_val != val:
                    expanded_vars[key] = new_val
                    changes += 1
        if changes == 0:
            limit_hit = False
            break

    if limit_hit:
        print("Warning: Variable expansion hit the iteration limit (5). Circular dependency or deep nesting detected.")

    # Check for undefined variables remaining in values
    for key, val in expanded_vars.items():
        if isinstance(val, str) and '%' in val:
            for var_name in set(re.findall(r'%(\w+)%', val)):
                if var_name not in expanded_vars:
                    print(f"Warning: Variable '%{var_name}%' referenced in '{key}' is not defined.")

    return expanded_vars

def execute_command(command: List[str], dry_run: bool, error_context: str) -> str | None:
    """Executes a subprocess command, handling dry-run and errors."""
    if dry_run:
        print(f"[DRY RUN] Would execute: {' '.join(command)}")
        return None

    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing {error_context}")
        print(e.stderr)
        return None

def run_clone_jobs(jobs_to_clone: List[str], flags: List[str], variables: Dict[str, Any], dry_run: bool) -> List[str]:
    new_urls = []
    for job_url in jobs_to_clone:
        command = ["openqa-clone-job", "--within-instance", job_url] + flags
        # Add variables
        for key, value in variables.items():
            if value is not None:
                command.append(f"{key}={value}")

        print(f"\nProcessing: {job_url}")

        output = execute_command(command, dry_run, f"clone for {job_url}")
        if output:
            extracted = extract_urls(output)
            if extracted:
                print(f"   Extracted {len(extracted)} new job URLs.")
                new_urls.extend(extracted)
            else:
                print("   No new job URLs found in output.")
    return new_urls

def run_iso_post(config: Dict[str, Any], flags: List[str], dry_run: bool) -> List[str]:
    required_vars = ['DISTRI', 'VERSION', 'FLAVOR', 'ARCH', '_GROUP_ID']
    variables = config.get('variables') or {}
    missing = [var for var in required_vars if var not in variables]
    if missing:
        print(f"Error: Missing required variables for ISO post: {', '.join(missing)}")
        sys.exit(1)

    # Separate scalar variables and list variables for expansion
    scalars = {}
    lists = {}
    for k, v in variables.items():
        if isinstance(v, list):
            lists[k] = v
        elif v is not None:
            scalars[k] = v

    # Generate all combinations of list variables
    list_keys = list(lists.keys())
    list_values = list(lists.values())
    combinations = list(itertools.product(*list_values)) if list_values else [()]

    all_new_urls = []

    # Determine host for URL construction once
    host = config.get('host')
    if host:
        if '--osd' in flags and 'suse.de' not in host:
            print(f"Error: Conflicting options: 'host' set to '{host}' but '--osd' flag provided.")
            sys.exit(1)
        if '--o3' in flags and 'opensuse.org' not in host:
            print(f"Error: Conflicting options: 'host' set to '{host}' but '--o3' flag provided.")
            sys.exit(1)
    else:
        host = 'https://openqa.suse.de'
        if '--osd' in flags:
            host = 'https://openqa.suse.de'
        elif '--o3' in flags:
            host = 'https://openqa.opensuse.org'
    host = host.rstrip('/')

    for combo in combinations:
        # Merge scalars with current combination
        current_vars = scalars.copy()
        for i, key in enumerate(list_keys):
            current_vars[key] = combo[i]

        current_vars = expand_variables(current_vars)

        # Construct command
        command = ["openqa-cli", "api", "-X", "post", "isos"] + flags
        for key, value in current_vars.items():
            command.append(f"{key}={value}")

        output = execute_command(command, dry_run, "ISO post command")
        if output:
            try:
                data = json.loads(output)
                job_ids = data.get('ids', [])

                if job_ids:
                    print(f"   Extracted {len(job_ids)} new job IDs.")
                    all_new_urls.extend([f"{host}/t{jid}" for jid in job_ids])
            except json.JSONDecodeError:
                print("   Warning: Output was not valid JSON. Could not extract job IDs.")

    return all_new_urls

def print_help_page() -> None:
    print("""OpenQA Clone Automator

Usage:
    clone_runner.py <config.yaml>... [options]

Description:
    Automates cloning of OpenQA jobs or posting of ISOs based on a YAML configuration.

Options:
    -o, --output    Custom output file path (optional).
    --dry-run       Print commands without executing.

--- Configuration Examples ---

[1] Clone Jobs Mode
    Use this to clone existing jobs with modified variables.

    # config_clone.yaml
    jobs_to_clone:
      - https://openqa.suse.de/tests/123456

    variables:
      ARCH: x86_64
      BUILD: '150'

    flags:
      - --skip-chained-deps

[2] ISO Post Mode
    Use this to post ISOs and trigger new jobs.

    # config_iso.yaml
    variables:
      DISTRI: sle
      VERSION: 15-SP5
      FLAVOR: [Online, Full]
      ARCH: x86_64
      BUILD: '150'
      _GROUP_ID: 100
      ISO: 'SLE-%VERSION%-%FLAVOR%-%ARCH%-Build%BUILD%-Media1.iso'

    flags:
      - --osd
""")

def main() -> None:
    parser = argparse.ArgumentParser(description="OpenQA Clone Automator", add_help=False)
    parser.add_argument("-h", "--help", action="store_true", help="Show this help message and exit")
    parser.add_argument("config_files", type=Path, nargs='*', help="Path to YAML config file(s)")
    # Output is now optional; if not provided, we generate it from the config name
    parser.add_argument("-o", "--output", type=Path, help="Custom output file path (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    if args.help or not args.config_files:
        print_help_page()
        sys.exit(0 if args.help else 1)

    # Warn if -o is used with multiple inputs, as we will ignore it or it's ambiguous
    if args.output and len(args.config_files) > 1:
        print("Warning: --output flag is ignored when multiple configuration files are provided. "
              "Output files will be named based on input files.")

    for config_path in args.config_files:
        if not config_path.is_file():
            print(f"Error: Config file '{config_path}' not found.")
            sys.exit(1)

        try:
            configs = load_configs(config_path)
        except ValueError as e:
            print(e)
            sys.exit(1)

        current_file_urls = []
        for i, config in enumerate(configs):
            variables = config.get('variables', {})
            validate_variables(variables)

            flags = config.get('flags', [])
            jobs_to_clone = config.get('jobs_to_clone', [])

            doc_label = f"doc {i+1}" if len(configs) > 1 else "doc"

            if jobs_to_clone:
                print(f"Starting clone process using config from: {config_path} [{doc_label}]")
                new_urls = run_clone_jobs(jobs_to_clone, flags, variables, args.dry_run)
            else:
                print(f"Starting ISO post process using config from: {config_path} [{doc_label}]")
                new_urls = run_iso_post(config, flags, args.dry_run)

            if new_urls:
                current_file_urls.extend(new_urls)

        if not args.dry_run and current_file_urls:
            output_file = args.output if (args.output and len(args.config_files) == 1) else config_path.with_name(f"{config_path.stem}.urls.txt")
            print("\n" + "="*40)
            with output_file.open("w", encoding="utf-8") as f:
                for url in current_file_urls:
                    f.write(url + "\n")
            print(f"Success! {len(current_file_urls)} URLs saved to '{output_file}'")
            print(f"You can now run: openqa-mon -i {output_file}")
            print("="*40)

if __name__ == "__main__":
    main()
