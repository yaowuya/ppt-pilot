"""Mechanical page-local settlement and delivery finalization for the fixed runtime."""
import copy
from types import SimpleNamespace
import re

from _delivery_contract import PAGE_FAILURE_REASONS, validate_delivery
from _generation_runtime import V2_VALIDATION_CHECKS, _validate_prompt_by_value
from _run_store import sha
from _runtime_owners import Owners


TERMINAL_BATCH_STATES = {'completed', 'complete', 'partial', 'failed'}


def _require(value, code='visual_generation_state_conflict'):
    if not value:
        raise ValueError(code)


class Delivery:
    """Hide omission, settlement, action planning and final partition mechanics."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store
        self.omission_reasons = {}

    def _policy(self):
        return self.runtime.run.get('production_policy', 'strict')

    def _validate_skip_request(self, slide_ids, manifest, txs, allow_partial):
        _require(isinstance(slide_ids, list) and len(slide_ids) == len(set(slide_ids)) and
                 all(isinstance(sid, str) and re.fullmatch(r'S[0-9]+', sid) for sid in slide_ids),
                 'invalid_runtime_input')
        _require(not slide_ids or allow_partial or self._policy() == 'best_effort',
                 'partial_delivery_not_authorized')
        by_slide = dict(zip(manifest['ordered_slide_ids'], manifest['transaction_refs']))
        for sid in slide_ids:
            _require(sid in by_slide, 'skip_slide_not_failed')
            ref = by_slide[sid]
            tx = txs[ref]
            _require(tx['state'] == 'failed' and tx['failure_reason'] in PAGE_FAILURE_REASONS,
                     'skip_slide_not_failed')

    def _record_policy(self, allow_partial):
        if not allow_partial:
            return
        _require(self._policy() in ('strict', 'best_effort'), 'invalid_production_policy')
        if self._policy() != 'best_effort':
            self.runtime.run['production_policy'] = 'best_effort'
            self.runtime.write_run()

    def _omit(self, manifest, txs, explicit):
        if self._policy() != 'best_effort':
            return []
        existing = list(manifest.get('omitted_transaction_refs', []))
        hashes = dict(manifest.get('omitted_transaction_sha256', {}))
        explicit = set(explicit)
        added = []
        for ref in manifest['transaction_refs']:
            tx = txs[ref]
            if ref in existing:
                if tx['slide_id'] in explicit:
                    self.omission_reasons[ref] = 'user_skipped'
                continue
            if tx['state'] != 'failed' or tx['failure_reason'] not in PAGE_FAILURE_REASONS:
                continue
            if tx['slide_id'] not in explicit and tx['generation_attempt'] < 3:
                continue
            observed = self.store.hash(ref)
            _require(observed != 'none', 'visual_generation_state_conflict')
            existing.append(ref)
            hashes[ref] = observed
            self.omission_reasons[ref] = ('user_skipped' if tx['slide_id'] in explicit else
                                          'attempts_exhausted')
            added.append(ref)
        if added:
            manifest['omitted_transaction_refs'] = existing
            manifest['omitted_transaction_sha256'] = hashes
            self.runtime.persist_graph(manifest, txs, [])
        return added

    def action_plan(self, manifest, txs):
        reservations = self.runtime.reservations(manifest, txs)
        if manifest.get('state') == 'superseded':
            return {'batch_id': manifest['batch_id'], 'dispatchable': [], 'promotable': [],
                    'revalidation_required': [],
                    'recoverable': [], 'exhausted': [], 'recoveries': [],
                    'global_blockers': [],
                    'reservations': [value for _, value in reservations.values()],
                    'in_flight': [], 'next_command': 'retire-batch',
                    'retirement_pending': True, 'same_run_required': True}
        omitted = set(manifest.get('omitted_transaction_refs', []))
        global_blockers = [{'slide_id': tx['slide_id'], 'transaction_id': tx['transaction_id'],
                            'failure_reason': tx['failure_reason']}
                           for ref, tx in txs.items() if tx['state'] == 'failed' and
                           ref not in omitted and tx['failure_reason'] not in PAGE_FAILURE_REASONS]
        if global_blockers:
            return {'batch_id': manifest['batch_id'], 'dispatchable': [], 'promotable': [],
                    'revalidation_required': [],
                    'recoverable': [], 'exhausted': [], 'recoveries': [],
                    'global_blockers': global_blockers,
                    'reservations': [value for _, value in reservations.values()],
                    'in_flight': [], 'next_command': 'resolve-global-failure',
                    'same_run_required': True}
        owners = Owners(self.store, self.runtime.run)
        from _runtime_revalidation import probe
        promotable, revalidation_required = [], []
        if self.runtime.run.get('stage') == 'production':
            for ref in manifest['transaction_refs']:
                tx = txs[ref]
                if tx['state'] != 'validated':
                    continue
                failure = probe(self.runtime, tx, owners.title_min_size)
                if failure is None:
                    promotable.append({'slide_id': tx['slide_id'], 'transaction_id': tx['transaction_id']})
                else:
                    revalidation_required.append({'slide_id': tx['slide_id'],
                        'transaction_id': tx['transaction_id'], **failure})
        dispatchable = [{'slide_id': txs[ref]['slide_id'], 'transaction_id': txs[ref]['transaction_id']}
                        for ref in manifest['transaction_refs']
                        if txs[ref]['state'] == 'compiled' and ref not in reservations]
        omitted_slides = {txs[ref]['slide_id'] for ref in omitted}
        raw = [item for item in self.runtime.failed_recoveries(
            manifest, txs, owners)
            if item['slide_id'] not in omitted_slides]
        exhausted, recoverable = [], []
        for item in raw:
            if item['remaining_attempts'] == 0:
                item = dict(item)
                item.pop('mode', None)
                item.update(next_command='review-anchor-policy' if self.runtime.run.get('stage') == 'anchor' else 'advance',
                            blocked_reason='generation_attempts_exhausted',
                            authorization='select_another_representative' if self.runtime.run.get('stage') == 'anchor' else '--allow-partial')
                exhausted.append(item)
            else:
                recoverable.append(item)
        in_flight = [{'slide_id': tx['slide_id'], 'transaction_id': tx['transaction_id'],
                      'host_task_id': tx['host_task_id']} for tx in txs.values()
                     if tx['state'] == 'generating']
        if revalidation_required:
            next_command = 'advance'
        elif promotable:
            next_command = 'promote'
        elif any(dispatch['state'] == 'reserved' for _, dispatch in reservations.values()):
            next_command = 'durable_lookup'
        elif any(txs[ref]['state'] == 'compiled' for ref in reservations):
            next_command = 'bind-task'
        elif dispatchable:
            next_command = 'dispatch-plan'
        elif in_flight:
            next_command = 'wait-for-generator'
        elif recoverable:
            next_command = recoverable[0]['next_command']
        elif exhausted:
            next_command = 'review-anchor-policy' if self.runtime.run.get('stage') == 'anchor' else 'advance'
        else:
            next_command = 'stage_scan'
        return {'batch_id': manifest['batch_id'], 'dispatchable': dispatchable,
                'promotable': promotable, 'revalidation_required': revalidation_required,
                'recoverable': recoverable,
                'exhausted': exhausted, 'recoveries': recoverable + exhausted,
                'global_blockers': [],
                'reservations': [value for _, value in reservations.values()],
                'in_flight': in_flight, 'next_command': next_command,
                'same_run_required': True}

    def _settled_outcomes(self, owners=None):
        directory = self.store.path('.ppt-pilot/visual-generation-batches')
        delivered, missing = {}, {}
        if not directory.exists():
            return delivered, missing
        versions = {}
        for path in sorted(directory.iterdir()):
            if path.suffix != '.json':
                continue
            # Final paths are shared by revisions; only the selected current owner can bind them.
            manifest, txs = self.runtime.graph(path.stem, active=False,
                                               verify_candidates=False, verify_finals=False)
            if manifest['state'] not in TERMINAL_BATCH_STATES:
                continue
            omitted = set(manifest.get('omitted_transaction_refs', []))
            for ref in manifest['transaction_refs']:
                tx = txs[ref]
                if ref in omitted:
                    outcome = ('missing', manifest['omitted_transaction_sha256'][ref])
                elif tx['state'] == 'promoted':
                    outcome = ('delivered', None)
                else:
                    continue
                versions.setdefault(tx['slide_id'], []).append((ref, tx, outcome))
        for sid, candidates in versions.items():
            prompt = self.store.read_bytes('.ppt-pilot/generation-prompts/' + sid + '.md').decode('utf-8')
            matching = []
            for candidate in candidates:
                try:
                    _validate_prompt_by_value(prompt, candidate[1])
                    if (owners is not None and
                            owners.compile(candidate[1])[0] != candidate[1]['transaction_id']):
                        continue
                except ValueError:
                    continue
                matching.append(candidate)
            if not matching:
                continue
            identities = {candidate[1]['transaction_id'] for candidate in matching}
            _require(len(identities) == 1, 'prompt_snapshot_conflict')
            ref, tx, outcome = matching[0]
            if outcome[0] == 'missing':
                missing[sid] = (ref, tx, outcome[1])
            else:
                _require(self.store.hash(tx['final_path']) == tx['candidate_sha256'],
                         'final_promotion_conflict')
                delivered[sid] = (ref, tx)
        return delivered, missing

    def _targets(self, owners):
        targets = list(owners.slides)
        if self.runtime.run.get('source_deck'):
            from _workflow_gate import Gate
            gate = Gate(self.store.root)
            gate.run = self.runtime.run
            gate.import_binding()
            _require(gate.targets == targets, 'delivery_targets_changed')
            targets = list(gate.targets)
        return targets

    def _prepare_delivery_or_next(self):
        owners = Owners(self.store, self.runtime.run)
        targets = self._targets(owners)
        delivered, missing = self._settled_outcomes(owners)
        processed = set(delivered) | set(missing)
        if processed != set(targets):
            unhandled = [sid for sid in targets if sid not in processed]
            _require(all(sid in self.runtime.run.get('dirty_slides', []) for sid in unhandled),
                     'delivery_partition_incomplete')
            operations = []
            history = self.runtime.run.get('interaction_history', {})
            for sid in unhandled[:5]:
                revisions = [rid for rid in owners.revisions
                    if history[rid].get('affected_scope') in ('deck', 'anchor') or
                    sid in history[rid].get('affected_scope', [])]
                operations.append({'slide_id': sid,
                    'generation_intent': 'user_recompose' if revisions else 'initial_generation',
                    'generation_trigger_id': ('interaction:' + revisions[-1] if revisions else
                        'initial:' + sid + ':' + owners.snapshots['storyboard_snapshot_id'])})
            from _run_store import canonical
            request = {'schema_version': 1, 'kind': 'prepare_visual_generation_batch',
                'expected_snapshots': owners.snapshots,
                'ordered_slide_ids': [item['slide_id'] for item in operations],
                'generation_operations': operations}
            request['request_id'] = sha(canonical(request).rstrip(b'\n'))
            request['expected_run_sha256'] = self.store.observed[self.runtime.run_name]
            return {'next_command': 'prepare-batch', 'prepare_request': request,
                    'unhandled_slide_ids': unhandled, 'capability_refresh_required': True}
        delivered_ids = [sid for sid in targets if sid in delivered]
        missing_items = []
        for sid in targets:
            if sid not in missing:
                continue
            ref, tx, transaction_hash = missing[sid]
            missing_items.append({'slide_id': sid,
                'reason': self.omission_reasons.get(ref,
                    'attempts_exhausted' if tx['generation_attempt'] >= 3 else 'user_skipped'),
                'failure_reason': tx['failure_reason'], 'generation_attempt': tx['generation_attempt'],
                'transaction_id': tx['transaction_id'], 'transaction_ref': ref,
                'transaction_sha256': transaction_hash})
        storyboard_path = next(name for name in
            ('.ppt-pilot/故事板.md', '.ppt-pilot/storyboard.md') if self.store.hash(name) != 'none')
        delivery = {'schema_version': 1,
            'status': 'prepared' if delivered_ids else 'failed', 'policy': self._policy(),
            'target_slide_ids': targets, 'delivered_slide_ids': delivered_ids,
            'missing_slides': missing_items, 'storyboard_sha256': self.store.hash(storyboard_path),
            'theme_sha256': self.store.hash('.ppt-pilot/theme.json'), 'quality_report_sha256': None,
            'slide_sha256': {sid: self.store.hash('slides/' + sid + '.svg') for sid in delivered_ids}}
        validate_delivery(delivery, targets)
        candidate_run = copy.deepcopy(self.runtime.run)
        candidate_run['delivery'] = delivery
        candidate_run['stage'] = 'qa' if delivered_ids else 'failed'
        from _workflow_gate import Gate
        gate = Gate(self.store.root)
        gate.run = candidate_run
        gate.conformance()
        self.runtime.run = candidate_run
        self.runtime.write_run()
        return {'next_command': 'finalize' if delivered_ids else 'delivery-failed',
                'delivery': delivery}

    def _ordinary_quality_report(self, delivered, owners=None):
        name, owner = self.runtime.qa_owner()
        fields = {'schema_version', 'kind', 'slide_id', 'transaction_id',
                  'candidate_sha256', 'checks', 'defect_id', 'failure_reason'}
        delivered_outcomes, _ = self._settled_outcomes(owners)
        for sid in delivered:
            _require(sid in delivered_outcomes, 'final_qa_required')
            tx = delivered_outcomes[sid][1]
            records = [record for record in owner['records']
                       if isinstance(record, dict) and record.get('transaction_id') == tx['transaction_id']
                       and record.get('candidate_sha256') == tx['candidate_sha256']]
            _require(len(records) == 1, 'final_qa_required')
            record = records[0]
            checks = record.get('checks')
            _require(set(record) == fields and record.get('schema_version') == 1 and
                     record.get('kind') == 'visual_generation_qa' and record.get('slide_id') == sid and
                     isinstance(checks, dict) and set(checks) == V2_VALIDATION_CHECKS and
                     all(value == 'passed' for value in checks.values()) and
                     record.get('defect_id') is None and record.get('failure_reason') is None,
                     'final_qa_required')
        final_review = owner.get('final_review')
        _require(isinstance(final_review, dict) and set(final_review) == {'status', 'slides'} and
                 final_review['status'] == 'PASS' and isinstance(final_review['slides'], list), 'final_qa_required')
        from _workflow_gate import Gate
        from _workflow_evidence import qa
        gate = Gate(self.store.root)
        gate.run = dict(self.runtime.run, dirty_slides=[item['slide_id'] for item in self.runtime.run['delivery']['missing_slides']])
        gate.targets = list(self.runtime.run['delivery']['target_slide_ids'])
        gate.evidence = {'qa': dict(final_review, report={'path': name, 'sha256': self.store.hash(name)[7:]})}
        qa(gate)
        for relative, expected in gate.hashes.items():
            _require(self.store.hash(relative) == 'sha256:' + expected, 'final_qa_required')
        return name

    def _source_quality_report(self):
        from _workflow_gate import Gate
        gate = Gate(self.store.root)
        gate.run = self.runtime.run
        gate.import_binding()
        report = gate.evidence.get('qa', {}).get('report', {})
        name = report.get('path')
        _require(isinstance(name, str) and name, 'final_qa_required')
        return name

    def _preflight_final_run(self, candidate):
        from _workflow_gate import Gate, STAGES
        gate = Gate(self.store.root)
        gate.run = candidate
        gate.conformance()
        if candidate.get('source_deck'):
            _require(candidate.get('mode') in ('guided', 'auto') and
                     candidate.get('deck_id') == gate.root.name, 'invalid_run_identity')
            gate.recovery()
            gate.import_binding()
            gate.delivery_record(gate.targets)
            from _workflow_evidence import check_stages
            check_stages(gate, STAGES.index('complete'))
        for name, expected in gate.hashes.items():
            _require(self.store.hash(name) == 'sha256:' + expected, 'final_qa_required')

    def finalize(self, args):
        del args
        self.runtime.priority()
        delivery = self.runtime.run.get('delivery')
        _require(isinstance(delivery, dict), 'delivery_missing')
        owners = None
        if not self.runtime.run.get('source_deck'):
            owner_run = self.runtime.run
            if owner_run.get('stage') == 'partial':
                owner_run = dict(owner_run, stage='qa')
            owners = Owners(self.store, owner_run)
        if delivery.get('status') in ('complete', 'partial'):
            _require(self.runtime.run.get('stage') == delivery['status'], 'delivery_status_mismatch')
            delivered = list(delivery['delivered_slide_ids'])
            missing_slide_ids = [item['slide_id'] for item in delivery['missing_slides']]
            _require(self.runtime.run.get('dirty_slides') == missing_slide_ids,
                     'dirty_slides')
            quality_path = (self._source_quality_report() if self.runtime.run.get('source_deck') else
                            self._ordinary_quality_report(delivered, owners))
            _require(self.store.hash(quality_path) == delivery.get('quality_report_sha256'),
                     'final_qa_required')
            if self.runtime.run.get('source_deck'):
                from _workflow_gate import check_run
                checked = check_run(self.store.root, delivery['status'])
                _require(checked.get('status') == 'PASS', 'final_qa_required')
            return {'replay': True, 'delivered_slide_ids': delivered,
                    'missing_slide_ids': missing_slide_ids}
        _require(self.runtime.run.get('stage') == 'qa' and delivery.get('status') == 'prepared' and
                 not self.runtime.run.get('active_visual_generation_batch') and
                 bool(delivery.get('delivered_slide_ids')), 'delivery_not_prepared')
        delivered = list(delivery['delivered_slide_ids'])
        missing_ids = [item['slide_id'] for item in delivery['missing_slides']]
        quality_path = (self._source_quality_report() if self.runtime.run.get('source_deck') else
                        self._ordinary_quality_report(delivered))
        quality_hash = self.store.hash(quality_path)
        _require(quality_hash != 'none', 'final_qa_required')
        status = 'partial' if missing_ids else 'complete'
        candidate_delivery = copy.deepcopy(delivery)
        candidate_delivery.update(status=status, quality_report_sha256=quality_hash)
        validate_delivery(candidate_delivery, delivery['target_slide_ids'], final=True)
        dirty = self.runtime.run.get('dirty_slides')
        _require(isinstance(dirty, list) and len(dirty) == len(set(dirty)) and
                 set(missing_ids) <= set(dirty), 'dirty_slides')
        candidate_run = copy.deepcopy(self.runtime.run)
        candidate_run['delivery'] = candidate_delivery
        candidate_run['stage'] = status
        delivered_set = set(delivered)
        remaining_dirty = [sid for sid in dirty if sid not in delivered_set]
        _require(len(remaining_dirty) == len(missing_ids) and
                 set(remaining_dirty) == set(missing_ids), 'dirty_slides')
        candidate_run['dirty_slides'] = remaining_dirty
        self._preflight_final_run(candidate_run)
        previous_run = self.runtime.run
        previous_barrier = self.store.before_write

        def final_barrier():
            if previous_barrier:
                previous_barrier()
            if not candidate_run.get('source_deck'):
                self._ordinary_quality_report(delivered, owners)
            self._preflight_final_run(candidate_run)

        self.runtime.run = candidate_run
        self.store.before_write = final_barrier
        try:
            self.runtime.write_run()
        except Exception:
            self.runtime.run = previous_run
            raise
        finally:
            self.store.before_write = previous_barrier
        if candidate_run.get('source_deck'):
            from _workflow_gate import check_run
            checked = check_run(self.store.root, status)
            errors = checked.get('errors', [])
            _require(checked.get('status') == 'PASS',
                     errors[0].get('code', 'final_qa_required') if errors else 'final_qa_required')
        return {'status': status, 'delivered_slide_ids': delivered,
                'missing_slide_ids': missing_ids, 'quality_report_sha256': quality_hash}

    def advance(self, args):
        self.runtime.priority(allow_legacy=True)
        _require(self.runtime.run.get('stage') in ('production', 'qa', 'complete', 'partial', 'failed'),
                 'production_stage_required')
        _require(isinstance(args.skip_slide, list) and all(isinstance(sid, str) for sid in args.skip_slide) and
                 len(args.skip_slide) == len(set(args.skip_slide)) and
                 all(re.fullmatch(r'S[0-9]+', sid) for sid in args.skip_slide), 'invalid_runtime_input')
        from _runtime_recovery import journal_path, pending, replay
        recoveries = pending(self.runtime)
        legacy = self.runtime.run.get('visual_generation_transaction')
        _require(not args.skip_slide or not recoveries and legacy is None, 'recovery_pending')
        for item in recoveries:
            name = journal_path(item['slide_id'], item['transaction_id'])
            replay(self.runtime, name, self.store.read_json(name), item['transaction_id'], item['mode'])
        if legacy is not None:
            _require(isinstance(legacy, dict) and bool(legacy), 'visual_generation_state_conflict')
            self.runtime.migrate_v1(args)
        if self.runtime.run.get('delivery') is not None:
            delivery = self.runtime.run['delivery']
            _require(set(args.skip_slide) <= {item['slide_id'] for item in delivery['missing_slides']},
                     'skip_slide_not_failed')
            next_command = ('finalize' if delivery.get('status') == 'prepared' else
                            'delivery-failed' if delivery.get('status') == 'failed' else 'stage_scan')
            return {'next_command': next_command, 'delivery': delivery}
        pointer = self.runtime.run.get('active_visual_generation_batch')
        if not pointer:
            _require(not args.skip_slide, 'skip_slide_not_failed')
            owners = Owners(self.store, self.runtime.run)
            self._targets(owners)
            self._settled_outcomes(owners)
            self._record_policy(args.allow_partial)
            return self._prepare_delivery_or_next()
        manifest, txs = self.runtime.graph()
        self.runtime.canonical(manifest, txs)
        if manifest.get('state') == 'superseded':
            return self.action_plan(manifest, txs)
        _require(not manifest.get('omitted_transaction_refs') or self._policy() == 'best_effort',
                 'partial_delivery_not_authorized')
        global_failures = [(ref, tx) for ref, tx in txs.items() if tx['state'] == 'failed' and
                           ref not in manifest.get('omitted_transaction_refs', []) and
                           tx['failure_reason'] not in PAGE_FAILURE_REASONS]
        if global_failures:
            raise ValueError(global_failures[0][1]['failure_reason'])
        self._validate_skip_request(args.skip_slide, manifest, txs, args.allow_partial)
        self._record_policy(args.allow_partial)
        if any(tx['state'] == 'validated' for tx in txs.values()):
            self.runtime.promote(SimpleNamespace(batch_id=manifest['batch_id'],
                expected_manifest_sha256=self.store.observed[
                    '.ppt-pilot/visual-generation-batches/' + manifest['batch_id'] + '.json']))
        if self.runtime.run.get('active_visual_generation_batch'):
            manifest, txs = self.runtime.graph()
            self._omit(manifest, txs, args.skip_slide)
            if manifest['state'] in TERMINAL_BATCH_STATES:
                self.runtime.persist_graph(manifest, txs, [])
                self.runtime.run.pop('active_visual_generation_batch', None)
                self.runtime.write_run()
            else:
                return self.action_plan(manifest, txs)
        return self._prepare_delivery_or_next()
