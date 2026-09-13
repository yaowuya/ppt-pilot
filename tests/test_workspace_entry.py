"""Workspace entry is a real CLI; all input and output lives in temporary fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_source_intake import _deck


class WorkspaceEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / 'workspace'
        self.workspace.mkdir()
        self.source = self.workspace / 'source.pptx'
        _deck(self.source)

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def run_fixture(self, run_id='existing', *, legacy=False, source=True, **fields):
        root = self.workspace / 'ppt-output' / run_id
        run = {'schema_version': 1, 'deck_id': run_id, 'mode': 'guided', 'stage': 'brief',
               'dirty_slides': [], 'manuscript_review': {
                   'required': True, 'cycle': 1, 'round': 0, 'mode': 'pending',
                   'state': 'pending', 'status': 'PENDING', 'latest_report': '文稿审查.md',
                   'open_blocking_findings': [], 'review_history': []}}
        if source:
            run['source_deck'] = {'kind': 'external_pptx', 'source_path': str(self.source),
                                  'inventory': '源稿清单.json', 'mapping': '源页映射.json',
                                  'evidence': '导入检查点.json'}
        run.update(fields)
        self.put(root / ('run.json' if legacy else '.ppt-pilot/run.json'), run)
        return root

    def command(self, *args):
        return [sys.executable, '-B', str(SCRIPTS / 'ppt_entry.py'),
                '--workspace', str(self.workspace), *args]

    def invoke(self, *args, code=0, os_fault=None):
        command = self.command(*args)
        if os_fault is not None:
            # Deterministic OS faults in a child; the unchanged public CLI still parses real argv.
            startup = ('import sys, runpy, os\nfrom pathlib import Path\n'
                       'script = sys.argv[1]\nsys.path.insert(0, str(Path(script).parent))\n'
                       'sys.argv = sys.argv[1:]\n' + os_fault + '\nrunpy.run_path(script, run_name="__main__")\n')
            command = [sys.executable, '-B', '-c', startup, *command[2:]]
        process = subprocess.run(command, capture_output=True, text=True,
                                 encoding='utf-8', timeout=20)
        self.assertEqual(process.returncode, code, process.stdout + process.stderr)
        self.assertEqual(process.stderr, '')
        return json.loads(process.stdout)

    def snapshot(self, root=None):
        root = root or self.workspace
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def run_dirs(self):
        output = self.workspace / 'ppt-output'
        return sorted(p.name for p in output.iterdir() if p.is_dir()) if output.exists() else []

    def test_repeated_continuation_reuses_unapproved_run_without_writes(self):
        root = self.run_fixture(pending_interaction={
            'id': 'brief-approval', 'kind': 'approval', 'stage': 'brief', 'status': 'pending',
            'question': 'Approve?', 'options': ['approve', 'request_revision']})
        before = self.snapshot()
        for _ in range(2):
            result = self.invoke('--source', str(self.source))
            self.assertEqual(result['status'], 'READY')
            self.assertEqual(result['run_dir'], str(root))
            self.assertEqual(result['next_command'], 'audit-run')
            self.assertTrue(result['reused'])
            self.assertFalse(result['created'])
            self.assertEqual(result['mode'], 'guided')
            self.assertEqual(result['writes'], [])
        self.assertEqual(self.run_dirs(), ['existing'])
        self.assertEqual(self.snapshot(), before)

    def test_multiple_candidates_persist_stable_selection_without_candidate_writes(self):
        roots = [self.run_fixture('alpha'), self.run_fixture('beta', mode='auto', legacy=True)]
        before = [self.snapshot(root) for root in roots]
        args = ('--source', str(self.source), '--action', 'revise', '--request', 'Revise S02 only.')
        first = self.invoke(*args)
        self.assertEqual(first['status'], 'CHOICE_REQUIRED')
        route_path = self.workspace / 'ppt-output/run-selection.json'
        saved = route_path.read_bytes()
        route = json.loads(saved)
        self.assertEqual(route['kind'], 'run_selection')
        self.assertEqual(route['schema_version'], 1)
        self.assertEqual(route['entry_action'], 'revise')
        self.assertEqual(route['operation_payload']['request'], 'Revise S02 only.')
        self.assertEqual(route['candidates'], ['alpha', 'beta'])
        self.assertEqual(route['options'], route['candidates'])
        self.assertEqual(set(route['option_effects']), {'alpha', 'beta'})
        self.assertIn(route['recommendation'], route['candidates'])
        self.assertTrue(route['recommendation_reason'])
        second = self.invoke(*args)
        self.assertEqual(second['selection'], first['selection'])
        self.assertEqual(second['writes'], [])
        self.assertEqual(route_path.read_bytes(), saved)
        self.assertEqual([self.snapshot(root) for root in roots], before)
        self.assertEqual(self.run_dirs(), ['alpha', 'beta'])

    def test_zero_candidates_never_creates_on_resume(self):
        before = self.snapshot()
        for _ in range(2):
            result = self.invoke('--source', str(self.source), code=2)
            self.assertEqual(result['errors'][0]['code'], 'run_not_found')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), [])
        self.assertFalse((self.workspace / 'ppt-output').exists())

    def test_failed_legacy_run_is_reused_even_without_source_argument(self):
        root = self.run_fixture('failed', legacy=True, mode='auto', stage='production',
            visual_generation_blocker={'state': 'generator_unavailable', 'status': 'active'},
            active_visual_generation_batch={'schema_version': 2, 'batch_id': 'old'})
        before = self.snapshot()
        for _ in range(2):
            result = self.invoke()
            self.assertEqual(result['run_dir'], str(root))
            self.assertEqual(result['mode'], 'auto')
            self.assertEqual(result['next_command'], 'audit-run')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['failed'])

    def test_answered_selection_replays_actual_answer_and_original_operation(self):
        roots = [self.run_fixture('alpha'), self.run_fixture('beta', mode='auto')]
        before = [self.snapshot(root) for root in roots]
        original = self.invoke('--action', 'revise', '--request', 'Change S02, keep the rest.')
        self.assertEqual(original['status'], 'CHOICE_REQUIRED')
        pending = (self.workspace / 'ppt-output/run-selection.json').read_bytes()
        missing = self.invoke('--run-id', 'beta', code=2)
        self.assertEqual(missing['errors'][0]['code'], 'selection_answer_required')
        self.assertEqual((self.workspace / 'ppt-output/run-selection.json').read_bytes(), pending)
        answered = self.invoke('--run-id', 'beta', '--answer', 'Use the beta variant, please.')
        self.assertEqual(answered['run_dir'], str(roots[1]))
        self.assertEqual(answered['next_command'], 'audit-run')
        self.assertEqual(answered['mode'], 'auto')
        self.assertEqual(answered['entry_action'], 'revise')
        self.assertEqual(answered['operation_payload'], {'request': 'Change S02, keep the rest.'})
        route_path = self.workspace / 'ppt-output/run-selection.json'
        saved = route_path.read_bytes()
        route = json.loads(saved)
        self.assertEqual(route['status'], 'answered')
        self.assertEqual(route['decision'], 'beta')
        self.assertEqual(route['answer'], 'Use the beta variant, please.')
        for args in [(), ('--run-id', 'beta', '--answer', 'Use the beta variant, please.')]:
            replay = self.invoke(*args)
            self.assertEqual(replay['run_dir'], str(roots[1]))
            self.assertEqual(replay['operation_payload'], answered['operation_payload'])
            self.assertEqual(replay['writes'], [])
            self.assertEqual(route_path.read_bytes(), saved)
        self.invoke('--run-id', 'alpha', '--answer', 'Actually alpha.', code=2)
        self.invoke('--request', 'Conflicting operation.', code=2)
        self.assertEqual(route_path.read_bytes(), saved)
        self.assertEqual([self.snapshot(root) for root in roots], before)

    def test_explicit_existing_run_id_disambiguates_legitimate_same_source_variants(self):
        self.run_fixture('alpha')
        beta = self.run_fixture('beta', mode='auto')
        before = self.snapshot()
        chosen = self.invoke('--source', str(self.source), '--run-id', 'beta')
        self.assertEqual(chosen['run_dir'], str(beta))
        self.assertEqual(chosen['next_command'], 'audit-run')
        self.invoke('--run-id', 'missing', code=2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['alpha', 'beta'])

    def test_existing_routing_contract_is_preserved_and_malformed_route_is_not_replaced(self):
        self.run_fixture('quarterly-review')
        target = self.run_fixture('annual-plan')
        fixture = Path(__file__).parent / 'fixtures/workspace-run-selection.json'
        route = json.loads(fixture.read_text(encoding='utf-8'))
        path = self.workspace / 'ppt-output/run-selection.json'
        self.put(path, route)
        before = self.snapshot()
        pending = self.invoke()
        self.assertEqual(pending['selection'], route)
        self.assertEqual(self.snapshot(), before)
        selected = self.invoke('--run-id', 'annual-plan', '--answer', 'Select annual-plan.')
        self.assertEqual(selected['run_dir'], str(target))
        self.assertEqual(selected['operation_payload'], route['operation_payload'])
        del route['operation_payload']
        self.put(path, route)
        before = self.snapshot()
        self.invoke('--run-id', 'annual-plan', '--answer', 'Select annual-plan.', code=2)
        self.assertEqual(self.snapshot(), before)

    def test_new_is_explicit_minimal_and_same_id_replays_without_overwrite(self):
        self.invoke('--action', 'new', '--source', str(self.source), code=2)
        self.assertFalse((self.workspace / 'ppt-output').exists())
        source_bytes = self.source.read_bytes()
        first = self.invoke('--action', 'new', '--run-id', 'deliberate', '--source', str(self.source))
        root = self.workspace / 'ppt-output/deliberate'
        self.assertTrue(first['created'])
        self.assertFalse(first['reused'])
        self.assertEqual(first['run_dir'], str(root))
        self.assertEqual(first['next_command'], 'audit-run')
        run = json.loads((root / '.ppt-pilot/run.json').read_bytes())
        self.assertEqual(run['deck_id'], 'deliberate')
        self.assertEqual(run['mode'], 'guided')
        self.assertEqual(run['stage'], 'brief')
        self.assertEqual(run['manuscript_review']['state'], 'pending')
        self.assertEqual(run['manuscript_review']['review_history'], [])
        self.assertEqual(run['entry_source'], {'source_path': str(self.source),
            'sha256': hashlib.sha256(source_bytes).hexdigest()})
        self.assertNotIn('source_deck', run)
        self.assertEqual(set(self.snapshot(root)), {str(Path('.ppt-pilot/run.json'))})
        before = self.snapshot()
        for args in [('--action', 'new', '--run-id', 'deliberate', '--mode', 'auto'), ()]:
            replay = self.invoke('--source', str(self.source), *args)
            self.assertTrue(replay['reused'])
            self.assertFalse(replay['created'])
            self.assertEqual(replay['mode'], 'guided')
            self.assertEqual(replay['writes'], [])
            self.assertEqual(replay['run_dir'], str(root))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['deliberate'])
        audit = subprocess.run(first['audit_command'], capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)

    def test_new_adopts_existing_source_unless_independent_duplicate_is_explicit(self):
        existing = self.run_fixture('failed', stage='production', visual_generation_blocker={'status': 'active'})
        before = self.snapshot(existing)
        adopted = self.invoke('--action', 'new', '--run-id', 'not-created', '--source', str(self.source))
        self.assertEqual(adopted['run_dir'], str(existing))
        self.assertTrue(adopted['reused'])
        self.assertEqual(self.run_dirs(), ['failed'])
        created = self.invoke('--action', 'new', '--run-id', 'variant', '--source', str(self.source),
                              '--allow-duplicate', '--mode', 'auto')
        self.assertTrue(created['created'])
        self.assertEqual(created['mode'], 'auto')
        for _ in range(2):
            replay = self.invoke('--action', 'new', '--run-id', 'variant', '--source', str(self.source),
                                 '--allow-duplicate')
            self.assertTrue(replay['reused'])
            self.assertEqual(self.run_dirs(), ['failed', 'variant'])
        self.assertEqual(self.snapshot(existing), before)

    def test_new_collision_and_mismatched_identity_never_overwrite_or_add_suffix(self):
        root = self.run_fixture('occupied')
        other = self.workspace / 'different.pptx'
        _deck(other, first_text='Different content')
        inventory = root / '.ppt-pilot/源稿清单.json'
        process = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'ppt_source_intake.py'),
                                  '--source', str(self.source), '--output', str(inventory)],
                                 capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        partial = self.workspace / 'ppt-output/partial'
        partial.mkdir()
        (partial / 'foreign.txt').write_text('Do not adopt or overwrite.', encoding='utf-8')
        before = self.snapshot()
        for _ in range(2):
            mismatch = self.invoke('--action', 'new', '--run-id', 'occupied', '--source', str(other), code=2)
            self.assertEqual(mismatch['errors'][0]['code'], 'source_identity_conflict')
            self.invoke('--action', 'new', '--run-id', 'partial', code=2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['occupied', 'partial'])

    def test_inventory_hash_finds_moved_source_but_never_merges_legitimate_variants(self):
        alpha = self.run_fixture('alpha')
        beta = self.run_fixture('beta')
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        for root in (alpha, beta):
            self.put(root / '.ppt-pilot/源稿清单.json', {'schema_version': 1,
                'kind': 'pptx_source_inventory', 'source': {'sha256': digest}})
        moved = self.workspace / 'moved.pptx'
        self.source.rename(moved)
        before = [self.snapshot(root) for root in (alpha, beta)]
        chosen = self.invoke('--source', str(moved), '--run-id', 'alpha')
        self.assertEqual(chosen['run_dir'], str(alpha))
        ambiguous = self.invoke('--source', str(moved))
        self.assertEqual(ambiguous['status'], 'CHOICE_REQUIRED')
        self.assertEqual(ambiguous['selection']['candidates'], ['alpha', 'beta'])
        self.assertEqual(self.run_dirs(), ['alpha', 'beta'])
        self.assertEqual([self.snapshot(root) for root in (alpha, beta)], before)

    def test_changed_source_hash_requires_choice_not_recreation(self):
        root = self.run_fixture('old-version')
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.put(root / '.ppt-pilot/源稿清单.json', {'schema_version': 1,
            'kind': 'pptx_source_inventory', 'source': {'sha256': digest}})
        _deck(self.source, first_text='Changed source version')
        before = self.snapshot(root)
        result = self.invoke('--source', str(self.source))
        self.assertEqual(result['status'], 'CHOICE_REQUIRED')
        self.assertEqual(result['selection']['candidates'], ['old-version'])
        self.assertNotIn('options', result['selection'])
        path = self.workspace / 'ppt-output/run-selection.json'
        saved = path.read_bytes()
        self.assertEqual(self.invoke('--source', str(self.source))['status'], 'CHOICE_REQUIRED')
        self.assertEqual(path.read_bytes(), saved)
        selected = self.invoke('--run-id', 'old-version', '--answer', 'old-version')
        self.assertEqual(selected['run_dir'], str(root))
        self.assertNotIn('decision', selected['selection'])
        self.assertEqual(self.invoke()['run_dir'], str(root))
        self.assertEqual(self.snapshot(root), before)
        self.assertEqual(self.run_dirs(), ['old-version'])

    def test_new_same_id_changed_bootstrap_source_is_conflict(self):
        self.invoke('--action', 'new', '--run-id', 'one', '--source', str(self.source))
        _deck(self.source, first_text='Changed after bootstrap')
        before = self.snapshot()
        for _ in range(2):
            result = self.invoke('--action', 'new', '--run-id', 'one', '--source', str(self.source), code=2)
            self.assertEqual(result['errors'][0]['code'], 'source_identity_conflict')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['one'])

    def test_source_path_is_canonical_and_unknown_binding_requires_choice(self):
        root = self.run_fixture('one', source=False)
        before = self.snapshot(root)
        result = self.invoke('--source', './source.pptx')
        self.assertEqual(result['status'], 'CHOICE_REQUIRED')
        self.assertEqual(result['selection']['operation_payload']['source']['source_path'], str(self.source))
        self.assertEqual(result['selection']['candidates'], ['one'])
        self.assertEqual(self.snapshot(root), before)
        self.assertEqual(self.run_dirs(), ['one'])

    def test_external_answered_route_replay_is_byte_identical(self):
        self.run_fixture('quarterly-review')
        target = self.run_fixture('annual-plan')
        fixture = Path(__file__).parent / 'fixtures/workspace-run-selection.json'
        route = json.loads(fixture.read_text(encoding='utf-8'))
        route.update(status='answered', answer='Use annual-plan please.', decision='annual-plan')
        self.put(self.workspace / 'ppt-output/run-selection.json', route)
        before = self.snapshot()
        result = self.invoke()
        self.assertEqual(result['run_dir'], str(target))
        self.assertEqual(result['writes'], [])
        self.assertEqual(self.snapshot(), before)

    def test_saved_source_payload_is_validated_before_replaying_a_choice(self):
        self.run_fixture('alpha')
        self.run_fixture('beta')
        route = self.invoke('--source', str(self.source))['selection']
        path = self.workspace / 'ppt-output/run-selection.json'
        unsafe = json.loads(json.dumps(route))
        unsafe['operation_payload']['source']['source_path'] = r'\\server\share\private.pptx'
        self.put(path, unsafe)
        before = self.snapshot()
        self.invoke('--run-id', 'beta', '--answer', 'beta', code=2)
        self.assertEqual(self.snapshot(), before)
        self.put(path, route)
        _deck(self.source, first_text='Changed while awaiting selection')
        before = self.snapshot()
        self.invoke('--run-id', 'beta', '--answer', 'beta', code=2)
        self.assertEqual(self.snapshot(), before)

    def test_open_selection_requires_exact_answer_and_rejects_fake_finite_options(self):
        for run_id in ('a', 'b', 'c', 'd', 'e'):
            self.run_fixture(run_id)
        route = self.invoke()['selection']
        self.assertNotIn('options', route)
        path = self.workspace / 'ppt-output/run-selection.json'
        saved = path.read_bytes()
        self.invoke('--run-id', 'c', '--answer', 'Maybe c?', code=2)
        self.assertEqual(path.read_bytes(), saved)
        bad = dict(route, options=['a', 'b'])
        self.put(path, bad)
        before = self.snapshot()
        self.invoke(code=2)
        self.assertEqual(self.snapshot(), before)
        self.put(path, route)
        result = self.invoke('--run-id', 'c', '--answer', 'c')
        self.assertEqual(result['run_id'], 'c')
        self.assertNotIn('decision', result['selection'])
        self.assertEqual(self.invoke()['run_id'], 'c')

    def test_repeated_ambiguous_new_intent_reuses_the_same_selection(self):
        self.run_fixture('alpha')
        self.run_fixture('beta')
        args = ('--action', 'new', '--run-id', 'proposed', '--source', str(self.source),
                '--request', 'Continue redesigning this source.')
        first = self.invoke(*args)
        saved = (self.workspace / 'ppt-output/run-selection.json').read_bytes()
        second = self.invoke(*args)
        self.assertEqual(second['selection'], first['selection'])
        self.assertEqual((self.workspace / 'ppt-output/run-selection.json').read_bytes(), saved)
        self.assertEqual(self.run_dirs(), ['alpha', 'beta'])
        result = self.invoke('--run-id', 'beta', '--answer', 'Use beta.')
        self.assertEqual(result['entry_action'], 'resume')
        self.assertEqual(result['next_command'], 'audit-run')
        self.assertEqual(result['operation_payload']['request'], 'Continue redesigning this source.')

    def test_input_validation_prevents_unrelated_writes(self):
        self.run_fixture('one')
        sentinel = self.workspace / 'unrelated.txt'
        sentinel.write_text('Keep this file unchanged.', encoding='utf-8')
        before = self.snapshot()
        bad_ids = ('../escape', 'a/b', 'a\\b', 'x:ads', '.', '..', '', 'CON', 'com1', 'a?', 'a\n')
        for value in bad_ids:
            with self.subTest(run_id=repr(value)):
                self.invoke('--action', 'new', '--run-id', value, code=2)
        bad_sources = (r'\\server\share\a.pptx', r'\\?\C:\a.pptx', r'\\.\NUL',
            'file:///tmp/a.pptx', 'https://example.invalid/a.pptx', str(self.source) + ':ads',
            str(self.workspace), str(self.source) + '\n', 'NUL', '', '/??/C:/a.pptx')
        for value in bad_sources:
            with self.subTest(source=repr(value)):
                self.invoke('--action', 'new', '--run-id', 'never-created', '--source', value, code=2)
        for args in [('--allow-duplicate',), ('--mode', 'auto'), ('--answer', 'one'), ('--request', '  ')]:
            self.invoke(*args, code=2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['one'])

    def test_links_are_rejected_without_touching_targets(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        secret = outside / 'source.pptx'
        secret.write_bytes(self.source.read_bytes())
        link = self.workspace / 'linked.pptx'
        try:
            link.symlink_to(secret)
        except (OSError, NotImplementedError):
            self.skipTest('OS does not permit creating symlinks')
        before = self.snapshot(outside)
        self.invoke('--source', str(link), code=2)
        self.assertFalse((self.workspace / 'ppt-output').exists())
        output = self.workspace / 'ppt-output'
        output.symlink_to(outside, target_is_directory=True)
        self.invoke('--action', 'new', '--run-id', 'never-created', code=2)
        self.assertEqual(self.snapshot(outside), before)
        output.unlink()
        root = self.run_fixture('one')
        run = root / '.ppt-pilot/run.json'
        external_run = outside / 'run.json'
        external_run.write_bytes(run.read_bytes())
        run.unlink()
        run.symlink_to(external_run)
        before = self.snapshot(outside)
        self.invoke('--run-id', 'one', code=2)
        self.assertEqual(self.snapshot(outside), before)
        self.assertEqual(self.run_dirs(), ['one'])

    def test_concurrent_new_same_source_never_creates_two_runs(self):
        processes = [subprocess.Popen(self.command('--action', 'new', '--run-id', run_id,
            '--source', str(self.source)), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8') for run_id in ('first', 'second', 'first')]
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(stderr, '')
            result = json.loads(stdout)
            results.append(result)
            if process.returncode:
                self.assertEqual(process.returncode, 2, stdout)
                self.assertEqual(result['errors'][0]['code'], 'runtime_busy')
            else:
                self.assertEqual(result['status'], 'READY')
        self.assertEqual(sum(result['created'] for result in results), 1)
        self.assertEqual(len(self.run_dirs()), 1)
        before = self.snapshot()
        result = self.invoke('--source', str(self.source))
        self.assertTrue(result['reused'])
        self.assertEqual(self.snapshot(), before)

    def test_workspace_lock_busy_has_zero_side_effects(self):
        from _run_store import RunStore
        before = self.snapshot()
        with RunStore(self.workspace).lock():
            result = self.invoke('--action', 'new', '--run-id', 'one', code=2)
        self.assertEqual(result['errors'][0]['code'], 'runtime_busy')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows reparse-point coverage')
    def test_windows_junctions_are_rejected_even_without_symlink_privilege(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (outside / 'sentinel.txt').write_text('unchanged', encoding='utf-8')
        output = self.workspace / 'ppt-output'
        command = subprocess.run(['cmd', '/c', 'mklink', '/J', str(output), str(outside)],
                                 capture_output=True, timeout=20)
        self.assertEqual(command.returncode, 0, command.stderr)
        before = self.snapshot(outside)
        self.invoke('--action', 'new', '--run-id', 'one', code=2)
        self.invoke('--run-id', 'one', code=2)
        self.invoke('--workspace', str(output / '..'), '--action', 'new', '--run-id', 'one', code=2)
        self.assertEqual(self.snapshot(outside), before)
        output.rmdir()  # Remove only the fixture junction, never its target.
        root = self.run_fixture('one')
        internal = root / '.ppt-pilot'
        (internal / 'run.json').unlink()
        internal.rmdir()
        command = subprocess.run(['cmd', '/c', 'mklink', '/J', str(internal), str(outside)],
                                 capture_output=True, timeout=20)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.invoke('--source', str(self.source), code=2)
        self.assertEqual(self.snapshot(outside), before)
        internal.rmdir()

    def test_foreign_and_split_brain_runs_are_not_repaired_or_used_for_new_suffixes(self):
        root = self.run_fixture('one')
        raw = (root / '.ppt-pilot/run.json').read_bytes()
        for value in [b'{"schema_version":1,"schema_version":1}', b'[]', b'{invalid']:
            (root / '.ppt-pilot/run.json').write_bytes(value)
            before = self.snapshot()
            self.invoke('--source', str(self.source), code=2)
            self.invoke('--action', 'new', '--run-id', 'other', '--source', str(self.source), code=2)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.run_dirs(), ['one'])
        (root / '.ppt-pilot/run.json').write_bytes(raw)
        (root / 'run.json').write_bytes(raw)
        before = self.snapshot()
        self.invoke('--run-id', 'one', code=2)
        self.assertEqual(self.snapshot(), before)

    def test_source_inventory_cannot_escape_the_candidate_run(self):
        root = self.run_fixture('one')
        path = root / '.ppt-pilot/run.json'
        run = json.loads(path.read_bytes())
        run['source_deck']['inventory'] = '../unrelated.json'
        self.put(path, run)
        self.put(self.workspace / 'unrelated.json', {'secret': 'not a source inventory'})
        before = self.snapshot()
        self.invoke('--source', str(self.source), code=2)
        self.invoke('--action', 'new', '--run-id', 'other', '--source', str(self.source), code=2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['one'])

    def test_explicit_new_without_source_creates_an_independent_topic_run(self):
        existing = self.run_fixture('old-topic', source=False)
        before = self.snapshot(existing)
        created = self.invoke('--action', 'new', '--run-id', 'new-topic', '--request', 'A different presentation.')
        self.assertTrue(created['created'])
        self.assertEqual(created['run_id'], 'new-topic')
        self.assertEqual(created['next_command'], 'audit-run')
        for _ in range(2):
            replay = self.invoke('--action', 'new', '--run-id', 'new-topic')
            self.assertTrue(replay['reused'])
            self.assertEqual(replay['run_id'], 'new-topic')
        self.assertEqual(self.snapshot(existing), before)
        self.assertEqual(self.run_dirs(), ['new-topic', 'old-topic'])

    def test_selected_source_is_rechecked_after_the_run_lock(self):
        root = self.run_fixture('one', source=False, entry_source={
            'source_path': str(self.source), 'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()})
        other = self.workspace / 'other.pptx'
        _deck(other, first_text='A different source')
        path = root / '.ppt-pilot/run.json'
        changed = json.loads(path.read_bytes())
        changed['entry_source'] = {'source_path': str(other), 'sha256': hashlib.sha256(other.read_bytes()).hexdigest()}
        changed_bytes = json.dumps(changed).encode('utf-8')
        fault = (f'target = Path({str(path)!r})\nreplacement = {changed_bytes!r}\n'
            'original_stat = Path.stat\nreads = 0\n'
            'def racing_stat(path, *args, **kwargs):\n'
            '    global reads\n    observed = original_stat(path, *args, **kwargs)\n'
            '    if path == target and not args and not kwargs:\n'
            '        reads += 1\n'
            '        if reads == 2:\n'
            '            target.write_bytes(replacement)\n'
            '    return observed\n'
            'Path.stat = racing_stat\n')
        result = self.invoke('--run-id', 'one', '--source', str(self.source), code=2, os_fault=fault)
        self.assertEqual(result['errors'][0]['code'], 'source_identity_conflict')
        self.assertEqual(result['writes'], [])
        self.assertEqual(path.read_bytes(), changed_bytes)
        self.assertEqual(self.run_dirs(), ['one'])

    def test_publish_failure_reports_partial_root_and_never_recreates_on_retry(self):
        fault = ('def denied_replace(source, target):\n'
                 '    raise PermissionError("injected filesystem publish failure")\n'
                 'os.replace = denied_replace\n')
        result = self.invoke('--action', 'new', '--run-id', 'one', '--source', str(self.source),
                             code=2, os_fault=fault)
        root = self.workspace / 'ppt-output/one'
        self.assertEqual(result.get('run_dir'), str(root))
        self.assertTrue(result.get('partial_creation'))
        self.assertFalse(result['created'])
        self.assertIn('ppt-output/one', result['directories_created'])
        self.assertEqual(result['writes'], [])
        self.assertFalse((root / '.ppt-pilot/run.json').exists())
        before = self.snapshot()
        for _ in range(2):
            self.invoke('--action', 'new', '--run-id', 'one', '--source', str(self.source), code=2)
            self.invoke('--source', str(self.source), code=2)
            self.assertEqual(self.run_dirs(), ['one'])
        self.assertEqual(self.snapshot(), before)

    def test_postpublish_verification_failure_reports_actual_write_and_preserves_failure(self):
        fault = ('original_replace = os.replace\n'
                 'def corrupt_replace(source, target):\n'
                 '    original_replace(source, target)\n'
                 '    Path(target).write_bytes(b"injected post-publish corruption")\n'
                 'os.replace = corrupt_replace\n')
        result = self.invoke('--action', 'new', '--run-id', 'one', '--source', str(self.source),
                             code=2, os_fault=fault)
        root = self.workspace / 'ppt-output/one'
        self.assertEqual(result['errors'][0]['code'], 'write_verification_failed')
        self.assertEqual(result.get('run_dir'), str(root))
        self.assertTrue(result.get('partial_creation'))
        self.assertTrue(result['created'])
        self.assertEqual(result['writes'], ['ppt-output/one/.ppt-pilot/run.json'])
        self.assertEqual((root / '.ppt-pilot/run.json').read_bytes(), b'injected post-publish corruption')
        before = self.snapshot()
        for _ in range(2):
            self.invoke('--action', 'new', '--run-id', 'one', code=2)
            self.invoke('--source', str(self.source), code=2)
        self.assertEqual(self.run_dirs(), ['one'])
        self.assertEqual(self.snapshot(), before)

    @unittest.skipUnless(os.name == 'nt', 'Windows 8.3 path aliases')
    def test_short_workspace_alias_cannot_bypass_the_long_path_lock(self):
        import ctypes
        from _run_store import RunStore
        long = self.workspace.with_name('workspace with a long directory name')
        self.workspace.rename(long)
        self.workspace = long
        self.source = long / 'source.pptx'
        get_short = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
        get_short.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
        get_short.restype = ctypes.c_uint
        size = get_short(str(long), None, 0)
        if not size:
            self.skipTest('8.3 aliases unavailable on this fixture volume')
        buffer = ctypes.create_unicode_buffer(size)
        self.assertTrue(get_short(str(long), buffer, size))
        short = Path(buffer.value)
        if os.path.normcase(str(short)) == os.path.normcase(str(long)):
            self.skipTest('Fixture volume does not generate distinct 8.3 aliases')
        self.assertTrue(short.samefile(long))
        before = self.snapshot()
        with RunStore(long).lock():
            for workspace in (long, short):
                blocked = self.invoke('--workspace', str(workspace), '--action', 'new', '--run-id', 'one', code=2)
                self.assertEqual(blocked['errors'][0]['code'], 'runtime_busy')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), [])
        created = self.invoke('--workspace', str(short), '--action', 'new', '--run-id', 'one',
                              '--source', str(short / 'source.pptx'))
        self.assertEqual(created['run_dir'], str(long / 'ppt-output/one'))
        self.assertEqual(created['operation_payload']['source']['source_path'], str(self.source))
        before = self.snapshot()
        replay = self.invoke('--workspace', str(short), '--source', str(self.source))
        self.assertTrue(replay['reused'])
        self.assertEqual(replay['run_dir'], created['run_dir'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['one'])

    def test_resolved_nonlocal_paths_are_rejected_before_further_filesystem_io(self):
        before = self.snapshot()
        paths = [r'\\server\share\workspace', r'\\?\C:\workspace']
        if os.name == 'nt':
            paths.append(r'Z:\workspace')
        for remote in paths:
            fault = (f'target = Path({str(self.workspace)!r})\nremote = Path({remote!r})\n'
                'if os.name == "nt":\n'
                '    import ctypes\n    original_kernel = ctypes.WinDLL\n'
                '    def mapped_kernel(*args, **kwargs):\n'
                '        kernel = original_kernel(*args, **kwargs)\n'
                '        kernel.GetDriveTypeW = lambda drive: 4 if str(drive).lower().startswith("z:") else 3\n'
                '        return kernel\n'
                '    ctypes.WinDLL = mapped_kernel\n'
                'original_resolve = Path.resolve\noriginal_lstat = Path.lstat\n'
                'def redirected_resolve(path, *args, **kwargs):\n'
                '    return remote if path == target else original_resolve(path, *args, **kwargs)\n'
                'def guarded_lstat(path, *args, **kwargs):\n'
                '    if str(path).replace(chr(92), "/").startswith("//") or str(path).lower().startswith("z:"):\n'
                '        raise ValueError("nonlocal_filesystem_probe")\n'
                '    return original_lstat(path, *args, **kwargs)\n'
                'Path.resolve = redirected_resolve\nPath.lstat = guarded_lstat\n')
            result = self.invoke('--action', 'new', '--run-id', 'one', code=2, os_fault=fault)
            self.assertEqual(result['errors'][0]['code'], 'unsafe_entry_path')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows mapped drive policy')
    def test_mapped_network_drive_is_rejected_before_local_path_probes(self):
        fault = ('import ctypes\noriginal_kernel = ctypes.WinDLL\n'
            'def remote_kernel(*args, **kwargs):\n'
            '    kernel = original_kernel(*args, **kwargs)\n'
            '    kernel.GetDriveTypeW = lambda drive: 4\n'
            '    return kernel\n'
            'ctypes.WinDLL = remote_kernel\n'
            f'target = Path({str(self.workspace)!r})\noriginal_lstat = Path.lstat\n'
            'def guarded_lstat(path, *args, **kwargs):\n'
            '    if path == target:\n'
            '        raise ValueError("nonlocal_filesystem_probe")\n'
            '    return original_lstat(path, *args, **kwargs)\n'
            'Path.lstat = guarded_lstat\n')
        before = self.snapshot()
        result = self.invoke('--action', 'new', '--run-id', 'one', code=2, os_fault=fault)
        self.assertEqual(result['errors'][0]['code'], 'unsafe_entry_path')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), [])

    def test_answered_selection_does_not_depend_on_unselected_run_survival(self):
        alpha = self.run_fixture('alpha')
        beta = self.run_fixture('beta', mode='auto')
        self.invoke('--source', str(self.source), '--request', 'Continue the selected deck.')
        answered = self.invoke('--run-id', 'beta', '--answer', 'Use beta, please.')
        alpha.rename(Path(self.temp.name) / 'archived-alpha')
        before = self.snapshot()
        for args in [(), ('--run-id', 'beta', '--answer', 'Use beta, please.')]:
            replay = self.invoke(*args)
            self.assertEqual(replay['status'], 'READY')
            self.assertEqual(replay['run_dir'], str(beta))
            self.assertEqual(replay['next_command'], 'audit-run')
            self.assertEqual(replay['selection'], answered['selection'])
            self.assertEqual(replay['operation_payload'], answered['operation_payload'])
            self.assertEqual(replay['writes'], [])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.run_dirs(), ['beta'])

    @unittest.skipUnless(os.name == 'nt', 'Windows source alias compatibility')
    def test_saved_short_source_alias_replays_without_rewriting_original_payload(self):
        import ctypes
        long = self.workspace / 'source with a long filename.pptx'
        self.source.rename(long)
        self.source = long
        get_short = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
        get_short.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
        get_short.restype = ctypes.c_uint
        size = get_short(str(long), None, 0)
        if not size:
            self.skipTest('8.3 aliases unavailable on this fixture volume')
        buffer = ctypes.create_unicode_buffer(size)
        self.assertTrue(get_short(str(long), buffer, size))
        short = buffer.value
        if os.path.normcase(short) == os.path.normcase(str(long)):
            self.skipTest('Fixture volume does not generate distinct 8.3 aliases')
        self.assertTrue(Path(short).samefile(long))
        self.run_fixture('alpha')
        beta = self.run_fixture('beta')
        route = self.invoke('--source', str(long))['selection']
        route['operation_payload']['source']['source_path'] = short
        path = self.workspace / 'ppt-output/run-selection.json'
        self.put(path, route)
        before = self.snapshot()
        self.assertEqual(self.invoke()['selection'], route)
        self.assertEqual(self.snapshot(), before)
        result = self.invoke('--source', str(long), '--run-id', 'beta', '--answer', 'Use beta.')
        self.assertEqual(result['run_dir'], str(beta))
        self.assertEqual(result['operation_payload'], route['operation_payload'])
        saved = path.read_bytes()
        for args in [(), ('--source', short), ('--source', str(long))]:
            replay = self.invoke(*args)
            self.assertEqual(replay['run_dir'], str(beta))
            self.assertEqual(replay['writes'], [])
            self.assertEqual(path.read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
