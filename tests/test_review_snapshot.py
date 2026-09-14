"""Content-review snapshot semantics and runtime binding."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ppt-start/scripts'
sys.path.insert(0, str(SCRIPTS))

from _review_snapshot import create_review_snapshot, review_snapshot, validate_review_snapshot
from _run_store import RunStore
from _runtime_owners import Owners
from _workflow_gate import MANUSCRIPT_FILES, check_run
from tests.test_source_workflow_gate import Fixture as SourceFixture


OUTLINE_ID = 'sha256:' + '1' * 64
STORYBOARD_ID = 'sha256:' + '2' * 64


def structured_document(value, prefix='# Storyboard\n\n', suffix='\nReview all factual copy.\n'):
    return (prefix + '```ppt-pilot-json\n' +
            json.dumps(value, ensure_ascii=False, indent=2) + '\n```' + suffix).encode('utf-8')


def slide(slide_id='S01', previous='START', following='END'):
    return {
        'slide_id': slide_id,
        'role': 'decision',
        'assertion_title': 'Retention improved to 42%',
        'audience_takeaway': 'Continue the bounded pilot',
        'source_ids': ['SRC-1'],
        'forbidden_claims': ['Do not claim causality'],
        'content_blocks': [{
            'block_id': slide_id + '-B1',
            'display_copy': 'Retention improved to 42% in the pilot cohort',
            'priority': 'core',
            'reading_order': 1,
            'claim_id': 'C-1',
            'source_ids': ['SRC-1'],
            'qualifiers': [{
                'display_text': 'Observed in the pilot cohort only',
                'confidence': 'medium',
                'scope': 'Q2 pilot cohort',
                'causality': 'association only',
            }],
            'metric': {
                'display_value': '42%',
                'number_text': '42',
                'unit': '%',
                'period': 'Q2',
                'comparator': 'versus 34%',
                'baseline': '34%',
            },
        }],
        'visual_intent': 'Compare pilot and baseline without implying causality',
        'layout_family': 'comparison',
        'density_budget': 'low',
        'previous_link': previous,
        'next_link': following,
    }


def storyboard():
    return {
        'schema_version': 1,
        'outline_snapshot_id': OUTLINE_ID,
        'storyboard_snapshot_id': STORYBOARD_ID,
        'applied_visual_revision_ids': [],
        'narrative_relationships': {'arc': 'evidence-to-decision'},
        'future_owner_field': {'style_word': 'conservative', 'layout_family': 'nested-content'},
        'slides': [slide()],
    }


class ReviewSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.ppt-pilot').mkdir()
        for name in MANUSCRIPT_FILES[:-1]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Exact manuscript bytes for ' + name + '\n', encoding='utf-8')
        self.write_storyboard(storyboard())

    def write_storyboard(self, value, prefix='# Storyboard\n\n', suffix='\nReview all factual copy.\n'):
        (self.root / MANUSCRIPT_FILES[-1]).write_bytes(structured_document(value, prefix, suffix))

    def snapshot(self):
        return create_review_snapshot(RunStore(self.root), MANUSCRIPT_FILES)

    def test_cli_returns_complete_immutable_snapshot_without_writes(self):
        tool_root = self.root / 'tool'
        tool_root.mkdir()
        for name in ('ppt_review_snapshot.py', '_review_snapshot.py', '_run_store.py'):
            shutil.copy2(SCRIPTS / name, tool_root / name)
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run([
            sys.executable, str(tool_root / 'ppt_review_snapshot.py'),
            '--run-dir', str(self.root),
        ], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload['status'], 'SNAPSHOT')
        frozen = payload['reviewed_file_snapshot']
        self.assertEqual(set(frozen), {
            'snapshot_id', 'files', 'file_hashes', 'semantic_file_hashes'})
        self.assertEqual(tuple(frozen['files']), MANUSCRIPT_FILES)
        self.assertEqual(set(frozen['file_hashes']), set(MANUSCRIPT_FILES))
        self.assertEqual(set(frozen['semantic_file_hashes']), set(MANUSCRIPT_FILES))
        self.assertRegex(frozen['snapshot_id'], r'^sha256:[0-9a-f]{64}$')
        self.assertIn('never approves', payload['notice'])
        validate_review_snapshot(
            frozen,
            {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
             for name in MANUSCRIPT_FILES},
            RunStore(self.root).read_bytes,
        )
        after = {p.relative_to(self.root).as_posix(): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after, before)

    def test_only_precise_visual_and_operational_owner_paths_are_content_neutral(self):
        approved = self.snapshot()
        changed = storyboard()
        changed['storyboard_snapshot_id'] = 'sha256:' + '3' * 64
        changed['applied_visual_revision_ids'] = ['visual-revision-1']
        changed['slides'][0]['applied_visual_revision_ids'] = []
        changed['slides'][0]['layout_family'] = 'single-column'
        changed['slides'][0]['visual_intent'] = 'Use one strong comparison axis'
        self.write_storyboard(changed)
        current = self.snapshot()
        name = MANUSCRIPT_FILES[-1]
        self.assertNotEqual(current['file_hashes'][name], approved['file_hashes'][name])
        self.assertEqual(current['semantic_file_hashes'][name], approved['semantic_file_hashes'][name])

        changed.pop('applied_visual_revision_ids')
        changed['slides'][0].pop('applied_visual_revision_ids')
        self.write_storyboard(changed)
        absent = self.snapshot()
        self.assertEqual(absent['semantic_file_hashes'][name], approved['semantic_file_hashes'][name])

    def test_facts_claims_metrics_units_qualifiers_sources_relationships_unknowns_and_prose_are_bound(self):
        base_value = storyboard()
        approved = self.snapshot()['semantic_file_hashes'][MANUSCRIPT_FILES[-1]]
        mutations = {
            'claim': lambda value: value['slides'][0].__setitem__('assertion_title', 'Retention improved to 43%'),
            'number': lambda value: value['slides'][0]['content_blocks'][0]['metric'].__setitem__('number_text', '43'),
            'unit': lambda value: value['slides'][0]['content_blocks'][0]['metric'].__setitem__('unit', 'points'),
            'qualifier': lambda value: value['slides'][0]['content_blocks'][0]['qualifiers'][0].__setitem__('scope', 'All customers'),
            'source': lambda value: value['slides'][0]['content_blocks'][0].__setitem__('source_ids', ['SRC-2']),
            'narrative_relationship': lambda value: value['narrative_relationships'].__setitem__('arc', 'problem-to-solution'),
            'unknown_root_field': lambda value: value['future_owner_field'].__setitem__('style_word', 'expressive'),
            'nested_same_named_field': lambda value: value['future_owner_field'].__setitem__('layout_family', 'changed-content'),
            'schema_version': lambda value: value.__setitem__('schema_version', 2),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                candidate = copy.deepcopy(base_value)
                mutate(candidate)
                self.write_storyboard(candidate)
                result = review_snapshot(self.root)
                if label == 'schema_version':
                    self.assertEqual(result['status'], 'BLOCKED', result)
                else:
                    self.assertEqual(result['status'], 'SNAPSHOT', result)
                    self.assertNotEqual(
                        result['reviewed_file_snapshot']['semantic_file_hashes'][MANUSCRIPT_FILES[-1]],
                        approved,
                    )
        self.write_storyboard(base_value, prefix='# Changed prose\n\n')
        self.assertNotEqual(
            self.snapshot()['semantic_file_hashes'][MANUSCRIPT_FILES[-1]], approved)

    def test_bom_prefixed_storyboard_still_binds_all_surrounding_prose(self):
        name = MANUSCRIPT_FILES[-1]
        self.write_storyboard(storyboard(), prefix='# Storyboard\nAA\n')
        path = self.root / name
        path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes())
        approved = self.snapshot()['semantic_file_hashes'][name]

        self.write_storyboard(storyboard(), prefix='# Storyboard\nBB\n')
        path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes())
        changed = self.snapshot()['semantic_file_hashes'][name]

        self.assertNotEqual(changed, approved)

    def test_non_storyboard_manuscripts_remain_byte_bound(self):
        approved = self.snapshot()
        name = MANUSCRIPT_FILES[0]
        (self.root / name).write_text('A visually styled prose rewrite\n', encoding='utf-8')
        changed = self.snapshot()
        self.assertNotEqual(
            approved['semantic_file_hashes'][name], changed['semantic_file_hashes'][name])
        self.assertEqual(changed['semantic_file_hashes'][name], changed['file_hashes'][name])

    def test_malformed_structured_projection_fails_closed(self):
        malformed = storyboard()
        cases = []
        wrong_slides = copy.deepcopy(malformed)
        wrong_slides['slides'] = {}
        cases.append(structured_document(wrong_slides))
        wrong_member_metadata = copy.deepcopy(malformed)
        wrong_member_metadata['slides'][0]['applied_visual_revision_ids'] = 'revision-1'
        cases.append(structured_document(wrong_member_metadata))
        malformed_revision_id = copy.deepcopy(malformed)
        malformed_revision_id['applied_visual_revision_ids'] = ['revision-1']
        cases.append(structured_document(malformed_revision_id))
        cases.append(structured_document(malformed).replace(b'"schema_version": 1', b'"schema_version": 1,\n  "schema_version": 1'))
        cases.append(b'\xff' + structured_document(malformed))
        cases.append(b'# Storyboard\n```ppt-pilot-json\n{"slides": []}\n')
        for raw in cases:
            with self.subTest(raw=raw[:80]):
                (self.root / MANUSCRIPT_FILES[-1]).write_bytes(raw)
                result = review_snapshot(self.root)
                self.assertEqual(result['status'], 'BLOCKED', result)
                self.assertEqual(result['errors'][0]['code'], 'review_snapshot_invalid')

    def test_missing_five_file_coverage_fails_closed(self):
        (self.root / MANUSCRIPT_FILES[1]).unlink()
        result = review_snapshot(self.root)
        self.assertEqual(result['status'], 'BLOCKED', result)
        self.assertEqual(result['errors'][0]['code'], 'manuscript_files_invalid')


class ApprovalBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = SourceFixture(self.root)
        (self.root / MANUSCRIPT_FILES[-1]).write_bytes(structured_document(storyboard()))
        self.freeze_semantic_review()

    def freeze_semantic_review(self):
        frozen = create_review_snapshot(RunStore(self.root), MANUSCRIPT_FILES)
        latest = self.fixture.run['manuscript_review']['review_history'][-1]
        latest['reviewed_file_snapshot'] = frozen
        report = b'# Formal review\n\n```ppt-pilot-json\n' + json.dumps(
            latest, ensure_ascii=False, sort_keys=True).encode('utf-8') + b'\n```\n'
        (self.root / '.ppt-pilot/文稿审查.md').write_bytes(report)
        self.fixture.evidence['manuscript'] = {
            'files': {name: self.fixture.sha(name) for name in MANUSCRIPT_FILES},
            'report': self.fixture.record('.ppt-pilot/文稿审查.md'),
            'review_snapshot_id': frozen['snapshot_id'],
        }
        self.fixture.evidence['anchor']['review_snapshot_id'] = frozen['snapshot_id']
        self.fixture.save()
        return frozen

    def save_current_manuscript_hashes(self):
        self.fixture.evidence['manuscript']['files'] = {
            name: self.fixture.sha(name) for name in MANUSCRIPT_FILES}
        self.fixture.save()

    def test_visual_only_storyboard_change_retains_content_approval_without_rebinding_evidence(self):
        before = self.fixture.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot']
        approved_evidence = copy.deepcopy(self.fixture.evidence['manuscript'])
        value = storyboard()
        value['storyboard_snapshot_id'] = 'sha256:' + '4' * 64
        value['applied_visual_revision_ids'] = ['visual-revision-1']
        value['slides'][0]['applied_visual_revision_ids'] = ['visual-revision-1']
        value['slides'][0]['layout_family'] = 'single-column'
        value['slides'][0]['visual_intent'] = 'Use a single evidence lane'
        (self.root / MANUSCRIPT_FILES[-1]).write_bytes(structured_document(value))
        bytes_before_gate = {path.relative_to(self.root).as_posix(): path.read_bytes()
                             for path in self.root.rglob('*') if path.is_file()}

        result = check_run(self.root, 'theme')

        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(self.fixture.evidence['manuscript'], approved_evidence)
        self.assertEqual(
            self.fixture.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot'], before)
        bytes_after_gate = {path.relative_to(self.root).as_posix(): path.read_bytes()
                            for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(bytes_after_gate, bytes_before_gate)

    def test_semantic_approval_rejects_arbitrary_evidence_hash_map(self):
        value = storyboard()
        value['slides'][0]['layout_family'] = 'single-column'
        (self.root / MANUSCRIPT_FILES[-1]).write_bytes(structured_document(value))
        self.fixture.evidence['manuscript']['files'][MANUSCRIPT_FILES[-1]] = 'f' * 64
        self.fixture.save()

        result = check_run(self.root, 'theme')

        self.assertEqual(result['status'], 'BLOCKED', result)
        self.assertEqual(result['errors'][0]['code'], 'review_snapshot_mismatch', result)

    def test_content_and_prose_changes_invalidate_semantic_approval(self):
        for label, update in (
            ('numeric', lambda value: value['slides'][0]['content_blocks'][0]['metric'].__setitem__('number_text', '99')),
            ('qualifier', lambda value: value['slides'][0]['content_blocks'][0]['qualifiers'][0].__setitem__('causality', 'causal')),
            ('source', lambda value: value['slides'][0].__setitem__('source_ids', ['SRC-2'])),
            ('narrative', lambda value: value['narrative_relationships'].__setitem__('arc', 'different')),
            ('unknown', lambda value: value['future_owner_field'].__setitem__('new_fact', 'changed')),
        ):
            with self.subTest(label=label):
                value = storyboard()
                update(value)
                (self.root / MANUSCRIPT_FILES[-1]).write_bytes(structured_document(value))
                self.save_current_manuscript_hashes()
                result = check_run(self.root, 'theme')
                self.assertEqual(result['status'], 'BLOCKED', result)
                self.assertEqual(result['errors'][0]['code'], 'manuscript_stale', result)
        (self.root / MANUSCRIPT_FILES[-1]).write_bytes(
            structured_document(storyboard(), suffix='\nChanged surrounding prose.\n'))
        self.save_current_manuscript_hashes()
        result = check_run(self.root, 'theme')
        self.assertEqual(result['status'], 'BLOCKED', result)
        self.assertEqual(result['errors'][0]['code'], 'manuscript_stale', result)

    def test_forged_semantic_metadata_cannot_upgrade_legacy_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = SourceFixture(Path(directory))
            name = MANUSCRIPT_FILES[-1]
            legacy.write(name, 'Changed legacy storyboard')
            legacy.evidence['manuscript']['files'][name] = legacy.sha(name)
            current = create_review_snapshot(RunStore(legacy.root), MANUSCRIPT_FILES)
            latest = legacy.run['manuscript_review']['review_history'][-1]
            latest['reviewed_file_snapshot']['semantic_file_hashes'] = current['semantic_file_hashes']
            legacy.evidence['manuscript']['review_snapshot_id'] = latest['reviewed_file_snapshot']['snapshot_id']
            legacy.save()
            result = check_run(legacy.root, 'theme')
            self.assertEqual(result['status'], 'BLOCKED', result)
            self.assertEqual(result['errors'][0]['code'], 'review_snapshot_mismatch', result)

        with tempfile.TemporaryDirectory() as directory:
            retrofit = SourceFixture(Path(directory))
            retrofit.write(MANUSCRIPT_FILES[-1], 'Changed legacy storyboard')
            forged = create_review_snapshot(RunStore(retrofit.root), MANUSCRIPT_FILES)
            retrofit.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot'] = forged
            retrofit.evidence['manuscript']['files'] = forged['file_hashes']
            retrofit.evidence['manuscript']['review_snapshot_id'] = forged['snapshot_id']
            # The approved report remains the old report and cannot bind this new snapshot.
            retrofit.save()
            result = check_run(retrofit.root, 'theme')
            self.assertEqual(result['status'], 'BLOCKED', result)
            self.assertEqual(result['errors'][0]['code'], 'review_report_mismatch', result)

    def test_legacy_raw_approval_remains_exact_and_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = SourceFixture(Path(directory))
            self.assertEqual(check_run(legacy.root, 'theme')['status'], 'PASS')
            self.assertNotIn('semantic_file_hashes',
                legacy.run['manuscript_review']['review_history'][-1]['reviewed_file_snapshot'])
            legacy.write(MANUSCRIPT_FILES[-1], 'Visual words still change legacy bytes')
            legacy.save()
            result = check_run(legacy.root, 'theme')
            self.assertEqual(result['status'], 'BLOCKED', result)
            self.assertEqual(result['errors'][0]['code'], 'manuscript_stale', result)


class RuntimeReviewBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.ppt-pilot').mkdir()
        self.outline = {
            'outline_snapshot_id': OUTLINE_ID,
            'argument_framework': 'pyramid',
            'opening_framework': 'none',
            'sequence_template': 'evidence-decision',
            'narrative_id': 'narrative-1',
            'narrative_choice_reason': 'One bounded decision',
            'narrative_step1_bullets': '- Start with evidence\n- End with decision\n',
        }
        self.document('大纲.md', self.outline)
        self.board = storyboard()
        self.document('.ppt-pilot/故事板.md', self.board)
        for name in ('.ppt-pilot/简报.md', '.ppt-pilot/研究.md', '.ppt-pilot/来源.md'):
            (self.root / name).write_text('Exact ' + name + '\n', encoding='utf-8')
        frozen = create_review_snapshot(RunStore(self.root), MANUSCRIPT_FILES)
        self.latest = {
            'cycle': 1,
            'round': 1,
            'verdict': 'PASS',
            'review_mode': 'inline_fallback',
            'findings': [],
            'fallback_evidence': {
                'delegation_attempted': True,
                'reason': 'delegation_capability_unavailable',
                'host_detail': 'hermetic test',
            },
            'reviewed_file_snapshot': frozen,
        }
        self.document('.ppt-pilot/文稿审查.md', self.latest)
        self.run = {
            'schema_version': 1,
            'deck_id': self.root.name,
            'mode': 'auto',
            'stage': 'production',
            'dirty_slides': ['S01'],
            'manuscript_review': {
                'required': True,
                'cycle': 1,
                'round': 1,
                'mode': 'inline_fallback',
                'state': 'manuscript_approved',
                'status': 'PASSED',
                'latest_report': '文稿审查.md',
                'open_blocking_findings': [],
                'review_history': [self.latest],
            },
        }
        self.write_json('.ppt-pilot/run.json', self.run)
        self.write_json('.ppt-pilot/theme.json', {
            'selected_style_id': 'jiawei-product',
            'selected_style_display_name': '嘉为产品',
            'style_kind': 'style_pack',
            'style_manifest_version': '1.2.0',
        })

    def document(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'# Canonical owner\n\n```ppt-pilot-json\n' +
                         json.dumps(value, ensure_ascii=False).encode('utf-8') + b'\n```\n')

    def write_json(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def test_runtime_accepts_visual_revision_but_uses_new_visual_prompt_identity(self):
        initial = Owners(RunStore(self.root), self.run)
        initial_identity = initial.compile({
            'slide_id': 'S01',
            'generation_intent': 'initial_generation',
            'generation_trigger_id': 'initial:S01:' + STORYBOARD_ID,
        })[0]

        self.board['slides'][0]['layout_family'] = 'single-column'
        self.board['slides'][0]['visual_intent'] = 'Use a single evidence lane'
        self.document('.ppt-pilot/故事板.md', self.board)
        visual_only = Owners(RunStore(self.root), self.run)
        visual_identity = visual_only.compile({
            'slide_id': 'S01',
            'generation_intent': 'initial_generation',
            'generation_trigger_id': 'initial:S01:' + STORYBOARD_ID,
        })[0]
        self.assertNotEqual(visual_identity, initial_identity)

        self.board['storyboard_snapshot_id'] = 'sha256:' + '5' * 64
        self.board['applied_visual_revision_ids'] = ['visual-revision-1']
        self.document('.ppt-pilot/故事板.md', self.board)
        self.run['interaction_history'] = {
            'visual-revision-1': {
                'id': 'visual-revision-1',
                'kind': 'visual_revision',
                'stage': 'production',
                'affected_scope': ['S01'],
                'status': 'applied',
                'artifact_owner': '.ppt-pilot/故事板.md',
                'supersedes': [],
                'normalized_changes': {
                    'layout_family': 'single-column',
                    'visual_intent': 'Use a single evidence lane',
                },
            },
        }
        self.write_json('.ppt-pilot/run.json', self.run)
        revised = Owners(RunStore(self.root), self.run)
        revised_identity = revised.compile({
            'slide_id': 'S01',
            'generation_intent': 'user_recompose',
            'generation_trigger_id': 'interaction:visual-revision-1',
        })[0]
        self.assertEqual(revised.snapshots['storyboard_snapshot_id'], 'sha256:' + '5' * 64)
        self.assertEqual(revised.revisions, ['visual-revision-1'])
        self.assertNotEqual(revised_identity, initial_identity)

    def test_runtime_rejects_content_change_under_semantic_approval(self):
        self.board['slides'][0]['content_blocks'][0]['metric']['number_text'] = '99'
        self.document('.ppt-pilot/故事板.md', self.board)
        with self.assertRaisesRegex(ValueError, 'manuscript_stale'):
            Owners(RunStore(self.root), self.run)

    def test_runtime_rejects_source_mapping_change_under_semantic_approval(self):
        self.board['slides'][0]['source_ids'] = ['SRC-2']
        self.board['slides'][0]['content_blocks'][0]['source_ids'] = ['SRC-2']
        self.document('.ppt-pilot/故事板.md', self.board)
        with self.assertRaisesRegex(ValueError, 'manuscript_stale'):
            Owners(RunStore(self.root), self.run)


if __name__ == '__main__':
    unittest.main()
