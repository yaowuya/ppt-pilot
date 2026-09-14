"""Read-only construction and validation of manuscript review snapshots."""
import hashlib
import re

from _run_store import RunStore, canonical, parse_json, sha


CHINESE_MANUSCRIPT_FILES = (
    '.ppt-pilot/简报.md',
    '.ppt-pilot/研究.md',
    '.ppt-pilot/来源.md',
    '大纲.md',
    '.ppt-pilot/故事板.md',
)
ENGLISH_MANUSCRIPT_FILES = (
    '.ppt-pilot/brief.md',
    '.ppt-pilot/research.md',
    '.ppt-pilot/sources.md',
    'outline.md',
    '.ppt-pilot/storyboard.md',
)
MANUSCRIPT_FILE_SETS = (CHINESE_MANUSCRIPT_FILES, ENGLISH_MANUSCRIPT_FILES)
STORYBOARD_FILES = {CHINESE_MANUSCRIPT_FILES[-1], ENGLISH_MANUSCRIPT_FILES[-1]}
_HASH = re.compile(r'^[0-9a-f]{64}$')
_SNAPSHOT_ID = re.compile(r'^sha256:[0-9a-f]{64}$')
_STRUCTURED_FENCE = re.compile(
    rb'(?m)^```ppt-pilot-json(?:\r\n|\n)'
    rb'(?P<payload>.*?)'
    rb'(?:\r\n|\n)```(?=(?:\r\n|\n)|\Z)',
    re.DOTALL,
)


class ReviewSnapshotError(ValueError):
    """Stable internal failure code for fail-closed snapshot validation."""


def _fail(code):
    raise ReviewSnapshotError(code)


def _hex(data):
    return hashlib.sha256(data).hexdigest()


def _string_list(value):
    return (isinstance(value, list) and
            all(isinstance(item, str) and item for item in value) and
            len(value) == len(set(value)))


def _validate_revision_ids(value):
    if not _string_list(value):
        _fail('storyboard_projection_invalid')
    numbers = []
    for revision_id in value:
        match = re.fullmatch(r'visual-revision-([0-9]+)', revision_id)
        if match is None:
            _fail('storyboard_projection_invalid')
        numbers.append(int(match.group(1)))
    if numbers != sorted(numbers):
        _fail('storyboard_projection_invalid')


def _project_storyboard(raw):
    """Project only the explicitly authorized structured-owner paths."""
    markers = raw.count(b'```ppt-pilot-json')
    if markers == 0:
        return None
    try:
        raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        _fail('storyboard_projection_invalid')
    offset = 3 if raw.startswith(b'\xef\xbb\xbf') else 0
    matches = list(_STRUCTURED_FENCE.finditer(raw[offset:]))
    if markers != 1 or len(matches) != 1:
        _fail('storyboard_projection_invalid')
    match = matches[0]
    try:
        value = parse_json(match.group('payload'))
    except (UnicodeDecodeError, ValueError):
        _fail('storyboard_projection_invalid')
    if not isinstance(value, dict):
        _fail('storyboard_projection_invalid')
    if type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        _fail('storyboard_projection_invalid')
    snapshot_id = value.get('storyboard_snapshot_id')
    if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID.fullmatch(snapshot_id):
        _fail('storyboard_projection_invalid')
    slides = value.get('slides')
    if not isinstance(slides, list) or not slides:
        _fail('storyboard_projection_invalid')
    if 'applied_visual_revision_ids' in value:
        _validate_revision_ids(value['applied_visual_revision_ids'])

    projected = dict(value)
    projected.pop('storyboard_snapshot_id', None)
    projected.pop('applied_visual_revision_ids', None)
    projected_slides = []
    for member in slides:
        if not isinstance(member, dict):
            _fail('storyboard_projection_invalid')
        for field in ('layout_family', 'visual_intent'):
            if not isinstance(member.get(field), str) or not member[field].strip():
                _fail('storyboard_projection_invalid')
        if 'applied_visual_revision_ids' in member:
            _validate_revision_ids(member['applied_visual_revision_ids'])
        projected_member = dict(member)
        projected_member.pop('applied_visual_revision_ids', None)
        projected_member.pop('layout_family', None)
        projected_member.pop('visual_intent', None)
        projected_slides.append(projected_member)
    projected['slides'] = projected_slides
    start = offset + match.start()
    end = offset + match.end()
    return {
        'format': 'ppt-pilot-storyboard-content-v1',
        'prefix_sha256': _hex(raw[:start]),
        'storyboard': projected,
        'suffix_sha256': _hex(raw[end:]),
    }


def semantic_hash(name, raw):
    """Return an unprefixed semantic digest; non-storyboard files stay byte-bound."""
    if name not in STORYBOARD_FILES:
        return _hex(raw)
    projection = _project_storyboard(raw)
    if projection is None:
        return _hex(raw)
    return _hex(canonical(projection).rstrip(b'\n'))


def semantic_file_hashes(files, read_bytes):
    result = {}
    for name in files:
        try:
            raw = read_bytes(name)
        except (FileNotFoundError, OSError, ValueError):
            _fail('storyboard_projection_invalid' if name in STORYBOARD_FILES
                  else 'manuscript_files_invalid')
        result[name] = semantic_hash(name, raw)
    return result


def _normalized_files(files, canonical=False):
    if not isinstance(files, (list, tuple)) or len(files) != 5 or not all(
            isinstance(name, str) for name in files):
        _fail('manuscript_files_invalid')
    matches = [candidate for candidate in MANUSCRIPT_FILE_SETS
               if set(files) == set(candidate)]
    if len(matches) != 1:
        _fail('manuscript_files_invalid')
    if canonical:
        return matches[0]
    return tuple(files)


def _hash_map(value, files):
    if (not isinstance(value, dict) or set(value) != set(files) or
            any(not isinstance(value[name], str) or not _HASH.fullmatch(value[name])
                for name in files)):
        _fail('review_snapshot_mismatch')
    return {name: value[name] for name in files}


def review_snapshot_id(files, file_hashes, semantic_hashes):
    """Compute the immutable v1 identity over both exact and semantic bindings."""
    payload = {
        'schema_version': 1,
        'kind': 'manuscript_review_snapshot',
        'files': list(files),
        'file_hashes': {name: file_hashes[name] for name in files},
        'semantic_file_hashes': {name: semantic_hashes[name] for name in files},
    }
    return sha(canonical(payload).rstrip(b'\n'))


def create_review_snapshot(store, files=None):
    """Compute, but never persist or approve, one complete review snapshot."""
    if not isinstance(store, RunStore):
        store = RunStore(store)
    if files is None:
        complete = []
        for candidate in MANUSCRIPT_FILE_SETS:
            try:
                for name in candidate:
                    store.read_bytes(name)
            except (FileNotFoundError, OSError, ValueError):
                continue
            complete.append(candidate)
        if len(complete) != 1:
            _fail('manuscript_files_invalid')
        files = complete[0]
    files = _normalized_files(files, canonical=True)
    raw_by_file = {}
    for name in files:
        try:
            raw_by_file[name] = store.read_bytes(name)
        except (FileNotFoundError, OSError, ValueError):
            _fail('manuscript_files_invalid')
    exact = {name: _hex(raw_by_file[name]) for name in files}
    semantic = {name: semantic_hash(name, raw_by_file[name]) for name in files}
    return {
        'snapshot_id': review_snapshot_id(files, exact, semantic),
        'files': list(files),
        'file_hashes': exact,
        'semantic_file_hashes': semantic,
    }


def validate_review_snapshot(snapshot, current_file_hashes, read_bytes):
    """Validate a frozen snapshot against current files without granting approval."""
    if not isinstance(snapshot, dict):
        _fail('review_snapshot_mismatch')
    files = _normalized_files(snapshot.get('files'))
    exact = _hash_map(snapshot.get('file_hashes'), files)
    if (not isinstance(current_file_hashes, dict) or
            set(current_file_hashes) != set(files) or
            any(not isinstance(current_file_hashes[name], str) or
                not _HASH.fullmatch(current_file_hashes[name]) for name in files)):
        _fail('review_snapshot_mismatch')

    if 'semantic_file_hashes' not in snapshot:
        if exact != current_file_hashes:
            _fail('manuscript_stale')
        if not isinstance(snapshot.get('snapshot_id'), str) or not snapshot['snapshot_id']:
            _fail('review_snapshot_mismatch')
        return 'legacy'

    if set(snapshot) != {'snapshot_id', 'files', 'file_hashes', 'semantic_file_hashes'}:
        _fail('review_snapshot_mismatch')
    if files != _normalized_files(files, canonical=True):
        _fail('review_snapshot_mismatch')
    semantic = _hash_map(snapshot.get('semantic_file_hashes'), files)
    if any(semantic[name] != exact[name] for name in files if name not in STORYBOARD_FILES):
        _fail('review_snapshot_mismatch')
    expected_id = review_snapshot_id(files, exact, semantic)
    if snapshot.get('snapshot_id') != expected_id:
        _fail('review_snapshot_mismatch')
    try:
        current_semantic = semantic_file_hashes(files, read_bytes)
    except ReviewSnapshotError as exc:
        if str(exc) == 'storyboard_projection_invalid':
            _fail('manuscript_stale')
        raise
    if current_semantic != semantic:
        _fail('manuscript_stale')
    return 'semantic'


def review_snapshot(run_dir):
    """Read-only CLI/API result. SNAPSHOT is diagnostic and never means PASS."""
    try:
        frozen = create_review_snapshot(RunStore(run_dir))
    except ReviewSnapshotError as exc:
        code = str(exc)
        if code != 'manuscript_files_invalid':
            code = 'review_snapshot_invalid'
        return {
            'status': 'BLOCKED',
            'errors': [{
                'code': code,
                'next_action': 'Fix the five manuscript owners, then compute a fresh review snapshot.',
            }],
        }
    except (OSError, ValueError):
        return {
            'status': 'BLOCKED',
            'errors': [{
                'code': 'review_snapshot_invalid',
                'next_action': 'Fix the five manuscript owners, then compute a fresh review snapshot.',
            }],
        }
    return {
        'status': 'SNAPSHOT',
        'reviewed_file_snapshot': frozen,
        'notice': 'Diagnostic only: this command never approves a manuscript or grants review PASS.',
    }
