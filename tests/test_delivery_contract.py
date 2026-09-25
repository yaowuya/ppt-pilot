"""Delivery completeness is independent from validation of delivered pages."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from types import MappingProxyType


MODULE = Path(__file__).resolve().parents[1] / 'skills/ppt-editable/scripts/_ppt_editable/delivery_contract.py'


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


class DeliveryContractTests(unittest.TestCase):
    def module(self):
        self.assertTrue(MODULE.is_file(), 'Shared delivery contract is not implemented')
        spec = importlib.util.spec_from_file_location('delivery_contract_under_test', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self):
        identity = 'sha256:' + 'a' * 64
        ref = '.ppt-pilot/visual-generation-transactions/S02-' + 'a' * 64 + '.json'
        transaction = {'schema_version': 2, 'kind': 'visual_generation_transaction',
                       'batch_id': 'batch-test', 'slide_id': 'S02', 'transaction_id': identity,
                       'state': 'failed', 'failure_reason': 'svg_contract_failed', 'generation_attempt': 3}
        transaction_bytes = json.dumps(transaction).encode()
        files = {'.ppt-pilot/故事板.md': b'storyboard', '.ppt-pilot/theme.json': b'theme',
                 '.ppt-pilot/质量检查报告.md': b'qa', 'slides/S01.svg': b'<svg/>',
                 ref: transaction_bytes,
                 '.ppt-pilot/visual-generation-batches/batch-test.json': json.dumps({
                     'batch_id': 'batch-test', 'state': 'partial', 'ordered_slide_ids': ['S01', 'S02'],
                     'transaction_refs': ['unused', ref], 'omitted_transaction_refs': [ref],
                     'omitted_transaction_sha256': {ref: digest(transaction_bytes)},
                 }).encode()}
        value = {'schema_version': 1, 'status': 'partial', 'policy': 'best_effort',
                 'target_slide_ids': ['S01', 'S02'], 'delivered_slide_ids': ['S01'],
                 'missing_slides': [{'slide_id': 'S02', 'reason': 'attempts_exhausted',
                     'failure_reason': 'svg_contract_failed', 'generation_attempt': 3,
                     'transaction_id': identity, 'transaction_ref': ref,
                     'transaction_sha256': digest(files[ref])}],
                 'storyboard_sha256': digest(files['.ppt-pilot/故事板.md']),
                 'theme_sha256': digest(files['.ppt-pilot/theme.json']),
                 'quality_report_sha256': digest(files['.ppt-pilot/质量检查报告.md']),
                 'slide_sha256': {'S01': digest(files['slides/S01.svg'])}}
        return value, files

    def verify(self, value, files):
        self.module().verify_delivery_evidence(value, files.__getitem__,
            storyboard_path='.ppt-pilot/故事板.md', theme_path='.ppt-pilot/theme.json',
            quality_report_path='.ppt-pilot/质量检查报告.md', target_slide_ids=['S01', 'S02'])

    def test_valid_partial_delivery_preserves_input_and_failed_evidence(self):
        value, files = self.fixture()
        before = copy.deepcopy((value, files))
        self.verify(value, files)
        self.assertEqual((value, files), before)

    def test_complete_cannot_hide_missing_pages(self):
        value, _ = self.fixture()
        value['status'] = 'complete'
        with self.assertRaisesRegex(ValueError, 'delivery_'):
            self.module().validate_delivery(value)
        value['delivered_slide_ids'] = ['S01', 'S02']
        value['missing_slides'] = []
        value['slide_sha256']['S02'] = 'sha256:' + 'b' * 64
        self.module().validate_delivery(value, ['S01', 'S02'], final=True)

    def test_invalid_partition_policy_and_fields_fail_closed(self):
        changes = [
            {'delivered_slide_ids': []}, {'delivered_slide_ids': ['S02', 'S01']},
            {'delivered_slide_ids': ['S01', 'S01']}, {'target_slide_ids': ['S01', 'S01']},
            {'target_slide_ids': ['S01', 'S02', 'S03']}, {'missing_slides': []},
            {'policy': 'strict'}, {'schema_version': True}, {'status': 'PASS'},
            {'status': []}, {'slide_sha256': {}}, {'quality_report_sha256': None},
            {'theme_sha256': 'unbound'}, {'extra': 'not allowed'},
        ]
        module = self.module()
        for change in changes:
            with self.subTest(change=change):
                value, _ = self.fixture()
                value.update(change)
                with self.assertRaisesRegex(ValueError, 'delivery_'):
                    module.validate_delivery(value, ['S01', 'S02'], final=True)

    def test_prepared_is_not_exportable_and_empty_delivery_is_failed(self):
        module = self.module()
        value, _ = self.fixture()
        value.update(status='prepared', quality_report_sha256=None)
        module.validate_delivery(value)
        with self.assertRaisesRegex(ValueError, 'delivery_'):
            module.validate_delivery(value, final=True)
        value.update(status='failed', target_slide_ids=['S02'], delivered_slide_ids=[], slide_sha256={})
        module.validate_delivery(value, ['S02'])
        with self.assertRaisesRegex(ValueError, 'delivery_'):
            module.validate_delivery(value, final=True)

    def test_missing_page_cannot_relabel_global_corruption_or_unsafe_ref(self):
        changes = [
            {'failure_reason': 'candidate_hash_mismatch'}, {'failure_reason': 'generator_unavailable'},
            {'transaction_ref': '../private.json'}, {'transaction_id': 'sha256:' + 'b' * 64},
            {'generation_attempt': True}, {'generation_attempt': 2}, {'generation_attempt': -1},
            {'reason': 'approved'}, {'slide_id': 'S01'}, {'transaction_sha256': 'unbound'},
        ]
        module = self.module()
        for change in changes:
            with self.subTest(change=change):
                value, _ = self.fixture()
                value['missing_slides'][0].update(change)
                with self.assertRaisesRegex(ValueError, 'delivery_'):
                    module.validate_delivery(value)

    def test_tampered_bound_files_or_failed_transaction_are_rejected(self):
        value, files = self.fixture()
        for path in ('.ppt-pilot/故事板.md', '.ppt-pilot/theme.json', '.ppt-pilot/质量检查报告.md',
                     'slides/S01.svg', value['missing_slides'][0]['transaction_ref']):
            with self.subTest(path=path):
                damaged = dict(files)
                damaged[path] += b' changed'
                with self.assertRaisesRegex(ValueError, 'delivery_'):
                    self.verify(value, damaged)
        ref = value['missing_slides'][0]['transaction_ref']
        for change in ({'state': 'validated'}, {'generation_attempt': 2}, {'slide_id': 'S01'},
                       {'failure_reason': 'candidate_hash_mismatch'}, {'batch_id': '../private'}):
            with self.subTest(change=change):
                damaged = dict(files)
                transaction = json.loads(damaged[ref])
                transaction.update(change)
                damaged[ref] = json.dumps(transaction).encode()
                rebound = copy.deepcopy(value)
                rebound['missing_slides'][0]['transaction_sha256'] = digest(damaged[ref])
                with self.assertRaisesRegex(ValueError, 'delivery_'):
                    self.verify(rebound, damaged)

    def test_omission_must_belong_to_current_manifest_slot(self):
        value, files = self.fixture()
        path = '.ppt-pilot/visual-generation-batches/batch-test.json'
        for change in ({'omitted_transaction_refs': []}, {'transaction_refs': ['unused', 'replaced']},
                       {'ordered_slide_ids': ['S02', 'S01']}, {'state': 'active'},
                       {'omitted_transaction_sha256': {}}):
            with self.subTest(change=change):
                damaged = dict(files)
                manifest = json.loads(files[path])
                manifest.update(change)
                damaged[path] = json.dumps(manifest).encode()
                with self.assertRaisesRegex(ValueError, 'delivery_'):
                    self.verify(value, damaged)

    def test_delivery_cannot_contradict_content_gate_state(self):
        module = self.module()
        review = {'required': True, 'state': 'manuscript_approved', 'status': 'PASSED',
                  'open_blocking_findings': []}
        module.validate_delivery_review_state({'manuscript_review': review})
        for change in ({'required': False}, {'state': 'pending'}, {'status': 'FAILED'},
                       {'open_blocking_findings': ['H1']}, {'pending_round': {}},
                       {'open_blocking_findings': {}}):
            with self.subTest(change=change):
                value = dict(review)
                value.update(change)
                with self.assertRaisesRegex(ValueError, 'delivery_manuscript_not_approved'):
                    module.validate_delivery_review_state({'manuscript_review': value})

    def test_immutable_run_context_sequences_are_supported(self):
        def freeze(value):
            if isinstance(value, dict):
                return MappingProxyType({k: freeze(v) for k, v in value.items()})
            if isinstance(value, list):
                return tuple(freeze(v) for v in value)
            return value
        value, files = self.fixture()
        self.verify(freeze(value), files)


if __name__ == '__main__':
    unittest.main()
