"""Behavioral checks for the read-only automatic SVG dispatch planner."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(SCRIPTS))
from _generation_concurrency import plan_dispatch


def observation(capacity=10, ready=12):
    return {'schema_version': 1,
            'capabilities': {'fresh_isolation': True, 'concurrent_tasks': True,
                             'durable_lookup': True, 'worker_capacity': capacity},
            'ready_slide_ids': ['S%02d' % number for number in range(1, ready + 1)],
            'in_flight_slide_ids': [], 'history': []}


class ConcurrencyTests(unittest.TestCase):
    def test_initial_target_five(self):
        value = observation()
        result = plan_dispatch(value)
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(result['target_concurrency'], 5)
        self.assertEqual(result['dispatch_slide_ids'], value['ready_slide_ids'][:5])

    def test_growth_seven_nine_ten_and_replay(self):
        for completed, expected in ((4, 5), (5, 7), (10, 9), (15, 10), (30, 10)):
            with self.subTest(completed=completed):
                value = observation()
                value['history'] = [{'event_id': 'event-%d' % index, 'outcome': 'validated'} for index in range(completed)]
                result = plan_dispatch(value)
                self.assertEqual(result['target_concurrency'], expected)
                self.assertEqual(result, plan_dispatch(value))
                value['history'] += copy.deepcopy(value['history'])
                self.assertEqual(result, plan_dispatch(value))

    def test_known_capacity_and_remaining_work(self):
        for capacity, expected in ((3, 3), (5, 5), (10, 5)):
            result = plan_dispatch(observation(capacity))
            self.assertEqual(result['effective_concurrency'], expected)
        result = plan_dispatch(observation(10, ready=2))
        self.assertEqual(result['effective_concurrency'], 2)
        self.assertIn('remaining_work_limited', result['limitations'])

    def test_unknown_capacity_and_safety_capabilities(self):
        result = plan_dispatch(observation(None))
        self.assertEqual(result['effective_concurrency'], 1)
        self.assertIn('worker_capacity_unknown', result['limitations'])
        for field in ('concurrent_tasks', 'durable_lookup'):
            value = observation()
            value['capabilities'][field] = False
            result = plan_dispatch(value)
            self.assertEqual(result['effective_concurrency'], 1)
            self.assertIn('capability_limited', result['limitations'])

    def test_zero_capacity_wait_and_fresh_isolation_unavailable_block(self):
        result = plan_dispatch(observation(0))
        self.assertEqual(result['status'], 'WAIT')
        self.assertEqual(result['dispatch_slide_ids'], [])
        value = observation()
        value['capabilities']['fresh_isolation'] = False
        result = plan_dispatch(value)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['effective_concurrency'], 0)

    def test_existing_workers_subtracted_repeated_poll_and_late_completion(self):
        value = observation()
        value['in_flight_slide_ids'] = value['ready_slide_ids'][:3]
        value['ready_slide_ids'] = value['ready_slide_ids'][3:]
        result = plan_dispatch(value)
        self.assertEqual(result['available_slots'], 2)
        self.assertEqual(result['dispatch_slide_ids'], ['S04', 'S05'])
        value['in_flight_slide_ids'] += result['dispatch_slide_ids']
        value['ready_slide_ids'] = value['ready_slide_ids'][2:]
        self.assertEqual(plan_dispatch(value)['status'], 'WAIT')
        value['in_flight_slide_ids'].remove('S01')
        value['history'].append({'event_id': 'S01-validated', 'outcome': 'validated'})
        self.assertEqual(plan_dispatch(value)['dispatch_slide_ids'], ['S06'])

    def test_reduced_capacity_does_not_cancel_in_flight(self):
        value = observation(2)
        value['in_flight_slide_ids'] = value['ready_slide_ids'][:5]
        value['ready_slide_ids'] = value['ready_slide_ids'][5:]
        original = copy.deepcopy(value)
        result = plan_dispatch(value)
        self.assertEqual(result['status'], 'WAIT')
        self.assertEqual(result['available_slots'], 0)
        self.assertIn('in_flight_exceeds_limit', result['limitations'])
        self.assertEqual(value, original)

    def test_legacy_batch_inventory_caps(self):
        for width in (3, 4):
            value = observation()
            value['batch_width'] = width
            result = plan_dispatch(value)
            self.assertEqual(result['effective_concurrency'], width)
            self.assertEqual(result['target_concurrency'], 5)
            self.assertIn('legacy_batch_cap', result['limitations'])

    def test_pressure_and_failure_reset_growth(self):
        for outcome in ('rate_limited', 'timeout', 'capacity_limited', 'failed'):
            value = observation()
            value['history'] = [{'event_id': str(index), 'outcome': 'validated'} for index in range(10)]
            value['history'].append({'event_id': 'pressure', 'outcome': outcome})
            result = plan_dispatch(value)
            self.assertEqual(result['target_concurrency'], 5)

    def test_upstream_blocked_and_no_remaining_slides(self):
        value = observation()
        value['blocked'] = True
        self.assertEqual(plan_dispatch(value)['status'], 'BLOCKED')
        self.assertEqual(plan_dispatch(value)['dispatch_slide_ids'], [])
        self.assertEqual(plan_dispatch(observation(10, 0))['status'], 'WAIT')

    def test_invalid_types_and_ids_fail_closed(self):
        cases = []
        for field, malformed in (('schema_version', True), ('schema_version', 2), ('blocked', 1),
                                  ('batch_width', False), ('batch_width', 0), ('batch_width', 11),
                                  ('batch_width', 5.0), ('history', {}), ('ready_slide_ids', 'S01'),
                                  ('ready_slide_ids', ['S1']), ('ready_slide_ids', ['S01', 'S01']),
                                  ('ready_slide_ids', [1]), ('in_flight_slide_ids', ['S01'])):
            value = observation()
            value[field] = malformed
            cases.append(value)
        for field, malformed in (('worker_capacity', True), ('worker_capacity', -1), ('worker_capacity', 2.5),
                                 ('fresh_isolation', 1), ('concurrent_tasks', None), ('durable_lookup', 'yes')):
            value = observation()
            value['capabilities'][field] = malformed
            cases.append(value)
        for value in cases + [None, [], 'text']:
            with self.subTest(value=value):
                result = plan_dispatch(value)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertEqual(result['dispatch_slide_ids'], [])
                self.assertEqual(result['effective_concurrency'], 0)

    def test_conflicting_history_duplicate_invalid(self):
        value = observation()
        value['history'] = [{'event_id': 'event', 'outcome': 'validated'}, {'event_id': 'event', 'outcome': 'failed'}]
        self.assertEqual(plan_dispatch(value)['status'], 'BLOCKED')

    def test_optional_defaults_and_growth_after_pressure(self):
        value = observation()
        del value['history']
        self.assertEqual(plan_dispatch(value)['target_concurrency'], 5)
        value['history'] = [{'event_id': 'pressure', 'outcome': 'rate_limited'}] + [
            {'event_id': 'validated-%d' % index, 'outcome': 'validated'} for index in range(5)]
        self.assertEqual(plan_dispatch(value)['target_concurrency'], 7)
        value['capabilities']['worker_capacity'] = 5
        self.assertEqual(plan_dispatch(value)['effective_concurrency'], 5)
        value['capabilities']['worker_capacity'] = 10
        self.assertEqual(plan_dispatch(value)['effective_concurrency'], 7)

    def test_malformed_event_records_and_missing_capabilities(self):
        for event in (None, [], {}, {'event_id': '', 'outcome': 'validated'},
                      {'event_id': 1, 'outcome': 'validated'}, {'event_id': 'x', 'outcome': 'unknown'},
                      {'event_id': 'x', 'outcome': ['validated']}):
            value = observation()
            value['history'] = [event]
            self.assertEqual(plan_dispatch(value)['status'], 'BLOCKED')
        value = observation()
        del value['capabilities']['worker_capacity']
        self.assertEqual(plan_dispatch(value)['status'], 'BLOCKED')

    def test_cli_real_json_no_writes_and_optimized_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text(json.dumps(observation()), encoding='utf-8')
            original = path.read_bytes()
            command = [sys.executable, '-O', str(SCRIPTS / 'ppt_concurrency.py'), '--input', str(path)]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)['dispatch_slide_ids'], ['S01', 'S02', 'S03', 'S04', 'S05'])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            path.write_text(json.dumps(observation(0)), encoding='utf-8')
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(json.loads(process.stdout)['status'], 'WAIT')
            for malformed in ('{', '{"schema_version":1,"schema_version":1}', '[]'):
                path.write_text(malformed, encoding='utf-8')
                process = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(process.returncode, 2)
                self.assertEqual(json.loads(process.stdout)['status'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
