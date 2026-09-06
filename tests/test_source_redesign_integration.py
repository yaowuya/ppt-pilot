"""Public CLI regression for external-deck intake, not a simulated deck generator."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills' / 'ppt-start' / 'scripts'


class SourceRedesignIntegrationTests(unittest.TestCase):
    def test_intake_to_complete_cli_with_synthetic_review_and_render_evidence(self):
        # The fixture stands in for completed host actions; this does not test a model generator.
        from test_source_intake import _deck
        from test_source_workflow_gate import Fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Fixture(root)
            _deck(fixture.source)
            inventory_path = root / '.ppt-pilot/imported-inventory.json'
            intake = subprocess.run([sys.executable, str(SCRIPTS / 'ppt_source_intake.py'), '--source', str(fixture.source), '--output', str(inventory_path)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(intake.returncode, 0, intake.stderr)
            inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
            fixture.run['source_deck']['inventory'] = inventory_path.name
            fixture.evidence['source_sha256'] = inventory['source']['sha256']
            fixture.mapping['source_sha256'] = inventory['source']['sha256']
            fixture.write_json('.ppt-pilot/源页映射.json', fixture.mapping)
            fixture.evidence['mapping_sha256'] = fixture.sha('.ppt-pilot/源页映射.json')
            fixture.evidence['source_audit']['inventory_sha256'] = fixture.sha('.ppt-pilot/imported-inventory.json')
            fixture.evidence['source_audit']['visual_checked_slide_ids'] = [page['source_slide_id'] for page in inventory['slides']]
            fixture.save()
            command = [sys.executable, str(SCRIPTS / 'ppt_workflow_gate.py'), '--run-dir', str(root)]
            for stage in ('research', 'outline', 'storyboard', 'manuscript_review', 'theme', 'anchor', 'production', 'qa', 'complete'):
                with self.subTest(stage=stage):
                    result = subprocess.run(command + ['--before', stage], capture_output=True, text=True, encoding='utf-8')
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    self.assertEqual(json.loads(result.stdout)['status'], 'PASS')
            fixture.write('slides/S01.svg', '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><text>Changed after render</text></svg>')
            result = subprocess.run(command + ['--before', 'complete'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            self.assertEqual(json.loads(result.stdout)['status'], 'BLOCKED')

    def test_external_deck_cannot_skip_to_visuals_even_in_auto_production(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / '旧稿.pptx'
            with zipfile.ZipFile(source, 'w') as package:
                package.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
                package.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="root" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>')
                package.writestr('ppt/presentation.xml', '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="256" r:id="page"/></p:sldIdLst></p:presentation>')
                package.writestr('ppt/_rels/presentation.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="page" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide7.xml"/></Relationships>')
                package.writestr('ppt/slides/slide7.xml', '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Preserve original claim</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
            original = source.read_bytes()
            run = workspace / 'imported-deck'
            internal = run / '.ppt-pilot'
            internal.mkdir(parents=True)
            inventory = internal / '源稿清单.json'
            result = subprocess.run([sys.executable, str(SCRIPTS / 'ppt_source_intake.py'), '--source', str(source), '--output', str(inventory)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(inventory.read_text(encoding='utf-8'))
            self.assertEqual(data['slides'][0]['part'], 'ppt/slides/slide7.xml')
            self.assertEqual(data['slide_count'], 1)
            mapping = {'schema_version': 1, 'source_sha256': data['source']['sha256'], 'slides': [{'source_slide_id': 'SRC-S001', 'action': 'restyle', 'targets': ['S01'], 'reason': 'Retain content; change product styling'}]}
            (internal / '源页映射.json').write_text(json.dumps(mapping), encoding='utf-8')
            state = {'schema_version': 1, 'deck_id': run.name, 'mode': 'auto', 'stage': 'production', 'dirty_slides': [], 'manuscript_review': {'required': True, 'round': 0, 'mode': 'pending', 'state': 'pending', 'status': 'PENDING', 'latest_report': '文稿审查.md', 'open_blocking_findings': [], 'review_history': []}, 'source_deck': {'kind': 'external_pptx', 'source_path': str(source), 'inventory': '源稿清单.json', 'mapping': '源页映射.json', 'evidence': '导入检查点.json'}}
            (internal / 'run.json').write_text(json.dumps(state), encoding='utf-8')
            before = {str(p.relative_to(run)): hashlib.sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file()}
            for optimized in (False, True):
                command = [sys.executable] + (['-O'] if optimized else []) + [str(SCRIPTS / 'ppt_workflow_gate.py'), '--run-dir', str(run), '--before', 'theme']
                checked = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(checked.returncode, 2, checked.stderr + checked.stdout)
                report = json.loads(checked.stdout)
                self.assertEqual(report['status'], 'BLOCKED')
                self.assertTrue(report['errors'])
                for error in report['errors']:
                    self.assertTrue(error['code'])
                    self.assertTrue(error['reentry_stage'])
                    self.assertTrue(error['next_action'])
            after = {str(p.relative_to(run)): hashlib.sha256(p.read_bytes()).hexdigest() for p in run.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((run / 'slides').exists())


if __name__ == '__main__':
    unittest.main()
