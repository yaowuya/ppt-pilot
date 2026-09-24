"""Shared completeness and evidence contract for full and partial deliveries."""
import hashlib
import json
import re
from collections.abc import Mapping


PAGE_FAILURE_REASONS = frozenset({
    'generator_refused', 'generator_timeout', 'generator_output_malformed',
    'svg_contract_failed', 'fact_source_mismatch', 'visual_qa_failed',
})
DELIVERY_FIELDS = frozenset({
    'schema_version', 'status', 'policy', 'target_slide_ids', 'delivered_slide_ids',
    'missing_slides', 'storyboard_sha256', 'theme_sha256', 'quality_report_sha256', 'slide_sha256',
})
MISSING_FIELDS = frozenset({
    'slide_id', 'reason', 'failure_reason', 'generation_attempt',
    'transaction_id', 'transaction_ref', 'transaction_sha256',
})
_SHA = re.compile(r'sha256:[0-9a-f]{64}\Z')
_SLIDE = re.compile(r'S[0-9]{1,6}\Z')
_BATCH = re.compile(r'[a-z0-9][a-z0-9-]{0,127}\Z')


def _require(condition, reason='invalid'):
    if not condition:
        raise ValueError('delivery_' + reason)


def _sha(value):
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _ids(value):
    _require(isinstance(value, (list, tuple)) and len(value) <= 1000)
    _require(all(isinstance(item, str) and _SLIDE.fullmatch(item) for item in value))
    _require(len(value) == len(set(value)), 'partition_invalid')
    return list(value)


def validate_delivery(value, target_slide_ids=None, *, final=False):
    _require(isinstance(value, Mapping) and set(value) == DELIVERY_FIELDS)
    _require(type(value['schema_version']) is int and value['schema_version'] == 1)
    status, policy = value['status'], value['policy']
    _require(isinstance(status, str) and status in {'prepared', 'complete', 'partial', 'failed'})
    _require(isinstance(policy, str) and policy in {'strict', 'best_effort'})
    if final:
        _require(status in {'complete', 'partial'}, 'not_final')
    targets, delivered = _ids(value['target_slide_ids']), _ids(value['delivered_slide_ids'])
    _require(bool(targets), 'partition_invalid')
    if target_slide_ids is not None:
        _require(targets == list(target_slide_ids), 'targets_changed')
    missing = value['missing_slides']
    _require(isinstance(missing, (list, tuple)) and len(missing) <= len(targets))
    missing_ids = []
    for item in missing:
        _require(isinstance(item, Mapping) and set(item) == MISSING_FIELDS)
        sid = item['slide_id']
        _require(isinstance(sid, str) and _SLIDE.fullmatch(sid))
        _require(isinstance(item['reason'], str) and item['reason'] in {'attempts_exhausted', 'user_skipped'})
        _require(isinstance(item['failure_reason'], str) and item['failure_reason'] in PAGE_FAILURE_REASONS)
        attempt = item['generation_attempt']
        _require(type(attempt) is int and 0 <= attempt <= 10000)
        _require(item['reason'] != 'attempts_exhausted' or attempt >= 3, 'budget_not_exhausted')
        _require(_sha(item['transaction_id']) and _sha(item['transaction_sha256']))
        expected = '.ppt-pilot/visual-generation-transactions/' + sid + '-' + item['transaction_id'][7:] + '.json'
        _require(item['transaction_ref'] == expected, 'transaction_mismatch')
        missing_ids.append(sid)
    _require(len(missing_ids) == len(set(missing_ids)), 'partition_invalid')
    _require(not set(delivered) & set(missing_ids) and set(delivered) | set(missing_ids) == set(targets), 'partition_invalid')
    _require(delivered == [sid for sid in targets if sid in delivered] and
             missing_ids == [sid for sid in targets if sid in missing_ids], 'order_invalid')
    _require(status != 'complete' or bool(delivered) and not missing, 'status_mismatch')
    _require(status != 'partial' or bool(delivered) and bool(missing) and policy == 'best_effort', 'status_mismatch')
    _require(status != 'failed' or not delivered, 'status_mismatch')
    _require(status != 'prepared' or bool(delivered), 'status_mismatch')
    _require(not missing or not delivered or policy == 'best_effort', 'partial_not_authorized')
    _require(_sha(value['storyboard_sha256']) and _sha(value['theme_sha256']))
    quality = value['quality_report_sha256']
    _require(_sha(quality) if status in {'complete', 'partial'} else quality is None or _sha(quality))
    hashes = value['slide_sha256']
    _require(isinstance(hashes, Mapping) and set(hashes) == set(delivered) and all(_sha(v) for v in hashes.values()))
    return value


def validate_delivery_review_state(run):
    """Delivery declarations cannot contradict the workflow's content-gate state."""
    review = run.get('manuscript_review')
    _require(isinstance(review, Mapping), 'manuscript_not_approved')
    findings = review.get('open_blocking_findings')
    _require(review.get('required') is True and review.get('state') == 'manuscript_approved' and
             review.get('status') == 'PASSED' and isinstance(findings, (list, tuple)) and
             not findings and review.get('pending_round') is None, 'manuscript_not_approved')


def _json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result)
            result[key] = value
        return result
    try:
        value = json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError('delivery_evidence_invalid') from exc
    _require(isinstance(value, dict), 'evidence_invalid')
    return value


def verify_delivery_evidence(value, read_bytes, *, storyboard_path, theme_path,
                             quality_report_path, target_slide_ids=None, final=True):
    """The caller supplies its own safe, read-only, run-relative artifact reader."""
    validate_delivery(value, target_slide_ids, final=final)

    def bound(path, expected):
        try:
            data = read_bytes(path)
        except (OSError, KeyError, ValueError) as exc:
            raise ValueError('delivery_evidence_unreadable') from exc
        _require('sha256:' + hashlib.sha256(data).hexdigest() == expected, 'evidence_stale')
        return data

    bound(storyboard_path, value['storyboard_sha256'])
    bound(theme_path, value['theme_sha256'])
    if value['quality_report_sha256'] is not None:
        bound(quality_report_path, value['quality_report_sha256'])
    for sid, expected in value['slide_sha256'].items():
        bound('slides/' + sid + '.svg', expected)
    for item in value['missing_slides']:
        tx = _json(bound(item['transaction_ref'], item['transaction_sha256']))
        _require(tx.get('schema_version') == 2 and tx.get('kind') == 'visual_generation_transaction' and
                 tx.get('state') == 'failed' and all(tx.get(key) == item[key] for key in
                    ('slide_id', 'transaction_id', 'failure_reason', 'generation_attempt')), 'transaction_mismatch')
        batch_id = tx.get('batch_id')
        _require(isinstance(batch_id, str) and _BATCH.fullmatch(batch_id), 'transaction_mismatch')
        try:
            manifest = _json(read_bytes('.ppt-pilot/visual-generation-batches/' + batch_id + '.json'))
        except (OSError, KeyError, ValueError) as exc:
            raise ValueError('delivery_evidence_unreadable') from exc
        ids, refs = manifest.get('ordered_slide_ids'), manifest.get('transaction_refs')
        omitted = manifest.get('omitted_transaction_refs')
        sealed = manifest.get('omitted_transaction_sha256')
        _require(manifest.get('batch_id') == batch_id and manifest.get('state') in ('partial', 'failed') and
                 isinstance(ids, list) and isinstance(refs, list) and len(ids) == len(refs) and
                 isinstance(omitted, list) and item['transaction_ref'] in omitted and
                 isinstance(sealed, dict) and sealed.get(item['transaction_ref']) == item['transaction_sha256'],
                 'omission_unbound')
        _require(ids.count(item['slide_id']) == 1 and refs[ids.index(item['slide_id'])] == item['transaction_ref'],
                 'omission_unbound')
    return value
