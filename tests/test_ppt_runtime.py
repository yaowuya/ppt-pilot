"""Real facade/store integration, without a model or Office dependency."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import shutil
from unittest import mock

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(SCRIPTS))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'test'
        self.scripts = SCRIPTS
        (self.root / '.ppt-pilot/runtime-inputs').mkdir(parents=True)
        self.put('.ppt-pilot/run.json', {'schema_version': 1, 'deck_id': 'test',
                 'mode': 'auto', 'stage': 'production', 'dirty_slides': ['S01'],
                 'manuscript_review': {}})

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def invoke(self, command, *args):
        result = subprocess.run([sys.executable, '-B', str(self.scripts / 'ppt_runtime.py'),
                                 command, '--run-dir', str(self.root), *args],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertIn(result.returncode, (0, 2), result.stderr)
        return result, json.loads(result.stdout)

    def document(self, name, value):
        (self.root / name).write_text('# Canonical owner\n\n```ppt-pilot-json\n' +
                                     json.dumps(value, ensure_ascii=False) + '\n```\n', encoding='utf-8')

    def prepared_fixture(self, host='claude-code', slide_count=1, style_id='jiawei-product'):
        from _run_store import sha, canonical
        from _runtime_owners import Owners
        import _prompt_runtime
        self.install = Path(self.temp.name) / '.claude'
        for skill in ('ppt-start', 'ppt-style-extract'):
            shutil.copytree(SCRIPTS.parents[1] / skill, self.install / 'skills' / skill,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (self.install / 'agents').mkdir()
        shutil.copyfile(SCRIPTS.parents[2] / 'hosts/claude-code/agents/ppt-svg-generator.md',
                        self.install / 'agents/ppt-svg-generator.md')
        self.scripts = self.install / 'skills/ppt-start/scripts'
        outline_id = 'sha256:' + '1' * 64
        storyboard_id = 'sha256:' + '2' * 64
        self.document('大纲.md', {'outline_snapshot_id': outline_id, 'argument_framework': '金字塔原理',
            'opening_framework': 'none', 'sequence_template': '总-分-总', 'narrative_id': 'narrative-1',
            'narrative_choice_reason': 'Single decision', 'narrative_step1_bullets': '- 金字塔原理：结论先行\n- 精确表达：保留事实\n- 层级执行：突出重点\n'})
        slide = {'slide_id': 'S01', 'role': 'single-assertion', 'assertion_title': 'Hello',
            'audience_takeaway': 'Hello', 'source_ids': [], 'forbidden_claims': [],
            'content_blocks': [{'block_id': 'S01-B1', 'display_copy': 'Hello', 'priority': 'core',
                'reading_order': 1, 'claim_id': 'none', 'source_ids': [], 'qualifiers': [], 'metric': 'none'}],
            'visual_intent': 'Clear message', 'layout_family': 'single-assertion', 'density_budget': 'low',
            'previous_link': 'START', 'next_link': 'END'}
        slides = []
        for number in range(1, slide_count + 1):
            item = json.loads(json.dumps(slide))
            item.update(slide_id=f'S{number:02d}', previous_link='START' if number == 1 else f'S{number-1:02d}',
                        next_link='END' if number == slide_count else f'S{number+1:02d}')
            item['content_blocks'][0]['block_id'] = item['slide_id'] + '-B1'
            slides.append(item)
        slide_ids = [item['slide_id'] for item in slides]
        self.document('.ppt-pilot/故事板.md', {'outline_snapshot_id': outline_id,
            'storyboard_snapshot_id': storyboard_id, 'applied_visual_revision_ids': [], 'slides': slides})
        for name in ('简报', '研究', '来源'):
            (self.root / '.ppt-pilot' / (name + '.md')).write_text('# ' + name + '\n', encoding='utf-8')
        files = ['.ppt-pilot/简报.md', '.ppt-pilot/研究.md', '.ppt-pilot/来源.md', '大纲.md', '.ppt-pilot/故事板.md']
        latest = {'cycle': 1, 'round': 1, 'verdict': 'PASS', 'review_mode': 'inline_fallback', 'findings': [],
            'fallback_evidence': {'delegation_attempted': True, 'reason': 'delegation_capability_unavailable', 'host_detail': 'hermetic test'},
            'reviewed_file_snapshot': {'snapshot_id': 'review-1', 'files': files,
                'file_hashes': {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in files}}}
        self.document('.ppt-pilot/文稿审查.md', latest)
        self.run = {'schema_version': 1, 'deck_id': 'test', 'mode': 'auto', 'stage': 'production', 'dirty_slides': slide_ids,
            'manuscript_review': {'required': True, 'cycle': 1, 'round': 1, 'mode': 'inline_fallback',
                'state': 'manuscript_approved', 'status': 'PASSED', 'latest_report': '文稿审查.md',
                'open_blocking_findings': [], 'review_history': [latest]}}
        self.put('.ppt-pilot/run.json', self.run)
        style = json.loads((self.scripts.parent / 'assets/styles' / style_id / 'manifest.json').read_text(encoding='utf-8'))
        self.style = style
        self.put('.ppt-pilot/theme.json', {'selected_style_id': style_id, 'selected_style_display_name': style['display_name'],
            'style_kind': 'style_pack', 'style_manifest_version': style['version']})
        (self.root / '.ppt-pilot/samples').mkdir()
        sample = b'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>Anchor</title><desc>Fixture</desc></svg>'
        (self.root / '.ppt-pilot/samples/S01.svg').write_bytes(sample)
        self.run['anchor'] = {'status': 'validated', 'files': {'.ppt-pilot/samples/S01.svg': hashlib.sha256(sample).hexdigest()},
            'style_sha256': hashlib.sha256((self.root / '.ppt-pilot/theme.json').read_bytes()).hexdigest(), 'review_snapshot_id': 'review-1'}
        self.put('.ppt-pilot/run.json', self.run)
        from _run_store import RunStore
        owners = Owners(RunStore(self.root), self.run)
        self.request = {'schema_version': 1, 'kind': 'prepare_visual_generation_batch', 'expected_snapshots': owners.snapshots,
            'ordered_slide_ids': slide_ids, 'generation_operations': [{'slide_id': sid, 'generation_intent': 'initial_generation',
                'generation_trigger_id': 'initial:' + sid + ':' + storyboard_id} for sid in slide_ids]}
        self.request['request_id'] = sha(canonical(self.request).rstrip(b'\n'))
        self.request['expected_run_sha256'] = sha((self.root / '.ppt-pilot/run.json').read_bytes())
        self.put('.ppt-pilot/runtime-inputs/request.json', self.request)
        registry = next((entry for entry in json.loads(
            (SCRIPTS.parent / 'assets/host-adapters.json').read_text())['adapters']
            if entry['host'] == host), None)
        self.assertIsNotNone(registry, f'missing registered host adapter: {host}')
        if host == 'deepseek-harness':
            # No host config is installed or read by this compatibility route.
            environment = mock.patch.dict(os.environ, {'DSH_HOME': str(Path(self.temp.name) / 'absent-dsh-home')})
            environment.start()
            self.addCleanup(environment.stop)
            evidence = {
                'tool_name': 'subagent', 'instruction_sha256': registry['adapter_digest'],
                'spawn_primitive': 'fresh-context-subagent', 'tool_policy': 'inherited-not-isolated',
                'ambient_context': ['deployment_system_prompt', 'agent_preset', 'workspace_instructions'],
                'result_type': 'text', 'attribution_type': 'subagent_id',
                'session_id': 'hermetic-test-not-host-acceptance'}
            worker_capacity = 5
        else:
            evidence = {
                'agent_name': 'ppt-svg-generator', 'loaded_agent_sha256': registry['adapter_digest'],
                'spawn_primitive': 'fresh-context-subagent', 'allowed_tools': ['TodoWrite'],
                'ambient_context': ['CLAUDE.md', 'parent_git_status'], 'isolation': 'omitted',
                'result_type': 'text', 'session_id': 'hermetic-test-not-host-acceptance'}
            worker_capacity = 5
        self.capability = dict(registry, schema_version=1, kind='host_capability', observation={
            'native_fresh_isolation': True, 'remote_fresh_isolation': False, 'concurrent_tasks': True,
            'durable_lookup': True, 'worker_capacity': worker_capacity, 'prompt_by_value': True,
            'fresh_history': True, 'filesystem_none': host != 'deepseek-harness',
            'data_tools_none': host != 'deepseek-harness', 'attribution': True,
            'nested_cli_required': False, 'credential_probe_required': False,
            'current_context_only': False}, evidence=evidence)
        self.put('.ppt-pilot/runtime-inputs/cap.json', self.capability)
        if hasattr(self, 'prior_final'):
            (self.root / 'slides').mkdir(exist_ok=True)
            (self.root / 'slides/S01.svg').write_bytes(self.prior_final)
        result, prepared = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                      '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, prepared)
        self.batch = prepared['result']['batch_id']
        self.manifest_name = '.ppt-pilot/visual-generation-batches/' + self.batch + '.json'
        manifest = json.loads((self.root / self.manifest_name).read_text())
        self.txname = manifest['transaction_refs'][0]
        self.txid = self.tx()['transaction_id']
        return prepared

    def tx(self):
        return json.loads((self.root / self.txname).read_text())

    def reserve(self):
        result, body = self.invoke('reserve-dispatch', '--batch-id', self.batch, '--slide-id', 'S01',
            '--transaction-id', self.txid, '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.dispatch = body['result']['dispatch']['dispatch_id']
        return body

    def bind(self):
        result, body = self.invoke('bind-task', '--dispatch-id', self.dispatch, '--host-task-id', 'fixture-task')
        self.assertEqual(result.returncode, 0, body)
        return body

    def candidate(self):
        response = '```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><title>Hello</title><desc>One message</desc><g data-block-id="S01-B1"><text data-role="body" x="100" y="120" font-size="24" font-family="Arial" fill="#111111"><tspan x="100" y="120">Hello</tspan></text></g></svg>\n```\n'
        response = response.replace('One message', getattr(self, 'candidate_description', 'One message'))
        (self.root / '.ppt-pilot/runtime-inputs/response.txt').write_text(response, encoding='utf-8')
        result, body = self.invoke('ingest-result', '--dispatch-id', self.dispatch, '--response', '.ppt-pilot/runtime-inputs/response.txt')
        self.assertEqual(result.returncode, 0, body)
        return body

    def validate(self):
        from _generation_runtime import V2_VALIDATION_CHECKS
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01', 'transaction_id': self.txid,
            'candidate_sha256': self.tx()['candidate_sha256'], 'checks': {k: 'passed' for k in V2_VALIDATION_CHECKS},
            'defect_id': None, 'failure_reason': None}
        self.put('.ppt-pilot/runtime-inputs/qa.json', qa)
        result, body = self.invoke('record-validation', '--slide-id', 'S01', '--transaction-id', self.txid,
                                  '--input', '.ppt-pilot/runtime-inputs/qa.json')
        self.assertEqual(result.returncode, 0, body)
        return body

    def test_real_lifecycle_and_replays(self):
        self.prepared_fixture()
        result, body = self.invoke('dispatch-plan', '--batch-id', self.batch, '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(len(body['result']['items']), 1)
        self.assertEqual(body['writes'], [])
        self.assertTrue(self.reserve()['result']['spawn_authorized'])
        self.assertFalse(self.reserve()['result']['spawn_authorized'])
        self.bind()
        self.assertEqual(self.bind()['writes'], [])
        self.candidate()
        self.assertEqual(self.candidate()['writes'], [])
        self.validate()
        self.assertEqual(self.validate()['writes'], [])
        from _run_store import sha
        expected = sha((self.root / self.manifest_name).read_bytes())
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, body)
        self.assertTrue((self.root / 'slides/S01.svg').exists())
        result, replay = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, replay)
        self.assertEqual(replay['writes'], [])
        result, resumed = self.invoke('resume')
        self.assertEqual(result.returncode, 0, resumed)
        self.assertEqual(resumed['writes'], [])

    def test_prepare_replay_ignores_only_changed_run_cas(self):
        self.prepared_fixture()
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['writes'], [])
        self.request['expected_snapshots']['storyboard_snapshot_id'] = 'sha256:' + 'a' * 64
        self.put('.ppt-pilot/runtime-inputs/request.json', self.request)
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['writes'], [])

    def test_pointer_last_interruption_only_replays_pointer(self):
        self.prepared_fixture()
        self.put('.ppt-pilot/run.json', self.run)
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertTrue(body['result']['pointer_missing'])
        self.assertEqual(body['writes'], [])
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['writes'], ['.ppt-pilot/run.json'])

    def test_repaired_blocker_pointer_replay_restores_dispatch(self):
        self.prepared_fixture('deepseek-harness')
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.put('.ppt-pilot/run.json', self.run)
        self.put('.ppt-pilot/runtime-inputs/cap.json', dict(self.capability, host='unsupported'))
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(body['errors'][0]['code'], 'generator_unavailable')
        run_path = self.root / '.ppt-pilot/run.json'
        blocked_run = run_path.read_bytes()
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.put('.ppt-pilot/runtime-inputs/request.json', body['result']['prepare_request'])
        self.put('.ppt-pilot/runtime-inputs/cap.json', self.capability)
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        # Crash boundary: graph is durable, but the final run replacement was lost.
        run_path.write_bytes(blocked_run)
        result, body = self.invoke('resume')
        self.assertTrue(body['result']['pointer_missing'])
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['writes'], ['.ppt-pilot/run.json'])
        self.assertNotIn('visual_generation_blocker', json.loads(run_path.read_text(encoding='utf-8')))
        self.assertTrue(self.reserve()['result']['spawn_authorized'])

    def test_reserved_before_spawn_never_reselected(self):
        self.prepared_fixture()
        self.reserve()
        result, body = self.invoke('dispatch-plan', '--batch-id', self.batch, '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['items'], [])
        result, body = self.invoke('resume')
        self.assertEqual(body['result']['next_command'], 'durable_lookup')
        self.assertEqual(body['writes'], [])
        self.bind()
        result, body = self.invoke('bind-task', '--dispatch-id', self.dispatch, '--host-task-id', 'different-task')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['writes'], [])

    def test_crash_after_bound_owner_before_transaction_can_rebind(self):
        self.prepared_fixture()
        reservation = self.reserve()['result']['dispatch']
        from _runtime_commands import dispatch_path
        reservation.update(state='bound', host_task_id='fixture-task')
        self.put(dispatch_path(self.tx()), reservation)
        self.bind()
        self.assertEqual(self.tx()['state'], 'generating')
        self.assertEqual(self.tx()['generation_attempt'], 1)
        self.assertEqual(self.bind()['writes'], [])

    def test_changed_reviewed_bytes_block_dispatch(self):
        self.prepared_fixture()
        with (self.root / '.ppt-pilot/研究.md').open('a', encoding='utf-8') as file:
            file.write('Changed fact')
        result, body = self.invoke('dispatch-plan', '--batch-id', self.batch, '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'manuscript_stale')
        self.assertEqual(body['writes'], [])

    def test_forged_installed_agent_blocks_reservation(self):
        self.prepared_fixture()
        (self.install / 'agents/ppt-svg-generator.md').write_text('tools: Read', encoding='utf-8')
        result, body = self.invoke('reserve-dispatch', '--batch-id', self.batch, '--slide-id', 'S01',
            '--transaction-id', self.txid, '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'generator_unavailable')
        self.assertEqual(self.tx()['failure_reason'], 'generator_unavailable')
        self.assertFalse((self.root / '.ppt-pilot/visual-generation-dispatches').exists())

    def test_deepseek_native_subagent_lifecycle_without_host_config(self):
        self.prepared_fixture('deepseek-harness')
        result, planned = self.invoke('dispatch-plan', '--batch-id', self.batch,
                                     '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, planned)
        task = planned['result']['items'][0]
        self.assertTrue(task['fresh_history'])
        self.assertEqual(task['filesystem'], 'host-inherited')
        self.assertEqual(task['data_tools'], 'host-inherited')
        self.assertTrue(self.reserve()['result']['spawn_authorized'])
        self.assertFalse(self.reserve()['result']['spawn_authorized'])
        self.bind()
        self.candidate()
        self.assertEqual(self.candidate()['writes'], [])
        self.validate()
        from _run_store import sha
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256',
                                  sha((self.root / self.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 0, body)
        self.assertTrue((self.root / 'slides/S01.svg').is_file())

    def test_fixed_brand_title_uses_verified_style_size_at_ingest(self):
        self.prepared_fixture('deepseek-harness', style_id='jiawei-product')
        self.reserve()
        self.bind()
        response = ('```xml\n<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<title>Hello</title><desc>One message</desc><g data-block-id="S01-B1">'
            '<text data-role="title" x="120" y="140" font-size="36" font-family="Microsoft YaHei" fill="#000000">'
            '<tspan x="120" y="140">Hello</tspan></text></g></svg>\n```\n')
        (self.root / '.ppt-pilot/runtime-inputs/response.txt').write_text(response, encoding='utf-8')
        result, body = self.invoke('ingest-result', '--dispatch-id', self.dispatch,
                                  '--response', '.ppt-pilot/runtime-inputs/response.txt')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(self.tx()['state'], 'candidate_written')
        self.assertIn(b'font-size="36"', (self.root / self.tx()['candidate_path']).read_bytes())

    def test_changed_style_tokens_during_owner_load_fail_as_snapshot_conflict(self):
        self.prepared_fixture('deepseek-harness', style_id='jiawei-product')
        from _runtime_owners import Owners
        from _run_store import RunStore
        import _prompt_runtime as prompt
        original = prompt._read_regular_asset
        for mutation in ('role', 'malformed_json', 'huge_title', 'layout_type'):
            reads = 0

            def change_second_read(path, **kwargs):
                nonlocal reads
                raw = original(path, **kwargs)
                if path.name == 'tokens.json':
                    reads += 1
                    if reads == 2:
                        if mutation == 'malformed_json':
                            return b'{broken'
                        data = json.loads(raw)
                        if mutation == 'role':
                            data['prompt_role'] = 'unregistered'
                        elif mutation == 'huge_title':
                            data['typography']['page_title'] = 10 ** 400
                        else:
                            data['composition']['layout_family'] = []
                            data['prompt_baseline']['composition_rules']['layout_family'] = []
                        return json.dumps(data).encode('utf-8')
                return raw

            with self.subTest(mutation=mutation), mock.patch.object(prompt, '_read_regular_asset', side_effect=change_second_read):
                try:
                    Owners(RunStore(self.root), self.run)
                except Exception as error:
                    self.assertIsInstance(error, ValueError)
                    self.assertEqual(str(error), 'prompt_snapshot_conflict')
                else:
                    self.fail('Changed style tokens were accepted')

    def test_deepseek_native_parallel_reservations_and_capacity(self):
        self.prepared_fixture('deepseek-harness', slide_count=3)
        for capacity, expected in ((None, 1), (0, 0), (2, 2), (5, 3)):
            self.capability['observation']['worker_capacity'] = capacity
            self.put('.ppt-pilot/runtime-inputs/cap.json', self.capability)
            result, body = self.invoke('dispatch-plan', '--batch-id', self.batch,
                                      '--capability', '.ppt-pilot/runtime-inputs/cap.json')
            self.assertEqual(result.returncode, 0, body)
            self.assertEqual(len(body['result']['items']), expected)
        self.reserve()
        result, resumed = self.invoke('resume')
        self.assertEqual(resumed['result']['next_command'], 'durable_lookup')
        self.assertEqual(resumed['result']['reservations'][0]['dispatch_id'], self.dispatch)
        self.bind()
        result, body = self.invoke('dispatch-plan', '--batch-id', self.batch,
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual([item['slide_id'] for item in body['result']['items']], ['S02', 'S03'])
        self.assertEqual(body['result']['reservations'][0]['host_task_id'], 'fixture-task')

    def test_deepseek_native_rejects_false_isolation_and_wrong_tool(self):
        self.prepared_fixture('deepseek-harness')
        from _host_adapter_runtime import validate_capability
        cases = [('observation', 'filesystem_none', True), ('observation', 'data_tools_none', True),
                 ('observation', 'fresh_history', False), ('observation', 'current_context_only', True),
                 ('evidence', 'tool_name', 'subagent_fork'), ('evidence', 'tool_name', 'ppt_svg_generator'),
                 ('evidence', 'attribution_type', 'background_job_id'), ('evidence', 'session_id', '')]
        for section, key, value in cases:
            receipt = json.loads(json.dumps(self.capability))
            receipt[section][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'generator_unavailable'):
                validate_capability(receipt)

    def test_deepseek_native_rejects_tampered_plugin_instructions(self):
        self.prepared_fixture('deepseek-harness')
        instruction = self.scripts.parent / 'references/deepseek-harness.md'
        self.assertTrue(instruction.is_file())
        instruction.write_text('Tampered adapter policy', encoding='utf-8')
        result, body = self.invoke('reserve-dispatch', '--batch-id', self.batch,
            '--slide-id', 'S01', '--transaction-id', self.txid,
            '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'generator_unavailable')
        self.assertEqual(body['errors'][0]['details']['reason'], 'instruction_digest_mismatch')
        self.assertFalse((self.root / '.ppt-pilot/visual-generation-dispatches').exists())

    def test_deepseek_prepare_records_only_canonical_blocker(self):
        self.prepared_fixture()
        # Start another clean run with the same frozen manuscript, no generation owners.
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.put('.ppt-pilot/run.json', self.run)
        self.capability['host'] = 'deepseek'
        self.put('.ppt-pilot/runtime-inputs/cap.json', self.capability)
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json',
                                  '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'generator_unavailable')
        self.assertEqual(body['errors'][0].get('details', {}).get('reason'), 'adapter_not_registered')
        self.assertNotIn('canonical owner conflict', body['errors'][0]['next_action'])
        self.assertEqual(body['writes'], ['.ppt-pilot/run.json'])
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['visual_generation_blocker']['state'], 'generator_unavailable')
        self.assertFalse((self.root / '.ppt-pilot/visual-generation-batches').exists())
        result, resumed = self.invoke('resume')
        self.assertEqual(result.returncode, 0, resumed)
        self.assertEqual(resumed['result']['next_command'], 'prepare-batch')
        self.assertEqual(resumed['result']['prepare_request']['ordered_slide_ids'], ['S01'])
        self.assertTrue(resumed['result'].get('capability_refresh_required'))
        self.assertEqual(resumed['writes'], [])
        self.assertIn('visual_generation_blocker', json.loads(
            (self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8')))

    def test_malformed_response_records_failure_without_candidate(self):
        self.prepared_fixture()
        self.reserve()
        self.bind()
        (self.root / '.ppt-pilot/runtime-inputs/bad.txt').write_text('not SVG', encoding='utf-8')
        result, body = self.invoke('ingest-result', '--dispatch-id', self.dispatch, '--response', '.ppt-pilot/runtime-inputs/bad.txt')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.tx()['failure_reason'], 'generator_output_malformed')
        self.assertFalse((self.root / self.tx()['candidate_path']).exists())
        self.assertFalse((self.root / 'slides/S01.svg').exists())

    def test_actual_candidate_write_crash_never_adopts_orphan(self):
        self.prepared_fixture()
        self.reserve()
        self.bind()
        # Obtain valid text, then reset its committed tx to generating and remove candidate.
        self.candidate()
        tx = self.tx()
        (self.root / tx['candidate_path']).unlink()
        tx.update(state='generating', candidate_sha256=None)
        self.put(self.txname, tx)
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        runtime = Runtime(self.root)
        original = runtime.store.write_json
        def crash(name, value, expected):
            if name == self.txname:
                raise OSError('injected crash after candidate replace')
            return original(name, value, expected)
        with mock.patch.object(runtime.store, 'write_json', side_effect=crash):
            with self.assertRaises(OSError):
                runtime.execute(parser().parse_args(['ingest-result', '--run-dir', str(self.root),
                    '--dispatch-id', self.dispatch, '--response', '.ppt-pilot/runtime-inputs/response.txt']))
        self.assertTrue((self.root / tx['candidate_path']).exists())
        self.assertIsNone(self.tx()['candidate_sha256'])
        result, body = self.invoke('resume')
        self.assertEqual(body['errors'][0]['code'], 'orphan_candidate')
        self.assertEqual(body['writes'], [])

    def test_actual_promotion_crash_replays_final_cas(self):
        self.prepared_fixture()
        self.reserve()
        self.bind()
        self.candidate()
        self.validate()
        from _runtime_commands import Runtime
        from _run_store import sha
        from ppt_runtime import parser
        expected = sha((self.root / self.manifest_name).read_bytes())
        runtime = Runtime(self.root)
        with mock.patch.object(runtime.store, 'write_json', side_effect=OSError('after final CAS')):
            with self.assertRaises(OSError):
                runtime.execute(parser().parse_args(['promote', '--run-dir', str(self.root),
                    '--batch-id', self.batch, '--expected-manifest-sha256', expected]))
        self.assertTrue((self.root / 'slides/S01.svg').exists())
        self.assertEqual(self.tx()['state'], 'validated')
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, body)
        self.assertNotIn('slides/S01.svg', body['writes'])

    def test_final_conflict_and_stale_qa_preserve_bytes(self):
        self.prepared_fixture()
        self.reserve()
        self.bind()
        self.candidate()
        self.validate()
        final = self.root / 'slides/S01.svg'
        final.write_text('third party', encoding='utf-8')
        from _run_store import sha
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', sha((self.root / self.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'final_promotion_conflict')
        self.assertEqual(body['writes'], [])
        self.assertEqual(final.read_text(), 'third party')
        qa = json.loads((self.root / '.ppt-pilot/runtime-inputs/qa.json').read_text())
        qa['candidate_sha256'] = 'sha256:' + '9' * 64
        self.put('.ppt-pilot/runtime-inputs/qa.json', qa)
        result, body = self.invoke('record-validation', '--slide-id', 'S01', '--transaction-id', self.txid,
                                  '--input', '.ppt-pilot/runtime-inputs/qa.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'stale_validation')
        self.assertEqual(body['writes'], [])

    def test_transport_retry_limit_records_pending_blocker(self):
        self.prepared_fixture()
        for attempt in range(3):
            self.reserve()
            self.bind()
            result, body = self.invoke('record-generator-failure', '--dispatch-id', self.dispatch, '--reason', 'generator_timeout')
            self.assertEqual(result.returncode, 0, body)
            result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'retry')
            self.assertEqual(result.returncode, 2 if attempt == 2 else 0, body)
        self.assertEqual(self.tx()['generation_attempt'], 3)
        self.assertEqual(body['errors'][0]['code'], 'generation_attempts_exhausted')
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        self.assertEqual(run['pending_interaction']['kind'], 'blocker')

    def test_anchor_publication_keeps_finals_private(self):
        self.prepared_fixture()
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['stage'] = 'anchor'
        run.pop('anchor', None)
        (self.root / '.ppt-pilot/samples/S01.svg').unlink()
        self.put('.ppt-pilot/run.json', run)
        self.reserve()
        self.bind()
        self.candidate()
        self.validate()
        from _run_store import sha
        expected = sha((self.root / self.manifest_name).read_bytes())
        result, body = self.invoke('publish-anchors', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, body)
        self.assertTrue((self.root / '.ppt-pilot/samples/S01.svg').exists())
        self.assertFalse((self.root / 'slides/S01.svg').exists())
        self.assertEqual(self.tx()['state'], 'validated')
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['writes'], [])

    def test_store_cas_conflict_and_readonly_lock(self):
        from _run_store import RunStore, sha
        store = RunStore(self.root)
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*'))
        raw = (self.root / '.ppt-pilot/run.json').read_bytes()
        with store.lock():
            with self.assertRaisesRegex(ValueError, 'visual_generation_state_conflict'):
                store.write_bytes('.ppt-pilot/run.json', b'changed', 'sha256:' + '0'*64)
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), raw)
        self.assertEqual(before, sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*')))
        self.assertEqual(store.writes, [])

    def test_resume_can_supply_request_without_host_hash_glue(self):
        self.prepared_fixture()
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.put('.ppt-pilot/run.json', self.run)
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['prepare_request'], self.request)
        self.assertEqual(body['writes'], [])

    def test_explicit_migration_and_readonly_resume(self):
        self.prepared_fixture()
        from _generation_runtime import V1_TRANSACTION_FIELDS
        legacy = {k: v for k, v in self.tx().items() if k in V1_TRANSACTION_FIELDS}
        for name in ('visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.run['visual_generation_transaction'] = legacy
        self.put('.ppt-pilot/run.json', self.run)
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'migrate-v1')
        self.assertEqual(body['writes'], [])
        result, body = self.invoke('migrate-v1')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['generator_calls'], 0)
        result, body = self.invoke('migrate-v1')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['writes'], [])
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)

    def test_missing_fallback_evidence_never_invents_patch_attempts(self):
        self.prepared_fixture()
        self.reserve()
        self.bind()
        self.invoke('record-generator-failure', '--dispatch-id', self.dispatch, '--reason', 'generator_timeout')
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'fallback')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['writes'], [])

    def test_fallback_consumes_bound_prior_patch_defects(self):
        self.prepared_fixture()
        self.reserve()
        self.bind()
        self.candidate()
        from _generation_runtime import V2_VALIDATION_CHECKS
        qa = {'schema_version': 1, 'kind': 'visual_generation_qa', 'slide_id': 'S01', 'transaction_id': self.txid,
            'candidate_sha256': self.tx()['candidate_sha256'], 'checks': {k: 'failed' if k == 'visual' else 'passed' for k in V2_VALIDATION_CHECKS},
            'defect_id': 'contrast-1', 'failure_reason': 'visual_qa_failed'}
        self.put('.ppt-pilot/runtime-inputs/qa.json', qa)
        result, body = self.invoke('record-validation', '--slide-id', 'S01', '--transaction-id', self.txid, '--input', '.ppt-pilot/runtime-inputs/qa.json')
        self.assertEqual(result.returncode, 0, body)
        qa.update(fix_attempts_for_candidate=2, patch_defects=[{'defect_id': 'contrast-1', 'outcome': 'failed'}, {'defect_id': 'contrast-2', 'outcome': 'failed'}])
        self.document('.ppt-pilot/质量检查报告.md', {'schema_version': 1, 'kind': 'runtime_qa', 'records': [qa]})
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'fallback')
        self.assertEqual(result.returncode, 0, body)
        self.assertNotEqual(body['result']['transaction_id'], self.txid)
        self.assertEqual(self.tx()['state'], 'failed')
        self.assertIn('single-column or two-column fallback', body['result']['prompt_by_value'])

    def test_recompose_uses_reviewed_materialized_revision(self):
        self.prepared_fixture()
        self.reserve()
        self.bind()
        self.invoke('record-generator-failure', '--dispatch-id', self.dispatch, '--reason', 'generator_timeout')
        from _runtime_owners import markdown_owner
        board = markdown_owner((self.root / '.ppt-pilot/故事板.md').read_bytes())
        board['slides'][0]['layout_family'] = 'single-column'
        board['applied_visual_revision_ids'] = ['visual-revision-1']
        board['storyboard_snapshot_id'] = 'sha256:' + '8' * 64
        self.document('.ppt-pilot/故事板.md', board)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['interaction_history'] = {'visual-revision-1': {'id': 'visual-revision-1', 'kind': 'visual_revision',
            'stage': 'production', 'affected_scope': ['S01'], 'status': 'applied', 'artifact_owner': '.ppt-pilot/故事板.md',
            'supersedes': [], 'normalized_changes': {'layout_family': 'single-column'}}}
        latest = run['manuscript_review']['review_history'][-1]
        latest['reviewed_file_snapshot']['file_hashes']['.ppt-pilot/故事板.md'] = hashlib.sha256((self.root / '.ppt-pilot/故事板.md').read_bytes()).hexdigest()
        self.document('.ppt-pilot/文稿审查.md', latest)
        self.put('.ppt-pilot/run.json', run)
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 0, body)
        self.assertNotEqual(body['result']['transaction_id'], self.txid)
        self.assertIn('single-column', body['result']['prompt_by_value'])

    def test_readonly_store_rejects_symlink_if_platform_permits(self):
        from _run_store import RunStore
        target = self.root / '.ppt-pilot/runtime-inputs/real.json'
        target.write_text('{}')
        link = self.root / '.ppt-pilot/runtime-inputs/link.json'
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest('Windows symlink privilege unavailable')
        with self.assertRaisesRegex(ValueError, 'unsafe_evidence_path'):
            RunStore(self.root).read_json('.ppt-pilot/runtime-inputs/link.json')

    def prepared_source_fixture(self):
        self.prepared_fixture()
        from test_source_workflow_gate import Fixture
        source_root = Path(self.temp.name) / 'source-fixture'
        source_root.mkdir()
        source = Fixture(source_root)
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.run['stage'] = 'anchor'
        self.run['source_deck'] = source.run['source_deck']
        source.inventory['slide_count'] = 1
        source.inventory['slides'] = source.inventory['slides'][:1]
        source.mapping['slides'] = source.mapping['slides'][:1]
        self.put('.ppt-pilot/源稿清单.json', source.inventory)
        self.put('.ppt-pilot/源页映射.json', source.mapping)
        hashes = lambda name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        evidence = source.evidence
        evidence['mapping_sha256'] = hashes('.ppt-pilot/源页映射.json')
        evidence['target_slide_ids'] = ['S01']
        evidence['source_audit'].update(inventory_sha256=hashes('.ppt-pilot/源稿清单.json'),
            reviewed_slide_ids=['SRC-S001'], visual_checked_slide_ids=[])
        latest = self.run['manuscript_review']['review_history'][-1]
        evidence['manuscript'] = {'files': latest['reviewed_file_snapshot']['file_hashes'],
            'report': {'path': '.ppt-pilot/文稿审查.md', 'sha256': hashes('.ppt-pilot/文稿审查.md')}, 'review_snapshot_id': 'review-1'}
        evidence['style'] = {'files': {'.ppt-pilot/theme.json': hashes('.ppt-pilot/theme.json')},
            'selected_style_id': self.style['id'], 'style_manifest_version': self.style['version']}
        evidence.pop('anchor')
        evidence.pop('qa')
        self.put('.ppt-pilot/导入检查点.json', evidence)
        self.put('.ppt-pilot/run.json', self.run)
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.put('.ppt-pilot/runtime-inputs/request.json', body['result']['prepare_request'])
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json', '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 0, body)
        self.batch = body['result']['batch_id']
        self.manifest_name = '.ppt-pilot/visual-generation-batches/' + self.batch + '.json'
        self.txname = json.loads((self.root / self.manifest_name).read_text())['transaction_refs'][0]
        self.txid = self.tx()['transaction_id']
        return source, evidence

    def test_source_fixture_anchor_entry_and_stale_source(self):
        source, _ = self.prepared_source_fixture()
        source.source.write_bytes(b'changed external source')
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['writes'], [])

    def anchor_reentry_fixture(self, source=False):
        from _run_store import anchor_snapshot_id, sha
        self.prior_final = b'<svg xmlns="http://www.w3.org/2000/svg"><title>Prior final</title></svg>'
        evidence = self.prepared_source_fixture()[1] if source else None
        if not source:
            self.prepared_fixture()
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        prior = dict(run['anchor'])
        prior.update(status='approved', approval_interaction_id='prior-anchor',
                     artifact_snapshot_id=anchor_snapshot_id(prior))
        run['stage'] = 'anchor'
        run['interaction_history'] = {'prior-anchor': {'kind': 'approval', 'checkpoint': 'anchor',
            'approval_attempt': 1, 'decision': 'approve', 'status': 'applied',
            'artifact_snapshot_id': prior['artifact_snapshot_id']}}
        if source:
            evidence['anchor'] = prior
            self.put('.ppt-pilot/导入检查点.json', evidence)
            run.pop('anchor')
        else:
            run['anchor'] = prior
        self.put('.ppt-pilot/run.json', run)
        self.reserve(); self.bind(); self.candidate(); self.validate()
        expected = sha((self.root / self.manifest_name).read_bytes())
        return run, evidence, prior, expected

    def check_anchor_replacement(self, source):
        from _workflow_gate import MANUSCRIPT_FILES
        from _runtime_owners import markdown_owner
        run, evidence, prior, expected = self.anchor_reentry_fixture(source)
        before_run = (self.root / '.ppt-pilot/run.json').read_bytes()
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'publish-anchors')
        self.assertEqual(body['writes'], [])
        result, body = self.invoke('publish-anchors', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, body)
        published = body['result']['anchor_evidence']
        self.assertNotEqual(published['artifact_snapshot_id'], prior['artifact_snapshot_id'])
        self.assertEqual((self.root / '.ppt-pilot/samples/S01.svg').read_bytes(),
                         (self.root / self.tx()['candidate_path']).read_bytes())
        self.assertEqual((self.root / 'slides/S01.svg').read_bytes(), self.prior_final)
        self.assertEqual((self.root / '.ppt-pilot/run.json').read_bytes(), before_run)
        result, replay = self.invoke('publish-anchors', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, replay)
        self.assertEqual(replay['writes'], [])
        self.assertEqual(replay['result']['anchor_evidence'], published)
        run.update(mode='guided', stage='production')
        # Bind the new published evidence but retain the actual old decision.
        published.update(status='approved', approval_interaction_id='prior-anchor')
        run['interaction_history']['outline'] = {'kind': 'approval', 'checkpoint': 'outline',
            'status': 'applied', 'decision': 'approve', 'approval_attempt': 1,
            'artifact_snapshot_id': 'sha256:' + '1' * 64}
        if source:
            evidence['anchor'] = published
            evidence['approvals'] = {}
            for stage, filename in (('brief', MANUSCRIPT_FILES[0]), ('outline', MANUSCRIPT_FILES[3])):
                snapshot = markdown_owner((self.root / filename).read_bytes()).get('outline_snapshot_id') if stage == 'outline' else stage
                run['interaction_history'][stage] = {'kind': 'approval', 'checkpoint': stage,
                    'status': 'applied', 'decision': 'approve', 'approval_attempt': 1, 'artifact_snapshot_id': snapshot}
                evidence['approvals'][stage] = {'interaction_id': stage, 'artifact_snapshot_id': snapshot,
                    'artifact_sha256': hashlib.sha256((self.root / filename).read_bytes()).hexdigest()}
            self.put('.ppt-pilot/导入检查点.json', evidence)
        else:
            run['anchor'] = published
        self.put('.ppt-pilot/run.json', run)
        result, blocked = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 2, blocked)
        self.assertEqual(blocked['errors'][0]['code'], 'approval_stale' if source else 'approval_missing')
        self.assertEqual(blocked['writes'], [])
        self.assertEqual((self.root / 'slides/S01.svg').read_bytes(), self.prior_final)
        run['interaction_history']['new-anchor'] = dict(run['interaction_history']['prior-anchor'],
            approval_attempt=2, artifact_snapshot_id=published['artifact_snapshot_id'])
        published['approval_interaction_id'] = 'new-anchor'
        self.put('.ppt-pilot/run.json', run)
        if source:
            self.put('.ppt-pilot/导入检查点.json', evidence)
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, body)

    def test_final_anchor_replaces_owned_ordinary_sample_requires_new_approval(self):
        self.check_anchor_replacement(False)

    def test_final_anchor_replaces_owned_source_sample_requires_new_approval(self):
        self.check_anchor_replacement(True)

    def check_anchor_conflicts(self, source):
        run, evidence, prior, expected = self.anchor_reentry_fixture(source)
        sample = self.root / '.ppt-pilot/samples/S01.svg'
        for ownership in ('changed', 'unknown'):
            with self.subTest(ownership=ownership):
                sample.write_bytes(b'<svg xmlns="http://www.w3.org/2000/svg"><title>Third party</title></svg>')
                if ownership == 'unknown':
                    if source:
                        evidence.pop('anchor')
                        self.put('.ppt-pilot/导入检查点.json', evidence)
                    else:
                        run.pop('anchor')
                        self.put('.ppt-pilot/run.json', run)
                before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
                result, body = self.invoke('publish-anchors', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
                self.assertEqual(result.returncode, 2, body)
                self.assertEqual(body['errors'][0]['code'], 'anchor_sample_conflict')
                self.assertEqual(body['writes'], [])
                self.assertEqual({str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)

    def test_final_anchor_preserves_ordinary_third_party_samples(self):
        self.check_anchor_conflicts(False)

    def test_final_anchor_preserves_source_third_party_samples(self):
        self.check_anchor_conflicts(True)

    def test_final_anchor_owned_sample_cas_rejects_change_before_write(self):
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        _, _, _, expected = self.anchor_reentry_fixture()
        sample = self.root / '.ppt-pilot/samples/S01.svg'
        runtime = Runtime(self.root)
        original = runtime.store.write_bytes
        def changed(name, data, observed):
            if name == '.ppt-pilot/samples/S01.svg':
                sample.write_bytes(b'third-party-race')
            return original(name, data, observed)
        with mock.patch.object(runtime.store, 'write_bytes', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'visual_generation_state_conflict'):
                runtime.execute(parser().parse_args(['publish-anchors', '--run-dir', str(self.root),
                    '--batch-id', self.batch, '--expected-manifest-sha256', expected]))
        self.assertEqual(sample.read_bytes(), b'third-party-race')
        self.assertEqual(runtime.store.writes, [])
        self.assertEqual((self.root / 'slides/S01.svg').read_bytes(), self.prior_final)

    def test_source_guided_accepts_published_anchor_evidence(self):
        from _workflow_gate import check_run, MANUSCRIPT_FILES
        from _run_store import sha
        _, evidence = self.prepared_source_fixture()
        (self.root / '.ppt-pilot/samples/S01.svg').unlink()
        self.reserve()
        self.bind()
        self.candidate()
        self.validate()
        expected = sha((self.root / self.manifest_name).read_bytes())
        result, body = self.invoke('publish-anchors', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, body)
        evidence['anchor'] = body['result']['anchor_evidence']
        evidence['anchor'].update(status='approved', approval_interaction_id='anchor-approval')
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['mode'] = 'guided'
        run['stage'] = 'production'
        run['interaction_history'] = {'anchor-approval': {'kind': 'approval', 'checkpoint': 'anchor',
            'status': 'applied', 'decision': 'approve', 'approval_attempt': 1,
            'artifact_snapshot_id': evidence['anchor']['artifact_snapshot_id']}}
        evidence['approvals'] = {}
        for stage, filename in (('brief', MANUSCRIPT_FILES[0]), ('outline', MANUSCRIPT_FILES[3])):
            from _runtime_owners import markdown_owner
            snapshot_id = markdown_owner((self.root / filename).read_bytes()).get('outline_snapshot_id') if stage == 'outline' else stage
            run['interaction_history'][stage] = {'kind': 'approval', 'checkpoint': stage,
                'status': 'applied', 'decision': 'approve', 'approval_attempt': 1, 'artifact_snapshot_id': snapshot_id}
            evidence['approvals'][stage] = {'interaction_id': stage, 'artifact_snapshot_id': snapshot_id,
                'artifact_sha256': hashlib.sha256((self.root / filename).read_bytes()).hexdigest()}
        self.put('.ppt-pilot/run.json', run)
        self.put('.ppt-pilot/导入检查点.json', evidence)
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', expected)
        self.assertEqual(result.returncode, 0, body)
        checked = check_run(self.root, 'production')
        self.assertEqual(checked['status'], 'PASS', checked)
        sample = self.root / '.ppt-pilot/samples/S01.svg'
        sample.write_bytes(sample.read_bytes().replace(b'One message', b'Changed sample'))
        evidence['anchor']['files']['.ppt-pilot/samples/S01.svg'] = hashlib.sha256(sample.read_bytes()).hexdigest()
        self.put('.ppt-pilot/导入检查点.json', evidence)
        checked = check_run(self.root, 'production')
        self.assertEqual(checked['status'], 'BLOCKED', checked)
        self.assertEqual(checked['errors'][0]['code'], 'approval_stale', checked)

    def test_prompt_write_failure_records_failed_canonical_transaction(self):
        self.prepared_fixture()
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.put('.ppt-pilot/run.json', self.run)
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        runtime = Runtime(self.root)
        original = runtime.store.write_bytes
        def fail_prompt(name, data, expected):
            if name.startswith('.ppt-pilot/generation-prompts/'):
                raise OSError('synthetic prompt storage failure')
            return original(name, data, expected)
        with mock.patch('_runtime_commands.validate_capability', return_value=self.capability), mock.patch.object(runtime.store, 'write_bytes', side_effect=fail_prompt):
            with self.assertRaisesRegex(ValueError, 'prompt_write_failed'):
                runtime.execute(parser().parse_args(['prepare-batch', '--run-dir', str(self.root),
                    '--input', '.ppt-pilot/runtime-inputs/request.json', '--capability', '.ppt-pilot/runtime-inputs/cap.json']))
        self.assertEqual(self.tx()['failure_reason'], 'prompt_write_failed')
        self.assertFalse((self.root / self.manifest_name).exists())

    def test_closed_style_and_prompt_preflight_blockers(self):
        self.prepared_fixture()
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.put('.ppt-pilot/run.json', self.run)
        pack = self.install / 'skills/ppt-start/assets/styles' / self.style['id']
        for filename, broken, reason, state in (
            ('tokens.json', '{bad', 'style_asset_malformed', 'style_assets_unavailable'),
            ('STYLE.md', 'invalid guidance', 'style_asset_malformed', 'style_assets_unavailable'),
            ('prompt.md', 'invalid template', 'prompt_template_invalid', 'generation_prompt_unavailable')):
            with self.subTest(filename=filename):
                original = (pack / filename).read_bytes()
                (pack / filename).write_text(broken, encoding='utf-8')
                result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json', '--capability', '.ppt-pilot/runtime-inputs/cap.json')
                self.assertEqual(result.returncode, 2, body)
                self.assertEqual(body['errors'][0]['code'], reason, body)
                self.assertEqual(body['writes'], ['.ppt-pilot/run.json'])
                run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
                self.assertEqual(run['visual_generation_blocker']['state'], state)
                self.assertEqual(run['visual_generation_blocker']['resource'], 'assets/styles/' + self.style['id'] + '/' + filename)
                self.assertFalse((self.root / '.ppt-pilot/visual-generation-transactions').exists())
                (pack / filename).write_bytes(original)
                self.put('.ppt-pilot/run.json', self.run)
        (pack / 'tokens.json').unlink()
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json', '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(body['errors'][0]['code'], 'style_asset_target_invalid', body)
        self.assertEqual(body['writes'], ['.ppt-pilot/run.json'])

    def test_missing_canonical_identity_does_not_create_blocker(self):
        self.prepared_fixture()
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.put('.ppt-pilot/run.json', self.run)
        self.put('.ppt-pilot/theme.json', {'selected_style_id': '../unsafe'})
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json', '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['writes'], [])
        self.assertNotIn('visual_generation_blocker', json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8')))

    def apply_revision(self, number=1):
        from _runtime_owners import markdown_owner
        board = markdown_owner((self.root / '.ppt-pilot/故事板.md').read_bytes())
        value = 'single-column' if number % 2 else 'two-column'
        board['slides'][0]['layout_family'] = value
        revision = 'visual-revision-' + str(number)
        board['applied_visual_revision_ids'] = ['visual-revision-' + str(n) for n in range(1, number + 1)]
        board['storyboard_snapshot_id'] = 'sha256:' + str(number + 3) * 64
        self.document('.ppt-pilot/故事板.md', board)
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run.setdefault('interaction_history', {})[revision] = {'id': revision, 'kind': 'visual_revision',
            'stage': 'production', 'affected_scope': ['S01'], 'status': 'applied', 'artifact_owner': '.ppt-pilot/故事板.md',
            'supersedes': ['visual-revision-' + str(number-1) + ':layout_family'] if number > 1 else [],
            'normalized_changes': {'layout_family': value}}
        latest = run['manuscript_review']['review_history'][-1]
        latest['reviewed_file_snapshot']['file_hashes']['.ppt-pilot/故事板.md'] = hashlib.sha256((self.root / '.ppt-pilot/故事板.md').read_bytes()).hexdigest()
        self.document('.ppt-pilot/文稿审查.md', latest)
        self.put('.ppt-pilot/run.json', run)

    def finish_batch(self):
        self.reserve()
        self.bind()
        self.candidate()
        self.validate()
        from _run_store import sha
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', sha((self.root / self.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 0, body)

    def test_review_fallback_cannot_enter_prepare_directly(self):
        self.prepared_fixture()
        for name in ('generation-prompts', 'visual-generation-transactions', 'visual-generation-batches'):
            shutil.rmtree(self.root / '.ppt-pilot' / name)
        self.put('.ppt-pilot/run.json', self.run)
        from _run_store import canonical, sha
        request = self.request
        request['generation_operations'][0].update(generation_intent='deterministic_fallback', generation_trigger_id='fallback:S01:' + 'a'*64 + ':2')
        request['request_id'] = sha(canonical({k: v for k, v in request.items() if k not in ('request_id', 'expected_run_sha256')}).rstrip(b'\n'))
        self.put('.ppt-pilot/runtime-inputs/request.json', request)
        result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json', '--capability', '.ppt-pilot/runtime-inputs/cap.json')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])
        self.assertFalse((self.root / '.ppt-pilot/visual-generation-transactions').exists())

    def test_review_anchor_resume_before_and_after_publication(self):
        self.prepared_fixture()
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run.update(stage='anchor')
        run.pop('anchor')
        self.put('.ppt-pilot/run.json', run)
        (self.root / '.ppt-pilot/samples/S01.svg').unlink()
        self.reserve(); self.bind(); self.candidate(); self.validate()
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'publish-anchors')
        from _run_store import sha
        result, body = self.invoke('publish-anchors', '--batch-id', self.batch, '--expected-manifest-sha256', sha((self.root / self.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 0, body)
        result, body = self.invoke('resume')
        self.assertEqual(body['result']['next_command'], 'anchor_review')
        self.assertEqual(body['writes'], [])

    def test_review_guided_anchor_digest_rejects_rebound_old_approval(self):
        self.prepared_fixture()
        self.reserve(); self.bind(); self.candidate(); self.validate()
        from _run_store import sha, canonical
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['mode'] = 'guided'
        old_evidence = {k: run['anchor'][k] for k in ('files', 'style_sha256', 'review_snapshot_id')}
        old_id = sha(canonical(old_evidence).rstrip(b'\n'))
        run['interaction_history'] = {'outline-approval': {'kind': 'approval', 'checkpoint': 'outline', 'approval_attempt': 1,
            'artifact_snapshot_id': 'sha256:' + '1'*64, 'decision': 'approve', 'status': 'applied'},
            'anchor-approval': {'kind': 'approval', 'checkpoint': 'anchor', 'approval_attempt': 1,
                'artifact_snapshot_id': old_id, 'decision': 'approve', 'status': 'applied'}}
        sample = self.root / '.ppt-pilot/samples/S01.svg'
        sample.write_bytes(sample.read_bytes().replace(b'Anchor', b'Replaced'))
        run['anchor'].update(status='approved', approval_interaction_id='anchor-approval', artifact_snapshot_id=old_id)
        run['anchor']['files']['.ppt-pilot/samples/S01.svg'] = hashlib.sha256(sample.read_bytes()).hexdigest()
        self.put('.ppt-pilot/run.json', run)
        result, body = self.invoke('promote', '--batch-id', self.batch, '--expected-manifest-sha256', sha((self.root / self.manifest_name).read_bytes()))
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])
        self.assertFalse((self.root / 'slides/S01.svg').exists())

    def test_review_completed_slides_accept_two_new_revisions(self):
        self.prepared_fixture()
        self.finish_batch()
        for revision in (1, 2):
            self.apply_revision(revision)
            result, body = self.invoke('resume')
            self.assertEqual(result.returncode, 0, body)
            self.assertEqual(body['result']['next_command'], 'prepare-batch')
            request = body['result']['prepare_request']
            self.assertEqual(request['generation_operations'][0]['generation_trigger_id'], 'interaction:visual-revision-' + str(revision))
            self.put('.ppt-pilot/runtime-inputs/request.json', request)
            result, body = self.invoke('prepare-batch', '--input', '.ppt-pilot/runtime-inputs/request.json', '--capability', '.ppt-pilot/runtime-inputs/cap.json')
            self.assertEqual(result.returncode, 0, body)
            self.batch = body['result']['batch_id']
            self.manifest_name = '.ppt-pilot/visual-generation-batches/' + self.batch + '.json'
            self.txname = json.loads((self.root / self.manifest_name).read_text())['transaction_refs'][0]
            self.txid = self.tx()['transaction_id']
            self.candidate_description = 'Reviewed revision ' + str(revision)
            self.finish_batch()
            result, body = self.invoke('resume')
            self.assertEqual(result.returncode, 0, body)
            self.assertEqual(body['result']['next_command'], 'stage_scan')

    def interrupted_recovery(self, boundary):
        self.prepared_fixture()
        self.reserve(); self.bind()
        self.invoke('record-generator-failure', '--dispatch-id', self.dispatch, '--reason', 'generator_timeout')
        self.apply_revision()
        from _runtime_commands import Runtime
        from ppt_runtime import parser
        runtime = Runtime(self.root)
        original = runtime.store.write_json
        def crash(name, value, expected):
            should_fail = (boundary == 'journal' and '/visual-generation-recoveries/' in name or
                           boundary == 'prompt' and '/visual-generation-transactions/' in name or
                           boundary == 'transaction' and name == self.manifest_name)
            if should_fail:
                raise OSError('injected recovery crash after ' + boundary)
            result = original(name, value, expected)
            if boundary == 'journal-published' and '/visual-generation-recoveries/' in name:
                raise OSError('injected crash after journal publication')
            return result
        with mock.patch.object(runtime.store, 'write_json', side_effect=crash):
            with self.assertRaises(OSError):
                runtime.execute(parser().parse_args(['prepare-recovery', '--run-dir', str(self.root),
                    '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose']))
        return runtime

    def verify_recovery_replay(self):
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 0, body)
        result, replay = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 0, replay)
        self.assertEqual(replay['writes'], [])
        self.assertEqual(replay['result']['transaction_id'], body['result']['transaction_id'])
        journal = json.loads((self.root / body['result']['recovery_journal']).read_text(encoding='utf-8'))
        self.assertIn(self.txid, journal['old_prompt'])
        self.assertEqual(self.tx()['state'], 'failed')

    def test_review_recovery_replays_after_prompt_replace(self):
        self.interrupted_recovery('prompt')
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body['result']['next_command'], 'prepare-recovery')
        self.assertEqual(body['writes'], [])
        self.verify_recovery_replay()

    def test_review_recovery_replays_after_transaction_replace(self):
        self.interrupted_recovery('transaction')
        self.verify_recovery_replay()

    def test_review_interrupted_journal_publication_keeps_old_prompt(self):
        self.interrupted_recovery('journal')
        prompt = (self.root / '.ppt-pilot/generation-prompts/S01.md').read_text(encoding='utf-8')
        self.assertIn(self.txid, prompt)
        self.verify_recovery_replay()

    def test_review_recovery_replays_after_journal_publication(self):
        self.interrupted_recovery('journal-published')
        self.verify_recovery_replay()

    def test_review_recovery_rejects_changed_run_without_writes(self):
        self.interrupted_recovery('prompt')
        run = json.loads((self.root / '.ppt-pilot/run.json').read_text(encoding='utf-8'))
        run['dirty_slides'].append('S02')
        self.put('.ppt-pilot/run.json', run)
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])

    def test_review_recovery_rejects_third_party_prompt_without_writes(self):
        self.interrupted_recovery('transaction')
        target = self.root / '.ppt-pilot/generation-prompts/S01.md'
        target.write_text('third-party bytes', encoding='utf-8')
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])
        self.assertEqual(target.read_text(), 'third-party bytes')

    def test_review_recovery_rejects_third_party_manifest_without_writes(self):
        self.interrupted_recovery('transaction')
        manifest = json.loads((self.root / self.manifest_name).read_text())
        manifest['telemetry_summary']['third_party'] = True
        self.put(self.manifest_name, manifest)
        before = (self.root / self.manifest_name).read_bytes()
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])
        self.assertEqual((self.root / self.manifest_name).read_bytes(), before)

    def test_review_recovery_rejects_changed_replacement_tx_without_writes(self):
        self.interrupted_recovery('transaction')
        journal_path = next((self.root / '.ppt-pilot/visual-generation-recoveries').glob('*.json'))
        journal = json.loads(journal_path.read_text(encoding='utf-8'))
        txpath = journal['new_transaction_ref']
        tx = json.loads((self.root / txpath).read_text())
        tx['timing'].append({'third_party': True})
        self.put(txpath, tx)
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])

    def test_review_recovery_journal_rejects_extra_fields(self):
        self.interrupted_recovery('prompt')
        path = next((self.root / '.ppt-pilot/visual-generation-recoveries').glob('*.json'))
        journal = json.loads(path.read_text(encoding='utf-8'))
        journal['replacement_script'] = 'forbidden'
        path.write_text(json.dumps(journal), encoding='utf-8')
        result, body = self.invoke('prepare-recovery', '--slide-id', 'S01', '--transaction-id', self.txid, '--mode', 'recompose')
        self.assertEqual(result.returncode, 2, body)
        self.assertEqual(body['writes'], [])

    def test_unsafe_runtime_artifact_is_preserved(self):
        (self.root / 'helper.py').write_text('print(1)', encoding='utf-8')
        result, body = self.invoke('resume')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(body['errors'][0]['code'], 'runtime_code_artifact')
        self.assertEqual(body['writes'], [])
        self.assertEqual((self.root / 'helper.py').read_text(), 'print(1)')

    def test_unsafe_staging_path_rejected(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/runtime-boundaries.json').read_text())
        for path in cases['unsafe_input_paths']:
            with self.subTest(path=path):
                result, body = self.invoke('prepare-batch', '--input', path,
                                          '--capability', '.ppt-pilot/runtime-inputs/cap.json')
                self.assertEqual(result.returncode, 2)
                self.assertEqual(body['errors'][0]['code'], 'unsafe_runtime_input')
                self.assertEqual(body['writes'], [])

    def test_deepseek_cannot_self_register(self):
        from _host_adapter_runtime import validate_capability
        with self.assertRaisesRegex(ValueError, 'generator_unavailable'):
            validate_capability({'schema_version': 1, 'kind': 'host_capability',
                                 'host': 'deepseek', 'adapter_id': 'forged',
                                 'adapter_version': '1', 'adapter_digest': 'sha256:' + 'a'*64,
                                 'observation': {}, 'evidence': {}})


if __name__ == '__main__':
    unittest.main()
