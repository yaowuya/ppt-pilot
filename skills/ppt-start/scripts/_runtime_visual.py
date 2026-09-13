"""Failed-page visual decisions; frozen manuscript owners are never materialized."""
from argparse import Namespace
import re

import _prompt_runtime as prompt
from _generation_runtime import validate_v2_transaction, _transaction_ref
from _run_store import canonical, sha

REQUEST_FIELDS = {'schema_version', 'kind', 'request_id', 'expected_run_sha256', 'changes', 'answer'}
RECORD_FIELDS = {'id', 'kind', 'projection', 'stage', 'affected_scope', 'status', 'artifact_owner',
    'supersedes', 'normalized_changes', 'answer', 'request_id', 'expected_run_sha256',
    'source_transaction_id', 'review_snapshot_id'}


def require(value, code='invalid_runtime_input'):
    if not value:
        raise ValueError(code)


def bounded_text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def changes(value):
    require(isinstance(value, dict) and value and set(value) <= {'layout_family', 'visual_intent'})
    normalized = {}
    for key, text in value.items():
        require(bounded_text(text, 128 if key == 'layout_family' else 2000) and
                not any(ord(c) < 32 or ord(c) == 127 for c in text))
        text = text.strip()
        prompt._reject_unsafe_replacement(text.encode('utf-8'))
        require(not prompt.SOURCE_ANNOTATION_RE.search(text.encode('utf-8')), 'prompt_preflight_invalid')
        normalized[key] = text
    return normalized


def request_fields(value):
    require(isinstance(value.get('request_id'), str) and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value['request_id']))
    require(isinstance(value.get('expected_run_sha256'), str) and
            re.fullmatch(r'sha256:[0-9a-f]{64}', value['expected_run_sha256']))
    require(bounded_text(value.get('answer'), 8192))


def visual_revisions(store, run, slides, review_id, materialized):
    """Validate native history separately from legacy board-materialized revisions."""
    records, requests, sources, transactions = {}, set(), set(), []
    for rid, record in run.get('interaction_history', {}).items():
        if not isinstance(record, dict) or (record.get('projection') != 'runtime_visual' and
                (record.get('kind') != 'visual_revision' or 'projection' not in record)):
            continue
        require(set(record) == RECORD_FIELDS and record.get('projection') == 'runtime_visual' and
                record.get('kind') == 'visual_revision' and record.get('status') == 'applied' and
                record.get('id') == rid and re.fullmatch(r'visual-revision-[1-9][0-9]*', rid) and
                rid not in materialized, 'prompt_snapshot_conflict')
        scope = record['affected_scope']
        require(isinstance(scope, list) and len(scope) == 1 and isinstance(scope[0], str) and
                scope[0] in slides and record['stage'] in ('anchor', 'production') and
                record['review_snapshot_id'] == review_id and record['supersedes'] == [] and
                record['artifact_owner'] in ('.ppt-pilot/run.json', 'run.json'), 'prompt_snapshot_conflict')
        request_fields(record)
        require(changes(record['normalized_changes']) == record['normalized_changes'], 'prompt_snapshot_conflict')
        txid = record['source_transaction_id']
        require(isinstance(txid, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', txid), 'prompt_snapshot_conflict')
        source = (scope[0], txid)
        require(record['request_id'] not in requests and source not in sources, 'prompt_snapshot_conflict')
        requests.add(record['request_id'])
        sources.add(source)
        ref = '.ppt-pilot/visual-generation-transactions/' + scope[0] + '-' + txid[7:] + '.json'
        tx = store.read_json(ref)
        validate_v2_transaction(tx)
        require(tx['slide_id'] == scope[0] and tx['transaction_id'] == txid and tx['state'] == 'failed',
                'prompt_snapshot_conflict')
        from _runtime_recovery import journal_path, FIELDS
        name = journal_path(scope[0], txid)
        if store.hash(name) != 'none':
            journal = store.read_json(name)
            require(isinstance(journal, dict) and set(journal) == FIELDS and
                    type(journal['schema_version']) is int and journal['schema_version'] == 1 and
                    journal['kind'] == 'visual_generation_recovery' and journal['mode'] == 'recompose' and
                    journal['old_transaction_ref'] == ref and journal['old_transaction_sha256'] == store.observed[ref] and
                    journal['slide_id'] == scope[0] and journal['batch_id'] == tx['batch_id'] and
                    journal['manifest_path'] == '.ppt-pilot/visual-generation-batches/' + tx['batch_id'] + '.json',
                    'prompt_snapshot_conflict')
            replacement = journal['new_transaction']
            validate_v2_transaction(replacement)
            require(replacement['batch_id'] == tx['batch_id'] and replacement['slide_id'] == scope[0] and
                    replacement['generation_intent'] == 'user_recompose' and
                    replacement['generation_trigger_id'] == 'interaction:' + rid and
                    journal['new_transaction_ref'] == _transaction_ref(replacement) and
                    journal['new_transaction_sha256'] == sha(canonical(replacement)), 'prompt_snapshot_conflict')
        else:
            manifest_name = '.ppt-pilot/visual-generation-batches/' + tx['batch_id'] + '.json'
            require(run.get('active_visual_generation_batch') ==
                    {'schema_version': 2, 'batch_id': tx['batch_id'], 'manifest_path': manifest_name}, 'prompt_snapshot_conflict')
            manifest = store.read_json(manifest_name)
            require(manifest.get('batch_id') == tx['batch_id'] and ref in manifest.get('transaction_refs', []),
                    'prompt_snapshot_conflict')
        records[rid] = record
        transactions.append(tx)
    return dict(sorted(records.items(), key=lambda item: prompt._visual_revision_sort_key(item[0]))), transactions


def revise_visual(runtime, args):
    from _runtime_commands import transaction_path
    from _runtime_owners import Owners
    request = runtime.input(args.input)
    require(isinstance(request, dict) and set(request) == REQUEST_FIELDS and
            type(request['schema_version']) is int and request['schema_version'] == 1 and
            request['kind'] == 'visual_revision')
    request_fields(request)
    normalized = changes(request['changes'])
    runtime.priority()
    require(runtime.run.get('stage') in ('anchor', 'production'), 'recovery_not_allowed')
    ref = transaction_path(args.slide_id, args.transaction_id)
    manifest, txs = runtime.graph()
    owners = Owners(runtime.store, runtime.run)
    existing = [(rid, record) for rid, record in owners.visual_revisions.items()
                if record['request_id'] == request['request_id']]
    if existing:
        rid, record = existing[0]
        require(record['affected_scope'] == [args.slide_id] and
                record['source_transaction_id'] == args.transaction_id and
                record['normalized_changes'] == normalized and record['answer'] == request['answer'] and
                record['expected_run_sha256'] == request['expected_run_sha256'], 'visual_revision_request_conflict')
        from _runtime_recovery import journal_path, FIELDS, pending
        name = journal_path(args.slide_id, args.transaction_id)
        require(all(item == {'slide_id': args.slide_id, 'transaction_id': args.transaction_id, 'mode': 'recompose'}
                    for item in pending(runtime)), 'recovery_pending')
        if runtime.store.hash(name) != 'none' and ref in txs:
            journal = runtime.store.read_json(name)
            require(journal['new_transaction']['generation_trigger_id'] == 'interaction:' + rid and
                    journal['old_transaction_ref'] == ref and
                    journal['old_prompt'] == owners.compile(txs[ref])[2].decode('utf-8'),
                    'visual_revision_request_conflict')
            runtime.canonical(manifest, {key: tx for key, tx in txs.items() if key != ref})
        else:
            runtime.canonical(manifest, txs)
        if runtime.store.hash(name) != 'none' and ref not in txs:
            journal = runtime.store.read_json(name)
            require(isinstance(journal, dict) and set(journal) == FIELDS and
                    type(journal['schema_version']) is int and journal['schema_version'] == 1 and
                    journal['kind'] == 'visual_generation_recovery' and journal['mode'] == 'recompose',
                    'visual_revision_request_conflict')
            source = runtime.store.read_json(ref)
            old_envelope = owners.compile(source)[2]
            require(journal['old_prompt'] == old_envelope.decode('utf-8') and
                    journal['old_prompt_sha256'] == sha(old_envelope) and
                    journal['prompt_path'] == '.ppt-pilot/' + source['prompt_path'] and
                    journal['manifest_path'] == runtime.run['active_visual_generation_batch']['manifest_path'],
                    'visual_revision_request_conflict')
            for which in ('old', 'new'):
                historical = journal[which + '_manifest']
                require(isinstance(historical, dict) and sha(canonical(historical)) == journal[which + '_manifest_sha256'] and
                        historical['batch_id'] == manifest['batch_id'] and
                        historical['ordered_slide_ids'] == manifest['ordered_slide_ids'] and
                        all(historical[key] == value for key, value in owners.snapshots.items()),
                        'visual_revision_request_conflict')
            old_refs = journal['old_manifest']['transaction_refs']
            require(old_refs.count(ref) == 1 and journal['new_manifest']['transaction_refs'] ==
                    [journal['new_transaction_ref'] if old_ref == ref else old_ref for old_ref in old_refs] and
                    set(journal['expected_transaction_hashes']) == set(old_refs) and
                    journal['expected_transaction_hashes'][ref] == journal['old_transaction_sha256'],
                    'visual_revision_request_conflict')
            replacement = journal['new_transaction']
            validate_v2_transaction(replacement)
            identity, body_hash, envelope = owners.compile(replacement)
            require(replacement['generation_trigger_id'] == 'interaction:' + rid and
                    replacement['state'] == 'compiled' and replacement['generation_attempt'] == source['generation_attempt'] < 3 and
                    replacement['dispatch_epoch'] == source['dispatch_epoch'] + 1 and
                    replacement['generation_intent'] == 'user_recompose' and replacement['slide_id'] == args.slide_id and
                    replacement['batch_id'] == journal['batch_id'] == manifest['batch_id'] and
                    journal['slide_id'] == args.slide_id and journal['old_transaction_ref'] == ref and
                    journal['old_transaction_sha256'] == runtime.store.hash(ref) and
                    journal['new_transaction_ref'] == _transaction_ref(replacement) and
                    journal['new_transaction_sha256'] == sha(canonical(replacement)) and
                    replacement['transaction_id'] == identity and replacement['compiled_prompt_sha256'] == body_hash and
                    journal['new_prompt'] == envelope.decode('utf-8') and journal['new_prompt_sha256'] == sha(envelope),
                    'visual_revision_request_conflict')
            current = next(tx for tx in txs.values() if tx['slide_id'] == args.slide_id)
            ancestor, seen = current, set()
            while ancestor['transaction_id'] != identity:
                trigger = ancestor['generation_trigger_id'].removeprefix('interaction:')
                newer = owners.visual_revisions.get(trigger)
                require(newer is not None and newer['affected_scope'] == [args.slide_id] and
                        prompt._visual_revision_sort_key(trigger) > prompt._visual_revision_sort_key(rid) and
                        ancestor['transaction_id'] not in seen, 'visual_revision_request_conflict')
                seen.add(ancestor['transaction_id'])
                ancestor = runtime.store.read_json(transaction_path(args.slide_id, newer['source_transaction_id']))
                validate_v2_transaction(ancestor)
                historical_id, historical_hash, _ = owners.compile(ancestor)
                require(ancestor['transaction_id'] == historical_id and ancestor['compiled_prompt_sha256'] == historical_hash and
                        ancestor['batch_id'] == manifest['batch_id'], 'visual_revision_request_conflict')
            if current['transaction_id'] != identity:
                return dict(transaction_id=identity, current_transaction_id=current['transaction_id'],
                            visual_revision_id=rid, replay=True, superseded=True, next_command='resume')
            return dict(transaction_id=identity, prompt_by_value=journal['new_prompt'], recovery_journal=name,
                        visual_revision_id=rid, replay=True)
        require(ref in txs and txs[ref]['state'] == 'failed' and owners.revision_for(args.slide_id) == rid,
                'recovery_not_allowed')
        result = runtime.prepare_recovery(Namespace(slide_id=args.slide_id, transaction_id=args.transaction_id, mode='recompose'))
        return dict(result, visual_revision_id=rid, replay=True)
    from _runtime_recovery import pending
    require(not pending(runtime), 'recovery_pending')
    runtime.canonical(manifest, txs)
    require(ref in txs and txs[ref]['state'] == 'failed', 'recovery_not_allowed')
    require(txs[ref]['generation_attempt'] < 3, 'generation_attempts_exhausted')
    require(request['expected_run_sha256'] == runtime.store.observed[runtime.run_name],
            'visual_generation_state_conflict')
    manifest_name = runtime.run['active_visual_generation_batch']['manifest_path']
    manifest_hash = runtime.store.observed[manifest_name]
    stored_manifest = runtime.store.read_json(manifest_name)
    require(sha(canonical(stored_manifest)) == manifest_hash, 'visual_generation_state_conflict')
    history = dict(runtime.run.get('interaction_history', {}))
    require(not any(r['request_id'] == request['request_id'] or
                    (r['affected_scope'] == [args.slide_id] and r['source_transaction_id'] == args.transaction_id)
                    for r in owners.visual_revisions.values()), 'visual_revision_request_conflict')
    number = max((int(key.removeprefix('visual-revision-')) for key in history
                  if re.fullmatch(r'visual-revision-[0-9]+', key)), default=0) + 1
    rid = 'visual-revision-' + str(number)
    history[rid] = dict(id=rid, kind='visual_revision', projection='runtime_visual',
        stage=runtime.run['stage'], affected_scope=[args.slide_id], status='applied',
        artifact_owner=runtime.run_name, supersedes=[], normalized_changes=normalized,
        answer=request['answer'], request_id=request['request_id'],
        expected_run_sha256=request['expected_run_sha256'], source_transaction_id=args.transaction_id,
        review_snapshot_id=runtime.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot']['snapshot_id'])
    revised = dict(runtime.run, interaction_history=history)
    identity, _, _ = Owners(runtime.store, revised).compile(dict(slide_id=args.slide_id, generation_intent='user_recompose',
                                                               generation_trigger_id='interaction:' + rid))
    require(runtime.store.hash(transaction_path(args.slide_id, identity)) == 'none', 'visual_generation_state_conflict')
    runtime.run = revised
    runtime.write_run()
    result = runtime.prepare_recovery(Namespace(slide_id=args.slide_id, transaction_id=args.transaction_id, mode='recompose'))
    return dict(result, visual_revision_id=rid)
