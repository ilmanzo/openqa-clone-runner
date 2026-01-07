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

def load_config(config_path: Path) -> Dict[str, Any]:
    try:
        with config_path.open('r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{config_path}': {e}")
        sys.exit(1)

def extract_urls(output_text: str) -> List[str]:
    """Parses output looking for: '- jobname -> https://url...' """
    url_pattern = re.compile(r"->\s+(https?://\S+)")
    return url_pattern.findall(output_text)

def run_clone_jobs(jobs_to_clone: List[str], flags: List[str], variables: Dict[str, Any], dry_run: bool) -> List[str]:
    new_urls = []
    for job_url in jobs_to_clone:
        command = ["openqa-clone-job", "--within-instance", job_url] + flags
        # Add variables
        for key, value in variables.items():
            if value is not None:
                command.append(f"{key}={value}")

        print(f"\nProcessing: {job_url}")

        if dry_run:
            print(f"[DRY RUN] Would execute: {' '.join(command)}")
            continue

        try:
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True
            )
            print(result.stdout)

            extracted = extract_urls(result.stdout)
            if extracted:
                print(f"   Extracted {len(extracted)} new job URLs.")
                new_urls.extend(extracted)
            else:
                print("   No new job URLs found in output.")

        except subprocess.CalledProcessError as e:
            print(f"Error executing clone for {job_url}")
            print(e.stderr)
    return new_urls

def run_iso_post(config: Dict[str, Any], flags: List[str], dry_run: bool) -> List[str]:
    required_vars = ['DISTRI', 'VERSION', 'FLAVOR', 'ARCH', '_GROUP_ID']
    variables = config.get('variables') or {}
    missing = [var for var in required_vars if var not in variables]
    if missing:
        print(f"Error: Missing required variables for ISO post: {', '.join(missing)}")
        sys.exit(1)

    # Separate scalar variables and list variables for expansion
    scalars = {k: v for k, v in variables.items() if not isinstance(v, list) and v is not None}
    lists = {k: v for k, v in variables.items() if isinstance(v, list)}

    # Generate all combinations of list variables
    list_keys = list(lists.keys())
    list_values = list(lists.values())
    combinations = list(itertools.product(*list_values)) if list_values else [()]

    all_new_urls = []

    for combo in combinations:
        # Merge scalars with current combination
        current_vars = scalars.copy()
        for i, key in enumerate(list_keys):
            current_vars[key] = combo[i]

        # Construct command
        command = ["openqa-cli", "api", "-X", "post", "isos"] + flags
        for key, value in current_vars.items():
            command.append(f"{key}={value}")

        if dry_run:
            print(f"[DRY RUN] Would execute: {' '.join(command)}")
            continue

        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            print(result.stdout)

            try:
                data = json.loads(result.stdout)
                job_ids = data.get('ids', [])

                # Determine host for URL construction
                host = config.get('host', 'https://openqa.suse.de')
                if 'host' not in config:
                    if '--osd' in flags:
                        host = 'https://openqa.suse.de'
                    elif '--o3' in flags:
                        host = 'https://openqa.opensuse.org'
                host = host.rstrip('/')

                if job_ids:
                    print(f"   Extracted {len(job_ids)} new job IDs.")
                    all_new_urls.extend([f"{host}/t{jid}" for jid in job_ids])
            except json.JSONDecodeError:
                print("   Warning: Output was not valid JSON. Could not extract job IDs.")

        except subprocess.CalledProcessError as e:
            print(f"Error executing ISO post command")
            print(e.stderr)
            # We don't exit here to allow other combinations to proceed
            # sys.exit(1)

    return all_new_urls

def main() -> None:
    parser = argparse.ArgumentParser(description="OpenQA Clone Automator")
    parser.add_argument("-c", "--config", required=True, type=Path, help="Path to YAML config file")
    # Output is now optional; if not provided, we generate it from the config name
    parser.add_argument("-o", "--output", type=Path, help="Custom output file path (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    # Determine output filename automatically if not provided
    if args.output:
        output_file = args.output
    else:
        # e.g., 'configs/my_test.yaml' -> 'my_test.urls.txt'
        output_file = args.config.with_name(f"{args.config.stem}.urls.txt")

    if not args.config.exists():
        print(f"Error: Config file '{args.config}' not found.")
        sys.exit(1)

    config = load_config(args.config)
    flags = config.get('flags', [])
    variables = config.get('variables', {})

    jobs_to_clone = config.get('jobs_to_clone', [])
    if jobs_to_clone:
        print(f"Starting clone process using config: {args.config}")
        print(f"Output will be saved to: {output_file}")
        all_new_urls = run_clone_jobs(jobs_to_clone, flags, variables, args.dry_run)
    else:
        print(f"No 'jobs_to_clone' found. Switching to ISO post mode.")
        all_new_urls = run_iso_post(config, flags, args.dry_run)

    # Save to the automatically named file
    if not args.dry_run and all_new_urls:
        with output_file.open("w", encoding="utf-8") as f:
            for url in all_new_urls:
                f.write(url + "\n")

        print("\n" + "="*40)
        print(f"Success! URLs saved to '{output_file}'")
        print(f"You can now run:\n   openqa-mon -i {output_file}")
        print("="*40)

if __name__ == "__main__":
    main()