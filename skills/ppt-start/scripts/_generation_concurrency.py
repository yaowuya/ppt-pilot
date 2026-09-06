"""Pure, bounded automatic SVG dispatch planning; no host or filesystem changes."""
import re


OUTCOMES = ('validated', 'rate_limited', 'timeout', 'capacity_limited', 'failed')


def blocked_result(reason):
    """Use the same fail-closed shape for input and CLI decoding errors."""
    return {'schema_version': 1, 'status': 'BLOCKED', 'target_concurrency': 5,
            'effective_concurrency': 0, 'available_slots': 0, 'dispatch_slide_ids': [],
            'limitations': ['invalid_observation'], 'reason': reason}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _slide_ids(value):
    _require(isinstance(value, list), 'Slide inventories must be lists.')
    _require(all(isinstance(item, str) and re.fullmatch(r'S[0-9]{2,}', item) and
                 any(char != '0' for char in item[1:]) for item in value),
             'Slide IDs must be stable positive S01-style identifiers.')
    _require(len(value) == len(set(value)), 'Slide inventories must contain unique IDs.')
    return value


def _validate(value):
    _require(isinstance(value, dict), 'Observation must be a JSON object.')
    required = {'schema_version', 'capabilities', 'ready_slide_ids', 'in_flight_slide_ids'}
    _require(required <= set(value) <= required | {'history', 'batch_width', 'blocked'},
             'Observation has missing or unsupported fields.')
    _require(type(value['schema_version']) is int and value['schema_version'] == 1,
             'Observation schema_version must be integer 1.')
    capabilities = value['capabilities']
    _require(isinstance(capabilities, dict) and set(capabilities) ==
             {'fresh_isolation', 'concurrent_tasks', 'durable_lookup', 'worker_capacity'},
             'Capabilities must contain exactly the four supported fields.')
    _require(all(type(capabilities[key]) is bool for key in
                 ('fresh_isolation', 'concurrent_tasks', 'durable_lookup')),
             'Capability flags must be booleans.')
    capacity = capabilities['worker_capacity']
    _require(capacity is None or (type(capacity) is int and capacity >= 0),
             'worker_capacity must be a nonnegative integer or null.')
    ready = _slide_ids(value['ready_slide_ids'])
    in_flight = _slide_ids(value['in_flight_slide_ids'])
    _require(not set(ready).intersection(in_flight), 'Ready and in-flight inventories must be disjoint.')
    _require(type(value.get('blocked', False)) is bool, 'blocked must be a boolean.')
    if 'batch_width' in value:
        _require(type(value['batch_width']) is int and 1 <= value['batch_width'] <= 10,
                 'Active batch_width must be an integer from 1 through 10.')
    history = value.get('history', [])
    _require(isinstance(history, list), 'History must be a list of durable events.')
    seen, consecutive = {}, 0
    for event in history:
        _require(isinstance(event, dict) and set(event) == {'event_id', 'outcome'},
                 'Each history event must contain exactly event_id and outcome.')
        event_id, outcome = event['event_id'], event['outcome']
        _require(isinstance(event_id, str) and bool(event_id.strip()), 'History event_id must be nonempty text.')
        _require(isinstance(outcome, str) and outcome in OUTCOMES, 'History outcome is unsupported.')
        if event_id in seen:
            _require(seen[event_id] == outcome, 'Conflicting duplicate history event.')
            continue
        seen[event_id] = outcome
        consecutive = consecutive + 1 if outcome == 'validated' else 0
    return capabilities, ready, in_flight, consecutive


def plan_dispatch(observation):
    """Plan from the caller's latest frozen-scope observation without mutating it.

    Capacity includes this run's in-flight generators, but excludes its coordinator
    and unrelated tasks. The caller records dispatch ownership before polling again;
    this pure calculation neither launches workers nor reserves capacity.
    """
    try:
        capabilities, ready, in_flight, consecutive = _validate(observation)
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        return blocked_result('Invalid observation: ' + str(error))
    target = min(10, 5 + 2 * (consecutive // 5))
    result = {'schema_version': 1, 'status': 'WAIT', 'target_concurrency': target,
              'effective_concurrency': 0, 'available_slots': 0, 'dispatch_slide_ids': [],
              'limitations': [], 'reason': ''}
    limitations = result['limitations']
    if observation.get('blocked', False):
        result.update(status='BLOCKED', reason='Resolve the existing workflow blocker before dispatch.')
        limitations.append('upstream_blocked')
        return result
    if not capabilities['fresh_isolation']:
        result.update(status='BLOCKED', reason='Fresh isolated generation is unavailable; no dispatch is safe.')
        limitations.append('fresh_isolation_unavailable')
        return result
    capacity = capabilities['worker_capacity']
    if capacity is None:
        capacity = 1
        limitations.append('worker_capacity_unknown')
    elif capacity < target:
        limitations.append('worker_capacity_limited')
    safety_cap = target
    if not capabilities['concurrent_tasks'] or not capabilities['durable_lookup']:
        safety_cap = 1
        limitations.append('capability_limited')
    batch_cap = observation.get('batch_width', target)
    if batch_cap < target:
        limitations.append('legacy_batch_cap')
    remaining = len(ready) + len(in_flight)
    if remaining < target:
        limitations.append('remaining_work_limited')
    effective = min(target, capacity, safety_cap, batch_cap, remaining)
    slots = max(0, effective - len(in_flight))
    dispatch = ready[:slots]
    result.update(effective_concurrency=effective, available_slots=slots, dispatch_slide_ids=dispatch)
    if len(in_flight) > effective:
        limitations.append('in_flight_exceeds_limit')
        result['reason'] = 'Existing workers exceed the current limit; wait without canceling or duplicating them.'
    elif capacity == 0:
        result['reason'] = 'No generator slots are currently allocated to this run; wait for capacity.'
    elif remaining == 0:
        result['reason'] = 'No ready or in-flight slides remain in this generation scope.'
    elif dispatch:
        result['status'] = 'READY'
        result['reason'] = ('Dispatch %d ready slide(s); target %d, effective limit %d, %d already in flight.' %
                            (len(dispatch), target, effective, len(in_flight)))
    else:
        result['reason'] = 'All currently available slots are occupied; wait for a durable completion or capacity change.'
    return result
