"""Exercise adaptive generation contracts against the actual pure planner."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

from test_visual_generation_contract import (
    GENERATION_PROMPT_METADATA_FIELDS, _transaction_ref, negotiate_host_capability,
    rebuild_batch_cursors, schedule_epoch, validate_v2_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/ppt-start/scripts'))
FIXTURES = ROOT / 'tests/fixtures'


def batch(width, count=None):
    count = width if count is None else count
    original = json.loads((FIXTURES / 'visual-generation-batch-v2-cases.json').read_text('utf-8'))['cases']['four-slide-active']
    manifest = copy.deepcopy(original['manifest'])
    template = next(iter(original['transactions'].values()))
    manifest.update(batch_width=width, ordered_slide_ids=[], transaction_refs=[], blocker_cursor=count)
    transactions, prompts = {}, {}
    for number in range(1, count + 1):
        sid = 'S%02d' % number
        suffix = hashlib.sha256(sid.encode()).hexdigest()
        tx = copy.deepcopy(template)
        tx.update(slide_id=sid, transaction_id='sha256:' + suffix, prompt_snapshot_id='sha256:' + suffix,
                  prompt_path='generation-prompts/' + sid + '.md', final_path='slides/' + sid + '.svg',
                  candidate_path='slides/.candidates/' + sid + '-' + suffix + '.svg')
        body = '# Role\nComplete isolated prompt for ' + sid + '.\n'
        tx['compiled_prompt_sha256'] = 'sha256:' + hashlib.sha256(body.encode()).hexdigest()
        metadata = {key: 'test' for key in GENERATION_PROMPT_METADATA_FIELDS}
        metadata.update(slide_id=sid, prompt_snapshot_id=tx['prompt_snapshot_id'],
                        workspace_output_path=tx['final_path'], format='creative-brief-v1')
        prompts[sid] = '\n'.join(['# ' + sid + ' 页面生成 Prompt', '', '## Snapshot metadata'] +
                                ['- **%s**：%s' % (key, metadata[key]) for key in GENERATION_PROMPT_METADATA_FIELDS] +
                                ['', '## Compiled Prompt', '', body])
        ref = _transaction_ref(tx)
        manifest['ordered_slide_ids'].append(sid)
        manifest['transaction_refs'].append(ref)
        transactions[ref] = tx
    return manifest, transactions, prompts


def observation(successes=0, capacity=10):
    return {'schema_version': 1,
            'capabilities': {'fresh_isolation': True, 'concurrent_tasks': True,
                             'durable_lookup': True, 'worker_capacity': capacity},
            'ready_slide_ids': ['S%02d' % n for n in range(1, 21)], 'in_flight_slide_ids': [],
            'history': [{'event_id': 'validated-%d' % n, 'outcome': 'validated'} for n in range(successes)]}


class AdaptiveContractTests(unittest.TestCase):
    def test_manifest_supports_five_eight_ten_and_legacy_tails(self):
        for width in (3, 4, 5, 8, 10):
            for count in (1, width):
                with self.subTest(width=width, count=count):
                    manifest, transactions, _ = batch(width, count)
                    validate_v2_manifest(manifest, transactions)
                    self.assertEqual(rebuild_batch_cursors(manifest, transactions), (0, count))

    def test_manifest_rejects_invalid_width_and_incomplete_or_reordered_inventory(self):
        for width in (0, 2, 11, True, 5.0, '5'):
            manifest, transactions, _ = batch(5)
            manifest['batch_width'] = width
            with self.subTest(width=width), self.assertRaises(ValueError):
                validate_v2_manifest(manifest, transactions)
        for mutate in (lambda m, t: m['ordered_slide_ids'].reverse(),
                       lambda m, t: t.pop(m['transaction_refs'][-1]),
                       lambda m, t: m['transaction_refs'].reverse()):
            manifest, transactions, _ = batch(10)
            mutate(manifest, transactions)
            with self.assertRaises(ValueError):
                validate_v2_manifest(manifest, transactions)

    def test_actual_planner_automatically_increases_target_and_resets_on_pressure(self):
        from _generation_concurrency import plan_dispatch
        for successes, target in ((0, 5), (5, 7), (10, 9), (15, 10), (25, 10)):
            with self.subTest(successes=successes):
                value = observation(successes)
                result = plan_dispatch(value)
                self.assertEqual(result['target_concurrency'], target)
                self.assertEqual(result['effective_concurrency'], target)
                self.assertEqual(len(result['dispatch_slide_ids']), target)
                duplicate = copy.deepcopy(value)
                duplicate['history'] += copy.deepcopy(value['history'])
                self.assertEqual(plan_dispatch(duplicate), result)
        for outcome in ('rate_limited', 'timeout', 'capacity_limited', 'failed'):
            value = observation(15)
            value['history'].append({'event_id': 'pressure', 'outcome': outcome})
            self.assertEqual(plan_dispatch(value)['target_concurrency'], 5)

    def test_actual_planner_respects_host_zero_unknown_and_immutable_active_width(self):
        from _generation_concurrency import plan_dispatch
        for capacity, effective in ((3, 3), (0, 0), (None, 1)):
            result = plan_dispatch(observation(15, capacity))
            self.assertEqual(result['target_concurrency'], 10)
            self.assertEqual(result['effective_concurrency'], effective)
            self.assertEqual(len(result['dispatch_slide_ids']), effective)
        value = observation(15)
        value['batch_width'] = 4
        self.assertEqual(plan_dispatch(value)['effective_concurrency'], 4)

    def test_negotiation_uses_automatic_planner_without_treating_zero_capacity_as_unavailable(self):
        case = json.loads((FIXTURES / 'visual-generation-host-capability-cases.json').read_text('utf-8'))['cases'][0]
        case.pop('configured_width', None)
        case['capability']['worker_capacity'] = 10
        self.assertEqual(negotiate_host_capability(case)['selected_width'], 5)
        case['history'] = observation(15)['history']
        self.assertEqual(negotiate_host_capability(case)['selected_width'], 10)
        case['capability']['worker_capacity'] = 3
        self.assertEqual(negotiate_host_capability(case)['selected_width'], 3)
        case['capability']['worker_capacity'] = 0
        result = negotiate_host_capability(case)
        self.assertEqual(result['selected_width'], 0)
        self.assertIsNone(result['error'])

    def test_repeated_schedule_reserves_existing_tasks_and_refills_only_freed_slots(self):
        manifest, transactions, prompts = batch(10)
        capability = {'selected_width': 3, 'error': None, 'prompt_bytes_by_slide': prompts}
        first = schedule_epoch(manifest, transactions, capability)
        self.assertEqual([task['slide_id'] for task in first], ['S01', 'S02', 'S03'])
        for index, task in enumerate(first):
            tx = transactions[manifest['transaction_refs'][index]]
            tx.update(host_task_id='task-' + task['slide_id'], host_attribution_id='attr-' + task['slide_id'],
                      state='generating' if index == 0 else 'compiled')
        self.assertEqual(schedule_epoch(manifest, transactions, capability), [])
        manifest['dispatch_epoch'] += 1
        self.assertEqual(schedule_epoch(manifest, transactions, capability), [])
        finished = transactions[manifest['transaction_refs'][0]]
        finished.update(state='candidate_written', candidate_sha256='sha256:' + 'a' * 64)
        refill = schedule_epoch(manifest, transactions, capability)
        self.assertEqual([task['slide_id'] for task in refill], ['S04'])
        fresh, fresh_txs, fresh_prompts = batch(10)
        self.assertEqual(schedule_epoch(fresh, fresh_txs, dict(capability, selected_width=0,
                                                            prompt_bytes_by_slide=fresh_prompts)), [])

    def test_partial_reservation_identity_fails_closed_before_dispatch(self):
        for field in ('host_attribution_id', 'host_task_id'):
            manifest, transactions, prompts = batch(10)
            transactions[manifest['transaction_refs'][0]][field] = 'unresolved-reservation'
            capability = {'selected_width': 3, 'error': None, 'prompt_bytes_by_slide': prompts}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'host task identity'):
                schedule_epoch(manifest, transactions, capability)


if __name__ == '__main__':
    unittest.main()
