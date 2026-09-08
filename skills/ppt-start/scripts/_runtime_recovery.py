"""Immutable, runtime-derived journal for replacing a shared slide prompt."""
from _run_store import canonical, sha
from _runtime_owners import Owners
from _generation_runtime import validate_v2_transaction, validate_v2_manifest, _transaction_ref, _validate_prompt_by_value

FIELDS = {'schema_version', 'kind', 'mode', 'slide_id', 'batch_id', 'expected_run_sha256',
    'old_transaction_ref', 'old_transaction_sha256', 'new_transaction_ref', 'new_transaction_sha256',
    'manifest_path', 'old_manifest', 'old_manifest_sha256', 'new_manifest', 'new_manifest_sha256',
    'prompt_path', 'old_prompt', 'old_prompt_sha256', 'new_prompt', 'new_prompt_sha256', 'new_transaction',
    'expected_transaction_hashes'}


def require(value):
    if not value:
        raise ValueError('visual_generation_state_conflict')


def journal_path(slide_id, transaction_id):
    # The caller has validated these via transaction_path before use.
    return '.ppt-pilot/visual-generation-recoveries/' + slide_id + '-' + transaction_id[7:] + '.json'


def validate_journal(runtime, journal, old_id=None, mode=None):
    require(isinstance(journal, dict) and set(journal) == FIELDS and
            type(journal['schema_version']) is int and journal['schema_version'] == 1 and
            journal['kind'] == 'visual_generation_recovery' and journal['mode'] in ('recompose', 'fallback'))
    require(mode is None or mode == journal['mode'])
    tx = journal['new_transaction']
    validate_v2_transaction(tx)
    require(tx['state'] == 'compiled' and tx['slide_id'] == journal['slide_id'] and tx['batch_id'] == journal['batch_id'])
    require(journal['new_transaction_ref'] == _transaction_ref(tx) and journal['new_transaction_sha256'] == sha(canonical(tx)))
    old = runtime.store.read_json(journal['old_transaction_ref'])
    validate_v2_transaction(old)
    require(old['state'] == 'failed' and old['slide_id'] == tx['slide_id'] and old['batch_id'] == tx['batch_id'] and
            old['transaction_id'] != tx['transaction_id'] and journal['old_transaction_ref'] == _transaction_ref(old) and
            runtime.store.observed[journal['old_transaction_ref']] == journal['old_transaction_sha256'])
    require(old_id is None or old['transaction_id'] == old_id)
    require(journal['prompt_path'] == '.ppt-pilot/' + old['prompt_path'] == '.ppt-pilot/' + tx['prompt_path'])
    require(journal['manifest_path'] == '.ppt-pilot/visual-generation-batches/' + tx['batch_id'] + '.json')
    for which in ('old', 'new'):
        require(isinstance(journal[which + '_prompt'], str) and
                sha(journal[which + '_prompt'].encode('utf-8')) == journal[which + '_prompt_sha256'])
        require(sha(canonical(journal[which + '_manifest'])) == journal[which + '_manifest_sha256'])
    _validate_prompt_by_value(journal['old_prompt'], old)
    _validate_prompt_by_value(journal['new_prompt'], tx)
    require(tx['prior_final_sha256'] == old['prior_final_sha256'] and tx['generation_attempt'] == 0 and
            tx['dispatch_epoch'] == old['dispatch_epoch'] + 1 and tx['host_task_id'] is None)
    expected_tx = dict(old, transaction_id=tx['transaction_id'], prompt_snapshot_id=tx['transaction_id'],
        compiled_prompt_sha256=tx['compiled_prompt_sha256'], candidate_path=tx['candidate_path'],
        state='compiled', generation_attempt=0, candidate_sha256=None, failure_reason=None,
        dispatch_epoch=old['dispatch_epoch'] + 1, host_attribution_id=None, host_task_id=None,
        validation={'state': 'pending', 'checks': {key: 'pending' for key in old['validation']['checks']}},
        timing=[], generation_intent=tx['generation_intent'], generation_trigger_id=tx['generation_trigger_id'])
    require(tx == expected_tx)
    old_manifest, new_manifest = journal['old_manifest'], journal['new_manifest']
    old_refs, new_refs = old_manifest['transaction_refs'], new_manifest['transaction_refs']
    require(isinstance(journal['expected_transaction_hashes'], dict) and set(journal['expected_transaction_hashes']) == set(old_refs))
    for ref, digest in journal['expected_transaction_hashes'].items():
        require(runtime.store.hash(ref) == digest)
    require(journal['old_transaction_ref'] in old_refs and journal['new_transaction_ref'] not in old_refs)
    expected_refs = list(old_refs)
    expected_refs[expected_refs.index(journal['old_transaction_ref'])] = journal['new_transaction_ref']
    require(new_refs == expected_refs)
    old_txs = {ref: old if ref == journal['old_transaction_ref'] else runtime.store.read_json(ref) for ref in old_refs}
    new_txs = dict(old_txs)
    del new_txs[journal['old_transaction_ref']]
    new_txs[journal['new_transaction_ref']] = tx
    validate_v2_manifest(old_manifest, old_txs)
    validate_v2_manifest(new_manifest, new_txs)
    owners = Owners(runtime.store, runtime.run)
    identity, body_hash, prompt = owners.compile(tx)
    require(identity == tx['transaction_id'] and body_hash == tx['compiled_prompt_sha256'] and prompt.decode('utf-8') == journal['new_prompt'])
    require(all(new_manifest[key] == value for key, value in owners.snapshots.items()))
    expected = dict(old_manifest)
    expected.update(owners.snapshots)
    expected['transaction_refs'] = new_refs
    runtime.refresh(expected, new_txs)
    require(expected == new_manifest)
    if journal['mode'] == 'fallback':
        require(tx['generation_intent'] == 'deterministic_fallback' and tx['generation_trigger_id'] ==
                'fallback:' + tx['slide_id'] + ':' + old['transaction_id'][7:] + ':2')
        runtime.fallback_evidence(old)
    else:
        require(tx['generation_intent'] == 'user_recompose' and owners.revisions and
                tx['generation_trigger_id'] == 'interaction:' + owners.revisions[-1])
    return old, tx


def replay(runtime, name, journal, old_id, mode):
    old, tx = validate_journal(runtime, journal, old_id, mode)
    store = runtime.store
    require(name == journal_path(old['slide_id'], old['transaction_id']))
    require(store.observed[runtime.run_name] == journal['expected_run_sha256'])
    require(runtime.run.get('active_visual_generation_batch') == {'schema_version': 2, 'batch_id': tx['batch_id'], 'manifest_path': journal['manifest_path']})
    manifest_hash = store.hash(journal['manifest_path'])
    prompt_hash = store.hash(journal['prompt_path'])
    tx_hash = store.hash(journal['new_transaction_ref'])
    require(manifest_hash in (journal['old_manifest_sha256'], journal['new_manifest_sha256']))
    require(prompt_hash in (journal['old_prompt_sha256'], journal['new_prompt_sha256']))
    require(tx_hash in ('none', journal['new_transaction_sha256']))
    # A published manifest must already have the exact replacement prompt+tx.
    require(manifest_hash != journal['new_manifest_sha256'] or
            (prompt_hash == journal['new_prompt_sha256'] and tx_hash == journal['new_transaction_sha256']))
    store.write_bytes(journal['prompt_path'], journal['new_prompt'].encode('utf-8'), prompt_hash)
    store.write_json(journal['new_transaction_ref'], tx, tx_hash)
    store.write_json(journal['manifest_path'], journal['new_manifest'], manifest_hash)
    return {'transaction_id': tx['transaction_id'], 'prompt_by_value': journal['new_prompt'], 'recovery_journal': name}


def pending(runtime):
    directory = runtime.store.path('.ppt-pilot/visual-generation-recoveries')
    if not directory.exists():
        return []
    result = []
    for path in sorted(directory.iterdir()):
        if path.suffix != '.json':
            continue
        name = path.relative_to(runtime.store.root).as_posix()
        journal = runtime.store.read_json(name)
        require(isinstance(journal, dict) and set(journal) == FIELDS and
                type(journal['schema_version']) is int and journal['schema_version'] == 1 and
                journal['kind'] == 'visual_generation_recovery' and journal['mode'] in ('recompose', 'fallback'))
        manifest = runtime.store.read_json(journal['manifest_path'])
        if journal['old_transaction_ref'] in manifest.get('transaction_refs', []):
            old, _ = validate_journal(runtime, journal)
            require(name == journal_path(old['slide_id'], old['transaction_id']))
            result.append({'slide_id': old['slide_id'], 'transaction_id': old['transaction_id'], 'mode': journal['mode']})
    return result
