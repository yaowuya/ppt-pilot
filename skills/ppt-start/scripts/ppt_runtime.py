#!/usr/bin/env python3
"""Public deterministic PPT visual runtime; emits exactly one JSON document."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
from _runtime_commands import Runtime
from _workflow_gate import GateError
from _host_adapter_runtime import CapabilityError, inspect_host
from _svg_geometry import GeometryError


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest='command', required=True)
    diagnostic = commands.add_parser('inspect-host', help='Read-only adapter/receipt check; no run or live host attestation')
    diagnostic.add_argument('--host', required=True)
    diagnostic.add_argument('--capability', help='Optional regular local JSON receipt; no UNC/device paths or writes')
    definitions = {
        'prepare-batch': ('input', 'capability'), 'dispatch-plan': ('batch-id', 'capability'),
        'reserve-dispatch': ('batch-id', 'slide-id', 'transaction-id', 'capability'),
        'bind-task': ('dispatch-id', 'host-task-id'), 'ingest-result': ('dispatch-id', 'response'),
        'record-generator-failure': ('dispatch-id', 'reason'),
        'record-validation': ('slide-id', 'transaction-id', 'input'),
        'prepare-recovery': ('slide-id', 'transaction-id', 'mode'),
        'revise-visual': ('slide-id', 'transaction-id', 'input'),
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
        if args.command == 'inspect-host':
            result = inspect_host(args.host, args.capability)
        else:
            runtime = Runtime(args.run_dir)
            result = runtime.execute(args)
    except GateError as exc:
        error = exc.error
    except CapabilityError as exc:
        error = {'code': 'generator_unavailable', 'details': exc.details,
                 'reentry_stage': runtime.run.get('stage', 'brief') if runtime else 'installation',
                 'next_action': exc.next_action}
    except GeometryError as exc:
        error = {'code': 'svg_contract_failed', 'details': exc.details,
                 'reentry_stage': runtime.run.get('stage', 'anchor') if runtime else 'anchor',
                 'next_action': 'Run resume for bounded in-place page recovery; preserve the same run, reviewed facts, and passed siblings.'}
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, ValueError) and str(exc).replace('_', '').isalnum() else 'invalid_or_unreadable_evidence'
        actions = {
            'recovery_not_allowed': 'Run resume in the same run and follow its eligible recovery or required visual-revision input; never reset counters or create a replacement run.',
            'recovery_scope_conflict': 'Preserve the same run and passed siblings; use revise-visual for a failed page without modifying frozen manuscript files.',
            'visual_revision_pending': 'Replay the pending visual decision or its recompose recovery in the same run; do not retry its old source transaction.',
            'generation_attempts_exhausted': 'Keep the same run and resolve its existing production blocker; do not reset attempts or create another run.',
            'manuscript_stale': 'Reviewed facts or file bytes changed. Preserve the same run/history and complete the required review; pure visual corrections use revise-visual instead of rewriting the storyboard.',
            'pending_review_round': 'Validate and resume the existing pending review round in the same run; do not create another round or run.',
        }
        error = {'code': code, 'reentry_stage': runtime.run.get('stage', 'brief') if runtime else 'brief',
                 'next_action': actions.get(code, 'Resolve the named canonical owner conflict in the same run and repeat this command; do not create a replacement run.')}
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
