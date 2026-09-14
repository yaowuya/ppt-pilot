"""Closed host registry validation and read-only installed-adapter diagnostics."""
from pathlib import Path, PureWindowsPath
from _run_store import RunStore, no_follow, parse_json, sha

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'assets/host-adapters.json'
IDENTITY = ('host', 'adapter_id', 'adapter_version', 'adapter_digest')
FIELDS = {'schema_version', 'kind', *IDENTITY, 'observation', 'evidence'}
OBSERVATIONS = {'native_fresh_isolation', 'remote_fresh_isolation', 'concurrent_tasks',
    'durable_lookup', 'worker_capacity', 'prompt_by_value', 'fresh_history',
    'filesystem_none', 'data_tools_none', 'attribution', 'nested_cli_required',
    'credential_probe_required', 'current_context_only'}


class CapabilityError(ValueError):
    """Keep the canonical blocker code; details belong only to diagnostics."""
    def __init__(self, reason, field, expected=None):
        super().__init__('generator_unavailable')
        self.details = {'reason': reason, 'field': field, 'skill_root': str(ROOT),
                        'registry_path': str(REGISTRY)}
        if expected is not None:
            self.details['expected'] = expected
        self.next_action = ('Check this installed Skill with inspect-host. Rebuild capability from '
            'its registered identity and current host observations; do not reuse stale evidence '
            'or edit canonical run owners. Installation/digest failures require a matching Skill update.')


def _registry_entries():
    try:
        no_follow(REGISTRY)
        registry = parse_json(REGISTRY.read_bytes())
    except (OSError, ValueError):
        raise CapabilityError('registry_unreadable', 'registry_path')
    if (not isinstance(registry, dict) or type(registry.get('schema_version')) is not int or
        registry['schema_version'] != 1 or not isinstance(registry.get('adapters'), list) or
        any(not isinstance(entry, dict) or set(entry) != set(IDENTITY) or
            any(not isinstance(entry[key], str) or not entry[key] for key in IDENTITY)
            for entry in registry['adapters'])):
        raise CapabilityError('invalid_registry', 'registry_path')
    identities = [tuple(entry[key] for key in IDENTITY) for entry in registry['adapters']]
    if len(identities) != len(set(identities)):
        raise CapabilityError('invalid_registry', 'registry_path')
    return registry['adapters']


def _claude_instruction_path(filename):
    """Resolve only package-owned source or installed Claude Agent locations."""
    package_root = ROOT.parent.parent
    source_root = package_root / 'hosts/claude-code/agents'
    if source_root.is_dir():
        return source_root / filename
    return package_root / 'agents' / filename


def _adapter_spec(entry):
    host, adapter_id = entry['host'], entry['adapter_id']
    if host == 'claude-code' and adapter_id == 'ppt-svg-generator':
        fixed = {'native_fresh_isolation': True, 'remote_fresh_isolation': False,
                 'prompt_by_value': True, 'fresh_history': True, 'filesystem_none': True,
                 'data_tools_none': True, 'attribution': True, 'nested_cli_required': False,
                 'credential_probe_required': False, 'current_context_only': False}
        expected = {'agent_name': 'ppt-svg-generator', 'loaded_agent_sha256': entry['adapter_digest'],
            'spawn_primitive': 'fresh-context-subagent', 'allowed_tools': ['TodoWrite'],
            'ambient_context': ['CLAUDE.md', 'parent_git_status'], 'isolation': 'omitted',
            'result_type': 'text'}
        instruction = _claude_instruction_path('ppt-svg-generator.md')
    elif host == 'claude-code' and adapter_id == 'ppt-svg-generator-sdk':
        fixed = {'native_fresh_isolation': True, 'remote_fresh_isolation': False,
                 'prompt_by_value': True, 'fresh_history': True, 'filesystem_none': True,
                 'data_tools_none': True, 'attribution': True, 'nested_cli_required': False,
                 'credential_probe_required': False, 'current_context_only': False}
        expected = {'agent_name': 'ppt-svg-generator-sdk',
            'loaded_agent_sha256': entry['adapter_digest'],
            'spawn_primitive': 'fresh-context-subagent', 'allowed_tools': ['ListAgents'],
            'ambient_context': ['CLAUDE.md', 'parent_git_status'],
            'isolation': ('omitted', 'worktree'), 'execution_mode': 'foreground',
            'result_type': 'text'}
        instruction = _claude_instruction_path('ppt-svg-generator-sdk.md')
    elif host == 'deepseek-harness' and adapter_id == 'native-subagent':
        fixed = {'native_fresh_isolation': True, 'remote_fresh_isolation': False,
                 'prompt_by_value': True, 'fresh_history': True, 'filesystem_none': False,
                 'data_tools_none': False, 'attribution': True, 'nested_cli_required': False,
                 'credential_probe_required': False, 'current_context_only': False}
        expected = {'tool_name': 'subagent', 'instruction_sha256': entry['adapter_digest'],
            'spawn_primitive': 'fresh-context-subagent', 'tool_policy': 'inherited-not-isolated',
            'ambient_context': ['deployment_system_prompt', 'agent_preset', 'workspace_instructions'],
            'result_type': 'text', 'attribution_type': 'subagent_id'}
        # Plugin-owned instructions, never DSH configuration or a receipt-controlled path.
        instruction = ROOT / 'references/deepseek-harness.md'
    else:
        raise CapabilityError('adapter_not_registered', 'adapter_id')
    return entry, fixed, expected, instruction


def _adapter_for_host(host):
    entries = [entry for entry in _registry_entries() if entry['host'] == host]
    if not entries or host not in ('claude-code', 'deepseek-harness'):
        raise CapabilityError('adapter_not_registered', 'host')
    if len(entries) > 1:
        legacy = [entry for entry in entries if entry['adapter_id'] == 'ppt-svg-generator']
        if host != 'claude-code' or len(legacy) != 1:
            raise CapabilityError('adapter_not_registered', 'host')
        entries = legacy + [entry for entry in entries if entry not in legacy]
        for entry in entries:
            try:
                spec = _adapter_spec(entry)
                _verify_instruction(spec[0], spec[3])
            except CapabilityError:
                continue
            return spec
    return _adapter_spec(entries[0])


def _adapter_for_receipt(receipt):
    host = receipt['host']
    entries = [entry for entry in _registry_entries() if entry['host'] == host]
    if not entries or host not in ('claude-code', 'deepseek-harness'):
        raise CapabilityError('adapter_not_registered', 'host')
    exact = [entry for entry in entries
             if all(receipt[key] == entry[key] for key in IDENTITY)]
    if len(exact) == 1:
        return _adapter_spec(exact[0])
    diagnostic = entries
    by_adapter = [entry for entry in entries if entry['adapter_id'] == receipt['adapter_id']]
    if len(by_adapter) == 1:
        diagnostic = by_adapter
    if len(diagnostic) == 1:
        for key in IDENTITY:
            if receipt[key] != diagnostic[0][key]:
                raise CapabilityError('adapter_identity_mismatch', key, diagnostic[0][key])
    raise CapabilityError('adapter_identity_mismatch', 'adapter_identity')


def _verify_instruction(entry, instruction):
    try:
        no_follow(instruction)
        raw = instruction.read_bytes().decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    except (OSError, ValueError):
        raise CapabilityError('instruction_unreadable', 'instruction_path', str(instruction))
    if sha((raw.rstrip('\n') + '\n').encode('utf-8')) != entry['adapter_digest']:
        raise CapabilityError('instruction_digest_mismatch', 'adapter_digest', entry['adapter_digest'])


def validate_capability(receipt):
    if (not isinstance(receipt, dict) or set(receipt) != FIELDS or
        type(receipt['schema_version']) is not int or receipt['schema_version'] != 1 or
        receipt['kind'] != 'host_capability'):
        raise CapabilityError('invalid_capability', 'capability')
    entry, fixed, expected, instruction = _adapter_for_receipt(receipt)
    obs, evidence = receipt['observation'], receipt['evidence']
    if not isinstance(obs, dict) or set(obs) != OBSERVATIONS:
        raise CapabilityError('invalid_observation', 'observation', sorted(OBSERVATIONS))
    for key in sorted(OBSERVATIONS - {'worker_capacity'}):
        if type(obs[key]) is not bool:
            raise CapabilityError('invalid_observation', 'observation.' + key, 'boolean')
    capacity = obs['worker_capacity']
    if capacity is not None and (type(capacity) is not int or capacity < 0):
        raise CapabilityError('invalid_observation', 'observation.worker_capacity', 'null or nonnegative integer')
    for key, value in fixed.items():
        if obs[key] != value:
            raise CapabilityError('observation_mismatch', 'observation.' + key, value)
    if not isinstance(evidence, dict) or set(evidence) != set(expected) | {'session_id'}:
        raise CapabilityError('invalid_evidence', 'evidence', sorted(set(expected) | {'session_id'}))
    for key, value in expected.items():
        matches = evidence[key] in value if isinstance(value, tuple) else evidence[key] == value
        if not matches:
            raise CapabilityError('evidence_mismatch', 'evidence.' + key, value)
    if not isinstance(evidence['session_id'], str) or not evidence['session_id'].strip():
        raise CapabilityError('invalid_evidence', 'evidence.session_id', 'nonempty current host session ID')
    _verify_instruction(entry, instruction)
    width = 1 if capacity is None or not (obs['concurrent_tasks'] and obs['durable_lookup']) else min(capacity, 5)
    return dict(receipt, selected_width=0 if capacity == 0 else width)


def inspect_host(host, capability_path=None):
    """No run/owner access or writes. An accepted declaration is not live attestation."""
    entry, _, _, instruction = _adapter_for_host(host)
    _verify_instruction(entry, instruction)
    result = {'skill_root': str(ROOT), 'registry_path': str(REGISTRY),
        'instruction_path': str(instruction), 'adapter': entry,
        'receipt_checked': False, 'live_host_verified': False}
    if capability_path is not None:
        raw = str(capability_path)
        windows = PureWindowsPath(raw)
        # Reject network/device/stream syntax before any input-path filesystem call.
        if (raw.replace('\\', '/').startswith(('//', '/??/')) or '\x00' in raw or
            ':' in raw[len(windows.drive):] or (windows.drive and not windows.root) or
            any(PureWindowsPath(part).is_reserved() for part in windows.parts)):
            raise CapabilityError('unsafe_capability_path', 'capability')
        path = Path(capability_path).absolute()
        if path.drive.startswith('\\\\'):
            raise CapabilityError('unsafe_capability_path', 'capability')
        try:
            # Reuse the no-follow regular-file reader; never read devices/FIFOs.
            receipt = RunStore(path.parent).read_json(path.name)
        except (OSError, ValueError):
            raise CapabilityError('capability_unreadable', 'capability')
        if isinstance(receipt, dict) and receipt.get('host') != host:
            raise CapabilityError('adapter_identity_mismatch', 'host', host)
        validated = validate_capability(receipt)
        selected, _, _, selected_instruction = _adapter_for_receipt(receipt)
        result.update(receipt_checked=True, selected_width=validated['selected_width'],
                      adapter=selected, instruction_path=str(selected_instruction))
    return result
