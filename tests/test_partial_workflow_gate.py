"""Partial delivery changes coverage, never source or per-delivered-page gates."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_source_workflow_gate import Fixture
from _workflow_gate import Gate, audit_run, check_run


class PartialWorkflowGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = Fixture(self.root)

    def prepare_partial(self, status='partial'):
        fx = self.fixture
        (self.root / 'slides/S02.svg').unlink()
        fx.evidence['qa']['slides'] = fx.evidence['qa']['slides'][:1]
        fx.write('.ppt-pilot/质量检查报告.md', 'S01 reviewed PASS; S02 omitted after failed attempts.')
        fx.evidence['qa']['report'] = fx.record('.ppt-pilot/质量检查报告.md')
        tid = 'sha256:' + 'b' * 64
        ref = '.ppt-pilot/visual-generation-transactions/S02-' + 'b' * 64 + '.json'
        fx.write_json(ref, {'schema_version': 2, 'kind': 'visual_generation_transaction',
            'batch_id': 'batch-partial', 'slide_id': 'S02', 'transaction_id': tid,
            'state': 'failed', 'failure_reason': 'svg_contract_failed', 'generation_attempt': 3})
        fx.write_json('.ppt-pilot/visual-generation-batches/batch-partial.json', {
            'batch_id': 'batch-partial', 'state': 'partial', 'ordered_slide_ids': ['S01', 'S02'],
            'transaction_refs': ['unused', ref], 'omitted_transaction_refs': [ref],
            'omitted_transaction_sha256': {ref: 'sha256:' + fx.sha(ref)}})
        fx.run.update(stage='qa' if status == 'prepared' else status,
                      production_policy='best_effort', dirty_slides=['S02'])
        fx.run['delivery'] = {'schema_version': 1, 'status': status, 'policy': 'best_effort',
            'target_slide_ids': ['S01', 'S02'], 'delivered_slide_ids': ['S01'],
            'missing_slides': [{'slide_id': 'S02', 'reason': 'attempts_exhausted',
                'failure_reason': 'svg_contract_failed', 'generation_attempt': 3,
                'transaction_id': tid, 'transaction_ref': ref, 'transaction_sha256': 'sha256:' + fx.sha(ref)}],
            'storyboard_sha256': 'sha256:' + fx.sha('.ppt-pilot/故事板.md'),
            'theme_sha256': 'sha256:' + fx.sha('.ppt-pilot/theme.json'),
            'quality_report_sha256': None if status == 'prepared' else 'sha256:' + fx.sha('.ppt-pilot/质量检查报告.md'),
            'slide_sha256': {'S01': 'sha256:' + fx.sha('slides/S01.svg')}}
        fx.save()

    def assert_blocked(self, code=None, before='partial'):
        self.fixture.save()
        result = check_run(self.root, before)
        self.assertEqual(result['status'], 'BLOCKED', result)
        if code:
            self.assertEqual(result['errors'][0]['code'], code, result)

    def test_manuscript_gate_preserves_legacy_english_owners(self):
        from _review_snapshot import CHINESE_MANUSCRIPT_FILES, ENGLISH_MANUSCRIPT_FILES
        from _workflow_evidence import manuscript
        names = dict(zip(CHINESE_MANUSCRIPT_FILES, ENGLISH_MANUSCRIPT_FILES))
        for old, new in names.items():
            (self.root / old).rename(self.root / new)
        frozen = self.fixture.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot']
        frozen['files'] = list(ENGLISH_MANUSCRIPT_FILES)
        frozen['file_hashes'] = {names[name]: value for name, value in frozen['file_hashes'].items()}
        self.fixture.evidence['manuscript']['files'] = dict(frozen['file_hashes'])
        gate = Gate(self.root)
        gate.run = self.fixture.run
        gate.evidence = self.fixture.evidence
        try:
            manuscript(gate)
        except ValueError as exc:
            self.fail('Approved English owners were rejected: ' + str(exc))
        self.assertEqual(gate.review_snapshot_id, frozen['snapshot_id'])

    def test_partial_gates_check_delivered_subset_and_preserve_original_intent(self):
        self.prepare_partial()
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(audit_run(self.root)['status'], 'PASS')
        self.assertEqual(check_run(self.root, 'partial')['status'], 'PASS')
        self.assertEqual(self.fixture.evidence['target_slide_ids'], ['S01', 'S02'])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_prepared_partition_allows_qa_but_never_full_completion(self):
        self.prepare_partial('prepared')
        self.assertEqual(check_run(self.root, 'qa')['status'], 'PASS')
        self.assertEqual(check_run(self.root, 'partial')['status'], 'PASS')
        self.assert_blocked(before='complete')

    def test_partial_label_without_bound_delivery_is_invalid(self):
        self.fixture.run['stage'] = 'partial'
        self.assert_blocked('delivery_missing')

    def test_unknown_production_policy_cannot_authorize_progress(self):
        for policy in (True, [], 'ignore_errors'):
            with self.subTest(policy=policy):
                self.fixture.run['production_policy'] = policy
                self.fixture.save()
                result = audit_run(self.root)
                self.assertEqual(result['status'], 'BLOCKED', result)
                self.assertEqual(result['errors'][0]['code'], 'invalid_production_policy')

    def test_delivery_does_not_treat_empty_active_controls_as_absent(self):
        self.prepare_partial()
        for field in ('active_visual_generation_batch', 'visual_generation_transaction'):
            with self.subTest(field=field):
                self.fixture.run[field] = {}
                self.fixture.save()
                result = audit_run(self.root)
                self.assertEqual(result['status'], 'BLOCKED', result)
                self.assertEqual(result['errors'][0]['code'], field)
                self.fixture.run.pop(field)

    def test_partial_requires_persisted_best_effort_authorization(self):
        self.prepare_partial()
        self.fixture.run.pop('production_policy')
        self.assert_blocked('delivery_policy_mismatch')

    def test_delivered_page_cannot_be_dirty_or_unreviewed(self):
        self.prepare_partial()
        self.fixture.run['dirty_slides'].append('S01')
        self.assert_blocked('dirty_slides')
        self.fixture.run['dirty_slides'] = ['S02']
        self.fixture.evidence['qa']['slides'][0]['visual_review'] = 'FAIL'
        self.assert_blocked('qa_visual_review_missing')

    def test_partial_does_not_hide_invalid_or_unknown_dirty_pages(self):
        self.prepare_partial()
        for dirty in (['S99'], ['S02', 'S02'], [{}], None):
            with self.subTest(dirty=dirty):
                self.fixture.run['dirty_slides'] = dirty
                self.assert_blocked('dirty_slides')

    def test_partial_cannot_hide_source_drift_or_expand_qa_to_unreviewed_pages(self):
        self.prepare_partial()
        self.fixture.source.write_bytes(b'changed original')
        self.assert_blocked('source_changed')

    def test_partial_cannot_shrink_original_target_inventory(self):
        self.prepare_partial()
        record = self.fixture.run['delivery']
        record.update(status='complete', target_slide_ids=['S01'], missing_slides=[])
        self.fixture.run['stage'] = 'complete'
        self.assert_blocked('delivery_targets_changed', before='complete')

    def test_tampered_omission_record_is_not_an_escape_hatch(self):
        self.prepare_partial()
        ref = self.fixture.run['delivery']['missing_slides'][0]['transaction_ref']
        tx = json.loads((self.root / ref).read_text())
        tx['generation_attempt'] = 0
        self.fixture.write_json(ref, tx)
        self.assert_blocked('delivery_evidence_stale')

    def test_partial_delivery_files_have_the_same_firewall_as_complete(self):
        self.prepare_partial()
        self.fixture.write('delivery/editable/deck-partial-editable.pptx', 'synthetic delivery')
        self.fixture.write('delivery/editable/editable-result-partial.json', '{}')
        self.fixture.write('delivery/editable/.editable-partial.lock', '')
        self.fixture.write('delivery/editable/.tmp/test/input.json', '{}')
        self.assertEqual(audit_run(self.root)['status'], 'PASS')
        self.fixture.write('deck.pptx', 'outside delivery')
        result = audit_run(self.root)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['errors'][0]['code'], 'pptx_outside_delivery')

    def test_failed_terminal_has_no_pptx_delivery_permission(self):
        self.prepare_partial()
        record = self.fixture.run['delivery']
        missing = copy.deepcopy(record['missing_slides'][0])
        missing['slide_id'] = 'S01'
        missing['transaction_ref'] = missing['transaction_ref'].replace('S02-', 'S01-')
        tx = json.loads((self.root / record['missing_slides'][0]['transaction_ref']).read_text())
        tx['slide_id'] = 'S01'
        self.fixture.write_json(missing['transaction_ref'], tx)
        missing['transaction_sha256'] = 'sha256:' + self.fixture.sha(missing['transaction_ref'])
        refs = [missing['transaction_ref'], record['missing_slides'][0]['transaction_ref']]
        self.fixture.write_json('.ppt-pilot/visual-generation-batches/batch-partial.json', {
            'batch_id': 'batch-partial', 'state': 'failed', 'ordered_slide_ids': ['S01', 'S02'],
            'transaction_refs': refs, 'omitted_transaction_refs': refs,
            'omitted_transaction_sha256': {ref: 'sha256:' + self.fixture.sha(ref) for ref in refs}})
        record.update(status='failed', delivered_slide_ids=[], slide_sha256={}, quality_report_sha256=None)
        record['missing_slides'].insert(0, missing)
        self.fixture.run.update(stage='failed', dirty_slides=['S01', 'S02'])
        self.fixture.save()
        self.assertEqual(audit_run(self.root)['status'], 'PASS')
        self.fixture.write('delivery/editable/empty.pptx', 'not a delivery')
        self.assertEqual(audit_run(self.root)['errors'][0]['code'], 'precomplete_pptx')


if __name__ == '__main__':
    unittest.main()
