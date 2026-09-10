"""Closed host registry validation; receipts never register adapters."""
from pathlib import Path
from _run_store import no_follow, parse_json, sha

FIELDS = {'schema_version', 'kind', 'host', 'adapter_id', 'adapter_version',
          'adapter_digest', 'observation', 'evidence'}
OBSERVATIONS = {'native_fresh_isolation', 'remote_fresh_isolation', 'concurrent_tasks',
    'durable_lookup', 'worker_capacity', 'prompt_by_value', 'fresh_history',
    'filesystem_none', 'data_tools_none', 'attribution', 'nested_cli_required',
    'credential_probe_required', 'current_context_only'}


def validate_capability(receipt):
    root = Path(__file__).resolve().parents[1]
    registry_path = root / 'assets/host-adapters.json'
    no_follow(registry_path)
    registry = parse_json(registry_path.read_bytes())
    if (not isinstance(receipt, dict) or set(receipt) != FIELDS or
        type(receipt['schema_version']) is not int or receipt['schema_version'] != 1 or
        receipt['kind'] != 'host_capability' or registry.get('schema_version') != 1):
        raise ValueError('generator_unavailable')
    entries = [entry for entry in registry['adapters'] if
               (entry['host'], entry['adapter_id'], entry['adapter_version'], entry['adapter_digest']) ==
               tuple(receipt[k] for k in ('host', 'adapter_id', 'adapter_version', 'adapter_digest'))]
    if len(entries) != 1:
        raise ValueError('generator_unavailable')
    entry, obs, evidence = entries[0], receipt['observation'], receipt['evidence']
    if not isinstance(obs, dict) or set(obs) != OBSERVATIONS:
        raise ValueError('generator_unavailable')
    if any(type(value) is not bool for key, value in obs.items() if key != 'worker_capacity'):
        raise ValueError('generator_unavailable')
    if obs['worker_capacity'] is not None and (type(obs['worker_capacity']) is not int or obs['worker_capacity'] < 0):
        raise ValueError('generator_unavailable')
    # Fresh conversation context and tool isolation are separate capabilities.
    isolated_tools = receipt['host'] == 'claude-code'
    fixed = {'native_fresh_isolation': True, 'remote_fresh_isolation': False,
             'prompt_by_value': True, 'fresh_history': True, 'filesystem_none': isolated_tools,
             'data_tools_none': isolated_tools, 'attribution': True, 'nested_cli_required': False,
             'credential_probe_required': False, 'current_context_only': False}
    if any(obs[k] != v for k, v in fixed.items()) or not isinstance(evidence, dict):
        raise ValueError('generator_unavailable')
    if receipt['host'] == 'claude-code':
        expected = {'agent_name': 'ppt-svg-generator', 'loaded_agent_sha256': entry['adapter_digest'],
            'spawn_primitive': 'fresh-context-subagent', 'allowed_tools': ['TodoWrite'],
            'ambient_context': ['CLAUDE.md', 'parent_git_status'], 'isolation': 'omitted',
            'result_type': 'text'}
        # Only the installed sibling agents directory is authoritative.
        instruction = root.parent.parent / 'agents/ppt-svg-generator.md'
    elif receipt['host'] == 'deepseek-harness':
        expected = {'tool_name': 'subagent', 'instruction_sha256': entry['adapter_digest'],
            'spawn_primitive': 'fresh-context-subagent', 'tool_policy': 'inherited-not-isolated',
            'ambient_context': ['deployment_system_prompt', 'agent_preset', 'workspace_instructions'],
            'result_type': 'text', 'attribution_type': 'subagent_id'}
        # Plugin-owned instructions, not DSH_HOME, presets, or a receipt-controlled path.
        instruction = root / 'references/deepseek-harness.md'
    else:
        raise ValueError('generator_unavailable')
    if set(evidence) != set(expected) | {'session_id'} or any(evidence[k] != v for k, v in expected.items()):
        raise ValueError('generator_unavailable')
    no_follow(instruction)
    try:
        raw = instruction.read_bytes().decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
        actual = sha((raw.rstrip('\n') + '\n').encode('utf-8'))
    except (OSError, UnicodeError):
        raise ValueError('generator_unavailable')
    if (not isinstance(evidence['session_id'], str) or not evidence['session_id'].strip() or
            actual != entry['adapter_digest']):
        raise ValueError('generator_unavailable')
    capacity = obs['worker_capacity']
    width = 1 if capacity is None or not (obs['concurrent_tasks'] and obs['durable_lookup']) else min(capacity, 5)
    return dict(receipt, selected_width=0 if capacity == 0 else width)
