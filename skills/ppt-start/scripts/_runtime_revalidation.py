"""Journaled invalidation of stale page validation after validator upgrades."""
import base64
import copy
import math
import re

from _generation_runtime import validate_v2_manifest, validate_v2_transaction
from _run_store import canonical, parse_json, sha
from _svg_geometry import GEOMETRY_ERROR_REASONS, GeometryError


VALIDATOR_VERSION = 1
_FIELDS = {
    'schema_version', 'kind', 'slide_id', 'transaction_id', 'candidate_sha256',
    'source_transaction_sha256', 'source_transaction_bytes_base64',
    'source_validation_record', 'failure_reason', 'failure_check', 'failure_details',
    'replacement_transaction_sha256', 'replacement_transaction_bytes_base64',
    'replacement_generation_attempt', 'validator_version', 'title_min_size',
}
_FAILURE_CHECKS = {
    'svg_contract_failed': {'xml', 'office', 'geometry_text'},
    'fact_source_mismatch': {'fact_source'},
    'visual_qa_failed': {'visual'},
}
_ALLOWED_DETAIL_REASONS = GEOMETRY_ERROR_REASONS | frozenset({
    'current_svg_contract_failed', 'current_fact_source_mismatch',
    'current_visual_qa_required',
})
_QA_FIELDS = {
    'schema_version', 'kind', 'slide_id', 'transaction_id', 'candidate_sha256',
    'checks', 'defect_id', 'failure_reason',
}
_TEMP = re.compile(r'S[0-9]+-[0-9a-f]{64}\.json\.[A-Za-z0-9_-]+\.tmp\Z')
_ALLOWED_TAGS = {
    'svg', 'g', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
    'path', 'text', 'tspan', 'title', 'desc',
}


def _require(condition, code='validation_invalidation_conflict'):
    if not condition:
        raise ValueError(code)


def _bounded_number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 10 ** 9


def _details(value):
    _require(isinstance(value, dict) and set(value) <= {'reason', 'bbox', 'bounds', 'element'})
    reason = value.get('reason')
    _require(reason in _ALLOWED_DETAIL_REASONS)
    result = {'reason': reason}
    if 'bbox' in value:
        bbox = value['bbox']
        _require(isinstance(bbox, (list, tuple)) and len(bbox) == 4 and all(_bounded_number(v) for v in bbox))
        result['bbox'] = list(bbox)
    if 'bounds' in value:
        _require(value['bounds'] == [64, 64, 1216, 656])
        result['bounds'] = list(value['bounds'])
    if 'element' in value:
        element = value['element']
        _require(isinstance(element, dict) and set(element) == {'tag', 'index'} and
                 element['tag'] in _ALLOWED_TAGS and type(element['index']) is int and
                 0 <= element['index'] <= 100000)
        result['element'] = dict(element)
    return result


def classify(error):
    """Return a page-local revalidation failure, or None for a global error."""
    if isinstance(error, GeometryError):
        return {'failure_reason': 'svg_contract_failed', 'failure_check': 'geometry_text',
                'failure_details': _details(error.details)}
    if not isinstance(error, ValueError):
        return None
    code = str(error)
    if code == 'svg_contract_failed':
        return {'failure_reason': code, 'failure_check': 'office',
                'failure_details': {'reason': 'current_svg_contract_failed'}}
    if code == 'fact_source_mismatch':
        return {'failure_reason': code, 'failure_check': 'fact_source',
                'failure_details': {'reason': 'current_fact_source_mismatch'}}
    if code == 'visual_qa_required':
        return {'failure_reason': 'visual_qa_failed', 'failure_check': 'visual',
                'failure_details': {'reason': 'current_visual_qa_required'}}
    return None


def _probe_candidate(runtime, transaction, title_min_size, record):
    try:
        raw = runtime.store.read_bytes(transaction['candidate_path'])
        _require(sha(raw) == transaction['candidate_sha256'], 'candidate_hash_mismatch')
        text = raw.decode('utf-8')
        from _svg_runtime import validate_svg
        warnings = []
        validate_svg(text, enriched=True, title_min_size=title_min_size, warnings=warnings)
        if warnings and record['checks']['visual'] != 'passed':
            raise ValueError('visual_qa_required')
        return None
    except GeometryError as error:
        return classify(error)
    except UnicodeError:
        return {'failure_reason': 'svg_contract_failed', 'failure_check': 'xml',
                'failure_details': {'reason': 'current_svg_contract_failed'}}
    except ValueError as error:
        if str(error) in ('candidate_hash_mismatch', 'validation_invalidation_conflict'):
            raise
        code = str(error)
        if code not in ('fact_source_mismatch', 'visual_qa_required'):
            error = ValueError('svg_contract_failed')
        return classify(error)


def probe(runtime, transaction, title_min_size):
    """Recheck only candidate validity; malformed owner/QA evidence remains global."""
    return _probe_candidate(runtime, transaction, title_min_size,
                            runtime.validation_evidence(transaction))


def _journal_path(journal):
    _require(isinstance(journal, dict) and re.fullmatch(r'S[0-9]+', journal.get('slide_id', '')) is not None)
    return '.ppt-pilot/visual-generation-invalidations/{}-{}.json'.format(
        journal['slide_id'], sha(canonical(journal))[7:])


def _qa_record(runtime, transaction):
    _, owner = runtime.qa_owner()
    records = [record for record in owner['records'] if isinstance(record, dict) and
               record.get('transaction_id') == transaction['transaction_id'] and
               record.get('candidate_sha256') == transaction['candidate_sha256']]
    _require(len(records) == 1, 'validation_evidence_missing')
    return records[0]


def _decode(value):
    _require(isinstance(value, str))
    try:
        return base64.b64decode(value.encode('ascii'), validate=True)
    except (UnicodeError, ValueError):
        raise ValueError('validation_invalidation_conflict') from None


def _replacement(source, failure):
    value = copy.deepcopy(source)
    value['state'] = 'failed'
    value['failure_reason'] = failure['failure_reason']
    value['validation']['state'] = 'failed'
    value['validation']['checks'][failure['failure_check']] = 'failed'
    validate_v2_transaction(value)
    return value


def _journal(source_bytes, source, record, failure, title_min_size):
    replacement = _replacement(source, failure)
    replacement_bytes = canonical(replacement)
    return {
        'schema_version': 1,
        'kind': 'visual_generation_validation_invalidation',
        'slide_id': source['slide_id'],
        'transaction_id': source['transaction_id'],
        'candidate_sha256': source['candidate_sha256'],
        'source_transaction_sha256': sha(source_bytes),
        'source_transaction_bytes_base64': base64.b64encode(source_bytes).decode('ascii'),
        'source_validation_record': copy.deepcopy(record),
        'failure_reason': failure['failure_reason'],
        'failure_check': failure['failure_check'],
        'failure_details': _details(failure['failure_details']),
        'replacement_transaction_sha256': sha(replacement_bytes),
        'replacement_transaction_bytes_base64': base64.b64encode(replacement_bytes).decode('ascii'),
        'replacement_generation_attempt': replacement['generation_attempt'],
        'validator_version': VALIDATOR_VERSION,
        'title_min_size': title_min_size,
    }


def _validate(value):
    _require(isinstance(value, dict) and set(value) == _FIELDS and
             type(value['schema_version']) is int and value['schema_version'] == 1 and
             value['kind'] == 'visual_generation_validation_invalidation' and
             type(value['replacement_generation_attempt']) is int and
             type(value['validator_version']) is int and value['validator_version'] == VALIDATOR_VERSION and
             type(value['title_min_size']) in (int, float) and math.isfinite(value['title_min_size']) and
             34 <= value['title_min_size'] <= 4096)
    source_bytes = _decode(value['source_transaction_bytes_base64'])
    replacement_bytes = _decode(value['replacement_transaction_bytes_base64'])
    _require(sha(source_bytes) == value['source_transaction_sha256'] and
             sha(replacement_bytes) == value['replacement_transaction_sha256'])
    source = parse_json(source_bytes)
    replacement = parse_json(replacement_bytes)
    validate_v2_transaction(source)
    validate_v2_transaction(replacement)
    _require(source['state'] == 'validated' and source['validation']['state'] == 'passed' and
             source['slide_id'] == value['slide_id'] and
             source['transaction_id'] == value['transaction_id'] and
             source['candidate_sha256'] == value['candidate_sha256'] and
             source['generation_attempt'] == value['replacement_generation_attempt'])
    failure = {'failure_reason': value['failure_reason'], 'failure_check': value['failure_check'],
               'failure_details': _details(value['failure_details'])}
    _require(failure['failure_reason'] in _FAILURE_CHECKS and
             failure['failure_check'] in _FAILURE_CHECKS[failure['failure_reason']] and
             replacement == _replacement(source, failure))
    detail_reason = failure['failure_details']['reason']
    _require((failure['failure_check'] == 'geometry_text' and detail_reason in GEOMETRY_ERROR_REASONS) or
             (failure['failure_check'] in ('xml', 'office') and detail_reason == 'current_svg_contract_failed') or
             (failure['failure_check'] == 'fact_source' and detail_reason == 'current_fact_source_mismatch') or
             (failure['failure_check'] == 'visual' and detail_reason == 'current_visual_qa_required'))
    record = value['source_validation_record']
    _require(isinstance(record, dict) and set(record) == _QA_FIELDS and
             type(record.get('schema_version')) is int and record['schema_version'] == 1 and
             record.get('kind') == 'visual_generation_qa' and record.get('slide_id') == source['slide_id'] and
             record.get('transaction_id') == source['transaction_id'] and
             record.get('candidate_sha256') == source['candidate_sha256'] and
             record.get('checks') == source['validation']['checks'] and
             record.get('defect_id') is None and record.get('failure_reason') is None)
    return source, replacement, source_bytes, replacement_bytes


def _scan(runtime):
    directory = runtime.store.path('.ppt-pilot/visual-generation-invalidations')
    if not directory.exists():
        return {}
    _require(directory.is_dir())
    result = {}
    identities = set()
    for path in sorted(directory.iterdir()):
        if _TEMP.fullmatch(path.name):
            continue
        _require(path.is_file() and re.fullmatch(r'S[0-9]+-[0-9a-f]{64}\.json', path.name) is not None)
        name = path.relative_to(runtime.store.root).as_posix()
        journal = runtime.store.read_json(name)
        source, replacement, source_bytes, replacement_bytes = _validate(journal)
        _require(name == _journal_path(journal))
        identity = (source['batch_id'], source['transaction_id'])
        _require(identity not in identities)
        identities.add(identity)
        current_record = _qa_record(runtime, source)
        _require(current_record == journal['source_validation_record'])
        actual_failure = _probe_candidate(runtime, source, journal['title_min_size'], current_record)
        _require(actual_failure == {
            'failure_reason': journal['failure_reason'],
            'failure_check': journal['failure_check'],
            'failure_details': journal['failure_details'],
        })
        result[name] = (journal, source, replacement, source_bytes, replacement_bytes)
    return result


def _manifest_graph(runtime, name):
    manifest = runtime.store.read_json(name)
    _require(isinstance(manifest, dict) and manifest.get('kind') == 'visual_generation_batch')
    transactions = {}
    for ref in manifest.get('transaction_refs', []):
        _require(isinstance(ref, str))
        transaction = runtime.store.read_json(ref)
        validate_v2_transaction(transaction)
        transactions[ref] = transaction
    validate_v2_manifest(manifest, transactions)
    return manifest, transactions


def validate_invalidations(runtime, manifest, transactions, journals=None):
    """Verify current manifest bindings and allow only a replayable pre-binding crash."""
    journals = _scan(runtime) if journals is None else journals
    batch_id = manifest['batch_id']
    relevant = {name: value for name, value in journals.items()
                if value[1]['batch_id'] == batch_id}
    bound = manifest.get('validation_invalidation_refs', [])
    hashes = manifest.get('validation_invalidation_sha256', {})
    _require(isinstance(bound, list) and len(bound) == len(set(bound)) and
             isinstance(hashes, dict) and set(hashes) == set(bound) and
             set(bound) <= set(relevant))
    slot = {ref: index for index, ref in enumerate(manifest['transaction_refs'])}
    bound_slots = []
    for name, value in relevant.items():
        journal, source, _, source_bytes, replacement_bytes = value
        ref = '.ppt-pilot/visual-generation-transactions/{}-{}.json'.format(
            source['slide_id'], source['transaction_id'][7:])
        _require(ref in slot)
        current = runtime.store.hash(ref)
        if name in hashes:
            _require(runtime.store.observed[name] == hashes[name] == sha(canonical(journal)) and
                     current in (sha(source_bytes), sha(replacement_bytes)))
            bound_slots.append((slot[ref], name))
        else:
            # A hard crash may leave journal bytes before their manifest binding.
            # It is not authority: advance must reproduce the exact failure before binding it.
            _require(current == sha(source_bytes) and source['state'] == 'validated')
    _require(bound == [name for _, name in sorted(bound_slots)])


def validate_run_invalidations(runtime):
    """Audit journals before every command, including terminal delivery early returns."""
    journals = _scan(runtime)
    batch_names = {'.ppt-pilot/visual-generation-batches/' + value[1]['batch_id'] + '.json'
                   for value in journals.values()}
    directory = runtime.store.path('.ppt-pilot/visual-generation-batches')
    if directory.exists():
        _require(directory.is_dir())
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix == '.json':
                name = path.relative_to(runtime.store.root).as_posix()
                raw = runtime.store.read_bytes(name)
                if (b'"validation_invalidation_refs"' in raw or
                        b'"validation_invalidation_sha256"' in raw):
                    value = parse_json(raw)
                    if isinstance(value, dict):
                        batch_names.add(name)
    for name in sorted(batch_names):
        manifest, transactions = _manifest_graph(runtime, name)
        validate_invalidations(runtime, manifest, transactions, journals)


def invalidate(runtime, manifest, transactions, ref, failure, title_min_size):
    """Journal then replace only one currently validated transaction; replay is idempotent."""
    source = transactions[ref]
    _require(source['state'] == 'validated')
    source_bytes = runtime.store.read_bytes(ref)
    expected = _journal(source_bytes, source, _qa_record(runtime, source), failure, title_min_size)
    name = _journal_path(expected)
    observed = runtime.store.hash(name)
    if observed == 'none':
        runtime.store.write_json(name, expected, 'none')
        journal = expected
    else:
        journal = runtime.store.read_json(name)
        _require(journal == expected)
    frozen_source, replacement, frozen_bytes, replacement_bytes = _validate(journal)
    _require(frozen_source == source and frozen_bytes == source_bytes)
    journal_hash = sha(canonical(journal))
    bound = list(manifest.get('validation_invalidation_refs', []))
    hashes = dict(manifest.get('validation_invalidation_sha256', {}))
    if name not in bound:
        bound.append(name)
        hashes[name] = journal_hash
        manifest['validation_invalidation_refs'] = bound
        manifest['validation_invalidation_sha256'] = hashes
        runtime.persist_graph(manifest, transactions, [])
    else:
        _require(hashes.get(name) == journal_hash)
    _require(runtime.store.hash(name) == journal_hash)
    current = runtime.store.hash(ref)
    if current == journal['source_transaction_sha256']:
        runtime.store.write_bytes(ref, replacement_bytes, current)
    elif current != journal['replacement_transaction_sha256']:
        raise ValueError('validation_invalidation_conflict')
    transactions[ref] = replacement
    runtime.persist_graph(manifest, transactions, [])
    return {'slide_id': replacement['slide_id'], 'transaction_id': replacement['transaction_id'],
            'failure_reason': replacement['failure_reason'], 'journal_path': name,
            'generation_attempt': replacement['generation_attempt']}
