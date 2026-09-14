"""Page-local visual failures preserve healthy work and explicit delivery evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import shutil
from unittest import mock

from tests import test_ppt_runtime as runtime_tests

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(SCRIPTS))

from _generation_runtime import (
    V2_VALIDATION_CHECKS,
    rebuild_batch_cursors,
    validate_v2_manifest,
)


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def transaction(slide_id, state='compiled', failure_reason=None):
    identity = digest(slide_id.encode('ascii'))
    candidate = digest((slide_id + '-candidate').encode('ascii')) if state in {'candidate_written', 'validated', 'promoted'} else None
    checks = {key: 'pending' for key in V2_VALIDATION_CHECKS}
    validation_state = 'pending'
    if state in {'validated', 'promoted'}:
        checks = {key: 'passed' for key in V2_VALIDATION_CHECKS}
        validation_state = 'passed'
    elif state == 'failed' and failure_reason in {'svg_contract_failed', 'fact_source_mismatch', 'visual_qa_failed'}:
        check = {'svg_contract_failed': 'xml', 'fact_source_mismatch': 'fact_source',
                 'visual_qa_failed': 'visual'}[failure_reason]
        checks[check] = 'failed'
        validation_state = 'failed'
    return {
        'schema_version': 2, 'kind': 'visual_generation_transaction', 'batch_id': 'batch-local',
        'transaction_id': identity, 'slide_id': slide_id, 'generation_intent': 'initial_generation',
        'generation_trigger_id': 'initial:' + slide_id, 'prompt_path': 'generation-prompts/' + slide_id + '.md',
        'prompt_snapshot_id': identity, 'compiled_prompt_sha256': digest((slide_id + '-prompt').encode('ascii')),
        'candidate_path': 'slides/.candidates/' + slide_id + '-' + identity[7:] + '.svg',
        'final_path': 'slides/' + slide_id + '.svg', 'prior_final_sha256': 'none', 'state': state,
        'generation_attempt': 3 if state == 'failed' else 0, 'candidate_sha256': candidate,
        'failure_reason': failure_reason, 'dispatch_epoch': 0, 'host_attribution_id': None,
        'host_task_id': None, 'validation': {'state': validation_state, 'checks': checks}, 'timing': [],
    }


def manifest(transactions, **changes):
    refs = ['.ppt-pilot/visual-generation-transactions/' + tx['slide_id'] + '-' + tx['transaction_id'][7:] + '.json'
            for tx in transactions]
    value = {
        'schema_version': 2, 'kind': 'visual_generation_batch', 'batch_id': 'batch-local',
        'batch_width': 5, 'ordered_slide_ids': [tx['slide_id'] for tx in transactions],
        'storyboard_snapshot_id': digest(b'storyboard'), 'theme_snapshot_id': digest(b'theme'),
        'source_audit_snapshot_id': digest(b'sources'),
        'generation_prompt_template_snapshot_id': digest(b'template'), 'transaction_refs': refs,
        'dispatch_epoch': 0, 'promotion_cursor': 0, 'blocker_cursor': len(refs),
        'active_blocker_ref': None, 'state': 'active', 'created_at': 'fixture', 'updated_at': 'fixture',
        'telemetry_summary': {},
    }
    value.update(changes)
    return value, dict(zip(refs, transactions))


class PageLocalManifestTests(unittest.TestCase):
    def test_page_failure_does_not_become_a_global_batch_blocker(self):
        value, txs = manifest([
            transaction('S01', 'failed', 'generator_timeout'),
            transaction('S02', 'compiled'),
        ])
        self.assertEqual(rebuild_batch_cursors(value, txs), (0, 2))
        validate_v2_manifest(value, txs)

    def test_integrity_failure_remains_a_global_batch_blocker(self):
        value, txs = manifest([
            transaction('S01', 'failed', 'candidate_hash_mismatch'),
            transaction('S02', 'compiled'),
        ])
        value.update(blocker_cursor=0, active_blocker_ref=value['transaction_refs'][0],
                     state='blocked')
        self.assertEqual(rebuild_batch_cursors(value, txs), (0, 0))
        validate_v2_manifest(value, txs)

    def test_omitted_failure_is_sealed_and_terminal_without_changing_transaction(self):
        failed = transaction('S01', 'failed', 'svg_contract_failed')
        healthy = transaction('S02', 'promoted')
        value, txs = manifest([failed, healthy])
        ref = value['transaction_refs'][0]
        failed_before = copy.deepcopy(failed)
        value.update(
            omitted_transaction_refs=[ref],
            omitted_transaction_sha256={ref: digest(json.dumps(failed, sort_keys=True).encode())},
            promotion_cursor=2,
            blocker_cursor=2,
            state='partial',
        )
        validate_v2_manifest(value, txs)
        self.assertEqual(failed, failed_before)


class EntryProductionPolicyTests(unittest.TestCase):
    def invoke(self, workspace, run_id, *extra):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'ppt_entry.py'),
            '--workspace', str(workspace), '--action', 'new', '--run-id', run_id, *extra],
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_new_runs_default_best_effort_and_may_explicitly_select_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            created = self.invoke(workspace, 'default-policy')
            self.assertEqual(created.get('production_policy'), 'best_effort')
            default = json.loads((workspace / 'ppt-output/default-policy/.ppt-pilot/run.json').read_text(encoding='utf-8'))
            self.assertEqual(default.get('production_policy'), 'best_effort')
            self.invoke(workspace, 'strict-policy', '--production-policy', 'strict')
            strict = json.loads((workspace / 'ppt-output/strict-policy/.ppt-pilot/run.json').read_text(encoding='utf-8'))
            self.assertEqual(strict['production_policy'], 'strict')


class ImportedFinalizeTests(unittest.TestCase):
    def test_finalize_uses_existing_import_gates_and_render_evidence(self):
        from tests.test_source_workflow_gate import Fixture
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Fixture(root)
            fixture.run.update(stage='qa', production_policy='strict')
            fixture.run['delivery'] = {'schema_version': 1, 'status': 'prepared', 'policy': 'strict',
                'target_slide_ids': ['S01', 'S02'], 'delivered_slide_ids': ['S01', 'S02'],
                'missing_slides': [],
                'storyboard_sha256': 'sha256:' + fixture.sha('.ppt-pilot/故事板.md'),
                'theme_sha256': 'sha256:' + fixture.sha('.ppt-pilot/theme.json'),
                'quality_report_sha256': None,
                'slide_sha256': {sid: 'sha256:' + fixture.sha('slides/' + sid + '.svg')
                                 for sid in ('S01', 'S02')}}
            fixture.save()
            result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'ppt_runtime.py'),
                                     'finalize', '--run-dir', str(root)],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertTrue(result.stdout, result.stderr)
            body = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, body)
            run = json.loads((root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
            self.assertEqual(run['stage'], 'complete')
            self.assertEqual(run['delivery']['status'], 'complete')
            self.assertEqual(run['delivery']['quality_report_sha256'],
                             'sha256:' + fixture.sha('.ppt-pilot/质量检查报告.md'))
    def test_finalize_rejects_render_drift_before_committing_the_run(self):
        from tests.test_partial_workflow_gate import PartialWorkflowGateTests
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        for target in ('.ppt-pilot/renders/S01.png', 'original.pptx'):
            with self.subTest(target=target):
                fixture = PartialWorkflowGateTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                fixture.prepare_partial('prepared')
                runtime = Runtime(fixture.root)
                run_path = fixture.root / '.ppt-pilot/run.json'
                before = run_path.read_bytes()
                original = runtime.write_barrier
                changed = False

                def change_evidence_then_check():
                    nonlocal changed
                    if not changed:
                        changed = True
                        evidence = fixture.root / target
                        evidence.write_bytes(evidence.read_bytes() + b'changed evidence')
                    return original()

                with mock.patch.object(runtime, 'write_barrier', side_effect=change_evidence_then_check), self.assertRaises(ValueError):
                    runtime.execute(parser().parse_args(['finalize', '--run-dir', str(fixture.root)]))
                self.assertEqual(run_path.read_bytes(), before)
                self.assertEqual(runtime.run['stage'], 'qa')

    def test_finalize_partial_import_calls_partial_source_gate(self):
        from tests.test_source_workflow_gate import Fixture
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Fixture(root)
            (root / 'slides/S02.svg').unlink()
            fixture.evidence['qa']['slides'] = fixture.evidence['qa']['slides'][:1]
            fixture.write('.ppt-pilot/质量检查报告.md', 'S01 rendered and visually reviewed PASS; S02 omitted.')
            fixture.evidence['qa']['report'] = fixture.record('.ppt-pilot/质量检查报告.md')
            identity = 'sha256:' + 'b' * 64
            ref = '.ppt-pilot/visual-generation-transactions/S02-' + 'b' * 64 + '.json'
            fixture.write_json(ref, {'schema_version': 2, 'kind': 'visual_generation_transaction',
                'batch_id': 'batch-partial', 'slide_id': 'S02', 'transaction_id': identity,
                'state': 'failed', 'failure_reason': 'svg_contract_failed', 'generation_attempt': 3})
            transaction_hash = 'sha256:' + fixture.sha(ref)
            fixture.write_json('.ppt-pilot/visual-generation-batches/batch-partial.json', {
                'batch_id': 'batch-partial', 'state': 'partial', 'ordered_slide_ids': ['S01', 'S02'],
                'transaction_refs': ['unused', ref], 'omitted_transaction_refs': [ref],
                'omitted_transaction_sha256': {ref: transaction_hash}})
            fixture.run.update(stage='qa', production_policy='best_effort', dirty_slides=['S02'])
            fixture.run['delivery'] = {'schema_version': 1, 'status': 'prepared',
                'policy': 'best_effort', 'target_slide_ids': ['S01', 'S02'],
                'delivered_slide_ids': ['S01'],
                'missing_slides': [{'slide_id': 'S02', 'reason': 'attempts_exhausted',
                    'failure_reason': 'svg_contract_failed', 'generation_attempt': 3,
                    'transaction_id': identity, 'transaction_ref': ref,
                    'transaction_sha256': transaction_hash}],
                'storyboard_sha256': 'sha256:' + fixture.sha('.ppt-pilot/故事板.md'),
                'theme_sha256': 'sha256:' + fixture.sha('.ppt-pilot/theme.json'),
                'quality_report_sha256': None,
                'slide_sha256': {'S01': 'sha256:' + fixture.sha('slides/S01.svg')}}
            fixture.save()
            result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'ppt_runtime.py'),
                                     'finalize', '--run-dir', str(root)],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertTrue(result.stdout, result.stderr)
            body = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, body)
            run = json.loads((root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
            self.assertEqual(run['stage'], 'partial')
            self.assertEqual(run['delivery']['status'], 'partial')
            self.assertEqual(run['dirty_slides'], ['S02'])


class PageLocalRuntimeTests(unittest.TestCase):
    def test_public_runtime_exposes_advance_finalize_and_submit_result(self):
        from ppt_runtime import parser
        command_action = next(action for action in parser()._actions if action.dest == 'command')
        self.assertTrue({'advance', 'finalize', 'submit-result', 'retire-batch'} <= set(command_action.choices))
        advance = parser().parse_args(['advance', '--run-dir', 'run', '--allow-partial',
                                       '--skip-slide', 'S02', '--skip-slide', 'S03'])
        self.assertTrue(advance.allow_partial)
        self.assertEqual(advance.skip_slide, ['S02', 'S03'])
        parser().parse_args(['finalize', '--run-dir', 'run'])
        parser().parse_args(['submit-result', '--run-dir', 'run', '--dispatch-id', 'dispatch',
                             '--host-task-id', 'task', '--response', '.ppt-pilot/runtime-inputs/result.txt'])

    def setUp(self):
        self.case = runtime_tests.RuntimeTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.prepared_fixture('deepseek-harness', slide_count=3)
        self.root = self.case.root
        sample = (self.root / '.ppt-pilot/samples/S01.svg').read_bytes()
        (self.root / '.ppt-pilot/samples/S02.svg').write_bytes(sample)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['anchor']['files']['.ppt-pilot/samples/S02.svg'] = hashlib.sha256(sample).hexdigest()
        self.case.put('.ppt-pilot/run.json', run)

    def graph(self):
        value = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        txs = {tx['slide_id']: (ref, tx) for ref in value['transaction_refs']
               for tx in [json.loads((self.root / ref).read_text(encoding='utf-8'))]}
        return value, txs

    def reprepare(self, slide_ids):
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run.pop('active_visual_generation_batch')
        self.case.put('.ppt-pilot/run.json', run)
        from _run_store import canonical, sha
        request = copy.deepcopy(self.case.request)
        request['ordered_slide_ids'] = list(slide_ids)
        request['generation_operations'] = [operation for operation in request['generation_operations']
                                            if operation['slide_id'] in slide_ids]
        request['request_id'] = sha(canonical({key: value for key, value in request.items()
            if key not in ('request_id', 'expected_run_sha256')}).rstrip(b'\n'))
        request['expected_run_sha256'] = sha((self.root / '.ppt-pilot/run.json').read_bytes())
        self.case.put('.ppt-pilot/runtime-inputs/request.json', request)
        result, body = self.case.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                        '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.case.batch = body['result']['batch_id']
        self.case.manifest_name = '.ppt-pilot/visual-generation-batches/' + self.case.batch + '.json'
        return request

    def reserve_bind(self, slide_id):
        _, txs = self.graph()
        tx = txs[slide_id][1]
        result, body = self.case.invoke(
            'reserve-dispatch', '--batch-id', self.case.batch, '--slide-id', slide_id,
            '--transaction-id', tx['transaction_id'], '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        dispatch_id = body['result']['dispatch']['dispatch_id']
        result, body = self.case.invoke('bind-task', '--dispatch-id', dispatch_id,
                                        '--host-task-id', 'task-' + slide_id)
        self.assertEqual(result.returncode, 0, body)
        return dispatch_id

    def write_candidate(self, slide_id, dispatch_id):
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
                    'viewBox="0 0 1280 720"><title>Fixture</title><desc>Fixture page</desc>'
                    '<g data-block-id="{0}-B1"><text data-role="body" x="100" y="120" '
                    'font-size="24" font-family="Arial"><tspan x="100" y="120">Hello</tspan>'
                    '</text></g></svg>\n```\n').format(slide_id)
        name = '.ppt-pilot/runtime-inputs/response-' + slide_id + '.txt'
        (self.root / name).write_text(response, encoding='utf-8')
        result, body = self.case.invoke('ingest-result', '--dispatch-id', dispatch_id, '--response', name)
        self.assertEqual(result.returncode, 0, body)

    def validate(self, slide_id, *, visual='passed'):
        _, txs = self.graph()
        tx = txs[slide_id][1]
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': slide_id,
              'transaction_id': tx['transaction_id'], 'candidate_sha256': tx['candidate_sha256'],
              'checks': {key: visual if key == 'visual' else 'passed' for key in V2_VALIDATION_CHECKS},
              'defect_id': None, 'failure_reason': None}
        name = '.ppt-pilot/runtime-inputs/qa-' + slide_id + '.json'
        self.case.put(name, qa)
        result, body = self.case.invoke('record-validation', '--slide-id', slide_id,
                                        '--transaction-id', tx['transaction_id'], '--input', name)
        self.assertEqual(result.returncode, 0, body)

    def fail_generation(self, slide_id, attempts=1, reason='generator_timeout'):
        for attempt in range(1, attempts + 1):
            dispatch = self.reserve_bind(slide_id)
            result, body = self.case.invoke('record-generator-failure', '--dispatch-id', dispatch,
                                            '--reason', reason)
            self.assertEqual(result.returncode, 0, body)
            if attempt < attempts:
                _, txs = self.graph()
                tx = txs[slide_id][1]
                result, body = self.case.invoke('prepare-recovery', '--slide-id', slide_id,
                    '--transaction-id', tx['transaction_id'], '--mode', 'retry')
                self.assertEqual(result.returncode, 0, body)

    def final_render_evidence(self):
        import base64
        from _runtime_owners import markdown_owner
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        name = '.ppt-pilot/质量检查报告.md'
        owner = markdown_owner((self.root / name).read_bytes())
        rows = []
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lWQAAAAASUVORK5CYII=')
        for sid in run['delivery']['delivered_slide_ids']:
            relative = '.ppt-pilot/renders/' + sid + '-final.png'
            path = self.root / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(png)
            svg = 'slides/' + sid + '.svg'
            svg_hash = digest((self.root / svg).read_bytes())[7:]
            rows.append({'slide_id': sid, 'svg': {'path': svg, 'sha256': svg_hash},
                         'render': {'path': relative, 'sha256': digest(png)[7:]},
                         'render_input_sha256': svg_hash, 'renderer': 'synthetic-fixture-renderer',
                         'visual_review': 'PASS'})
        owner['final_review'] = {'status': 'PASS', 'slides': rows}
        self.case.document(name, owner)

    def test_finalize_requires_bound_render_files_not_just_pass_booleans(self):
        for sid in ('S01', 'S02', 'S03'):
            dispatch = self.reserve_bind(sid)
            self.write_candidate(sid, dispatch)
            self.validate(sid)
        result, prepared = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, prepared)
        before = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, blocked = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'final_qa_required')
        self.assertEqual(blocked['writes'], [])
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before)

    def test_finalized_runtime_partial_deck_exports_without_rewriting_storyboard(self):
        for sid in ('S01', 'S02'):
            dispatch = self.reserve_bind(sid)
            self.write_candidate(sid, dispatch)
            self.validate(sid)
        self.fail_generation('S03', attempts=3)
        before = (self.root / '.ppt-pilot/故事板.md').read_bytes()
        result, prepared = self.case.invoke('advance', '--allow-partial')
        self.assertEqual(result.returncode, 0, prepared)
        self.final_render_evidence()
        result, final = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 0, final)
        converter = SCRIPTS.parents[1] / 'ppt-editable/scripts/svg_to_editable_pptx.py'
        converted = subprocess.run([sys.executable, '-B', str(converter), '--run-dir', str(self.root),
                                    '--skip-office', '--json'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(converted.returncode, 0, converted.stdout + converted.stderr)
        output = json.loads(converted.stdout)
        self.assertEqual(output['delivery_status'], 'partial')
        self.assertEqual(output['delivered_slide_ids'], ['S01', 'S02'])
        self.assertEqual(output['slide_count'], 2)
        self.assertEqual((self.root / '.ppt-pilot/故事板.md').read_bytes(), before)
        self.assertTrue((self.root / output['output_path']).is_file())

    def test_advance_reports_pending_nodes_without_mutating_or_skipping_them(self):
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['pending_interaction'] = {'id': 'confirm', 'status': 'pending'}
        self.case.put('.ppt-pilot/run.json', run)
        result, waiting = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, waiting)
        self.assertEqual(waiting['result']['next_command'], 'await-interaction')
        self.assertEqual(waiting['writes'], [])
        result, denied = self.case.invoke('advance', '--allow-partial')
        self.assertEqual(result.returncode, 2, denied)
        self.assertEqual(denied['writes'], [])

    def test_advance_keeps_anchor_work_out_of_formal_promotion(self):
        dispatch = self.reserve_bind('S01')
        self.write_candidate('S01', dispatch)
        self.validate('S01')
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['stage'] = 'anchor'
        self.case.put('.ppt-pilot/run.json', run)
        result, work = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, work)
        self.assertEqual(work['result']['next_command'], 'dispatch-plan')
        self.assertEqual(work['result']['promotable'], [])
        self.assertEqual(work['writes'], [])
        self.assertFalse((self.root / 'slides/S01.svg').exists())

    def test_advance_records_partial_policy_before_the_first_batch(self):
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run.pop('active_visual_generation_batch')
        run.pop('production_policy', None)
        self.case.put('.ppt-pilot/run.json', run)
        result, body = self.case.invoke('advance', '--allow-partial')
        self.assertEqual(result.returncode, 0, body)
        current = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(current.get('production_policy'), 'best_effort')
        self.assertEqual(body['result']['next_command'], 'prepare-batch')
        self.assertEqual(body['result']['prepare_request']['expected_run_sha256'], digest((self.root / '.ppt-pilot/run.json').read_bytes()))

    def test_advance_rejects_skip_without_an_active_failed_page_before_writes(self):
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run.pop('active_visual_generation_batch')
        self.case.put('.ppt-pilot/run.json', run)
        before = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, body = self.case.invoke('advance', '--allow-partial', '--skip-slide', 'S99')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before)

    def test_settlement_ignores_obsolete_final_bindings_but_checks_the_current_final(self):
        self.reprepare(['S01'])
        dispatch = self.reserve_bind('S01')
        self.write_candidate('S01', dispatch)
        self.validate('S01')
        result, body = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, body)
        current_manifest, txs = self.graph()
        current_tx = txs['S01'][1]
        obsolete = copy.deepcopy(current_tx)
        identity = digest(b'obsolete-page-operation')
        old_bytes = (self.root / current_tx['candidate_path']).read_bytes().replace(b'x="100"', b'x="120"')
        old_ref = '.ppt-pilot/visual-generation-transactions/S01-' + identity[7:] + '.json'
        obsolete.update(batch_id='batch-obsolete', transaction_id=identity, prompt_snapshot_id=identity,
                        candidate_path='slides/.candidates/S01-' + identity[7:] + '.svg',
                        candidate_sha256=digest(old_bytes))
        self.case.put(old_ref, obsolete)
        (self.root / obsolete['candidate_path']).write_bytes(old_bytes)
        historical = copy.deepcopy(current_manifest)
        historical.update(batch_id='batch-obsolete', transaction_refs=[old_ref])
        self.case.put('.ppt-pilot/visual-generation-batches/batch-obsolete.json', historical)
        before = (self.root / old_ref).read_bytes()
        result, body = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['unhandled_slide_ids'], ['S02', 'S03'])
        self.assertEqual((self.root / old_ref).read_bytes(), before)
        final_path = self.root / 'slides/S01.svg'
        final_path.write_bytes(final_path.read_bytes() + b'corrupt')
        result, blocked = self.case.invoke('advance')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'final_promotion_conflict')
        self.assertEqual(blocked['writes'], [])

    def test_normalized_text_role_is_exposed_and_cannot_substitute_for_visual_qa(self):
        dispatch = self.reserve_bind('S01')
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
                    'viewBox="0 0 1280 720"><title>Fixture</title><desc>Normalized label</desc>'
                    '<g data-block-id="S01-B1"><text data-role="body" x="100" y="120" font-size="14" '
                    'font-family="Arial"><tspan x="100" y="120">Label</tspan></text></g></svg>\n```\n')
        name = '.ppt-pilot/runtime-inputs/normalized.txt'
        (self.root / name).write_text(response, encoding='utf-8')
        result, ingested = self.case.invoke('ingest-result', '--dispatch-id', dispatch, '--response', name)
        self.assertEqual(result.returncode, 0, ingested)
        self.assertIn('text_role_normalized',
                      [warning['code'] for warning in ingested['result']['warnings']])
        tx = self.graph()[1]['S01'][1]
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01',
              'transaction_id': tx['transaction_id'], 'candidate_sha256': tx['candidate_sha256'],
              'checks': {key: 'not_rendered' if key == 'visual' else 'passed'
                         for key in V2_VALIDATION_CHECKS},
              'defect_id': None, 'failure_reason': None}
        self.case.put('.ppt-pilot/runtime-inputs/normalized-qa.json', qa)
        result, blocked = self.case.invoke('record-validation', '--slide-id', 'S01',
            '--transaction-id', tx['transaction_id'], '--input', '.ppt-pilot/runtime-inputs/normalized-qa.json')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'visual_qa_required')

    def test_warning_bearing_svg_requires_rendered_visual_qa(self):
        dispatch = self.reserve_bind('S01')
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
                    'viewBox="0 0 1280 720"><title>Fixture</title><desc>Margin warning</desc>'
                    '<g data-block-id="S01-B1"><text data-role="body" x="932" y="400" font-size="20" '
                    'font-family="Arial"><tspan x="932" y="400">' + ('一' * 13) +
                    '</tspan></text></g></svg>\n```\n')
        name = '.ppt-pilot/runtime-inputs/warning.txt'
        (self.root / name).write_text(response, encoding='utf-8')
        result, ingested = self.case.invoke('ingest-result', '--dispatch-id', dispatch, '--response', name)
        self.assertEqual(result.returncode, 0, ingested)
        self.assertEqual([warning['code'] for warning in ingested['result'].get('warnings', [])],
                         ['text_margin_unverified'])
        _, txs = self.graph()
        tx = txs['S01'][1]
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01',
              'transaction_id': tx['transaction_id'], 'candidate_sha256': tx['candidate_sha256'],
              'checks': {key: 'not_rendered' if key == 'visual' else 'passed'
                         for key in V2_VALIDATION_CHECKS},
              'defect_id': None, 'failure_reason': None}
        self.case.put('.ppt-pilot/runtime-inputs/warning-qa.json', qa)
        result, blocked = self.case.invoke('record-validation', '--slide-id', 'S01',
            '--transaction-id', tx['transaction_id'], '--input', '.ppt-pilot/runtime-inputs/warning-qa.json')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'visual_qa_required')
        self.assertEqual(self.graph()[1]['S01'][1]['state'], 'candidate_written')
        qa['checks']['visual'] = 'passed'
        self.case.put('.ppt-pilot/runtime-inputs/warning-qa.json', qa)
        result, passed = self.case.invoke('record-validation', '--slide-id', 'S01',
            '--transaction-id', tx['transaction_id'], '--input', '.ppt-pilot/runtime-inputs/warning-qa.json')
        self.assertEqual(result.returncode, 0, passed)

    def test_submit_result_folds_bind_and_ingest_with_idempotent_replay(self):
        _, txs = self.graph()
        tx = txs['S01'][1]
        result, reserved = self.case.invoke('reserve-dispatch', '--batch-id', self.case.batch,
            '--slide-id', 'S01', '--transaction-id', tx['transaction_id'],
            '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, reserved)
        dispatch_id = reserved['result']['dispatch']['dispatch_id']
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
                    'viewBox="0 0 1280 720"><title>Fixture</title><desc>Fixture</desc>'
                    '<g data-block-id="S01-B1"><text data-role="body" x="100" y="120" font-size="24" '
                    'font-family="Arial"><tspan x="100" y="120">Hello</tspan></text></g></svg>\n```\n')
        (self.root / '.ppt-pilot/runtime-inputs/submitted.txt').write_text(response, encoding='utf-8')
        args = ('--dispatch-id', dispatch_id, '--host-task-id', 'combined-task',
                '--response', '.ppt-pilot/runtime-inputs/submitted.txt')
        result, body = self.case.invoke('submit-result', *args)
        self.assertEqual(result.returncode, 0, body)
        current = self.graph()[1]['S01'][1]
        self.assertEqual(current['state'], 'candidate_written')
        self.assertEqual(current['generation_attempt'], 1)
        self.assertTrue((self.root / current['candidate_path']).is_file())
        result, replay = self.case.invoke('submit-result', *args)
        self.assertEqual(result.returncode, 0, replay)
        self.assertTrue(replay['result']['replay'])
        self.assertEqual(replay['writes'], [])

    def test_submit_result_replays_after_crash_between_bind_and_ingest_without_extra_attempt(self):
        _, txs = self.graph()
        tx = txs['S01'][1]
        result, reserved = self.case.invoke('reserve-dispatch', '--batch-id', self.case.batch,
            '--slide-id', 'S01', '--transaction-id', tx['transaction_id'],
            '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        dispatch_id = reserved['result']['dispatch']['dispatch_id']
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
                    'viewBox="0 0 1280 720"><title>Fixture</title><desc>Fixture</desc>'
                    '<g data-block-id="S01-B1"><text data-role="body" x="100" y="120" font-size="24" '
                    'font-family="Arial"><tspan x="100" y="120">Hello</tspan></text></g></svg>\n```\n')
        (self.root / '.ppt-pilot/runtime-inputs/crash-submit.txt').write_text(response, encoding='utf-8')
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        runtime = Runtime(self.root)
        args = parser().parse_args(['submit-result', '--run-dir', str(self.root),
            '--dispatch-id', dispatch_id, '--host-task-id', 'crash-task',
            '--response', '.ppt-pilot/runtime-inputs/crash-submit.txt'])
        with mock.patch.object(runtime, 'ingest_result', side_effect=OSError('crash after bind')), self.assertRaises(OSError):
            runtime.execute(args)
        self.assertEqual(self.graph()[1]['S01'][1]['generation_attempt'], 1)
        result, replay = self.case.invoke('submit-result', '--dispatch-id', dispatch_id,
            '--host-task-id', 'crash-task', '--response', '.ppt-pilot/runtime-inputs/crash-submit.txt')
        self.assertEqual(result.returncode, 0, replay)
        self.assertEqual(self.graph()[1]['S01'][1]['generation_attempt'], 1)
        self.assertEqual(self.graph()[1]['S01'][1]['state'], 'candidate_written')

    def test_resume_reports_coherent_action_sets_and_prefers_healthy_work(self):
        self.fail_generation('S01')
        dispatch = self.reserve_bind('S02')
        self.write_candidate('S02', dispatch)
        self.validate('S02')
        result, body = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        plan = body['result']
        self.assertEqual(plan['next_command'], 'promote')
        self.assertEqual([item['slide_id'] for item in plan['promotable']], ['S02'])
        self.assertEqual([item['slide_id'] for item in plan['dispatchable']], ['S03'])
        self.assertEqual([item['slide_id'] for item in plan['recoverable']], ['S01'])
        self.assertEqual(plan['exhausted'], [])
        self.assertEqual(body['writes'], [])

    def test_invalid_owner_blocks_policy_and_omission_writes_globally(self):
        self.fail_generation('S02')
        prompt = self.root / '.ppt-pilot/generation-prompts/S01.md'
        prompt.write_bytes(prompt.read_bytes() + b'changed owner')
        manifest_before = (self.root / self.case.manifest_name).read_bytes()
        run_before = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, blocked = self.case.invoke('advance', '--allow-partial', '--skip-slide', 'S02')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'prompt_snapshot_conflict')
        self.assertEqual(blocked['writes'], [])
        self.assertEqual((self.root / self.case.manifest_name).read_bytes(), manifest_before)
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), run_before)

    def test_global_generator_unavailable_blocks_batch_without_dispatching_sibling(self):
        bad = copy.deepcopy(self.case.capability)
        bad['host'] = 'unsupported'
        self.case.put('.ppt-pilot/runtime-inputs/bad-cap.json', bad)
        _, txs = self.graph()
        tx = txs['S01'][1]
        result, blocked = self.case.invoke('reserve-dispatch', '--batch-id', self.case.batch,
            '--slide-id', 'S01', '--transaction-id', tx['transaction_id'],
            '--capability', '.ppt-pilot/runtime-inputs/bad-cap.json')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'generator_unavailable')
        self.assertEqual(self.graph()[0]['state'], 'blocked')
        result, resumed = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, resumed)
        self.assertEqual(resumed['result']['next_command'], 'resolve-global-failure')
        self.assertEqual([item['slide_id'] for item in resumed['result']['global_blockers']], ['S01'])
        self.assertEqual(resumed['result']['dispatchable'], [])
        self.assertEqual(resumed['result']['promotable'], [])
        result, planned = self.case.invoke('dispatch-plan', '--batch-id', self.case.batch,
            '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, planned)
        self.assertEqual(planned['result']['items'], [])
        result, advanced = self.case.invoke('advance', '--allow-partial')
        self.assertEqual(result.returncode, 2, advanced)
        self.assertEqual(advanced['errors'][0]['code'], 'generator_unavailable')
        self.assertNotIn('omitted_transaction_refs', self.graph()[0])

    def test_graph_rejects_changed_bytes_after_page_omission(self):
        self.fail_generation('S02')
        result, body = self.case.invoke('advance', '--allow-partial', '--skip-slide', 'S02')
        self.assertEqual(result.returncode, 0, body)
        ref, tx = self.graph()[1]['S02']
        tx['timing'].append({'tampered': True})
        self.case.put(ref, tx)
        result, blocked = self.case.invoke('resume')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'omitted_transaction_hash_mismatch')
        self.assertEqual(blocked['writes'], [])

    def test_promotion_requires_matching_durable_page_qa_evidence(self):
        dispatch = self.reserve_bind('S01')
        self.write_candidate('S01', dispatch)
        manifest, txs = self.graph()
        ref, tx = txs['S01']
        tx['state'] = 'validated'
        tx['validation'] = {'state': 'passed',
                            'checks': {key: 'passed' for key in V2_VALIDATION_CHECKS}}
        self.case.put(ref, tx)
        from _run_store import sha
        result, blocked = self.case.invoke('promote', '--batch-id', self.case.batch,
            '--expected-manifest-sha256', sha((self.root / self.case.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'validation_evidence_missing')
        self.assertFalse((self.root / 'slides/S01.svg').exists())
        self.assertEqual(blocked['writes'], [])

    def test_page_failure_keeps_healthy_siblings_dispatchable_and_promotable(self):
        dispatch = self.reserve_bind('S01')
        result, body = self.case.invoke('record-generator-failure', '--dispatch-id', dispatch,
                                        '--reason', 'generator_timeout')
        self.assertEqual(result.returncode, 0, body)
        failed_ref, _ = self.graph()[1]['S01']
        failed_bytes = (self.root / failed_ref).read_bytes()

        result, planned = self.case.invoke('dispatch-plan', '--batch-id', self.case.batch,
                                           '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, planned)
        self.assertEqual([item['slide_id'] for item in planned['result']['items']], ['S02', 'S03'])

        dispatch = self.reserve_bind('S02')
        self.write_candidate('S02', dispatch)
        self.validate('S02')
        from _run_store import sha
        result, promoted = self.case.invoke('promote', '--batch-id', self.case.batch,
            '--expected-manifest-sha256', sha((self.root / self.case.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 0, promoted)
        self.assertEqual(promoted['result']['promoted_slide_ids'], ['S02'])
        self.assertTrue((self.root / 'slides/S02.svg').is_file())
        self.assertFalse((self.root / 'slides/S01.svg').exists())
        self.assertEqual((self.root / failed_ref).read_bytes(), failed_bytes)
        current = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        self.assertEqual(current['state'], 'active')
        self.assertIn('active_visual_generation_batch', json.loads(
            (self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8')))

    def test_partial_authorization_commits_before_omission_and_replays_after_crash(self):
        self.fail_generation('S02')
        manifest_before = (self.root / self.case.manifest_name).read_bytes()
        failed_ref, _ = self.graph()[1]['S02']
        failed_before = (self.root / failed_ref).read_bytes()
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        runtime = Runtime(self.root)
        args = parser().parse_args(['advance', '--run-dir', str(self.root),
                                    '--allow-partial', '--skip-slide', 'S02'])
        with mock.patch.object(runtime, 'persist_graph', side_effect=OSError('crash before omission ledger')), self.assertRaises(OSError):
            runtime.execute(args)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['production_policy'], 'best_effort')
        self.assertEqual((self.root / self.case.manifest_name).read_bytes(), manifest_before)
        self.assertEqual((self.root / failed_ref).read_bytes(), failed_before)
        result, replay = self.case.invoke('advance', '--skip-slide', 'S02')
        self.assertEqual(result.returncode, 0, replay)
        manifest = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        self.assertEqual(manifest['omitted_transaction_refs'], [failed_ref])
        self.assertEqual(replay['result']['recoverable'], [])
        self.assertEqual(replay['result']['exhausted'], [])
        self.assertEqual((self.root / failed_ref).read_bytes(), failed_before)

    def test_recomposed_transaction_never_resets_failed_generation_attempts(self):
        self.reprepare(['S01'])
        self.fail_generation('S01')
        self.case.apply_revision()
        old = self.graph()[1]['S01'][1]
        result, body = self.case.invoke('prepare-recovery', '--slide-id', 'S01',
            '--transaction-id', old['transaction_id'], '--mode', 'recompose')
        self.assertEqual(result.returncode, 0, body)
        replacement = self.graph()[1]['S01'][1]
        self.assertNotEqual(replacement['transaction_id'], old['transaction_id'])
        self.assertEqual(replacement['generation_attempt'], old['generation_attempt'])

    def test_advance_replays_valid_pending_recovery_journal_before_planning(self):
        self.reprepare(['S01'])
        self.fail_generation('S01')
        self.case.apply_revision()
        _, txs = self.graph()
        old_id = txs['S01'][1]['transaction_id']
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        runtime = Runtime(self.root)
        args = parser().parse_args(['prepare-recovery', '--run-dir', str(self.root),
            '--slide-id', 'S01', '--transaction-id', old_id, '--mode', 'recompose'])
        original = runtime.store.write_json

        def interrupt(name, value, expected):
            if '/visual-generation-transactions/' in name and old_id[7:] not in name:
                raise OSError('simulated crash after recovery prompt')
            return original(name, value, expected)

        with mock.patch.object(runtime.store, 'write_json', side_effect=interrupt), self.assertRaises(OSError):
            runtime.execute(args)
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        result, rejected = self.case.invoke('advance', '--allow-partial', '--skip-slide', 'S99')
        self.assertEqual(result.returncode, 2, rejected)
        self.assertEqual(rejected['writes'], [])
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
        result, body = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'dispatch-plan')
        self.assertEqual([item['slide_id'] for item in body['result']['dispatchable']], ['S01'])
        self.assertNotEqual(body['result']['dispatchable'][0]['transaction_id'], old_id)

    def test_advance_requires_opt_in_then_seals_exhausted_failure_and_prepares_partial_delivery(self):
        for slide_id in ('S01', 'S02'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        self.fail_generation('S03', attempts=3)
        failed_ref, failed = self.graph()[1]['S03']
        failed_bytes = (self.root / failed_ref).read_bytes()
        self.assertEqual(failed['generation_attempt'], 3)

        result, strict = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, strict)
        self.assertEqual(strict['result']['promotable'], [])
        self.assertEqual([item['slide_id'] for item in strict['result']['exhausted']], ['S03'])
        self.assertEqual(strict['result']['next_command'], 'advance')
        strict_run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertNotIn('production_policy', strict_run)
        self.assertIn('active_visual_generation_batch', strict_run)
        self.assertTrue((self.root / 'slides/S01.svg').is_file())
        self.assertTrue((self.root / 'slides/S02.svg').is_file())
        self.assertEqual((self.root / failed_ref).read_bytes(), failed_bytes)
        strict_manifest = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        self.assertNotIn('omitted_transaction_refs', strict_manifest)
        self.assertEqual(strict_manifest['state'], 'active')

        result, partial = self.case.invoke('advance', '--allow-partial')
        self.assertEqual(result.returncode, 0, partial)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['production_policy'], 'best_effort')
        self.assertEqual(run['stage'], 'qa')
        self.assertNotIn('active_visual_generation_batch', run)
        delivery = run['delivery']
        self.assertEqual(delivery['status'], 'prepared')
        self.assertEqual(delivery['target_slide_ids'], ['S01', 'S02', 'S03'])
        self.assertEqual(delivery['delivered_slide_ids'], ['S01', 'S02'])
        self.assertEqual(delivery['missing_slides'][0]['slide_id'], 'S03')
        self.assertEqual(delivery['missing_slides'][0]['reason'], 'attempts_exhausted')
        self.assertEqual(delivery['missing_slides'][0]['transaction_sha256'], digest(failed_bytes))
        self.assertEqual((self.root / failed_ref).read_bytes(), failed_bytes)
        settled = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        self.assertEqual(settled['state'], 'partial')
        self.assertEqual(settled['omitted_transaction_refs'], [failed_ref])
        self.assertEqual(settled['omitted_transaction_sha256'], {failed_ref: digest(failed_bytes)})
        result, replay = self.case.invoke('prepare-batch',
            '--input', '.ppt-pilot/runtime-inputs/request.json',
            '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, replay)
        self.assertEqual(replay['writes'], [])
        self.assertNotIn('active_visual_generation_batch', json.loads(
            (self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8')))

    def test_finalize_binds_real_page_qa_and_preserves_dirty_omission(self):
        for slide_id in ('S01', 'S02'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        self.fail_generation('S03', attempts=3)
        result, prepared = self.case.invoke('advance', '--allow-partial')
        self.assertEqual(result.returncode, 0, prepared)
        self.final_render_evidence()
        qa_bytes = (self.root / '.ppt-pilot/质量检查报告.md').read_bytes()
        result, resumed = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, resumed)
        self.assertEqual(resumed['result']['next_command'], 'finalize')
        self.assertEqual(resumed['writes'], [])
        self.final_render_evidence()
        result, final = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 0, final)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['stage'], 'partial')
        self.assertEqual(run['delivery']['status'], 'partial')
        self.assertEqual(run['delivery']['quality_report_sha256'], digest(qa_bytes))
        self.assertEqual(run['dirty_slides'], ['S03'])
        self.assertEqual(final['result']['delivered_slide_ids'], ['S01', 'S02'])
        self.assertEqual(final['result']['missing_slide_ids'], ['S03'])

    def test_zero_delivered_pages_end_in_failed_terminal_partition(self):
        for slide_id in ('S01', 'S02', 'S03'):
            self.fail_generation(slide_id)
        result, body = self.case.invoke('advance', '--allow-partial',
            '--skip-slide', 'S01', '--skip-slide', 'S02', '--skip-slide', 'S03')
        self.assertEqual(result.returncode, 0, body)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['stage'], 'failed')
        self.assertEqual(run['delivery']['status'], 'failed')
        self.assertEqual(run['delivery']['delivered_slide_ids'], [])
        self.assertEqual([item['slide_id'] for item in run['delivery']['missing_slides']],
                         ['S01', 'S02', 'S03'])
        self.assertNotIn('active_visual_generation_batch', run)
        manifest = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        self.assertEqual(manifest['state'], 'failed')
        self.assertEqual(run['dirty_slides'], ['S01', 'S02', 'S03'])

    def test_full_delivery_remains_complete_and_clears_only_delivered_dirty_pages(self):
        for slide_id in ('S01', 'S02', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        result, prepared = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, prepared)
        self.assertEqual(prepared['result']['delivery']['status'], 'prepared')
        self.assertEqual(prepared['result']['delivery']['missing_slides'], [])
        self.final_render_evidence()
        result, final = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 0, final)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['stage'], 'complete')
        self.assertEqual(run['delivery']['status'], 'complete')
        self.assertEqual(run['dirty_slides'], [])
        result, replay = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 0, replay)
        self.assertTrue(replay['result']['replay'])
        self.assertEqual(replay['writes'], [])

    def test_final_replay_revalidates_machine_qa_instead_of_trusting_rebound_hash(self):
        for slide_id in ('S01', 'S02', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        self.case.invoke('advance')
        self.final_render_evidence()
        result, final = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 0, final)
        report_path = self.root / '.ppt-pilot/质量检查报告.md'
        from _runtime_owners import markdown_owner
        owner = markdown_owner(report_path.read_bytes())
        owner['records'][0]['checks']['visual'] = 'not_rendered'
        self.case.document('.ppt-pilot/质量检查报告.md', owner)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['delivery']['quality_report_sha256'] = digest(report_path.read_bytes())
        self.case.put('.ppt-pilot/run.json', run)
        before = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, blocked = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'final_qa_required')
        self.assertEqual(blocked['writes'], [])
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before)

    def test_finalize_rejects_not_rendered_page_qa_without_mutating_prepared_delivery(self):
        for slide_id in ('S01', 'S02', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id, visual='not_rendered')
        result, prepared = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, prepared)
        before = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, blocked = self.case.invoke('finalize')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'final_qa_required')
        self.assertEqual(blocked['writes'], [])
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before)

    def test_advance_rebuilds_stale_completed_pages_from_current_owner_snapshots(self):
        for slide_id in ('S01', 'S02', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        from _run_store import sha
        result, promoted = self.case.invoke('promote', '--batch-id', self.case.batch,
            '--expected-manifest-sha256', sha((self.root / self.case.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 0, promoted)
        self.case.apply_revision()
        result, body = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'prepare-batch')
        self.assertEqual(body['result']['prepare_request']['ordered_slide_ids'], ['S01', 'S02', 'S03'])
        self.assertNotIn('delivery', json.loads(
            (self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8')))

    def test_advance_prepares_later_unhandled_targets_without_resurrecting_omission(self):
        self.reprepare(['S01', 'S02'])
        dispatch = self.reserve_bind('S01')
        self.write_candidate('S01', dispatch)
        self.validate('S01')
        self.fail_generation('S02', attempts=3)
        result, body = self.case.invoke('advance', '--allow-partial')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'prepare-batch')
        self.assertEqual(body['result']['prepare_request']['ordered_slide_ids'], ['S03'])
        self.assertNotIn('delivery', json.loads(
            (self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8')))
        result, resumed = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, resumed)
        self.assertEqual(resumed['result']['prepare_request']['ordered_slide_ids'], ['S03'])
        self.assertEqual(resumed['writes'], [])

        self.case.put('.ppt-pilot/runtime-inputs/request.json', body['result']['prepare_request'])
        result, prepared = self.case.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                            '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, prepared)
        self.case.batch = prepared['result']['batch_id']
        self.case.manifest_name = '.ppt-pilot/visual-generation-batches/' + self.case.batch + '.json'
        dispatch = self.reserve_bind('S03')
        self.write_candidate('S03', dispatch)
        self.validate('S03')
        result, final = self.case.invoke('advance')
        self.assertEqual(result.returncode, 0, final)
        delivery = final['result']['delivery']
        self.assertEqual(delivery['delivered_slide_ids'], ['S01', 'S03'])
        self.assertEqual([item['slide_id'] for item in delivery['missing_slides']], ['S02'])
        self.assertEqual(json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
                         ['dirty_slides'], ['S01', 'S02', 'S03'])

    def test_failed_candidate_is_preserved_but_never_enters_delivery(self):
        for slide_id in ('S01', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        dispatch = self.reserve_bind('S02')
        self.write_candidate('S02', dispatch)
        _, txs = self.graph()
        tx = txs['S02'][1]
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S02',
              'transaction_id': tx['transaction_id'], 'candidate_sha256': tx['candidate_sha256'],
              'checks': {key: 'failed' if key == 'visual' else 'passed'
                         for key in V2_VALIDATION_CHECKS},
              'defect_id': 'visual-defect', 'failure_reason': 'visual_qa_failed'}
        self.case.put('.ppt-pilot/runtime-inputs/failed-candidate-qa.json', qa)
        result, body = self.case.invoke('record-validation', '--slide-id', 'S02',
            '--transaction-id', tx['transaction_id'],
            '--input', '.ppt-pilot/runtime-inputs/failed-candidate-qa.json')
        self.assertEqual(result.returncode, 0, body)
        candidate = self.root / tx['candidate_path']
        candidate_bytes = candidate.read_bytes()
        result, body = self.case.invoke('advance', '--allow-partial', '--skip-slide', 'S02')
        self.assertEqual(result.returncode, 0, body)
        delivery = body['result']['delivery']
        self.assertEqual(delivery['delivered_slide_ids'], ['S01', 'S03'])
        self.assertEqual(set(delivery['slide_sha256']), {'S01', 'S03'})
        self.assertFalse((self.root / 'slides/S02.svg').exists())
        self.assertEqual(candidate.read_bytes(), candidate_bytes)

    def test_skip_slide_requires_best_effort_and_only_omits_named_failed_page(self):
        for slide_id in ('S01', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        self.fail_generation('S02')
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

        result, blocked = self.case.invoke('advance', '--skip-slide', 'S02')
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'partial_delivery_not_authorized')
        self.assertEqual(blocked['writes'], [])
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes()
                                  for path in self.root.rglob('*') if path.is_file()})

        result, body = self.case.invoke('advance', '--allow-partial', '--skip-slide', 'S02')
        self.assertEqual(result.returncode, 0, body)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['delivery']['missing_slides'][0]['reason'], 'user_skipped')
        self.assertEqual(run['delivery']['missing_slides'][0]['generation_attempt'], 1)
        self.assertEqual(run['dirty_slides'], ['S01', 'S02', 'S03'])

    def test_skip_slide_rejects_healthy_page_before_any_promotion(self):
        dispatch = self.reserve_bind('S01')
        self.write_candidate('S01', dispatch)
        self.validate('S01')
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        result, body = self.case.invoke('advance', '--allow-partial', '--skip-slide', 'S01')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['errors'][0]['code'], 'skip_slide_not_failed')
        self.assertEqual(body['writes'], [])
        self.assertFalse((self.root / 'slides/S01.svg').exists())
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes()
                                  for path in self.root.rglob('*') if path.is_file()})

    def test_interrupted_retirement_never_dispatches_or_promotes_superseded_batch(self):
        for slide_id in ('S01', 'S02', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        from _run_store import sha
        request = {'schema_version': 1, 'kind': 'visual_generation_batch_retirement',
                   'request_id': 'theme-crash',
                   'expected_run_sha256': sha((self.root / '.ppt-pilot/run.json').read_bytes()),
                   'reason': 'theme_change', 'selected_style_id': 'minimal-grid',
                   'answer': 'Apply the new theme.'}
        self.case.put('.ppt-pilot/runtime-inputs/retire-crash.json', request)
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        runtime = Runtime(self.root)
        args = parser().parse_args(['retire-batch', '--run-dir', str(self.root),
            '--batch-id', self.case.batch, '--expected-manifest-sha256',
            sha((self.root / self.case.manifest_name).read_bytes()),
            '--input', '.ppt-pilot/runtime-inputs/retire-crash.json'])
        with mock.patch.object(runtime, 'write_run', side_effect=OSError('crash after manifest')), self.assertRaises(OSError):
            runtime.execute(args)
        self.assertEqual(json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))['state'],
                         'superseded')
        result, resumed = self.case.invoke('resume')
        self.assertEqual(result.returncode, 0, resumed)
        self.assertEqual(resumed['result']['next_command'], 'retire-batch')
        self.assertEqual(resumed['result']['promotable'], [])
        result, replay = self.case.invoke('retire-batch', '--batch-id', self.case.batch,
            '--expected-manifest-sha256', sha((self.root / self.case.manifest_name).read_bytes()),
            '--input', '.ppt-pilot/runtime-inputs/retire-crash.json')
        self.assertEqual(result.returncode, 0, replay)
        self.assertEqual(json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))['stage'], 'theme')

    def test_retire_batch_preserves_terminal_transactions_for_a_real_theme_change(self):
        for slide_id in ('S01', 'S02', 'S03'):
            dispatch = self.reserve_bind(slide_id)
            self.write_candidate(slide_id, dispatch)
            self.validate(slide_id)
        from _run_store import sha
        manifest_before = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        tx_before = {ref: (self.root / ref).read_bytes() for ref in manifest_before['transaction_refs']}
        request = {'schema_version': 1, 'kind': 'visual_generation_batch_retirement',
                   'request_id': 'theme-change-1',
                   'expected_run_sha256': sha((self.root / '.ppt-pilot/run.json').read_bytes()),
                   'reason': 'theme_change', 'selected_style_id': 'minimal-grid',
                   'answer': 'Use the newly selected style.'}
        self.case.put('.ppt-pilot/runtime-inputs/retire.json', request)
        result, body = self.case.invoke('retire-batch', '--batch-id', self.case.batch,
            '--expected-manifest-sha256', sha((self.root / self.case.manifest_name).read_bytes()),
            '--input', '.ppt-pilot/runtime-inputs/retire.json')
        self.assertEqual(result.returncode, 0, body)
        manifest = json.loads((self.root / self.case.manifest_name).read_text(encoding='utf-8'))
        self.assertEqual(manifest['state'], 'superseded')
        self.assertEqual({ref: (self.root / ref).read_bytes() for ref in manifest['transaction_refs']}, tx_before)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['stage'], 'theme')
        self.assertNotIn('active_visual_generation_batch', run)
        self.assertEqual(run['dirty_slides'], ['S01', 'S02', 'S03'])
        self.assertEqual(run['interaction_history'][body['result']['revision_id']]['affected_scope'], 'deck')


if __name__ == '__main__':
    unittest.main()
