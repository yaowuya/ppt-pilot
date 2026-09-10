"""Fixed data-only lifecycle. Host spawning is deliberately outside this module."""
import base64
import copy
import re
from _run_store import RunStore, canonical, sha, anchor_snapshot_id
from _workflow_gate import Gate
from _runtime_owners import Owners, SNAPSHOTS, markdown_owner
from _host_adapter_runtime import validate_capability
from _generation_concurrency import plan_dispatch
from _generation_runtime import (V2_VALIDATION_CHECKS, validate_v2_manifest, validate_v2_transaction,
    rebuild_batch_cursors, _transaction_ref, _validate_prompt_by_value, validated_final_outcome,
    migrate_v1_run_to_v2)
from _svg_runtime import extract_svg, validate_candidate
from _prompt_runtime import AssetFailure
from _runtime_blockers import preflight_blocker

STAMP = '1970-01-01T00:00:00Z'  # deterministic owner timestamp, never host telemetry
DISPATCH_FIELDS = {'schema_version', 'kind', 'batch_id', 'slide_id', 'transaction_id',
    'dispatch_epoch', 'dispatch_id', 'host', 'adapter_id', 'adapter_version',
    'host_attribution_id', 'state', 'host_task_id', 'created_at', 'updated_at'}
REQUEST_FIELDS = {'schema_version', 'kind', 'request_id', 'expected_run_sha256',
                  'expected_snapshots', 'ordered_slide_ids', 'generation_operations'}
QA_FIELDS = {'schema_version', 'kind', 'slide_id', 'transaction_id', 'candidate_sha256',
             'checks', 'defect_id', 'failure_reason'}
RETRY = {'generator_unavailable', 'generator_refused', 'generator_timeout',
         'generator_output_malformed', 'candidate_write_failed', 'candidate_hash_mismatch'}


def ensure(condition, code='visual_generation_state_conflict'):
    if not condition:
        raise ValueError(code)


def manifest_path(batch_id):
    ensure(isinstance(batch_id, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]*', batch_id))
    return '.ppt-pilot/visual-generation-batches/' + batch_id + '.json'


def transaction_path(sid, identity):
    ensure(isinstance(sid, str) and re.fullmatch(r'S[0-9]+', sid))
    ensure(isinstance(identity, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', identity))
    return '.ppt-pilot/visual-generation-transactions/' + sid + '-' + identity[7:] + '.json'


def dispatch_path(tx):
    return '.ppt-pilot/visual-generation-dispatches/{}-{}-e{}.json'.format(
        tx['slide_id'], tx['transaction_id'][7:], tx['dispatch_epoch'])


def pending_validation():
    return {'state': 'pending', 'checks': {k: 'pending' for k in sorted(V2_VALIDATION_CHECKS)}}


class Runtime:
    def __init__(self, root):
        self.store = RunStore(root)
        self.run_name = None
        self.run = {}

    def audit(self):
        gate = Gate(self.store.root)
        self.run = gate.load_run()
        gate.conformance()
        self.run_name = '.ppt-pilot/run.json' if self.store.path('.ppt-pilot/run.json').exists() else 'run.json'
        self.store.read_bytes(self.run_name)

    def write_barrier(self):
        gate = Gate(self.store.root)
        gate.load_run()
        gate.conformance()
        observed = dict(self.store.observed)
        for name, expected in observed.items():
            ensure(self.store.hash(name) == expected)

    def input(self, name, text=False):
        ensure(isinstance(name, str) and name.startswith('.ppt-pilot/runtime-inputs/') and
               name.count('/') == 2 and name.endswith('.txt' if text else '.json'), 'unsafe_runtime_input')
        try:
            self.store.path(name)
        except ValueError:
            raise ValueError('unsafe_runtime_input')
        return self.store.read_bytes(name).decode('utf-8-sig') if text else self.store.read_json(name)

    def write_run(self):
        self.store.write_json(self.run_name, self.run, self.store.observed[self.run_name])

    def priority(self, allow_blocker=False, allow_legacy=False):
        ensure(not self.run.get('pending_interaction'), 'pending_interaction')
        ensure(not self.run.get('manuscript_review', {}).get('pending_round'), 'pending_review_round')
        ensure(allow_blocker or not self.run.get('visual_generation_blocker'), 'visual_generation_blocker')
        ensure(allow_legacy or not self.run.get('visual_generation_transaction'), 'visual_generation_transaction')

    def graph(self, batch_id=None, active=True, verify_candidates=True, verify_finals=True):
        pointer = self.run.get('active_visual_generation_batch')
        if batch_id is None:
            ensure(isinstance(pointer, dict))
            batch_id = pointer.get('batch_id')
        path = manifest_path(batch_id)
        if active:
            ensure(pointer == {'schema_version': 2, 'batch_id': batch_id, 'manifest_path': path})
        elif pointer:
            ensure(pointer['batch_id'] == batch_id)
        manifest = self.store.read_json(path)
        ensure(manifest.get('batch_id') == batch_id)
        txs = {}
        for ref in manifest.get('transaction_refs', []):
            ensure(isinstance(ref, str) and ref.startswith('.ppt-pilot/visual-generation-transactions/'))
            tx = self.store.read_json(ref)
            validate_v2_transaction(tx)
            ensure(_transaction_ref(tx) == ref)
            txs[ref] = tx
        # Cursor hints are never authority. A crash after transaction commit can
        # leave stale hints, which read-only resume projects without rewriting.
        self.refresh(manifest, txs)
        validate_v2_manifest(manifest, txs)
        for tx in txs.values():
            if verify_candidates and tx['candidate_sha256'] is not None:
                ensure(self.store.hash(tx['candidate_path']) == tx['candidate_sha256'], 'candidate_hash_mismatch')
            if verify_finals and tx['state'] == 'promoted':
                ensure(self.store.hash(tx['final_path']) == tx['candidate_sha256'], 'final_promotion_conflict')
        return manifest, txs

    def refresh(self, manifest, txs):
        pc, bc = rebuild_batch_cursors(manifest, txs)
        manifest.update(promotion_cursor=pc, blocker_cursor=bc,
            active_blocker_ref=manifest['transaction_refs'][bc] if bc < len(txs) else None,
            state='blocked' if bc < len(txs) else 'completed' if pc == len(txs) else 'active')

    def persist_graph(self, manifest, txs, changed):
        for ref in changed:
            validate_v2_transaction(txs[ref])
            self.store.write_json(ref, txs[ref], self.store.observed[ref])
        self.refresh(manifest, txs)
        validate_v2_manifest(manifest, txs)
        path = manifest_path(manifest['batch_id'])
        self.store.write_json(path, manifest, self.store.observed[path])

    def canonical(self, manifest, txs):
        owners = Owners(self.store, self.run)
        ensure(manifest['batch_id'].startswith('migration-') or all(manifest[k] == owners.snapshots[k] for k in SNAPSHOTS), 'prompt_snapshot_conflict')
        for tx in txs.values():
            identity, body_hash, envelope = owners.compile(tx)
            ensure(identity == tx['transaction_id'] and body_hash == tx['compiled_prompt_sha256'], 'prompt_snapshot_conflict')
            ensure(self.store.read_bytes('.ppt-pilot/' + tx['prompt_path']) == envelope, 'prompt_snapshot_conflict')
        return owners

    def blocker(self, owners, sid, reason='generator_unavailable'):
        existing = self.run.get('visual_generation_blocker')
        ensure(existing is None or existing.get('slide_id') == sid)
        self.run['visual_generation_blocker'] = {'state': 'generator_unavailable', 'slide_id': sid,
            'reason': reason, 'selected_style_id': owners.theme['selected_style_id'], 'resource': 'none',
            'storyboard_snapshot_id': owners.snapshots['storyboard_snapshot_id'],
            'theme_snapshot_id': owners.snapshots['theme_snapshot_id'], 'status': 'active'}
        if sid not in self.run['dirty_slides']:
            self.run['dirty_slides'].append(sid)
        self.write_run()

    def production_blocker(self, tx, reason):
        self.run['pending_interaction'] = {'id': 'production-' + tx['transaction_id'][7:],
            'stage': self.run['stage'], 'kind': 'blocker', 'status': 'pending',
            'question': 'Resolve ' + reason + ' for ' + tx['slide_id'] + ' before continuing generation.'}
        self.write_run()

    def prepare_batch(self, args):
        request = self.input(args.input)
        receipt = self.input(args.capability)
        self.priority(allow_blocker=True)
        ensure(isinstance(request, dict) and set(request) == REQUEST_FIELDS, 'invalid_runtime_input')
        ensure(type(request['schema_version']) is int and request['schema_version'] == 1 and
               request['kind'] == 'prepare_visual_generation_batch', 'invalid_runtime_input')
        slides = request['ordered_slide_ids']
        ensure(isinstance(slides, list) and 1 <= len(slides) <= 5 and all(isinstance(s, str) and re.fullmatch(r'S[0-9]+', s) for s in slides), 'invalid_runtime_input')
        ensure(len(set(slides)) == len(slides) and sorted(slides, key=lambda s: int(s[1:])) == slides, 'invalid_runtime_input')
        operations = request['generation_operations']
        ensure(isinstance(operations, list) and len(operations) == len(slides) and
            all(isinstance(op, dict) and set(op) == {'slide_id', 'generation_intent', 'generation_trigger_id'} for op in operations)
            and [op['slide_id'] for op in operations] == slides, 'invalid_runtime_input')
        ensure(all(op['generation_intent'] in ('initial_generation', 'user_recompose') for op in operations), 'recovery_not_allowed')
        ensure(isinstance(request['expected_snapshots'], dict) and set(request['expected_snapshots']) == SNAPSHOTS, 'invalid_runtime_input')
        identity = sha(canonical({k: v for k, v in request.items() if k not in ('request_id', 'expected_run_sha256')}).rstrip(b'\n'))
        ensure(identity == request['request_id'], 'invalid_runtime_input')
        batch_id = 'batch-' + identity[7:]
        path = manifest_path(batch_id)
        try:
            owners = Owners(self.store, self.run)
        except AssetFailure as failure:
            if hasattr(failure, 'canonical_context'):
                self.record_preflight_blocker(failure, failure.canonical_context, slides[0])
            raise
        ensure(request['expected_snapshots'] == owners.snapshots, 'prompt_snapshot_conflict')
        failed_slide = slides[0]
        try:
            compiled = []
            for op in operations:
                failed_slide = op['slide_id']
                compiled.append(owners.compile(op))
        except ValueError as error:
            if str(error) in ('prompt_preflight_invalid', 'prompt_snapshot_conflict'):
                context = {'selected_style_id': owners.theme['selected_style_id'],
                    'storyboard_snapshot_id': owners.snapshots['storyboard_snapshot_id'],
                    'theme_snapshot_id': owners.snapshots['theme_snapshot_id']}
                failure = AssetFailure(str(error), 'none' if str(error) == 'prompt_snapshot_conflict' else owners.template_path)
                self.record_preflight_blocker(failure, context, failed_slide)
            raise
        if self.store.hash(path) != 'none':
            manifest, txs = self.graph(batch_id, active=False)
            ensure(manifest['ordered_slide_ids'] == slides)
            self.canonical(manifest, txs)
            ensure([txs[ref]['transaction_id'] for ref in manifest['transaction_refs']] == [c[0] for c in compiled])
            if not self.run.get('active_visual_generation_batch') and manifest['state'] != 'completed':
                validate_capability(receipt)
                self.run.pop('visual_generation_blocker', None)
                self.run['active_visual_generation_batch'] = {'schema_version': 2, 'batch_id': batch_id, 'manifest_path': path}
                self.write_run()
            return {'batch_id': batch_id, 'replay': True}
        ensure(not self.run.get('active_visual_generation_batch'))
        ensure(request['expected_run_sha256'] == self.store.observed[self.run_name])
        try:
            validate_capability(receipt)
        except ValueError:
            self.blocker(owners, slides[0])
            raise ValueError('generator_unavailable')
        txs, prompts = {}, {}
        for op, (txid, body_hash, envelope) in zip(operations, compiled):
            sid = op['slide_id']
            tx = dict(schema_version=2, kind='visual_generation_transaction', batch_id=batch_id,
                transaction_id=txid, slide_id=sid, generation_intent=op['generation_intent'],
                generation_trigger_id=op['generation_trigger_id'], prompt_path='generation-prompts/' + sid + '.md',
                prompt_snapshot_id=txid, compiled_prompt_sha256=body_hash,
                candidate_path='slides/.candidates/' + sid + '-' + txid[7:] + '.svg', final_path='slides/' + sid + '.svg',
                prior_final_sha256=self.store.hash('slides/' + sid + '.svg'), state='compiled', generation_attempt=0,
                candidate_sha256=None, failure_reason=None, dispatch_epoch=0, host_attribution_id=None,
                host_task_id=None, validation=pending_validation(), timing=[])
            validate_v2_transaction(tx)
            ref = _transaction_ref(tx)
            ensure(self.store.hash(ref) == 'none')  # partial preparation is never overwritten
            txs[ref] = tx
            prompts['.ppt-pilot/' + tx['prompt_path']] = envelope
        manifest = dict(schema_version=2, kind='visual_generation_batch', batch_id=batch_id, batch_width=5,
            ordered_slide_ids=slides, transaction_refs=list(txs), dispatch_epoch=0, promotion_cursor=0,
            blocker_cursor=len(slides), active_blocker_ref=None, state='active', created_at=STAMP,
            updated_at=STAMP, telemetry_summary={}, **owners.snapshots)
        validate_v2_manifest(manifest, txs)
        for name, data in prompts.items():
            try:
                self.store.write_bytes(name, data, self.store.hash(name))
            except OSError:
                failed_ref, failed_tx = next((ref, tx) for ref, tx in txs.items() if '.ppt-pilot/' + tx['prompt_path'] == name)
                failed_tx.update(state='failed', failure_reason='prompt_write_failed')
                # A storage failure can prevent this best-effort canonical write
                # too. In that case the caller reports only observed writes.
                self.store.write_json(failed_ref, failed_tx, 'none')
                raise ValueError('prompt_write_failed')
        for ref, tx in txs.items():
            self.store.write_json(ref, tx, 'none')
        self.store.write_json(path, manifest, 'none')
        self.run.pop('visual_generation_blocker', None)
        self.run['active_visual_generation_batch'] = {'schema_version': 2, 'batch_id': batch_id, 'manifest_path': path}
        self.write_run()
        return {'batch_id': batch_id}

    def record_preflight_blocker(self, failure, context, slide_id):
        ensure(not self.run.get('active_visual_generation_batch'))
        blocker = preflight_blocker(failure, context, slide_id)
        existing = self.run.get('visual_generation_blocker')
        ensure(existing is None or existing.get('slide_id') == slide_id)
        self.run['visual_generation_blocker'] = blocker
        if slide_id not in self.run['dirty_slides']:
            self.run['dirty_slides'].append(slide_id)
        self.write_run()

    def reservations(self, manifest, txs):
        result = {}
        directory = self.store.path('.ppt-pilot/visual-generation-dispatches')
        if not directory.exists():
            return result
        for file in sorted(directory.iterdir()):
            if not file.name.endswith('.json'):
                continue
            name = file.relative_to(self.store.root).as_posix()
            dispatch = self.store.read_json(name)
            ensure(set(dispatch) == DISPATCH_FIELDS and dispatch['schema_version'] == 1 and dispatch['kind'] == 'visual_generation_dispatch')
            if dispatch['batch_id'] != manifest['batch_id']:
                continue
            ref = transaction_path(dispatch['slide_id'], dispatch['transaction_id'])
            # Retired recovery transactions keep historical reservations.
            if ref not in txs:
                continue
            tx = txs[ref]
            ensure(type(dispatch['dispatch_epoch']) is int and dispatch['dispatch_epoch'] >= 0)
            identity = sha(canonical({k: dispatch[k] for k in ('batch_id', 'transaction_id', 'dispatch_epoch', 'host', 'adapter_id', 'adapter_version')}).rstrip(b'\n'))
            ensure(dispatch['dispatch_id'] == identity and dispatch['host_attribution_id'] == identity)
            ensure(name == dispatch_path(dict(tx, dispatch_epoch=dispatch['dispatch_epoch'])))
            ensure(dispatch['state'] in ('reserved', 'bound') and
                   ((dispatch['state'] == 'reserved' and dispatch['host_task_id'] is None) or
                    (dispatch['state'] == 'bound' and isinstance(dispatch['host_task_id'], str) and dispatch['host_task_id'])))
            if dispatch['dispatch_epoch'] == tx['dispatch_epoch']:
                ensure(ref not in result)
                result[ref] = (name, dispatch)
                if tx['host_task_id'] is not None:
                    ensure(dispatch['state'] == 'bound' and tx['host_task_id'] == dispatch['host_task_id'] and
                           tx['host_attribution_id'] == dispatch['host_attribution_id'])
        for ref, tx in txs.items():
            ensure(tx['host_task_id'] is None or ref in result)
        return result

    def plan(self, manifest, txs, capability):
        reservations = self.reservations(manifest, txs)
        in_flight = [tx['slide_id'] for ref, tx in txs.items() if tx['state'] == 'generating' or
                     (tx['state'] == 'compiled' and ref in reservations)]
        ready = [txs[ref]['slide_id'] for ref in manifest['transaction_refs'] if txs[ref]['state'] == 'compiled' and ref not in reservations]
        obs = capability['observation']
        planned = plan_dispatch({'schema_version': 1, 'capabilities': {'fresh_isolation': obs['fresh_history'],
            'concurrent_tasks': obs['concurrent_tasks'], 'durable_lookup': obs['durable_lookup'], 'worker_capacity': obs['worker_capacity']},
            'ready_slide_ids': ready, 'in_flight_slide_ids': in_flight, 'batch_width': manifest['batch_width'],
            'blocked': manifest['state'] == 'blocked'})
        items = []
        for ref in manifest['transaction_refs']:
            tx = txs[ref]
            if tx['slide_id'] in planned['dispatch_slide_ids']:
                text = self.store.read_bytes('.ppt-pilot/' + tx['prompt_path']).decode('utf-8')
                _validate_prompt_by_value(text, tx)
                items.append({'slide_id': tx['slide_id'], 'transaction_id': tx['transaction_id'],
                    'dispatch_epoch': tx['dispatch_epoch'], 'prompt_by_value': text,
                    'fresh_history': obs['fresh_history'],
                    'filesystem': 'none' if obs['filesystem_none'] else 'host-inherited',
                    'data_tools': 'none' if obs['data_tools_none'] else 'host-inherited',
                    'output': 'text', 'expected_fence': 'xml'})
        return {'items': items, 'reservations': [d for _, d in reservations.values()], 'capacity': planned}

    def dispatch_plan(self, args):
        receipt = self.input(args.capability)
        self.priority()
        manifest, txs = self.graph(args.batch_id)
        self.canonical(manifest, txs)
        return self.plan(manifest, txs, validate_capability(receipt))

    def reserve_dispatch(self, args):
        receipt = self.input(args.capability)
        self.priority()
        manifest, txs = self.graph(args.batch_id)
        self.canonical(manifest, txs)
        try:
            capability = validate_capability(receipt)
        except ValueError:
            pending = next((ref for ref in manifest['transaction_refs'] if txs[ref]['state'] == 'compiled'), None)
            if pending is not None:
                self.fail(manifest, txs, pending, 'generator_unavailable')
            raise ValueError('generator_unavailable')
        ref = transaction_path(args.slide_id, args.transaction_id)
        ensure(ref in txs)
        tx = txs[ref]
        reservations = self.reservations(manifest, txs)
        if ref in reservations:
            dispatch = reservations[ref][1]
            ensure(all(dispatch[k] == capability[k] for k in ('host', 'adapter_id', 'adapter_version')))
            return {'dispatch': dispatch, 'spawn_authorized': False, 'resolution': 'durable_lookup_required'}
        plan = self.plan(manifest, txs, capability)
        ensure(any(item['transaction_id'] == tx['transaction_id'] for item in plan['items']), 'dispatch_not_eligible')
        dispatch = {k: capability[k] for k in ('host', 'adapter_id', 'adapter_version')}
        dispatch.update(batch_id=manifest['batch_id'], transaction_id=tx['transaction_id'], dispatch_epoch=tx['dispatch_epoch'])
        identity = sha(canonical(dispatch).rstrip(b'\n'))
        dispatch.update(schema_version=1, kind='visual_generation_dispatch', slide_id=tx['slide_id'],
            dispatch_id=identity, host_attribution_id=identity, state='reserved', host_task_id=None,
            created_at=STAMP, updated_at=STAMP)
        self.store.write_json(dispatch_path(tx), dispatch, 'none')
        return {'dispatch': dispatch, 'spawn_authorized': True, 'prompt_by_value': next(item['prompt_by_value'] for item in plan['items'] if item['slide_id'] == tx['slide_id'])}

    def find_dispatch(self, identity):
        self.priority()
        manifest, txs = self.graph()
        self.canonical(manifest, txs)
        found = [(ref, name, dispatch) for ref, (name, dispatch) in self.reservations(manifest, txs).items()
                 if dispatch['dispatch_id'] == identity]
        ensure(len(found) == 1)
        ref, name, dispatch = found[0]
        return manifest, txs, ref, name, dispatch

    def bind_task(self, args):
        manifest, txs, ref, name, dispatch = self.find_dispatch(args.dispatch_id)
        ensure(isinstance(args.host_task_id, str) and args.host_task_id.strip() and len(args.host_task_id) <= 512 and
               not any(ord(c) < 32 for c in args.host_task_id), 'invalid_runtime_input')
        tx = txs[ref]
        if dispatch['state'] == 'bound':
            ensure(dispatch['host_task_id'] == args.host_task_id)
            if tx['host_task_id'] == args.host_task_id:
                return {'dispatch': dispatch, 'replay': True}
        ensure(tx['state'] == 'compiled' and tx['host_task_id'] is None)
        dispatch.update(state='bound', host_task_id=args.host_task_id)
        self.store.write_json(name, dispatch, self.store.observed[name])
        tx.update(state='generating', host_task_id=args.host_task_id, host_attribution_id=dispatch['host_attribution_id'],
                  generation_attempt=tx['generation_attempt'] + 1)
        self.persist_graph(manifest, txs, [ref])
        return {'dispatch': dispatch}

    def fail(self, manifest, txs, ref, reason):
        tx = txs[ref]
        tx.update(state='failed', failure_reason=reason)
        if reason in ('svg_contract_failed', 'fact_source_mismatch', 'visual_qa_failed'):
            check = {'svg_contract_failed': 'xml', 'fact_source_mismatch': 'fact_source', 'visual_qa_failed': 'visual'}[reason]
            tx['validation']['state'] = 'failed'
            tx['validation']['checks'][check] = 'failed'
        self.persist_graph(manifest, txs, [ref])

    def ingest_result(self, args):
        response = self.input(args.response, text=True)
        manifest, txs, ref, _, dispatch = self.find_dispatch(args.dispatch_id)
        tx = txs[ref]
        ensure(dispatch['state'] == 'bound' and tx['host_task_id'] == dispatch['host_task_id'])
        ensure(tx['state'] in ('generating', 'candidate_written', 'validated', 'promoted'))
        owners = self.canonical(manifest, txs)
        blocks = owners.slides[tx['slide_id']]['content_blocks']
        try:
            data = validate_candidate(extract_svg(response), [b['block_id'] for b in blocks],
                                      {b['block_id']: b['source_ids'] for b in blocks})
        except ValueError as error:
            ensure(tx['state'] == 'generating')
            reason = str(error) if str(error) in ('generator_output_malformed', 'fact_source_mismatch', 'svg_contract_failed') else 'svg_contract_failed'
            self.fail(manifest, txs, ref, reason)
            raise ValueError(reason)
        if tx['state'] != 'generating':
            ensure(tx['candidate_sha256'] == sha(data))
            return {'candidate_sha256': tx['candidate_sha256'], 'replay': True}
        # A crash orphan is never adopted, even if its bytes happen to match.
        ensure(self.store.hash(tx['candidate_path']) == 'none', 'orphan_candidate')
        try:
            candidate_hash = self.store.write_bytes(tx['candidate_path'], data, 'none')
        except OSError:
            self.fail(manifest, txs, ref, 'candidate_write_failed')
            raise ValueError('candidate_write_failed')
        tx.update(state='candidate_written', candidate_sha256=candidate_hash)
        self.persist_graph(manifest, txs, [ref])
        return {'candidate_sha256': candidate_hash}

    def record_generator_failure(self, args):
        manifest, txs, ref, _, dispatch = self.find_dispatch(args.dispatch_id)
        tx = txs[ref]
        ensure(dispatch['state'] == 'bound')
        if tx['state'] == 'failed' and tx['failure_reason'] == args.reason:
            return {'replay': True}
        ensure(tx['state'] == 'generating')
        self.fail(manifest, txs, ref, args.reason)
        return {'failure_reason': args.reason}

    def qa_owner(self):
        name = '.ppt-pilot/质量检查报告.md'
        if self.store.hash(name) == 'none':
            return name, {'schema_version': 1, 'kind': 'runtime_qa', 'records': []}
        owner = markdown_owner(self.store.read_bytes(name))
        ensure(set(owner) == {'schema_version', 'kind', 'records'} and owner['schema_version'] == 1 and
               owner['kind'] == 'runtime_qa' and isinstance(owner['records'], list), 'qa_owner_conflict')
        return name, owner

    def record_validation(self, args):
        qa = self.input(args.input)
        self.priority()
        manifest, txs = self.graph(verify_candidates=False)
        self.canonical(manifest, txs)
        ref = transaction_path(args.slide_id, args.transaction_id)
        ensure(ref in txs)
        tx = txs[ref]
        ensure(isinstance(qa, dict) and set(qa) == QA_FIELDS and type(qa['schema_version']) is int and
               qa['schema_version'] == 1 and qa['kind'] == 'visual_generation_qa', 'invalid_runtime_input')
        ensure(qa['slide_id'] == args.slide_id and qa['transaction_id'] == args.transaction_id and
               qa['candidate_sha256'] == tx['candidate_sha256'], 'stale_validation')
        if self.store.hash(tx['candidate_path']) != tx['candidate_sha256']:
            ensure(tx['state'] == 'candidate_written')
            self.fail(manifest, txs, ref, 'candidate_hash_mismatch')
            raise ValueError('candidate_hash_mismatch')
        checks = qa['checks']
        ensure(isinstance(checks, dict) and set(checks) == V2_VALIDATION_CHECKS and
            all(value in ('passed', 'failed') or (key == 'visual' and value == 'not_rendered') for key, value in checks.items()), 'invalid_runtime_input')
        passed = 'failed' not in checks.values()
        reason = qa['failure_reason']
        expected_reason = ('svg_contract_failed' if any(checks[k] == 'failed' for k in ('xml', 'office', 'geometry_text')) else
                           'fact_source_mismatch' if checks['fact_source'] == 'failed' or checks['narrative'] == 'failed' else 'visual_qa_failed')
        ensure((passed and reason is None and qa['defect_id'] is None) or
               (not passed and reason == expected_reason and isinstance(qa['defect_id'], str) and
                re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', qa['defect_id'])), 'invalid_runtime_input')
        ensure(not (checks['narrative'] == 'failed' and checks['fact_source'] != 'failed'), 'invalid_runtime_input')
        name, owner = self.qa_owner()
        existing = [r for r in owner['records'] if r.get('transaction_id') == args.transaction_id and r.get('candidate_sha256') == qa['candidate_sha256']]
        if existing:
            ensure(existing == [qa], 'stale_validation')
            if tx['state'] in ('validated', 'promoted', 'failed'):
                ensure(tx['validation']['checks'] == checks)
                return {'replay': True}
        ensure(tx['state'] == 'candidate_written')
        if not existing:
            owner['records'].append(qa)
            self.store.write_bytes(name, b'# Runtime QA\n\n```ppt-pilot-json\n' + canonical(owner) + b'```\n', self.store.observed[name])
        tx['validation'] = {'state': 'passed' if passed else 'failed', 'checks': checks}
        tx.update(state='validated' if passed else 'failed', failure_reason=reason)
        # Narrative failure belongs to fact floor; exact v2 validator requires its check.
        self.persist_graph(manifest, txs, [ref])
        return {'validation': tx['validation']}

    def promote(self, args):
        self.priority()
        ensure(self.run.get('stage') == 'production', 'anchor_completion_required')
        manifest, txs = self.graph(args.batch_id, active=False)
        path = manifest_path(args.batch_id)
        owners = self.canonical(manifest, txs)
        if not self.run.get('source_deck'):
            anchor = self.run.get('anchor', {})
            ensure(isinstance(anchor, dict) and anchor.get('status') == ('approved' if self.run.get('mode') == 'guided' else 'validated'), 'anchor_completion_required')
            ensure(anchor.get('style_sha256') == owners.snapshots['theme_snapshot_id'][7:] and
                   anchor.get('review_snapshot_id') == self.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot']['snapshot_id'], 'anchor_binding_stale')
            files = anchor.get('files')
            ensure(isinstance(files, dict) and len(files) >= min(2, len(owners.slides)), 'anchor_files_invalid')
            for name, digest in files.items():
                ensure(name.startswith('.ppt-pilot/samples/') and name.endswith('.svg'), 'anchor_files_invalid')
                ensure(self.store.hash(name) == 'sha256:' + digest, 'anchor_binding_stale')
            if self.run.get('mode') == 'guided':
                history = self.run.get('interaction_history', {})
                record = history.get(anchor.get('approval_interaction_id'), {})
                evidence_id = anchor_snapshot_id(anchor)
                ensure(record.get('kind') == 'approval' and record.get('checkpoint') == 'anchor' and
                       record.get('decision') == 'approve' and record.get('status') == 'applied' and
                       isinstance(anchor.get('artifact_snapshot_id'), str) and
                       record.get('artifact_snapshot_id') == anchor['artifact_snapshot_id'] == evidence_id, 'approval_missing')
        if manifest['state'] == 'completed' and not self.run.get('active_visual_generation_batch'):
            return {'replay': True}
        ensure(self.run.get('active_visual_generation_batch', {}).get('batch_id') == args.batch_id)
        ensure(self.store.observed[path] == args.expected_manifest_sha256)
        ensure(all(tx['state'] in ('validated', 'promoted') for tx in txs.values()), 'validation_required')
        # Preflight every final before writing the first, so third-party bytes
        # cannot cause an avoidable partial promotion.
        outcomes = {}
        for ref, tx in txs.items():
            if tx['state'] == 'validated':
                observed = self.store.hash(tx['final_path'])
                outcome = validated_final_outcome(tx, observed)
                ensure(outcome != 'final_promotion_conflict', outcome)
                outcomes[ref] = (outcome, observed)
        for ref in manifest['transaction_refs']:
            tx = txs[ref]
            if ref not in outcomes:
                continue
            outcome, observed = outcomes[ref]
            self.write_barrier()  # fresh conformance without accepting changed run bytes
            if outcome == 'retry_atomic_promotion':
                data = self.store.read_bytes(tx['candidate_path'])
                ensure(sha(data) == tx['candidate_sha256'], 'candidate_hash_mismatch')
                self.store.write_bytes(tx['final_path'], data, observed)
            tx['state'] = 'promoted'
            self.persist_graph(manifest, txs, [ref])
        self.run.pop('active_visual_generation_batch', None)
        # Per-page checks passed; retain dirty flags until deck-level final QA.
        self.write_run()
        return {'batch_id': args.batch_id, 'promoted_slide_ids': manifest['ordered_slide_ids']}

    def publish_anchors(self, args):
        self.priority()
        ensure(self.run.get('stage') == 'anchor', 'anchor_stage_required')
        manifest, txs = self.graph(args.batch_id)
        owners = self.canonical(manifest, txs)
        ensure(self.store.observed[manifest_path(args.batch_id)] == args.expected_manifest_sha256)
        ensure(all(tx['state'] == 'validated' for tx in txs.values()), 'validation_required')
        # Existing canonical evidence proves which previous sample bytes we own.
        # It does not authorize changed bytes or approve the replacement digest.
        prior_anchor = (self.store.read_json('.ppt-pilot/' + self.run['source_deck']['evidence']).get('anchor', {})
                        if self.run.get('source_deck') else self.run.get('anchor', {}))
        prior_files = prior_anchor.get('files', {}) if isinstance(prior_anchor, dict) else {}
        ensure(isinstance(prior_files, dict), 'anchor_sample_conflict')
        samples = []
        for ref in manifest['transaction_refs']:
            tx = txs[ref]
            name = '.ppt-pilot/samples/' + tx['slide_id'] + '.svg'
            observed = self.store.hash(name)
            previous = prior_files.get(name)
            owned = (isinstance(previous, str) and re.fullmatch(r'[0-9a-f]{64}', previous)
                     and observed == 'sha256:' + previous)
            ensure(observed in ('none', tx['candidate_sha256']) or owned, 'anchor_sample_conflict')
            samples.append((name, tx, observed))
        for name, tx, observed in samples:
            self.store.write_bytes(name, self.store.read_bytes(tx['candidate_path']), observed)
        evidence = {'files': {name: tx['candidate_sha256'][7:] for name, tx, _ in samples},
            'style_sha256': owners.snapshots['theme_snapshot_id'][7:],
            'review_snapshot_id': self.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot']['snapshot_id']}
        evidence['artifact_snapshot_id'] = anchor_snapshot_id(evidence)
        return {'samples': [name for name, _, _ in samples], 'next_command': 'anchor_review',
                'anchor_evidence': evidence, 'approval_recorded': False}

    def prepare_recovery(self, args):
        self.priority()
        ref = transaction_path(args.slide_id, args.transaction_id)
        from _runtime_recovery import journal_path, replay
        journal_name = journal_path(args.slide_id, args.transaction_id)
        if self.store.hash(journal_name) != 'none':
            return replay(self, journal_name, self.store.read_json(journal_name), args.transaction_id, args.mode)
        manifest, txs = self.graph(verify_candidates=args.mode != 'retry')
        owners = Owners(self.store, self.run) if args.mode == 'recompose' else self.canonical(manifest, txs)
        ensure(ref in txs and txs[ref]['state'] == 'failed')
        tx = txs[ref]
        old_prompt = self.store.read_bytes('.ppt-pilot/' + tx['prompt_path'])
        _validate_prompt_by_value(old_prompt.decode('utf-8'), tx)
        if args.mode == 'retry':
            ensure(tx['failure_reason'] in RETRY or tx['failure_reason'] == 'prompt_write_failed', 'recovery_not_allowed')
            if tx['generation_attempt'] >= 3:
                self.production_blocker(tx, 'generation_attempts_exhausted')
                raise ValueError('generation_attempts_exhausted')
            # Preserve orphan evidence; an explicit retry replaces it only after
            # a fresh accepted result, so remove under exact observed hash here.
            candidate = self.store.hash(tx['candidate_path'])
            if candidate != 'none':
                self.store.remove_bytes(tx['candidate_path'], candidate)
            tx.update(state='compiled', failure_reason=None, candidate_sha256=None,
                dispatch_epoch=tx['dispatch_epoch'] + 1, host_attribution_id=None, host_task_id=None,
                validation=pending_validation())
            manifest['dispatch_epoch'] = max(manifest['dispatch_epoch'], tx['dispatch_epoch'])
            self.persist_graph(manifest, txs, [ref])
            return {'transaction_id': tx['transaction_id'], 'prompt_by_value': self.store.read_bytes('.ppt-pilot/' + tx['prompt_path']).decode()}
        if args.mode == 'fallback':
            self.fallback_evidence(tx)
            operation = dict(slide_id=tx['slide_id'], generation_intent='deterministic_fallback',
                             generation_trigger_id='fallback:' + tx['slide_id'] + ':' + tx['transaction_id'][7:] + ':2')
        else:
            ensure(owners.revisions, 'recovery_not_allowed')
            ensure(len(txs) == 1 or all(manifest[k] == owners.snapshots[k] for k in SNAPSHOTS), 'recovery_scope_conflict')
            operation = dict(slide_id=tx['slide_id'], generation_intent='user_recompose',
                             generation_trigger_id='interaction:' + owners.revisions[-1])
        identity, body_hash, envelope = owners.compile(operation)
        ensure(identity != tx['transaction_id'], 'recovery_not_allowed')
        replacement = dict(tx, transaction_id=identity, prompt_snapshot_id=identity,
            compiled_prompt_sha256=body_hash, candidate_path='slides/.candidates/' + tx['slide_id'] + '-' + identity[7:] + '.svg',
            state='compiled', generation_attempt=0, candidate_sha256=None, failure_reason=None,
            dispatch_epoch=tx['dispatch_epoch']+1, host_attribution_id=None, host_task_id=None,
            validation=pending_validation(), timing=[], **{k: operation[k] for k in ('generation_intent', 'generation_trigger_id')})
        new_ref = _transaction_ref(replacement)
        ensure(self.store.hash(new_ref) == 'none')
        old_manifest = copy.deepcopy(manifest)
        manifest['transaction_refs'][manifest['transaction_refs'].index(ref)] = new_ref
        manifest.update(owners.snapshots)
        del txs[ref]
        txs[new_ref] = replacement
        self.refresh(manifest, txs)
        validate_v2_manifest(manifest, txs)
        journal = {'schema_version': 1, 'kind': 'visual_generation_recovery', 'mode': args.mode,
            'slide_id': tx['slide_id'], 'batch_id': tx['batch_id'], 'expected_run_sha256': self.store.observed[self.run_name],
            'old_transaction_ref': ref, 'old_transaction_sha256': self.store.observed[ref],
            'new_transaction_ref': new_ref, 'new_transaction_sha256': sha(canonical(replacement)),
            'manifest_path': manifest_path(tx['batch_id']), 'old_manifest': old_manifest,
            'old_manifest_sha256': sha(canonical(old_manifest)), 'new_manifest': manifest,
            'new_manifest_sha256': sha(canonical(manifest)), 'prompt_path': '.ppt-pilot/' + tx['prompt_path'],
            'old_prompt': old_prompt.decode('utf-8'), 'old_prompt_sha256': sha(old_prompt),
            'new_prompt': envelope.decode('utf-8'), 'new_prompt_sha256': sha(envelope), 'new_transaction': replacement,
            'expected_transaction_hashes': {old_ref: self.store.observed[old_ref] for old_ref in old_manifest['transaction_refs']}}
        ensure(self.store.observed[journal['manifest_path']] == journal['old_manifest_sha256'])
        from _runtime_recovery import validate_journal
        validate_journal(self, journal, args.transaction_id, args.mode)
        self.store.write_json(journal_name, journal, 'none')
        return replay(self, journal_name, journal, args.transaction_id, args.mode)

    def fallback_evidence(self, tx):
        ensure(tx['failure_reason'] in ('svg_contract_failed', 'fact_source_mismatch', 'visual_qa_failed') and tx['candidate_sha256'] is not None, 'recovery_not_allowed')
        _, qa_owner = self.qa_owner()
        records = [r for r in qa_owner['records'] if r.get('transaction_id') == tx['transaction_id'] and r.get('candidate_sha256') == tx['candidate_sha256']]
        ensure(len(records) == 1 and records[0].get('fix_attempts_for_candidate') == 2 and
               isinstance(records[0].get('patch_defects'), list) and len(records[0]['patch_defects']) == 2 and
               all(isinstance(d, dict) and set(d) == {'defect_id', 'outcome'} and
                   isinstance(d['defect_id'], str) and d['defect_id'] and d['outcome'] == 'failed'
                   for d in records[0]['patch_defects']), 'recovery_not_allowed')

    def resume(self, args):
        blocker = self.run.get('visual_generation_blocker')
        retrying_generator = (isinstance(blocker, dict) and not self.run.get('active_visual_generation_batch') and
            blocker.get('state') == blocker.get('reason') == 'generator_unavailable' and
            blocker.get('resource') == 'none' and blocker.get('status') == 'active')
        self.priority(allow_blocker=retrying_generator, allow_legacy=True)
        from _runtime_recovery import pending
        recoveries = pending(self)
        if recoveries:
            return {'next_command': 'prepare-recovery', 'recoveries': recoveries}
        if self.run.get('visual_generation_transaction'):
            ensure(not self.run.get('active_visual_generation_batch'))
            return {'next_command': 'migrate-v1'}
        if not self.run.get('active_visual_generation_batch'):
            # Prepared-but-unpublished batches require explicit same-request replay.
            directory = self.store.path('.ppt-pilot/visual-generation-batches')
            completed = {}
            if directory.exists():
                for path in sorted(directory.iterdir()):
                    if path.suffix == '.json':
                        manifest, txs = self.graph(path.stem, active=False, verify_finals=False)
                        if manifest['state'] != 'completed':
                            self.canonical(manifest, txs)
                            return {'next_command': 'prepare-batch', 'batch_id': manifest['batch_id'], 'pointer_missing': True}
                        for tx in txs.values():
                            completed.setdefault(tx['slide_id'], []).append(tx)
            current = {}
            for sid, versions in completed.items():
                text = self.store.read_bytes('.ppt-pilot/generation-prompts/' + sid + '.md').decode('utf-8')
                matching = []
                for tx in versions:
                    try:
                        _validate_prompt_by_value(text, tx)
                        matching.append(tx)
                    except ValueError:
                        pass
                ensure(len({tx['transaction_id'] for tx in matching}) == 1, 'prompt_snapshot_conflict')
                current[sid] = matching[0]
                ensure(self.store.hash(current[sid]['final_path']) == current[sid]['candidate_sha256'], 'final_promotion_conflict')
            if self.run.get('stage') in ('anchor', 'production'):
                owners = Owners(self.store, self.run)
                if retrying_generator:
                    ensure(blocker.get('selected_style_id') == owners.theme['selected_style_id'] and
                        blocker.get('storyboard_snapshot_id') == owners.snapshots['storyboard_snapshot_id'] and
                        blocker.get('theme_snapshot_id') == owners.snapshots['theme_snapshot_id'],
                        'prompt_snapshot_conflict')
                operations = []
                for sid in owners.slides:
                    if sid not in self.run.get('dirty_slides', []):
                        continue
                    revisions = [rid for rid in owners.revisions if self.run['interaction_history'][rid].get('affected_scope') in ('deck', 'anchor') or sid in self.run['interaction_history'][rid].get('affected_scope', [])]
                    operation = {'slide_id': sid, 'generation_intent': 'user_recompose' if revisions else 'initial_generation',
                        'generation_trigger_id': 'interaction:' + revisions[-1] if revisions else 'initial:' + sid + ':' + owners.snapshots['storyboard_snapshot_id']}
                    current_id = None
                    if sid in current:
                        try:
                            current_id = owners.compile(current[sid])[0]
                        except ValueError:
                            pass  # A valid historical operation may be stale now.
                    if sid not in current or current[sid]['transaction_id'] != current_id:
                        operations.append(operation)
                operations = operations[:5]
                slides = [op['slide_id'] for op in operations]
                if retrying_generator:
                    ensure(slides and slides[0] == blocker.get('slide_id'))
                if slides:
                    request = {'schema_version': 1, 'kind': 'prepare_visual_generation_batch',
                        'expected_snapshots': owners.snapshots, 'ordered_slide_ids': slides,
                        'generation_operations': operations}
                    request['request_id'] = sha(canonical(request).rstrip(b'\n'))
                    request['expected_run_sha256'] = self.store.observed[self.run_name]
                    return {'next_command': 'prepare-batch', 'prepare_request': request}
            return {'next_command': 'stage_scan'}
        manifest, txs = self.graph()
        self.canonical(manifest, txs)
        reservations = self.reservations(manifest, txs)
        orphans = [tx['candidate_path'] for tx in txs.values() if tx['state'] == 'generating' and self.store.hash(tx['candidate_path']) != 'none']
        ensure(not orphans, 'orphan_candidate')
        ready = all(tx['state'] in ('validated', 'promoted') for tx in txs.values())
        promotion_command = 'promote'
        if ready and self.run.get('stage') == 'anchor':
            published = all(self.store.hash('.ppt-pilot/samples/' + tx['slide_id'] + '.svg') == tx['candidate_sha256'] for tx in txs.values())
            promotion_command = 'anchor_review' if published else 'publish-anchors'
        return {'batch_id': manifest['batch_id'], 'transactions': [{'slide_id': tx['slide_id'], 'transaction_id': tx['transaction_id'], 'state': tx['state']} for tx in txs.values()],
            'reservations': [d for _, d in reservations.values()], 'promotion_cursor': manifest['promotion_cursor'],
            'next_command': 'durable_lookup' if any(d['state'] == 'reserved' for _, d in reservations.values()) else
                            'bind-task' if any(txs[ref]['state'] == 'compiled' for ref in reservations) else
                            'prepare-recovery' if manifest['state'] == 'blocked' else promotion_command if ready else 'dispatch-plan'}

    def migrate_v1(self, args):
        self.priority(allow_legacy=True)
        if not self.run.get('visual_generation_transaction'):
            self.graph()
            return {'replay': True}
        ensure(not self.run.get('active_visual_generation_batch'))
        legacy = self.run['visual_generation_transaction']
        prior = self.store.hash(legacy['final_path'])
        probe = migrate_v1_run_to_v2(self.run, {'observed_prior_final_sha256': prior})
        ensure(probe['status'] == 'migrated')
        ref = _transaction_ref(probe['transaction'])
        path = manifest_path(probe['manifest']['batch_id'])
        durable = {}
        for name, key in ((ref, 'transaction_bytes_base64'), (path, 'manifest_bytes_base64')):
            if self.store.hash(name) != 'none':
                durable[key] = base64.b64encode(self.store.read_bytes(name)).decode()
        migrated = migrate_v1_run_to_v2(self.run, {'observed_prior_final_sha256': prior, 'durable': durable})
        ensure(migrated['status'] == 'migrated')
        for owner in migrated['write_order']:
            if owner == 'run':
                self.run = migrated['run']
                self.write_run()
            else:
                self.store.write_bytes(ref if owner == 'transaction' else path, migrated[owner + '_bytes'], 'none')
        return {'batch_id': migrated['manifest']['batch_id'], 'generator_calls': 0}

    def execute(self, args):
        self.audit()
        command = getattr(self, args.command.replace('-', '_'))
        if args.command not in ('prepare-recovery', 'resume'):
            from _runtime_recovery import pending
            ensure(not pending(self), 'recovery_pending')
        if args.command in ('resume', 'dispatch-plan'):
            return command(args)
        with self.store.lock():
            self.audit()
            if args.command != 'prepare-recovery':
                from _runtime_recovery import pending
                ensure(not pending(self), 'recovery_pending')
            self.store.before_write = self.write_barrier
            return command(args)
