"""Read-only, cumulative gates for external PPTX imports (Python 3.9+)."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import struct
import zlib
from _xml_safety import parse_xml

STAGES = ('research', 'outline', 'storyboard', 'manuscript_review', 'theme',
          'anchor', 'production', 'qa', 'complete')
WORKFLOW_STAGES = ('brief',) + STAGES
MANUSCRIPT_FILES = ('.ppt-pilot/简报.md', '.ppt-pilot/研究.md', '.ppt-pilot/来源.md',
                    '大纲.md', '.ppt-pilot/故事板.md')


class GateError(ValueError):
    def __init__(self, code, stage, action):
        super().__init__(action)
        self.error = {'code': code, 'reentry_stage': stage, 'next_action': action}


def require(condition, code, stage, action):
    if not condition:
        raise GateError(code, stage, action)


def object_value(value, stage='brief'):
    require(isinstance(value, dict), 'invalid_schema', stage, 'Supply a JSON object.')
    return value


def string(value):
    return isinstance(value, str) and bool(value.strip())


def string_list(value):
    return isinstance(value, list) and all(string(item) for item in value)


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def hash_value(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


class Gate:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.stage = 'brief'
        self.hashes = {}

    def path(self, value):
        require(string(value), 'unsafe_evidence_path', self.stage, 'Use a nonempty run-relative path.')
        parts = value.split('/')
        require('\\' not in value and ':' not in value and
                not PurePosixPath(value).is_absolute() and not PureWindowsPath(value).drive and
                all(part not in ('', '.', '..') for part in parts) and
                all(ord(char) >= 32 and ord(char) != 127 for char in value),
                'unsafe_evidence_path', self.stage, 'Use a safe run-relative evidence path.')
        path = self.root.joinpath(*parts)
        # Reject links, including in-run links, to keep all evidence owners unambiguous.
        cursor = self.root
        for part in parts:
            cursor = cursor / part
            require(not cursor.is_symlink() and not getattr(cursor, 'is_junction', lambda: False)(),
                    'unsafe_evidence_path', self.stage, 'Replace linked evidence with an owned regular file.')
        require(path.resolve().is_relative_to(self.root), 'unsafe_evidence_path', self.stage,
                'Keep evidence inside this run.')
        return path

    def file_hash(self, name):
        path = self.path(name)
        require(path.is_file() and path.stat().st_size > 0, 'missing_artifact', self.stage,
                'Create the required nonempty artifact: ' + name)
        result = digest(path)
        self.hashes[name] = result
        return result

    def read_json(self, name):
        self.file_hash(name)
        return object_value(json.loads(self.path(name).read_text(encoding='utf-8-sig'),
                                       object_pairs_hook=unique_object), self.stage)

    def bound(self, name, expected, code='stale_evidence'):
        require(hash_value(expected), 'invalid_schema', self.stage, 'Supply a lowercase SHA-256 digest.')
        actual = self.file_hash(name)
        require(actual == expected, code, self.stage, 'Rebuild and review changed evidence: ' + name)
        return actual

    def files(self, value, code='stale_evidence'):
        value = object_value(value, self.stage)
        require(bool(value), 'invalid_schema', self.stage, 'Supply nonempty file hash bindings.')
        for name, expected in value.items():
            self.bound(name, expected, code)
        return value

    def svg(self, name):
        self.file_hash(name)
        raw = self.path(name).read_bytes()
        try:
            root = parse_xml(raw, name)
        except ValueError:
            raise GateError('invalid_svg', self.stage, 'Replace malformed SVG evidence with the actual generated SVG.')
        require(root.tag in ('svg', '{http://www.w3.org/2000/svg}svg'),
                'invalid_svg', self.stage, 'Use an SVG document as visual evidence.')
        try:
            box = [float(value) for value in root.get('viewBox', '').replace(',', ' ').split()]
        except ValueError:
            box = []
        require(len(box) == 4 and all(math.isfinite(value) for value in box) and box == [0, 0, 1280, 720],
                'invalid_svg', self.stage, 'Supply the required SVG viewBox 0 0 1280 720.')

    def png(self, name):
        path = self.path(name)
        with path.open('rb') as stream:
            header = stream.read(33)
        require(path.suffix.lower() == '.png' and len(header) == 33 and
                header[:16] == b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR',
                'invalid_render', self.stage, 'Supply an actual PNG raster render (only PNG is supported by this gate).')
        width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', header[16:29])
        depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
        require(width > 0 and height > 0 and depth in depths.get(color, ()) and compression == 0 and
                filtering == 0 and interlace in (0, 1) and
                zlib.crc32(header[12:29]) == struct.unpack('>I', header[29:33])[0],
                'invalid_render', self.stage, 'Restore a PNG render with a valid IHDR and positive dimensions.')

    def load_run(self):
        candidates = [name for name in ('.ppt-pilot/run.json', 'run.json') if self.path(name).exists()]
        require(len(candidates) == 1, 'run_path_conflict' if candidates else 'run_missing',
                'brief', 'Resolve exactly one authoritative run.json in this run.')
        run = self.read_json(candidates[0])
        require(type(run.get('schema_version')) is int and run['schema_version'] == 1,
                'invalid_schema', 'brief', 'Use supported run schema_version 1.')
        self.run = run
        return run

    def conformance(self):
        """Reject host-invented workflow branches and premature PPTX output."""
        run = self.run
        require(run.get('stage') in WORKFLOW_STAGES, 'workflow_escape_state', 'theme',
                'Restore a canonical PPT Pilot stage before continuing.')
        escape_fields = sorted(key for key in run if
                               key.startswith('native_') or key in {
                                   'anchor_plan', 'execution_hold', 'run_level_generator_blocker'})
        require(not escape_fields, 'workflow_escape_state', 'theme',
                'Archive noncanonical control fields and resume the canonical SVG workflow: ' +
                ', '.join(escape_fields))

        source_path = None
        source = run.get('source_deck')
        if isinstance(source, dict) and string(source.get('source_path')):
            candidate = Path(source['source_path'])
            if candidate.is_absolute():
                source_path = candidate.resolve()

        pending = [self.root]
        pptx_files = []
        while pending:
            directory = pending.pop()
            entries = sorted(directory.iterdir(), key=lambda path: (path.is_dir(), path.name.lower()))
            for entry in entries:
                relative = entry.relative_to(self.root).as_posix()
                safe = self.path(relative)
                if safe.is_dir():
                    pending.append(safe)
                elif safe.is_file() and safe.suffix.lower() == '.pptx' and safe.resolve() != source_path:
                    pptx_files.append(relative)

        if run['stage'] != 'complete':
            require(not pptx_files, 'precomplete_pptx', 'theme',
                    'Quarantine premature PPTX output and resume theme -> anchor -> production -> qa: ' +
                    ', '.join(sorted(pptx_files)))
        invalid_delivery = [name for name in pptx_files
                            if not name.startswith('delivery/editable/')]
        require(not invalid_delivery, 'pptx_outside_delivery', 'complete',
                'Keep post-complete PPTX delivery only under delivery/editable/: ' +
                ', '.join(sorted(invalid_delivery)))

    def recovery(self, resume_active=False):
        run = self.run
        if run.get('pending_interaction') is not None:
            raise GateError('pending_interaction', 'brief',
                            'Resume the pending interaction before inspecting lower-priority workflow controls.')
        review = run.get('manuscript_review', {})
        checks = [('pending_review_round', object_value(review).get('pending_round'), 'manuscript_review'),
                  ('visual_generation_blocker', run.get('visual_generation_blocker'), 'production'),
                  ('visual_generation_transaction', run.get('visual_generation_transaction'), 'production'),
                  ('active_visual_generation_batch', run.get('active_visual_generation_batch'), 'production')]
        for code, value, stage in checks:
            if resume_active and code == 'active_visual_generation_batch':
                continue
            if value is not None:
                raise GateError(code, stage, 'Resume the existing durable control state before stage work: ' + code)

    def active_batch(self):
        pointer = self.run.get('active_visual_generation_batch')
        require(isinstance(pointer, dict) and pointer.get('schema_version') == 2 and string(pointer.get('batch_id')),
                'active_batch_missing', 'production', 'Use active-batch preflight only with an existing schema-v2 pointer.')
        manifest = self.read_json(pointer.get('manifest_path'))
        require(manifest.get('schema_version') == 2 and manifest.get('batch_id') == pointer['batch_id'],
                'active_batch_conflict', 'production', 'Resolve the active pointer and manifest identity before recovery.')
        require(self.run.get('stage') in ('anchor', 'production'), 'active_batch_stage_invalid', 'production',
                'Resume an active batch only at its existing anchor or production stage.')

    def history(self):
        raw = self.run.get('interaction_history', {})
        require(isinstance(raw, (dict, list)), 'invalid_schema', self.stage, 'Supply applied interaction history.')
        records = []
        for key, value in (raw.items() if isinstance(raw, dict) else enumerate(raw)):
            record = dict(object_value(value, self.stage))
            if isinstance(raw, dict):
                record.setdefault('id', key)
            require(string(record.get('id')), 'invalid_schema', self.stage, 'Each interaction needs its original id.')
            records.append(record)
        require(len({record['id'] for record in records}) == len(records), 'invalid_schema', self.stage,
                'Resolve duplicate interaction IDs.')
        return records

    def import_binding(self):
        source = object_value(self.run['source_deck'])
        require(source.get('kind') == 'external_pptx', 'invalid_schema', 'brief', 'Use external_pptx source binding.')
        original = source.get('source_path')
        require(string(original) and Path(original).is_absolute() and '://' not in original and
                not original.startswith(('\\\\', '//')),
                'invalid_source_path', 'brief', 'Bind an absolute local source PPTX path in run.json.')
        source_path = Path(original)
        require(source_path.suffix.lower() == '.pptx', 'invalid_source_path', 'brief', 'Bind the actual local .pptx source.')
        require(source_path.is_file(), 'source_missing', 'brief', 'Restore the run-authorized source file.')
        self.source_hash = digest(source_path)
        names = {}
        for key in ('inventory', 'mapping', 'evidence'):
            name = source.get(key)
            require(string(name) and '/' not in name and '\\' not in name and ':' not in name,
                    'unsafe_evidence_path', 'brief', 'Store source binding JSON files directly in .ppt-pilot/.')
            names[key] = '.ppt-pilot/' + name
        inventory = self.read_json(names['inventory'])
        mapping = self.read_json(names['mapping'])
        evidence = self.read_json(names['evidence'])
        for item in (inventory, mapping, evidence):
            require(type(item.get('schema_version')) is int and item['schema_version'] == 1,
                    'invalid_schema', 'brief', 'Use source evidence schema_version 1.')
        metadata = object_value(inventory.get('source'))
        require(inventory.get('kind') == 'pptx_source_inventory' and string(metadata.get('name')) and
                type(metadata.get('size_bytes')) is int and metadata['size_bytes'] == source_path.stat().st_size and
                metadata.get('sha256') == self.source_hash and mapping.get('source_sha256') == self.source_hash and
                evidence.get('source_sha256') == self.source_hash,
                'source_changed', 'brief', 'Re-extract the current source and re-audit its mapping and downstream evidence.')
        slides = inventory.get('slides')
        require(isinstance(slides, list) and slides and type(inventory.get('slide_count')) is int and
                inventory['slide_count'] == len(slides) and isinstance(inventory.get('warnings'), list),
                'invalid_inventory', 'brief', 'Restore complete source page inventory.')
        self.source_ids, self.warned_ids = [], []
        for position, item in enumerate(slides, 1):
            item = object_value(item)
            expected_id = 'SRC-S%03d' % position
            require(item.get('source_slide_id') == expected_id and type(item.get('position')) is int and
                    item['position'] == position and string(item.get('part')) and hash_value(item.get('sha256')) and
                    isinstance(item.get('texts'), list) and all(isinstance(text, str) for text in item['texts']) and
                    isinstance(item.get('notes'), list) and all(isinstance(note, str) for note in item['notes']) and
                    isinstance(item.get('tables'), list) and isinstance(item.get('objects'), list) and
                    isinstance(item.get('warnings'), list), 'invalid_inventory', 'brief',
                    'Restore ordered unique source IDs and full slide inventory fields.')
            self.source_ids.append(expected_id)
            if item['warnings']:
                self.warned_ids.append(expected_id)
        self.bound(names['mapping'], evidence.get('mapping_sha256'), 'mapping_changed')
        self.inventory_hash = self.hashes[names['inventory']]
        targets = evidence.get('target_slide_ids')
        require(string_list(targets) and targets and len(set(targets)) == len(targets) and
                all(re.fullmatch(r'S[0-9]{2,}', target) for target in targets),
                'invalid_target_ids', 'outline', 'Supply unique stable target slide IDs.')
        self.targets = targets
        self.mapping(mapping)
        self.evidence = evidence

    def mapping(self, mapping):
        rows = mapping.get('slides')
        require(isinstance(rows, list), 'invalid_mapping', 'outline', 'Map every source slide exactly once.')
        seen, owners = [], {}
        applied = {item['id']: item for item in self.history() if item.get('status') == 'applied' and
                   item.get('decision') == 'approve' and item.get('kind') == 'authorization'}
        for row in rows:
            row = object_value(row, 'outline')
            action, targets = row.get('action'), row.get('targets')
            require(string(row.get('source_slide_id')) and string(row.get('reason')) and
                    string_list(targets) and len(targets) == len(set(targets)) and
                    isinstance(action, str) and action in ('restyle', 'preserve', 'split', 'merge', 'omit'),
                    'invalid_mapping', 'outline', 'Supply valid action, source ID, unique targets and reason.')
            count = len(targets)
            require((action in ('restyle', 'preserve', 'merge') and count == 1) or
                    (action == 'split' and count >= 2) or (action == 'omit' and count == 0),
                    'mapping_cardinality', 'outline', 'Correct the target count for each mapping action.')
            if action != 'restyle' or 'authorization' in row:
                auth = object_value(row.get('authorization'), 'outline')
                interaction_id = auth.get('interaction_id')
                require(string(interaction_id) and interaction_id in applied, 'mapping_authorization_missing', 'outline',
                        'Record the real applied interaction authorizing this nondefault source decision.')
                expected = {'source_sha256': self.source_hash, 'source_slide_id': row['source_slide_id'],
                            'action': action, 'targets': targets}
                scopes = applied[interaction_id].get('source_mapping_authorizations')
                require(isinstance(scopes, list) and expected in scopes, 'mapping_authorization_mismatch', 'outline',
                        'Obtain explicit approval for this exact source hash, page, mapping action and target list.')
            seen.append(row['source_slide_id'])
            for target in targets:
                owners.setdefault(target, []).append(action)
        require(len(seen) == len(set(seen)) and set(seen) == set(self.source_ids) and
                set(owners) == set(self.targets), 'mapping_coverage', 'outline',
                'Cover all source and target pages exactly; omit only with explicit authorization.')
        for actions in owners.values():
            require((len(actions) == 1 and actions[0] != 'merge') or
                    (len(actions) >= 2 and all(action == 'merge' for action in actions)),
                    'mapping_cardinality', 'outline', 'Shared targets require at least two merge source rows.')


def check_run(run_dir, before):
    """Return a structured result; never mutate run or source artifacts."""
    return _check_run(run_dir, before)


def audit_run(run_dir):
    """Audit workflow control state and owned PPTX side effects without mutation."""
    result = {'status': 'BLOCKED', 'before': 'audit', 'errors': []}
    gate = None
    try:
        gate = Gate(run_dir)
        gate.load_run()
        gate.conformance()
        result['status'] = 'PASS'
    except GateError as error:
        result['errors'].append(error.error)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        result['errors'].append({'code': 'invalid_or_unreadable_evidence',
                                 'reentry_stage': gate.stage if gate else 'brief',
                                 'next_action': 'Repair unreadable or malformed evidence (' + type(error).__name__ + ').'})
    return result


def check_active_batch(run_dir):
    """Revalidate import inputs before existing active-batch recovery side effects."""
    return _check_run(run_dir, None, resume_active=True)


def _check_run(run_dir, before, resume_active=False):
    result = {'status': 'BLOCKED', 'before': before, 'errors': []}
    gate = None
    try:
        require(resume_active or before in STAGES, 'invalid_stage', 'brief', 'Choose a supported before stage.')
        gate = Gate(run_dir)
        run = gate.load_run()
        if resume_active:
            before = run.get('stage')
            result['before'] = before
        if 'source_deck' not in run:
            result['status'] = 'NOT_APPLICABLE'
            return result
        gate.conformance()
        if resume_active:
            gate.recovery(resume_active=True)
            gate.active_batch()
        if not resume_active:
            gate.recovery()
        require(run.get('mode') in ('guided', 'auto'), 'invalid_schema', 'brief', 'Use guided or auto mode.')
        require(run.get('deck_id') == gate.root.name, 'run_identity_mismatch', 'brief',
                'Bind run.deck_id to the name of this run directory.')
        gate.import_binding()
        from _workflow_evidence import check_stages
        check_stages(gate, STAGES.index(before))
        result['status'] = 'PASS'
    except GateError as error:
        result['errors'].append(error.error)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        result['errors'].append({'code': 'invalid_or_unreadable_evidence',
                                 'reentry_stage': gate.stage if gate else 'brief',
                                 'next_action': 'Repair unreadable or malformed evidence (' + type(error).__name__ + ').'})
    return result


def snapshot_run(run_dir):
    """Diagnostic hashes only. Deliberately cannot create a review/checkpoint record."""
    result = {'status': 'SNAPSHOT', 'files': {}, 'errors': [],
              'notice': 'Current bytes only; not frozen review evidence and not workflow approval.'}
    try:
        gate = Gate(run_dir)
        gate.load_run()
        pending = [gate.root]
        while pending:
            for path in pending.pop().iterdir():
                name = path.relative_to(gate.root).as_posix()
                safe = gate.path(name)
                if safe.is_dir():
                    pending.append(safe)
                elif safe.is_file():
                    gate.hashes[name] = digest(safe)
        result['files'] = gate.hashes
    except (GateError, OSError, ValueError, TypeError, RecursionError) as error:
        result['status'] = 'BLOCKED'
        result['errors'] = [error.error if isinstance(error, GateError) else
                            {'code': 'snapshot_failed', 'reentry_stage': 'brief',
                             'next_action': 'Repair unreadable or unsafe run files.'}]
    return result
