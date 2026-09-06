#!/usr/bin/env python3
"""Print a read-only automatic SVG dispatch plan from one JSON observation."""
import argparse
import json
from pathlib import Path

from _generation_concurrency import blocked_result, plan_dispatch


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key.')
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Path to the current JSON observation; read only.')
    args = parser.parse_args()
    try:
        observation = json.loads(Path(args.input).read_text(encoding='utf-8-sig'), object_pairs_hook=_unique_object)
        result = plan_dispatch(observation)
    except (OSError, ValueError, TypeError, RecursionError):
        result = blocked_result('Cannot read a valid, unambiguous JSON observation from --input.')
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
