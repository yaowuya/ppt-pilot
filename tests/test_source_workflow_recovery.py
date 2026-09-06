"""Regression tests for active import recovery and scoped authorization."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_source_workflow_gate import Fixture, SCRIPTS
import _workflow_gate as gate


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.f = Fixture(self.root)

    def active(self, stage='production'):
        self.f.run['stage'] = stage
        name = '.ppt-pilot/visual-generation-batches/batch-1.json'
        self.f.write_json(name, {'schema_version': 2, 'batch_id': 'batch-1'})
        self.f.run['active_visual_generation_batch'] = {'schema_version': 2, 'batch_id': 'batch-1', 'manifest_path': name}
        self.f.save()

    def test_active_recovery_unchanged_passes_but_changed_source_blocks_without_writes(self):
        self.active()
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(gate.check_active_batch(self.root)['status'], 'PASS')
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(gate.check_run(self.root, 'production')['errors'][0]['code'], 'active_visual_generation_batch')
        self.f.source.write_bytes(b'replaced source')
        result = gate.check_active_batch(self.root)
        self.assertEqual(result['errors'][0]['code'], 'source_changed')

    def test_active_anchor_needs_style_but_not_anchor_approval(self):
        self.active('anchor')
        del self.f.evidence['anchor']
        self.f.save()
        self.assertEqual(gate.check_active_batch(self.root)['status'], 'PASS')
        self.f.run['stage'] = 'production'
        self.f.save()
        self.assertEqual(gate.check_active_batch(self.root)['errors'][0]['code'], 'anchor_missing')

    def test_active_recovery_preserves_higher_control_priority(self):
        self.active()
        self.f.run.update(pending_interaction={}, visual_generation_blocker={}, visual_generation_transaction={})
        self.f.run['manuscript_review']['pending_round'] = {}
        for field, code in (('pending_interaction', 'pending_interaction'), ('pending_round', 'pending_review_round'),
                            ('visual_generation_blocker', 'visual_generation_blocker'),
                            ('visual_generation_transaction', 'visual_generation_transaction')):
            self.f.save()
            self.assertEqual(gate.check_active_batch(self.root)['errors'][0]['code'], code)
            del (self.f.run['manuscript_review'] if field == 'pending_round' else self.f.run)[field]

    def test_active_flag_rejects_absent_pointer_invalid_stage_and_cli_has_no_assert_bypass(self):
        self.assertEqual(gate.check_active_batch(self.root)['status'], 'BLOCKED')
        self.active('qa')
        self.assertEqual(gate.check_active_batch(self.root)['status'], 'BLOCKED')
        result = subprocess.run([sys.executable, '-O', str(SCRIPTS / 'ppt_workflow_gate.py'), '--run-dir',
                                 str(self.root), '--resume-active-batch'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'BLOCKED')

    def authorize_omit(self):
        row = self.f.mapping['slides'][1]
        row.update(action='omit', targets=[], authorization={'interaction_id': 'omit'})
        auth = {key: row[key] for key in ('source_slide_id', 'action', 'targets')}
        auth['source_sha256'] = self.f.mapping['source_sha256']
        self.f.run['interaction_history'] = {'omit': {'kind': 'authorization', 'status': 'applied',
            'decision': 'approve', 'source_mapping_authorizations': [auth]}}
        self.f.evidence['target_slide_ids'] = ['S01']
        self.f.write_json('.ppt-pilot/源页映射.json', self.f.mapping)
        self.f.evidence['mapping_sha256'] = self.f.sha('.ppt-pilot/源页映射.json')
        self.f.save()

    def test_negative_or_unrelated_mapping_approval_cannot_authorize_omit(self):
        self.authorize_omit()
        self.assertEqual(gate.check_run(self.root, 'outline')['status'], 'PASS')
        record = self.f.run['interaction_history']['omit']
        for key, value in (('decision', 'request_revision'), ('kind', 'approval'),
                           ('source_mapping_authorizations', [])):
            old = record[key]
            record[key] = value
            self.f.save()
            self.assertEqual(gate.check_run(self.root, 'outline')['status'], 'BLOCKED')
            record[key] = old
        auth = record['source_mapping_authorizations'][0]
        for key, value in (('source_sha256', '0' * 64), ('source_slide_id', 'SRC-S001'),
                           ('action', 'preserve'), ('targets', ['S01'])):
            old = auth[key]
            auth[key] = value
            self.f.save()
            self.assertEqual(gate.check_run(self.root, 'outline')['status'], 'BLOCKED')
            auth[key] = old

    def test_utf16_declarations_rejected_for_svg_and_shared_intake_parser(self):
        from _source_intake import _parse_xml
        xml = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE svg [<!ENTITY text "unsafe">]><svg viewBox="0 0 1280 720">&text;</svg>'
        name = '.ppt-pilot/samples/S01.svg'
        for encoding, bom in (('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff')):
            raw = bom + xml.encode(encoding)
            (self.root / name).write_bytes(raw)
            self.f.evidence['anchor']['files'][name] = self.f.sha(name)
            self.f.save()
            self.assertEqual(gate.check_run(self.root, 'production')['status'], 'BLOCKED')
            with self.assertRaises(ValueError):
                _parse_xml(raw, name)

    def test_svg_canvas_must_match_final_format(self):
        name = '.ppt-pilot/samples/S01.svg'
        self.f.write(name, '<svg viewBox="0 0 640 360"/>')
        self.f.evidence['anchor']['files'][name] = self.f.sha(name)
        self.f.save()
        self.assertEqual(gate.check_run(self.root, 'production')['status'], 'BLOCKED')

    def test_valid_utf16_svg_and_shared_parser_root_validation(self):
        from _source_intake import _parse_xml
        name = '.ppt-pilot/samples/S01.svg'
        xml = '<?xml version="1.0" encoding="UTF-16"?><svg viewBox="0 0 1280 720"/>'
        for encoding, bom in (('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff')):
            raw = bom + xml.encode(encoding)
            (self.root / name).write_bytes(raw)
            self.f.evidence['anchor']['files'][name] = self.f.sha(name)
            self.f.save()
            self.assertEqual(gate.check_run(self.root, 'production')['status'], 'PASS')
            self.assertEqual(_parse_xml(raw, name, 'svg').tag, 'svg')
            with self.assertRaises(ValueError):
                _parse_xml(raw, name, 'Relationships')

    def test_active_pointer_missing_manifest_or_unsafe_path_fails_closed(self):
        self.active()
        pointer = self.f.run['active_visual_generation_batch']
        for value in ('../other-run/batch.json', '.ppt-pilot/missing.json', None):
            pointer['manifest_path'] = value
            self.f.save()
            self.assertEqual(gate.check_active_batch(self.root)['status'], 'BLOCKED')

    def test_successful_active_cli_is_read_only(self):
        self.active('anchor')
        del self.f.evidence['anchor']
        self.f.save()
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, '-O', str(SCRIPTS / 'ppt_workflow_gate.py'), '--run-dir',
                                 str(self.root), '--resume-active-batch'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['before'], 'anchor')
        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
