#!/usr/bin/env python3
"""CLI for read-only import evidence checks and diagnostic current hashes."""
import argparse
import json

from _workflow_gate import STAGES, check_run, check_active_batch, snapshot_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--before', choices=STAGES)
    action.add_argument('--snapshot', action='store_true', help='Current hashes only; never approves or writes evidence.')
    action.add_argument('--resume-active-batch', action='store_true', help='Revalidate import inputs before active-batch recovery side effects.')
    args = parser.parse_args()
    if args.snapshot:
        result = snapshot_run(args.run_dir)
    elif args.resume_active_batch:
        result = check_active_batch(args.run_dir)
    else:
        result = check_run(args.run_dir, args.before)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
