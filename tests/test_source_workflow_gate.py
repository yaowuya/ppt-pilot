"""Behavioral tests for the additive external-source gate."""
import hashlib
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(SCRIPTS))
from _workflow_gate import check_run, snapshot_run, STAGES, MANUSCRIPT_FILES


class Fixture:
    def __init__(self, root):
        self.root = root
        self.source = root / 'original.pptx'
        self.source.write_bytes(b'synthetic source bytes')
        sha = self.sha('original.pptx')
        self.inventory = {'schema_version': 1, 'kind': 'pptx_source_inventory',
                          'source': {'name': 'original.pptx', 'sha256': sha, 'size_bytes': self.source.stat().st_size},
                          'slide_count': 2, 'slides': [], 'warnings': []}
        for index in (1, 2):
            self.inventory['slides'].append({'source_slide_id': 'SRC-S%03d' % index, 'position': index,
                'part': 'ppt/slides/slide%d.xml' % index, 'sha256': 'a' * 64, 'texts': ['Title'],
                'tables': [], 'notes': [], 'objects': [], 'warnings': ['Check image'] if index == 2 else []})
        self.mapping = {'schema_version': 1, 'source_sha256': sha, 'slides': [
            {'source_slide_id': 'SRC-S%03d' % index, 'action': 'restyle', 'targets': ['S%02d' % index],
             'reason': 'Rebuild original content in the target style.'} for index in (1, 2)]}
        self.write_json('.ppt-pilot/源稿清单.json', self.inventory)
        self.write_json('.ppt-pilot/源页映射.json', self.mapping)
        for name in MANUSCRIPT_FILES:
            self.write(name, 'Current manuscript ' + name)
        self.write('.ppt-pilot/文稿审查.md', 'Formal review round 1 PASS; no unresolved findings.')
        self.write_json('.ppt-pilot/theme.json', {'selected_style_id': 'target-product', 'style_manifest_version': '1.0.0'})
        for index in (1, 2):
            self.write('.ppt-pilot/samples/S%02d.svg' % index, '<svg viewBox="0 0 1280 720">sample %d</svg>' % index)
            self.write('slides/S%02d.svg' % index, '<svg viewBox="0 0 1280 720">final %d</svg>' % index)
            name = '.ppt-pilot/renders/S%02d.png' % index
            self.write(name, '')
            (root / name).write_bytes(base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lWQAAAAASUVORK5CYII='))
        self.write('.ppt-pilot/质量检查报告.md', 'Every page was visually checked; PASS.')
        files = {name: self.sha(name) for name in MANUSCRIPT_FILES}
        self.evidence = {'schema_version': 1, 'source_sha256': sha,
            'mapping_sha256': self.sha('.ppt-pilot/源页映射.json'), 'target_slide_ids': ['S01', 'S02'],
            'source_audit': {'status': 'complete', 'inventory_sha256': self.sha('.ppt-pilot/源稿清单.json'),
                'reviewed_slide_ids': ['SRC-S001', 'SRC-S002'], 'visual_checked_slide_ids': ['SRC-S002'],
                'notes': 'Reviewed warning page against original slide.'},
            'manuscript': {'files': files, 'report': self.record('.ppt-pilot/文稿审查.md'), 'review_snapshot_id': 'review-v1'},
            'style': {'files': {'.ppt-pilot/theme.json': self.sha('.ppt-pilot/theme.json')},
                      'selected_style_id': 'target-product', 'style_manifest_version': '1.0.0'},
            'anchor': {'files': {'.ppt-pilot/samples/S%02d.svg' % index: self.sha('.ppt-pilot/samples/S%02d.svg' % index)
                                  for index in (1, 2)}, 'style_sha256': self.sha('.ppt-pilot/theme.json'),
                       'review_snapshot_id': 'review-v1', 'status': 'validated'},
            'qa': {'status': 'PASS', 'report': self.record('.ppt-pilot/质量检查报告.md'), 'slides': [
                {'slide_id': 'S%02d' % index, 'svg': self.record('slides/S%02d.svg' % index),
                 'render': self.record('.ppt-pilot/renders/S%02d.png' % index),
                 'render_input_sha256': self.sha('slides/S%02d.svg' % index), 'renderer': 'synthetic-test-renderer',
                 'visual_review': 'PASS'} for index in (1, 2)]}}
        self.run = {'schema_version': 1, 'deck_id': root.name, 'mode': 'auto', 'stage': 'production', 'dirty_slides': [],
            'source_deck': {'kind': 'external_pptx', 'source_path': str(self.source), 'inventory': '源稿清单.json',
                            'mapping': '源页映射.json', 'evidence': '导入检查点.json'},
            'manuscript_review': {'required': True, 'state': 'manuscript_approved', 'status': 'PASSED', 'round': 1,
                'open_blocking_findings': [], 'latest_report': '文稿审查.md', 'review_history': [
                    {'round': 1, 'review_mode': 'subagent', 'verdict': 'PASS', 'findings': [],
                     'reviewed_file_snapshot': {'snapshot_id': 'review-v1', 'files': list(files), 'file_hashes': dict(files)},
                     'delegation_evidence': {'child_context_id': 'test-child', 'completion_event_id': 'test-event',
                                             'result_context_id': 'test-child'}}]}}
        self.save()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def write_json(self, name, value):
        self.write(name, json.dumps(value, ensure_ascii=False))

    def sha(self, name):
        return hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def record(self, name):
        return {'path': name, 'sha256': self.sha(name)}

    def save(self):
        self.write_json('.ppt-pilot/run.json', self.run)
        self.write_json('.ppt-pilot/导入检查点.json', self.evidence)

    def authorize(self, interaction_id):
        self.run.setdefault('interaction_history', {})[interaction_id] = {
            'kind': 'authorization', 'status': 'applied', 'decision': 'approve',
            'source_mapping_authorizations': [dict(source_sha256=self.mapping['source_sha256'],
                **{key: row[key] for key in ('source_slide_id', 'action', 'targets')}) for row in self.mapping['slides']]}

    def guided(self):
        self.run['mode'] = 'guided'
        self.run['interaction_history'] = {}
        self.evidence['approvals'] = {}
        for stage, filename in (('brief', MANUSCRIPT_FILES[0]), ('outline', MANUSCRIPT_FILES[3])):
            interaction_id = stage + '-approval'
            self.run['interaction_history'][interaction_id] = {'checkpoint': stage, 'status': 'applied',
                'kind': 'approval', 'approval_attempt': 1, 'decision': 'approve', 'artifact_snapshot_id': stage + '-v1'}
            self.evidence['approvals'][stage] = {'interaction_id': interaction_id,
                'artifact_snapshot_id': stage + '-v1', 'artifact_sha256': self.sha(filename)}
        binding = {key: self.evidence['anchor'][key] for key in ('files', 'style_sha256', 'review_snapshot_id')}
        anchor_id = 'sha256:' + hashlib.sha256(json.dumps(binding, ensure_ascii=False, sort_keys=True,
            separators=(',', ':')).encode('utf-8')).hexdigest()
        self.run['interaction_history']['anchor-approval'] = {'checkpoint': 'anchor', 'status': 'applied',
            'kind': 'approval', 'approval_attempt': 1, 'decision': 'approve', 'artifact_snapshot_id': anchor_id}
        self.evidence['anchor'].update(status='approved', approval_interaction_id='anchor-approval', artifact_snapshot_id=anchor_id)
        self.save()


class SourceGateTests(unittest.TestCase):
    def test_guided_anchor_replacement_requires_reapproval(self):
        self.fixture.guided()
        self.assertEqual(check_run(self.root, 'production')['status'], 'PASS')
        name = '.ppt-pilot/samples/S01.svg'
        self.fixture.write(name, '<svg viewBox="0 0 1280 720">replacement</svg>')
        self.fixture.evidence['anchor']['files'][name] = self.fixture.sha(name)
        self.blocked('production', 'approval_stale', 'anchor')

    def test_opaque_guided_anchor_approval_fails_closed(self):
        self.fixture.guided()
        self.fixture.evidence['anchor']['artifact_snapshot_id'] = 'anchor-v1'
        self.fixture.run['interaction_history']['anchor-approval']['artifact_snapshot_id'] = 'anchor-v1'
        self.blocked('production', 'approval_stale', 'anchor')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = Fixture(self.root)

    def blocked(self, before='complete', code=None, stage=None):
        self.fixture.save()
        result = check_run(self.root, before)
        self.assertEqual(result['status'], 'BLOCKED', result)
        if code:
            self.assertEqual(result['errors'][0]['code'], code, result)
        if stage:
            self.assertEqual(result['errors'][0]['reentry_stage'], stage, result)
        self.assertTrue(result['errors'][0]['next_action'])
        return result

    def audit(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / 'ppt_workflow_gate.py'),
             '--run-dir', str(self.root), '--audit-run'],
            capture_output=True, text=True, encoding='utf-8')
        if result.returncode not in (0, 2):
            self.fail(result.stderr + result.stdout)
        return result, json.loads(result.stdout)

    def test_all_nine_cumulative_stages_pass_without_mutation(self):
        initial = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertEqual(check_run(self.root, stage)['status'], 'PASS')
        final = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(initial, final)

    def test_precomplete_pptx_blocks_every_gate(self):
        self.fixture.write('unexpected.pptx', 'native detour')
        self.blocked('anchor', 'precomplete_pptx', 'theme')

    def test_noncanonical_native_control_state_blocks(self):
        for field in ('native_delivery', 'run_level_generator_blocker'):
            with self.subTest(field=field):
                self.fixture.run[field] = {'status': 'active'}
                self.blocked('anchor', 'workflow_escape_state', 'theme')
                del self.fixture.run[field]

    def test_audit_cli_is_read_only(self):
        before = {path.relative_to(self.root).as_posix(): path.read_bytes()
                  for path in self.root.rglob('*') if path.is_file()}
        result, payload = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(payload, {
            'status': 'PASS', 'before': 'audit', 'errors': []})
        after = {path.relative_to(self.root).as_posix(): path.read_bytes()
                 for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_complete_delivery_pptx_is_only_allowed_in_editable_directory(self):
        self.fixture.run['stage'] = 'complete'
        self.fixture.write('delivery/editable/deck-editable.pptx', 'validated delivery')
        self.fixture.save()
        result, payload = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(payload['status'], 'PASS')
        self.fixture.write('deck-editable.pptx', 'wrong delivery location')
        result, payload = self.audit()
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(payload['status'], 'BLOCKED', payload)
        self.assertEqual(payload['errors'][0]['code'], 'pptx_outside_delivery')

    def test_guided_valid_and_latest_approval_is_authoritative(self):
        self.fixture.guided()
        self.assertEqual(check_run(self.root, 'complete')['status'], 'PASS')
        self.fixture.run['interaction_history']['brief-revision'] = {'checkpoint': 'brief', 'status': 'applied',
            'kind': 'approval', 'approval_attempt': 2, 'decision': 'request_revision', 'artifact_snapshot_id': 'brief-v1'}
        self.blocked('theme', 'approval_missing', 'brief')

    def test_guided_boolean_cannot_replace_history(self):
        self.fixture.run['mode'] = 'guided'
        self.fixture.run['approved'] = {'brief': True, 'outline': True}
        self.blocked('research', 'approval_missing', 'brief')

    def test_guided_current_artifact_hash(self):
        self.fixture.guided()
        self.fixture.write(MANUSCRIPT_FILES[0], 'changed brief')
        self.blocked('research', 'approval_stale', 'brief')

    def test_stage_label_with_complete_upstream_cannot_bypass_review(self):
        del self.fixture.evidence['manuscript']
        self.blocked('theme', 'manuscript_missing', 'manuscript_review')

    def test_source_bytes_changed(self):
        self.fixture.source.write_bytes(b'changed source')
        self.blocked('research', 'source_changed', 'brief')

    def test_inventory_audit_stale(self):
        self.fixture.inventory['warnings'].append('new warning')
        self.fixture.write_json('.ppt-pilot/源稿清单.json', self.fixture.inventory)
        self.blocked('outline', 'source_audit_incomplete', 'research')

    def test_mapping_hash_stale(self):
        self.fixture.mapping['slides'][0]['reason'] = 'Changed reason'
        self.fixture.write_json('.ppt-pilot/源页映射.json', self.fixture.mapping)
        self.blocked('research', 'mapping_changed', 'brief')

    def test_mapping_coverage_and_action_cardinality(self):
        for change, expected in ((lambda rows: rows.pop(), 'mapping_coverage'),
                (lambda rows: rows[0].update(action='split'), 'mapping_cardinality'),
                (lambda rows: rows[0].update(action='merge', authorization={'interaction_id': 'merge'}), 'mapping_cardinality')):
            with self.subTest(expected=expected):
                original = json.loads(json.dumps(self.fixture.mapping))
                change(self.fixture.mapping['slides'])
                self.fixture.authorize('merge')
                self.fixture.write_json('.ppt-pilot/源页映射.json', self.fixture.mapping)
                self.fixture.evidence['mapping_sha256'] = self.fixture.sha('.ppt-pilot/源页映射.json')
                self.blocked('outline', expected, 'outline')
                self.fixture.mapping = original

    def test_preserve_requires_real_applied_authorization(self):
        row = self.fixture.mapping['slides'][0]
        row.update(action='preserve', authorization={'interaction_id': 'unknown'})
        self.fixture.write_json('.ppt-pilot/源页映射.json', self.fixture.mapping)
        self.fixture.evidence['mapping_sha256'] = self.fixture.sha('.ppt-pilot/源页映射.json')
        self.blocked('outline', 'mapping_authorization_missing', 'outline')

    def test_warned_page_requires_visual_check(self):
        self.fixture.evidence['source_audit']['visual_checked_slide_ids'] = []
        self.blocked('outline', 'source_audit_incomplete', 'research')

    def test_changed_manuscript_and_report_block(self):
        for filename, expected in ((MANUSCRIPT_FILES[4], 'manuscript_stale'),
                                   ('.ppt-pilot/文稿审查.md', 'review_report_stale')):
            with self.subTest(filename=filename):
                old = (self.root / filename).read_text(encoding='utf-8')
                self.fixture.write(filename, old + ' new')
                self.blocked('theme', expected, 'manuscript_review')
                self.fixture.write(filename, old)

    def test_rehash_does_not_rebind_formal_frozen_review(self):
        name = MANUSCRIPT_FILES[4]
        self.fixture.write(name, 'new storyboard')
        self.fixture.evidence['manuscript']['files'][name] = self.fixture.sha(name)
        self.blocked('theme', 'review_snapshot_mismatch', 'manuscript_review')

    def test_latest_round_block_cannot_use_earlier_pass(self):
        latest = json.loads(json.dumps(self.fixture.run['manuscript_review']['review_history'][-1]))
        latest.update(round=2, verdict='BLOCK')
        self.fixture.run['manuscript_review']['review_history'].append(latest)
        self.blocked('theme', 'review_not_latest_pass', 'manuscript_review')

    def test_review_missing_execution_or_open_high_blocks(self):
        latest = self.fixture.run['manuscript_review']['review_history'][-1]
        latest['delegation_evidence']['completion_event_id'] = ''
        self.blocked('theme', 'review_execution_missing', 'manuscript_review')
        latest['delegation_evidence']['completion_event_id'] = 'event'
        latest['findings'] = [{'severity': 'HIGH', 'status': 'ACCEPTED_RISK'}]
        self.blocked('theme', 'review_blocking_findings', 'manuscript_review')

    def test_style_hash_and_identity(self):
        self.fixture.evidence['style']['selected_style_id'] = 'old-deck-look'
        self.blocked('anchor', 'style_identity_mismatch', 'theme')
        self.fixture.evidence['style']['selected_style_id'] = 'target-product'
        self.fixture.write('.ppt-pilot/theme.json', '{}')
        self.blocked('anchor', 'style_stale', 'theme')

    def test_anchor_hash_and_auto_validation(self):
        self.fixture.evidence['anchor']['status'] = 'approved'
        self.blocked('production', 'anchor_not_approved', 'anchor')
        self.fixture.evidence['anchor']['status'] = 'validated'
        self.fixture.write('.ppt-pilot/samples/S01.svg', '<svg>changed</svg>')
        self.blocked('production', 'anchor_stale', 'anchor')

    def test_all_final_svgs_required_before_qa(self):
        (self.root / 'slides/S02.svg').unlink()
        self.blocked('qa', 'missing_artifact', 'production')

    def test_final_svg_render_and_manual_review_bindings(self):
        item = self.fixture.evidence['qa']['slides'][0]
        for key, value, expected in (('render_input_sha256', '0' * 64, 'qa_render_input_stale'),
                                     ('visual_review', 'pending', 'qa_visual_review_missing')):
            old = item[key]
            item[key] = value
            self.blocked('complete', expected, 'qa')
            item[key] = old
        self.fixture.write('.ppt-pilot/renders/S01.png', 'old render overwritten')
        self.blocked('complete', 'qa_render_stale', 'qa')

    def test_dirty_slides_block_complete(self):
        self.fixture.run['dirty_slides'] = ['S01']
        self.blocked('complete', 'dirty_slides', 'production')

    def test_recovery_priority(self):
        self.fixture.run.update(pending_interaction={}, visual_generation_blocker={},
                                visual_generation_transaction={}, active_visual_generation_batch={})
        self.fixture.run['manuscript_review']['pending_round'] = {}
        for key, expected in (('pending_interaction', 'pending_interaction'),
                              ('pending_round', 'pending_review_round'),
                              ('visual_generation_blocker', 'visual_generation_blocker'),
                              ('visual_generation_transaction', 'visual_generation_transaction'),
                              ('active_visual_generation_batch', 'active_visual_generation_batch')):
            self.blocked('complete', expected)
            owner = self.fixture.run['manuscript_review'] if key == 'pending_round' else self.fixture.run
            del owner[key]

    def test_unsafe_paths_and_double_run(self):
        self.fixture.evidence['manuscript']['report']['path'] = '../outside.md'
        self.blocked('theme', 'unsafe_evidence_path')
        self.fixture.write_json('run.json', self.fixture.run)
        self.blocked('research', 'run_path_conflict')

    def test_malformed_nested_forms_are_structured(self):
        for field in ('source_deck', 'manuscript_review'):
            old = self.fixture.run[field]
            for malformed in ([], 'text', 42, False):
                with self.subTest(field=field, malformed=malformed):
                    self.fixture.run[field] = malformed
                    self.blocked('complete')
            self.fixture.run[field] = old
        self.fixture.evidence['qa']['slides'] = [None]
        self.blocked('complete')

    def test_non_import_is_not_applicable(self):
        del self.fixture.run['source_deck']
        self.fixture.source.unlink()
        self.fixture.save()
        self.assertEqual(check_run(self.root, 'complete')['status'], 'NOT_APPLICABLE')

    def test_snapshot_cli_optimized_gate_and_no_writes(self):
        before = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPTS / 'ppt_workflow_gate.py'), '--run-dir', str(self.root), '--snapshot'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['status'], 'SNAPSHOT')
        self.assertNotIn('manuscript', payload)
        self.assertNotIn('review_snapshot_id', payload)
        after = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        del self.fixture.evidence['manuscript']
        self.fixture.save()
        result = subprocess.run([sys.executable, '-O', str(SCRIPTS / 'ppt_workflow_gate.py'), '--run-dir', str(self.root), '--before', 'theme'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['errors'][0]['code'], 'manuscript_missing')

    def test_pending_interaction_wins_even_over_malformed_review(self):
        self.fixture.run['pending_interaction'] = {'status': 'awaiting_answer'}
        self.fixture.run['manuscript_review'] = []
        self.blocked('complete', 'pending_interaction')

    def test_snapshot_hashes_empty_files_without_approval(self):
        self.fixture.write('.ppt-pilot/dashboard.log', '')
        result = snapshot_run(self.root)
        self.assertEqual(result['status'], 'SNAPSHOT', result)
        self.assertEqual(result['files']['.ppt-pilot/dashboard.log'], hashlib.sha256(b'').hexdigest())

    def test_anchor_must_be_an_actual_svg(self):
        name = '.ppt-pilot/samples/S01.svg'
        self.fixture.write(name, 'not an SVG')
        self.fixture.evidence['anchor']['files'][name] = self.fixture.sha(name)
        self.blocked('production', 'invalid_svg', 'anchor')

    def test_each_phase_requires_its_immediate_upstream(self):
        for stage, filename, reentry in (('research', MANUSCRIPT_FILES[0], 'brief'),
                ('outline', MANUSCRIPT_FILES[1], 'research'),
                ('storyboard', MANUSCRIPT_FILES[3], 'outline'),
                ('manuscript_review', MANUSCRIPT_FILES[4], 'storyboard')):
            with self.subTest(stage=stage):
                path = self.root / filename
                old = path.read_text(encoding='utf-8')
                path.unlink()
                self.blocked(stage, 'missing_artifact', reentry)
                self.fixture.write(filename, old)

    def test_valid_merge_mapping(self):
        for row in self.fixture.mapping['slides']:
            row.update(action='merge', targets=['S01'], authorization={'interaction_id': 'merge'})
        self.fixture.authorize('merge')
        self.fixture.evidence['target_slide_ids'] = ['S01']
        self.fixture.write_json('.ppt-pilot/源页映射.json', self.fixture.mapping)
        self.fixture.evidence['mapping_sha256'] = self.fixture.sha('.ppt-pilot/源页映射.json')
        self.fixture.save()
        self.assertEqual(check_run(self.root, 'outline')['status'], 'PASS')

    def test_valid_omit_with_applied_authorization(self):
        self.fixture.mapping['slides'][1].update(action='omit', targets=[], authorization={'interaction_id': 'omit-page'})
        self.fixture.authorize('omit-page')
        self.fixture.evidence['target_slide_ids'] = ['S01']
        self.fixture.write_json('.ppt-pilot/源页映射.json', self.fixture.mapping)
        self.fixture.evidence['mapping_sha256'] = self.fixture.sha('.ppt-pilot/源页映射.json')
        self.fixture.save()
        self.assertEqual(check_run(self.root, 'outline')['status'], 'PASS')

    def test_inline_fallback_pass_is_supported(self):
        latest = self.fixture.run['manuscript_review']['review_history'][-1]
        del latest['delegation_evidence']
        latest['review_mode'] = 'inline_fallback'
        latest['fallback_evidence'] = {'delegation_attempted': True,
            'reason': 'delegation_capability_unavailable', 'host_detail': 'Synthetic test host has no child capability.'}
        self.fixture.save()
        self.assertEqual(check_run(self.root, 'theme')['status'], 'PASS')

    def test_versions_duplicate_json_keys_and_empty_paragraphs(self):
        self.fixture.run['schema_version'] = True
        self.blocked('theme', 'invalid_schema')
        self.fixture.run['schema_version'] = 1
        self.fixture.save()
        self.fixture.write('.ppt-pilot/run.json', '{"schema_version":1,"schema_version":1}')
        self.assertEqual(check_run(self.root, 'theme')['status'], 'BLOCKED')
        self.fixture.save()
        self.fixture.inventory['slides'][0]['texts'] = ['']
        self.fixture.write_json('.ppt-pilot/源稿清单.json', self.fixture.inventory)
        self.fixture.evidence['source_audit']['inventory_sha256'] = self.fixture.sha('.ppt-pilot/源稿清单.json')
        self.fixture.save()
        self.assertEqual(check_run(self.root, 'outline')['status'], 'PASS')

    def test_symlink_evidence_rejected_when_platform_allows(self):
        link = self.root / '.ppt-pilot/linked.md'
        try:
            link.symlink_to(self.root / '.ppt-pilot/文稿审查.md')
        except OSError:
            self.skipTest('Platform does not grant symbolic-link creation.')
        self.fixture.evidence['manuscript']['report']['path'] = '.ppt-pilot/linked.md'
        self.blocked('theme', 'unsafe_evidence_path')
        self.assertEqual(snapshot_run(self.root)['status'], 'BLOCKED')

    def test_render_must_be_actual_png(self):
        name = '.ppt-pilot/renders/S01.png'
        self.fixture.write(name, 'not an actual render')
        self.fixture.evidence['qa']['slides'][0]['render'] = self.fixture.record(name)
        self.blocked('complete', 'invalid_render', 'qa')

    def test_svg_viewbox_required(self):
        name = '.ppt-pilot/samples/S01.svg'
        self.fixture.write(name, '<svg viewBox="0 0 -10 720"/>')
        self.fixture.evidence['anchor']['files'][name] = self.fixture.sha(name)
        self.blocked('production', 'invalid_svg', 'anchor')

    def test_approval_attempt_not_json_dictionary_order(self):
        self.fixture.guided()
        history = self.fixture.run['interaction_history']
        history['brief-10'] = dict(history['brief-approval'], approval_attempt=10)
        history['brief-2'] = dict(history['brief-approval'], approval_attempt=2, decision='request_revision')
        history['brief-decoration'] = {'checkpoint': 'brief', 'kind': 'visual_revision', 'status': 'applied'}
        self.fixture.evidence['approvals']['brief']['interaction_id'] = 'brief-10'
        self.fixture.save()
        self.assertEqual(check_run(self.root, 'complete')['status'], 'PASS')

    def test_older_pass_cannot_hide_later_round_by_list_reordering(self):
        review = self.fixture.run['manuscript_review']
        newer = dict(review['review_history'][0], round=2, verdict='BLOCK')
        review['review_history'].insert(0, newer)
        self.blocked('theme', 'review_not_latest_pass', 'manuscript_review')

    def test_unresolved_historical_blocker_cannot_disappear(self):
        review = self.fixture.run['manuscript_review']
        earlier = dict(review['review_history'][0], verdict='BLOCK', findings=[
            {'id': 'HIGH-1', 'severity': 'HIGH', 'status': 'OPEN'}])
        review['review_history'][0]['round'] = 2
        review['round'] = 2
        review['review_history'].insert(0, earlier)
        self.blocked('theme', 'review_blocking_findings', 'manuscript_review')

    def test_stage_label_cannot_bypass_missing_manuscript(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.ppt-pilot').mkdir()
            (root / '.ppt-pilot/run.json').write_text(json.dumps({
                'schema_version': 1, 'mode': 'auto', 'stage': 'production',
                'source_deck': {'kind': 'external_pptx', 'source_path': str(root / 'old.pptx'),
                                'inventory': '源稿清单.json', 'mapping': '源页映射.json',
                                'evidence': '导入检查点.json'}}), encoding='utf-8')
            result = check_run(root, 'theme')
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertTrue(result['errors'][0]['next_action'])


if __name__ == '__main__':
    unittest.main()
