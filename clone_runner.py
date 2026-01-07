#!/usr/bin/env python3.11
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

def construct_args(config: Dict[str, Any]) -> List[str]:
    """Builds the arguments list from the YAML config."""
    cmd_args = []
    cmd_args.extend(config.get('flags', []))

    variables = config.get('variables', {})
    if variables:
        for key, value in variables.items():
            if value is not None:
                cmd_args.append(f"{key}={value}")
    return cmd_args

def extract_urls(output_text: str) -> List[str]:
    """Parses output looking for: '- jobname -> https://url...' """
    url_pattern = re.compile(r"->\s+(https?://\S+)")
    return url_pattern.findall(output_text)

def main():
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
    common_args = construct_args(config)
    all_new_urls = []

    jobs_to_clone = config.get('jobs_to_clone', [])
    if not jobs_to_clone:
        print(f"Warning: No 'jobs_to_clone' list found in {args.config}")
        sys.exit(0)

    print(f"Starting clone process using config: {args.config}")
    print(f"Output will be saved to: {output_file}")

    for job_url in jobs_to_clone:
        command = ["openqa-clone-job", "--within-instance", job_url] + common_args

        print(f"\nProcessing: {job_url}")

        if args.dry_run:
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

            new_urls = extract_urls(result.stdout)
            if new_urls:
                print(f"   Extracted {len(new_urls)} new job URLs.")
                all_new_urls.extend(new_urls)
            else:
                print("   No new job URLs found in output.")

        except subprocess.CalledProcessError as e:
            print(f"Error executing clone for {job_url}")
            print(e.stderr)

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