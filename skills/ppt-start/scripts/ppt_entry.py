#!/usr/bin/env python3
"""Select a local PPT Pilot run; creation is explicit and never grants workflow approval."""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat

from _run_store import RunStore, canonical, no_follow, parse_json, sha


def require(condition, code):
    if not condition:
        raise ValueError(code)


def local_syntax(value):
    require(text(value), 'unsafe_entry_path')
    windows = PureWindowsPath(value)
    require(not any(PureWindowsPath(part).is_reserved() for part in windows.parts) and
            not value.replace('\\', '/').startswith(('//', '/??/')) and
            ':' not in value[len(windows.drive):] and
            not (windows.drive and (not windows.root or os.name != 'nt')) and
            all(ord(c) >= 32 and ord(c) != 127 for c in value), 'unsafe_entry_path')


def local_path(value, base):
    local_syntax(value)
    path = Path(value)
    path = path if path.is_absolute() else base / path
    local_syntax(str(path))
    if os.name == 'nt':
        import ctypes
        drive_type = ctypes.WinDLL('kernel32', use_last_error=True).GetDriveTypeW
        drive_type.argtypes, drive_type.restype = (ctypes.c_wchar_p,), ctypes.c_uint
        require(drive_type(path.anchor) != 4, 'unsafe_entry_path')  # DRIVE_REMOTE, before any path probes.
    no_follow(path)  # Check before resolution can erase a link/.. component.
    path = path.resolve()  # Expand Windows 8.3 aliases before deriving the workspace lock identity.
    local_syntax(str(path))  # Resolution must not turn an alias into a UNC/device path.
    if os.name == 'nt':
        require(drive_type(path.anchor) != 4, 'unsafe_entry_path')
    no_follow(path)
    return path


def valid_id(value):
    return (isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,119}', value)
            and not PureWindowsPath(value).is_reserved())


def candidate(root):
    store = RunStore(root)
    names = [name for name in ('.ppt-pilot/run.json', 'run.json') if store.path(name).exists()]
    require(len(names) == 1, 'run_path_conflict' if names else 'run_missing')
    run = parse_json(store.read_bytes(names[0]))
    require(isinstance(run, dict) and type(run.get('schema_version')) is int and
            run['schema_version'] == 1 and run.get('deck_id') == root.name and
            run.get('mode') in ('guided', 'auto'), 'invalid_run_identity')
    return {'root': root, 'store': store, 'name': names[0], 'run': run}


def source_input(value, workspace):
    path = local_path(value, workspace)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), 'unsafe_entry_path')
    require(info.st_size <= 272 * 1024 * 1024, 'source_too_large')
    raw = RunStore(path.parent).read_bytes(path.name)
    require(len(raw) <= 272 * 1024 * 1024, 'source_too_large')
    return {'source_path': str(path), 'sha256': sha(raw)[7:]}


def source_match(item, source):
    if source is None:
        return 'match'
    binding = item['run'].get('source_deck', item['run'].get('entry_source'))
    if not isinstance(binding, dict) or not text(binding.get('source_path')):
        return 'uncertain'
    require(Path(binding['source_path']).is_absolute(), 'invalid_source_binding')
    bound = local_path(binding['source_path'], item['root'])
    same_path = os.path.normcase(str(bound)) == os.path.normcase(source['source_path'])
    digest = binding.get('sha256')
    if 'source_deck' in item['run']:
        digest = None  # The actual source inventory, not a hand-written run field, owns this SHA.
        name = binding.get('inventory')
        if name is not None:
            require(isinstance(name, str) and '/' not in name and name.endswith('.json'), 'unsafe_entry_path')
            try:
                raw = item['store'].read_bytes('.ppt-pilot/' + name)
            except FileNotFoundError:
                raw = None
            if raw is not None:
                try:
                    inventory = parse_json(raw)
                except (ValueError, RecursionError):
                    return 'uncertain'
                if (not isinstance(inventory, dict) or type(inventory.get('schema_version')) is not int or
                        inventory['schema_version'] != 1 or inventory.get('kind') != 'pptx_source_inventory' or
                        not isinstance(inventory.get('source'), dict)):
                    return 'uncertain'
                digest = inventory['source'].get('sha256')
                if digest is None:
                    return 'uncertain'
    if digest is not None:
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            return 'uncertain'
        if digest == source['sha256']:
            return 'match'
        return 'uncertain' if same_path else 'different'
    return 'match' if same_path else 'uncertain'


def discover(workspace, source):
    output = workspace.path('ppt-output')
    if not output.exists():
        return []
    require(output.is_dir(), 'unsafe_entry_path')
    found = []
    for root in sorted(output.iterdir()):
        no_follow(root)
        if not root.is_dir():
            continue
        store = RunStore(root)
        if not any(store.path(name).exists() for name in ('.ppt-pilot/run.json', 'run.json')):
            continue
        require(valid_id(root.name), 'invalid_run_id')
        item = candidate(root)
        item['match'] = source_match(item, source)
        if item['match'] != 'different':
            found.append(item)
    return found


def ready(item, created=False):
    return {'status': 'READY', 'run_dir': str(item['root']), 'run_id': item['run']['deck_id'],
            'mode': item['run']['mode'], 'created': created, 'reused': not created,
            'next_command': 'audit-run', 'writes': [],
            'audit_command': [sys.executable, '-B', str(Path(__file__).with_name('ppt_workflow_gate.py')),
                              '--run-dir', str(item['root']), '--audit-run']}


SELECTION = 'ppt-output/run-selection.json'


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_selection(route):
    require(isinstance(route, dict) and type(route.get('schema_version')) is int and
            route['schema_version'] == 1 and route.get('kind') == 'run_selection' and
            route.get('entry_action') in ('resume', 'revise') and
            route.get('status') in ('pending', 'answered') and 'stage' not in route and
            text(route.get('question')), 'run_selection_conflict')
    payload, ids = route.get('operation_payload'), route.get('candidates')
    require(isinstance(payload, dict) and text(payload.get('request')) and
            isinstance(ids, list) and ids and all(valid_id(i) for i in ids) and
            len({os.path.normcase(i) for i in ids}) == len(ids), 'run_selection_conflict')
    if 'source' in payload:
        source = payload['source']
        require(isinstance(source, dict) and set(source) == {'source_path', 'sha256'} and
                text(source['source_path']) and Path(source['source_path']).is_absolute() and
                isinstance(source['sha256'], str) and re.fullmatch('[0-9a-f]{64}', source['sha256']),
                'run_selection_conflict')
        local_path(source['source_path'], Path.cwd())
    if 'requested_new_run_id' in payload:
        require(valid_id(payload['requested_new_run_id']) and route['entry_action'] == 'resume', 'run_selection_conflict')
    if 2 <= len(ids) <= 4:
        require(route.get('options') == ids and isinstance(route.get('option_effects'), dict) and
                set(route['option_effects']) == set(ids) and all(text(v) for v in route['option_effects'].values()) and
                route.get('recommendation') in ids and text(route.get('recommendation_reason')),
                'run_selection_conflict')
    else:
        require(not {'options', 'option_effects', 'recommendation', 'recommendation_reason'}.intersection(route),
                'run_selection_conflict')
    if route['status'] == 'pending':
        require('answer' not in route and 'decision' not in route, 'run_selection_conflict')
    if route['status'] == 'answered':
        require(text(route.get('answer')), 'run_selection_conflict')
        if 'options' in route:
            require(route.get('decision') in ids, 'run_selection_conflict')
        else:
            require(route['answer'] in ids and 'decision' not in route, 'run_selection_conflict')


def choose(workspace, route):
    return {'status': 'CHOICE_REQUIRED', 'selection': route,
            'selection_file': str(workspace.path(SELECTION)), 'created': False, 'reused': False,
            'next_command': 'select-run', 'writes': list(workspace.writes)}


def replay_selection(workspace, args, route, source, repeated_new=False):
    selected = None if repeated_new else args.run_id
    pending = route['status'] == 'pending'
    if pending:
        for run_id in route['candidates']:
            item = candidate(workspace.path('ppt-output/' + run_id))
            require(source_match(item, source) != 'different', 'run_selection_conflict')
        if selected is None:
            require(args.answer is None, 'selection_answer_required')
            return choose(workspace, route)
        require(selected in route['candidates'], 'run_selection_conflict')
        require(text(args.answer), 'selection_answer_required')
        if 'options' not in route:
            require(args.answer == selected, 'selection_answer_required')
        route = dict(route, status='answered', answer=args.answer)
        if 'options' in route:
            route['decision'] = selected
    run_id = route.get('decision', route['answer'])
    require(selected is None or selected == run_id, 'run_selection_conflict')
    require(args.answer is None or args.answer == route['answer'], 'run_selection_conflict')
    store = RunStore(workspace.path('ppt-output/' + run_id))
    with store.lock():
        item = candidate(store.root)
        require(source_match(item, source) != 'different', 'run_selection_conflict')
        if pending:
            workspace.write_json(SELECTION, route, workspace.observed[SELECTION])
        result = ready(item)
        result.update(entry_action=route['entry_action'], operation_payload=route['operation_payload'],
                      selection=route, selection_file=str(workspace.path(SELECTION)),
                      selection_sha256=workspace.observed[SELECTION], writes=list(workspace.writes))
        # Routing has not advanced the workflow. Downstream owns deletion after its next durable state.
        return result


def create_run(workspace, args, source, payload, effects):
    output = workspace.path('ppt-output')
    if not output.exists():
        output.mkdir(mode=0o700)
        effects['directories_created'].append('ppt-output')
    prefix = 'ppt-output/' + args.run_id
    root = workspace.path(prefix)
    root.mkdir(mode=0o700)  # Exclusive claim: never overwrite or suffix a failed/foreign root.
    effects['directories_created'].append(prefix)
    effects.update(run_dir=str(root), partial_creation=True)
    store = RunStore(root)
    run = {'schema_version': 1, 'deck_id': args.run_id, 'mode': args.mode or 'guided',
           'stage': 'brief', 'dirty_slides': [], 'manuscript_review': {
               'required': True, 'cycle': 1, 'round': 0, 'mode': 'pending', 'state': 'pending',
               'status': 'PENDING', 'latest_report': '文稿审查.md',
               'open_blocking_findings': [], 'review_history': []}}
    if source:
        # Bootstrap routing hint only. Real intake, never entry, owns source_deck and its inventory.
        run['entry_source'] = source
    try:
        with store.lock():
            store.path('.ppt-pilot').mkdir(mode=0o700)
            effects['directories_created'].append(prefix + '/.ppt-pilot')
            store.write_json('.ppt-pilot/run.json', run, 'none')
            result = ready(candidate(root), created=True)
    finally:
        effects['writes'].extend(prefix + '/' + name for name in store.writes)
        effects['created'] = bool(store.writes)  # Publication may precede a failed reread.
    result.update(entry_action='new', operation_payload=payload, writes=list(effects['writes']),
                  directories_created=list(effects['directories_created']))
    return result


def enter(args, effects):
    require(args.run_id is None or valid_id(args.run_id), 'invalid_run_id')
    require(args.request is None or text(args.request), 'request_required')
    require(not args.allow_duplicate or args.action == 'new', 'new_action_required')
    require(args.mode is None or args.action == 'new', 'new_action_required')
    require(args.action != 'new' or args.run_id is not None, 'new_run_id_required')
    workspace = RunStore(local_path(args.workspace, Path.cwd()))
    effects['writes'] = workspace.writes
    # ponytail: one workspace lock serializes entry; shard only if entry throughput requires it.
    with workspace.lock():
        source = source_input(args.source, workspace.root) if args.source is not None else None
        if workspace.path(SELECTION).exists():
            route = workspace.read_json(SELECTION)
            validate_selection(route)
            payload = route['operation_payload']
            repeated_new = (args.action == 'new' and route['entry_action'] == 'resume' and
                            payload.get('requested_new_run_id') == args.run_id and
                            not args.allow_duplicate and args.answer is None)
            require(args.action is None or args.action == route['entry_action'] or repeated_new, 'run_selection_conflict')
            require(args.request is None or args.request == payload['request'], 'run_selection_conflict')
            saved = payload.get('source')
            current = source_input(saved['source_path'], workspace.root) if saved else None
            if saved:
                require(current['sha256'] == saved['sha256'], 'source_identity_conflict')
            if source:
                require(current is not None and source['sha256'] == current['sha256'] and
                        os.path.normcase(source['source_path']) == os.path.normcase(current['source_path']), 'run_selection_conflict')
            return replay_selection(workspace, args, route, current, repeated_new)
        require(args.answer is None, 'run_selection_missing')
        action = args.action or 'resume'
        require(action != 'revise' or text(args.request), 'request_required')
        payload = {'request': args.request if args.request is not None else 'Continue the existing run.'}
        if source:
            payload['source'] = source
        if action == 'new':
            payload['requested_new_run_id'] = args.run_id
        target = workspace.path('ppt-output/' + args.run_id) if args.run_id else None
        explicit = target is not None and (target.exists() or action != 'new')
        if explicit:
            found = [candidate(target)]
            require(source_match(found[0], source) == 'match' if action == 'new' else
                    source_match(found[0], source) != 'different', 'source_identity_conflict')
        else:
            found = discover(workspace, source)
            if action == 'new' and (source is None or args.allow_duplicate or not found):
                return create_run(workspace, args, source, payload, effects)
        require(found, 'run_not_found')
        action = 'resume' if action == 'new' else action
        if len(found) > 1 or (not explicit and found[0].get('match') == 'uncertain'):
            ids = [item['run']['deck_id'] for item in found]
            route = {'schema_version': 1, 'kind': 'run_selection', 'entry_action': action,
                     'operation_payload': payload, 'status': 'pending',
                     'question': 'Which existing run should continue? Reply with its exact run ID.',
                     'candidates': ids}
            if 2 <= len(ids) <= 4:
                route.update(options=ids, option_effects={i: 'Resume only ' + i + ' through audit-run.' for i in ids},
                             recommendation=ids[0], recommendation_reason='First run in stable ID order; not approval or an automatic choice.')
            for item in found:
                expected = item['store'].observed[item['name']]
                require(item['store'].hash(item['name']) == expected, 'run_selection_conflict')
            workspace.write_bytes(SELECTION, canonical(route), 'none')
            return choose(workspace, route)
        with found[0]['store'].lock():
            item = candidate(found[0]['root'])
            match = source_match(item, source)
            require(match == 'match' if args.action == 'new' or not explicit else match != 'different',
                    'source_identity_conflict')
            result = ready(item)
            result.update(entry_action=action, operation_payload=payload)
            return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--source')
    parser.add_argument('--action', choices=('resume', 'revise', 'new'))
    parser.add_argument('--request')
    parser.add_argument('--run-id')
    parser.add_argument('--answer')
    parser.add_argument('--allow-duplicate', action='store_true')
    parser.add_argument('--mode', choices=('guided', 'auto'))
    args = parser.parse_args(argv)
    effects = {'created': False, 'writes': [], 'directories_created': []}
    try:
        result = enter(args, effects)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, ValueError) and re.fullmatch(r'[a-z_]+', str(exc)) else 'invalid_or_unreadable_entry'
        result = dict(effects, status='BLOCKED', errors=[{'code': code}])
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    sys.exit(main())
