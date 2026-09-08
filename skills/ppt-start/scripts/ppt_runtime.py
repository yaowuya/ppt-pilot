#!/usr/bin/env python3
"""Public deterministic PPT visual runtime; emits exactly one JSON document."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from _runtime_commands import Runtime
from _workflow_gate import GateError


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest='command', required=True)
    definitions = {
        'prepare-batch': ('input', 'capability'), 'dispatch-plan': ('batch-id', 'capability'),
        'reserve-dispatch': ('batch-id', 'slide-id', 'transaction-id', 'capability'),
        'bind-task': ('dispatch-id', 'host-task-id'), 'ingest-result': ('dispatch-id', 'response'),
        'record-generator-failure': ('dispatch-id', 'reason'),
        'record-validation': ('slide-id', 'transaction-id', 'input'),
        'prepare-recovery': ('slide-id', 'transaction-id', 'mode'),
        'promote': ('batch-id', 'expected-manifest-sha256'),
        'publish-anchors': ('batch-id', 'expected-manifest-sha256'), 'resume': (), 'migrate-v1': ()}
    for name, fields in definitions.items():
        command = commands.add_parser(name)
        command.add_argument('--run-dir', required=True)
        for field in fields:
            choices = {'reason': ('generator_refused', 'generator_timeout', 'generator_unavailable'),
                       'mode': ('retry', 'recompose', 'fallback')}.get(field)
            command.add_argument('--' + field, required=True, **({'choices': choices} if choices else {}))
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    runtime = None
    result, error = None, None
    try:
        runtime = Runtime(args.run_dir)
        result = runtime.execute(args)
    except GateError as exc:
        error = exc.error
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, ValueError) and str(exc).replace('_', '').isalnum() else 'invalid_or_unreadable_evidence'
        error = {'code': code, 'reentry_stage': runtime.run.get('stage', 'brief') if runtime else 'brief',
                 'next_action': 'Resolve the named canonical owner conflict and repeat this command.'}
    store = runtime.store if runtime else None
    response = {'status': 'BLOCKED' if error else 'PASS', 'command': args.command,
        'run_sha256': store.observed.get(runtime.run_name) if store else None,
        'state': runtime.run.get('stage') if runtime else None,
        'writes': list(store.writes) if store else [],
        'next_action': error['next_action'] if error else (result or {}).get('next_command', 'Continue the canonical workflow.')}
    if error:
        response['errors'] = [error]
        response['observed_hashes'] = dict(store.observed) if store else {}
    elif result is not None:
        response['result'] = result
    print(json.dumps(response, ensure_ascii=True, sort_keys=True))
    return 2 if error else 0


if __name__ == '__main__':
    sys.exit(main())
