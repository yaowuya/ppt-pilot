#!/usr/bin/env python3
"""Compute a read-only manuscript review snapshot without granting approval."""
import argparse
import json
import sys

sys.dont_write_bytecode = True

from _review_snapshot import review_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Compute a diagnostic manuscript review snapshot; never grants PASS.')
    parser.add_argument('--run-dir', required=True)
    args = parser.parse_args(argv)
    result = review_snapshot(args.run_dir)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
