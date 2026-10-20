"""Verify all original native fixtures, frozen identities and model assets."""
import argparse
import json
from pathlib import Path
from reproducibility import DEFAULT_CONFIG, load_config, verify_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--fixture-dir', type=Path, help='Optional externally restored original layout')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error('Output already exists')
    report = verify_inputs(load_config(args.config), args.fixture_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(report['status'] != 'PASS')


if __name__ == '__main__':
    main()
