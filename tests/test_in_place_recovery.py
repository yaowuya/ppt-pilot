"""Real CLI regressions: a failed page never requires another run directory."""
import json
import os
from pathlib import Path
import unittest
from unittest import mock

from tests import test_ppt_runtime as runtime_tests


class InPlaceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.case = runtime_tests.RuntimeTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.prepared_fixture('deepseek-harness', slide_count=2)
        self.root = self.case.root

    def fail_svg(self):
        self.case.reserve()
        self.case.bind()
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
                    '<title>Test</title><desc>Unsafe geometry</desc><g data-block-id="S01-B1">'
                    '<rect x="10" y="10" width="10" height="10"/></g></svg>\n```\n')
        (self.root / '.ppt-pilot/runtime-inputs/bad.txt').write_text(response, encoding='utf-8')
        result, body = self.case.invoke('ingest-result', '--dispatch-id', self.case.dispatch,
                                       '--response', '.ppt-pilot/runtime-inputs/bad.txt')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['errors'][0]['code'], 'svg_contract_failed')
        self.assertEqual(self.case.tx()['state'], 'failed')
        self.assertIsNone(self.case.tx()['candidate_sha256'])
        return body

    def test_rejected_svg_recovers_in_same_run_with_exact_prompt_and_sibling(self):
        review = (self.root / '.ppt-pilot/文稿审查.md').read_bytes()
        board = (self.root / '.ppt-pilot/故事板.md').read_bytes()
        prompt = (self.root / '.ppt-pilot/generation-prompts/S01.md').read_bytes()
        manifest = json.loads((self.root / self.case.manifest_name).read_bytes())
        sibling = self.root / manifest['transaction_refs'][1]
        prior_sibling = sibling.read_bytes()
        roots = set(self.root.parent.iterdir())
        self.fail_svg()
        result, resumed = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, resumed)
        plan = resumed['result'].get('recoveries', [])
        self.assertTrue(plan, 'Resume must supply actionable recovery arguments')
        self.assertEqual(plan[0]['slide_id'], 'S01')
        self.assertEqual(plan[0]['transaction_id'], self.case.txid)
        self.assertEqual(plan[0]['mode'], 'retry')
        self.assertEqual(plan[0]['failure_reason'], 'svg_contract_failed')
        self.assertEqual(plan[0]['remaining_attempts'], 2)
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01',
                                       '--transaction-id', self.case.txid, '--mode', 'retry')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(self.case.tx()['generation_attempt'], 1)
        self.case.reserve(); self.case.bind(); self.case.candidate(); self.case.validate()
        self.assertEqual(self.case.tx()['generation_attempt'], 2)
        self.assertEqual(self.case.tx()['state'], 'validated')
        self.assertEqual((self.root / '.ppt-pilot/文稿审查.md').read_bytes(), review)
        self.assertEqual((self.root / '.ppt-pilot/故事板.md').read_bytes(), board)
        self.assertEqual((self.root / '.ppt-pilot/generation-prompts/S01.md').read_bytes(), prompt)
        self.assertEqual(sibling.read_bytes(), prior_sibling)
        self.assertEqual(set(self.root.parent.iterdir()), roots)

    def test_output_retry_budget_cannot_reset_after_repeated_svg_failures(self):
        for attempt in (1, 2, 3):
            self.fail_svg()
            self.assertEqual(self.case.tx()['generation_attempt'], attempt)
            result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01',
                                           '--transaction-id', self.case.txid, '--mode', 'retry')
            if attempt < 3:
                self.assertEqual(result.returncode, 0, body)
            else:
                self.assertEqual(result.returncode, 2)
                self.assertEqual(body['errors'][0]['code'], 'generation_attempts_exhausted')
                run = json.loads((self.root / '.ppt-pilot/run.json').read_bytes())
                self.assertEqual(run['pending_interaction']['kind'], 'blocker')
                self.assertEqual(run['manuscript_review']['cycle'], 1)

    def test_interrupted_visual_decision_resumes_recompose_instead_of_output_retry(self):
        self.fail_svg()
        from _runtime_commands import Runtime
        from _run_store import sha
        from ppt_runtime import parser
        request = {'schema_version': 1, 'kind': 'visual_revision', 'request_id': 'layout-1',
                   'expected_run_sha256': sha((self.root / '.ppt-pilot/run.json').read_bytes()),
                   'changes': {'layout_family': 'single-column'}, 'answer': 'Use a single column.'}
        self.case.put('.ppt-pilot/runtime-inputs/revision.json', request)
        runtime = Runtime(self.root)
        args = parser().parse_args(['revise-visual', '--run-dir', str(self.root), '--slide-id', 'S01',
                                   '--transaction-id', self.case.txid, '--input', '.ppt-pilot/runtime-inputs/revision.json'])
        # Crash after the real revision decision commit, before journal preparation.
        with mock.patch.object(runtime, 'prepare_recovery', side_effect=OSError('simulated interruption')):
            with self.assertRaises(OSError):
                runtime.execute(args)
        result, body = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['recoveries'][0]['mode'], 'recompose')
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.case.txid, '--mode', 'retry')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'visual_revision_pending')
        self.assertEqual(body['writes'], [])
        result, body = self.case.invoke('revise-visual', '--slide-id', 'S01', '--transaction-id', self.case.txid,
                                       '--input', '.ppt-pilot/runtime-inputs/revision.json')
        self.assertEqual(result.returncode, 0, body)
        self.assertTrue(body['result']['replay'])

    def test_native_visual_correction_cannot_reset_the_generation_budget(self):
        from _run_store import sha
        for attempt in (1, 2, 3):
            self.fail_svg()
            self.assertEqual(self.case.tx()['generation_attempt'], attempt)
            request = {'schema_version': 1, 'kind': 'visual_revision', 'request_id': f'layout-{attempt}',
                       'expected_run_sha256': sha((self.root / '.ppt-pilot/run.json').read_bytes()),
                       'changes': {'visual_intent': f'Clear hierarchy variant {attempt}.'},
                       'answer': 'Correct the failed layout without changing content.'}
            self.case.put('.ppt-pilot/runtime-inputs/revision.json', request)
            result, body = self.case.invoke('revise-visual', '--slide-id', 'S01', '--transaction-id', self.case.txid,
                                           '--input', '.ppt-pilot/runtime-inputs/revision.json')
            if attempt == 3:
                self.assertEqual(result.returncode, 2)
                self.assertEqual(body['errors'][0]['code'], 'generation_attempts_exhausted')
                self.assertEqual(body['writes'], [])
                result, plan = self.case.invoke('resume')
                self.assertEqual(result.returncode, 0, plan)
                self.assertEqual(plan['result']['recoveries'][0]['blocked_reason'], 'generation_attempts_exhausted')
            else:
                self.assertEqual(result.returncode, 0, body)
                self.case.txid = body['result']['transaction_id']
                manifest = json.loads((self.root / self.case.manifest_name).read_bytes())
                self.case.txname = manifest['transaction_refs'][0]
                self.assertEqual(self.case.tx()['generation_attempt'], attempt, 'A visual repair reset the attempt budget')

    def test_retry_cannot_bypass_changed_reviewed_facts(self):
        self.fail_svg()
        brief = self.root / '.ppt-pilot/简报.md'
        brief.write_bytes(brief.read_bytes() + b'\nChanged fact\n')
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01',
                                       '--transaction-id', self.case.txid, '--mode', 'retry')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'manuscript_stale')
        self.assertEqual(body['writes'], [])
        self.assertEqual(self.case.tx()['generation_attempt'], 1)

    def test_failed_accepted_candidate_requires_visual_revision_not_output_retry(self):
        self.case.reserve(); self.case.bind(); self.case.candidate()
        from _generation_runtime import V2_VALIDATION_CHECKS
        tx = self.case.tx()
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01',
              'transaction_id': self.case.txid, 'candidate_sha256': tx['candidate_sha256'],
              'checks': {k: 'failed' if k == 'geometry_text' else 'passed' for k in V2_VALIDATION_CHECKS},
              'defect_id': 'layout-1', 'failure_reason': 'svg_contract_failed'}
        self.case.put('.ppt-pilot/runtime-inputs/qa.json', qa)
        result, body = self.case.invoke('record-validation', '--slide-id', 'S01', '--transaction-id', self.case.txid,
                                       '--input', '.ppt-pilot/runtime-inputs/qa.json')
        self.assertEqual(result.returncode, 0, body)
        candidate = self.root / tx['candidate_path']
        before = candidate.read_bytes()
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.case.txid, '--mode', 'retry')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'recovery_not_allowed')
        self.assertIn('same run', body['errors'][0]['next_action'])
        self.assertEqual(body['writes'], [])
        result, body = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'revise-visual')
        self.assertEqual(body['result']['recoveries'][0]['required_input'], 'visual_revision')
        self.assertIsNone(body['result']['recoveries'][0]['mode'])
        self.assertEqual(candidate.read_bytes(), before)
        exhausted = self.case.tx()
        exhausted['generation_attempt'] = 3
        self.case.put(self.case.txname, exhausted)
        result, plan = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, plan)
        self.assertEqual(plan['result']['recoveries'][0].get('blocked_reason'), 'generation_attempts_exhausted')
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.case.txid, '--mode', 'retry')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'generation_attempts_exhausted')
        self.assertEqual(candidate.read_bytes(), before)

    def test_qa_transaction_before_manifest_crash_can_recover_without_new_run(self):
        self.case.reserve(); self.case.bind(); self.case.candidate()
        from _generation_runtime import V2_VALIDATION_CHECKS
        from _runtime_commands import Runtime
        from _run_store import sha
        from ppt_runtime import parser
        tx = self.case.tx()
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01',
              'transaction_id': self.case.txid, 'candidate_sha256': tx['candidate_sha256'],
              'checks': {k: 'failed' if k == 'visual' else 'passed' for k in V2_VALIDATION_CHECKS},
              'defect_id': 'layout-1', 'failure_reason': 'visual_qa_failed'}
        self.case.put('.ppt-pilot/runtime-inputs/qa.json', qa)
        old_manifest = (self.root / self.case.manifest_name).read_bytes()
        original_replace = os.replace

        def crash_after_transaction(source, destination):
            original_replace(source, destination)
            if Path(destination) == self.root / self.case.txname:
                raise OSError('crash after failed transaction, before manifest')

        runtime = Runtime(self.root)
        args = parser().parse_args(['record-validation', '--run-dir', str(self.root), '--slide-id', 'S01',
                                   '--transaction-id', self.case.txid, '--input', '.ppt-pilot/runtime-inputs/qa.json'])
        with mock.patch.object(os, 'replace', side_effect=crash_after_transaction), self.assertRaises(OSError):
            runtime.execute(args)
        self.assertEqual(self.case.tx()['state'], 'failed')
        self.assertEqual((self.root / self.case.manifest_name).read_bytes(), old_manifest)
        request = {'schema_version': 1, 'kind': 'visual_revision', 'request_id': 'recover-after-qa',
                   'expected_run_sha256': sha((self.root / '.ppt-pilot/run.json').read_bytes()),
                   'changes': {'layout_family': 'single-column'}, 'answer': 'Fix the failed layout.'}
        self.case.put('.ppt-pilot/runtime-inputs/revision.json', request)
        result, body = self.case.invoke('revise-visual', '--slide-id', 'S01', '--transaction-id', self.case.txid,
                                       '--input', '.ppt-pilot/runtime-inputs/revision.json')
        self.assertEqual(result.returncode, 0, body)
        self.assertNotEqual(body['result']['transaction_id'], self.case.txid)
        manifest = json.loads((self.root / self.case.manifest_name).read_bytes())
        self.assertEqual(manifest['state'], 'active')
        self.assertEqual(len(manifest['transaction_refs']), 2)

    def test_pending_visual_decision_cannot_be_consumed_by_legacy_fallback(self):
        self.case.reserve(); self.case.bind(); self.case.candidate()
        from _generation_runtime import V2_VALIDATION_CHECKS
        from _runtime_commands import Runtime
        from _run_store import sha
        from ppt_runtime import parser
        tx = self.case.tx()
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01',
              'transaction_id': self.case.txid, 'candidate_sha256': tx['candidate_sha256'],
              'checks': {k: 'failed' if k == 'visual' else 'passed' for k in V2_VALIDATION_CHECKS},
              'defect_id': 'contrast-1', 'failure_reason': 'visual_qa_failed'}
        self.case.put('.ppt-pilot/runtime-inputs/qa.json', qa)
        result, body = self.case.invoke('record-validation', '--slide-id', 'S01', '--transaction-id', self.case.txid,
                                       '--input', '.ppt-pilot/runtime-inputs/qa.json')
        self.assertEqual(result.returncode, 0, body)
        # Existing legacy patch evidence is a supported fixture, not invented by the command.
        qa.update(fix_attempts_for_candidate=2, patch_defects=[{'defect_id': 'contrast-1', 'outcome': 'failed'},
                                                            {'defect_id': 'contrast-2', 'outcome': 'failed'}])
        self.case.document('.ppt-pilot/质量检查报告.md', {'schema_version': 1, 'kind': 'runtime_qa', 'records': [qa]})
        request = {'schema_version': 1, 'kind': 'visual_revision', 'request_id': 'visual-not-fallback',
                   'expected_run_sha256': sha((self.root / '.ppt-pilot/run.json').read_bytes()),
                   'changes': {'layout_family': 'two-column'}, 'answer': 'Use two columns.'}
        self.case.put('.ppt-pilot/runtime-inputs/revision.json', request)
        runtime = Runtime(self.root)
        args = parser().parse_args(['revise-visual', '--run-dir', str(self.root), '--slide-id', 'S01',
                                   '--transaction-id', self.case.txid, '--input', '.ppt-pilot/runtime-inputs/revision.json'])
        with mock.patch.object(runtime, 'prepare_recovery', side_effect=OSError('interrupted before journal')), self.assertRaises(OSError):
            runtime.execute(args)
        before = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.case.txid, '--mode', 'fallback')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'visual_revision_pending')
        self.assertEqual(body['writes'], [])
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before)

    def test_candidate_content_error_requests_classification_not_automatic_reapproval(self):
        self.case.reserve(); self.case.bind(); self.case.candidate()
        from _generation_runtime import V2_VALIDATION_CHECKS
        before = (self.root / '.ppt-pilot/run.json').read_bytes()
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01',
              'transaction_id': self.case.txid, 'candidate_sha256': self.case.tx()['candidate_sha256'],
              'checks': {k: 'failed' if k == 'fact_source' else 'passed' for k in V2_VALIDATION_CHECKS},
              'defect_id': 'missing-qualifier', 'failure_reason': 'fact_source_mismatch'}
        self.case.put('.ppt-pilot/runtime-inputs/qa.json', qa)
        result, body = self.case.invoke('record-validation', '--slide-id', 'S01', '--transaction-id', self.case.txid,
                                       '--input', '.ppt-pilot/runtime-inputs/qa.json')
        self.assertEqual(result.returncode, 0, body)
        result, body = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['recoveries'][0]['required_input'], 'classify_output_or_content_defect')
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before)

    def test_visible_source_leak_can_only_retry_same_approved_prompt(self):
        self.case.reserve(); self.case.bind()
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
                    '<title>Test</title><desc>source leak</desc><g data-block-id="S01-B1" data-source-id="SRC-1">'
                    '<rect x="100" y="100" width="10" height="10"/></g></svg>\n```\n')
        (self.root / '.ppt-pilot/runtime-inputs/leak.txt').write_text(response, encoding='utf-8')
        result, body = self.case.invoke('ingest-result', '--dispatch-id', self.case.dispatch,
                                       '--response', '.ppt-pilot/runtime-inputs/leak.txt')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'fact_source_mismatch')
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.case.txid, '--mode', 'retry')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(self.case.tx()['generation_attempt'], 1)
        self.assertEqual(self.case.tx()['state'], 'compiled')

    def test_svg_failure_reports_location_without_copying_svg_or_text_into_owner(self):
        body = self.fail_svg()
        details = body['errors'][0].get('details')
        self.assertIsNotNone(details, 'Geometry failure needs a locatable diagnostic')
        self.assertIn('bbox', details)
        self.assertEqual(details.get('element', {}).get('tag'), 'rect')
        self.assertIsInstance(details.get('element', {}).get('index'), int)
        self.assertNotIn('Unsafe geometry', json.dumps(details))
        self.assertNotIn('details', self.case.tx())
        self.assertEqual(self.case.tx()['failure_reason'], 'svg_contract_failed')

    def test_invalid_numeric_attribute_also_reports_safe_element_location(self):
        from _svg_runtime import validate_candidate
        from _svg_geometry import GeometryError
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
               '<title>Private title</title><desc>Private detail</desc><g data-block-id="S01-B1">'
               '<rect x="1e999" y="100" width="10" height="10"/></g></svg>')
        with self.assertRaises(GeometryError) as caught:
            validate_candidate(svg, ['S01-B1'], {'S01-B1': []})
        self.assertEqual(caught.exception.details.get('element'), {'tag': 'rect', 'index': 4})
        self.assertNotIn('Private', json.dumps(caught.exception.details))

    def test_resume_waits_for_bound_generator_when_no_other_work_is_ready(self):
        self.case.capability['observation']['worker_capacity'] = 1
        self.case.put('.ppt-pilot/runtime-inputs/cap.json', self.case.capability)
        self.case.reserve(); self.case.bind()
        result, body = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        # The response includes known in-flight work, not a fabricated failure/new-run suggestion.
        self.assertTrue(body['result'].get('in_flight'))
        self.assertEqual(body['result']['in_flight'][0]['slide_id'], 'S01')
        self.assertEqual(body['result']['in_flight'][0]['host_task_id'], 'fixture-task')
        self.assertEqual(body['writes'], [])

    def test_resume_rejects_malformed_pending_review_without_reading_batch(self):
        run = json.loads((self.root / '.ppt-pilot/run.json').read_bytes())
        run['manuscript_review']['pending_round'] = {}
        self.case.put('.ppt-pilot/run.json', run)
        result, body = self.case.invoke('resume')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'pending_review_round')
        self.assertEqual(body['writes'], [])

    def test_resume_routes_pending_manuscript_without_inspecting_old_batch(self):
        run = json.loads((self.root / '.ppt-pilot/run.json').read_bytes())
        run['stage'] = 'manuscript_review'
        run['manuscript_review'].update(state='pending', status='PENDING', round=0, cycle=2)
        self.case.put('.ppt-pilot/run.json', run)
        before = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, body = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'manuscript-review')
        self.assertEqual(body['writes'], [])
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
