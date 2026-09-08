"""Closed blocker tuples; resource identity comes from the resolver operation."""
import re


def preflight_blocker(failure, context, slide_id):
    style = context['selected_style_id']
    if not isinstance(style, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', style):
        raise ValueError('canonical_owner_missing')
    root = 'assets/styles/' + style + '/'
    registry = 'assets/styles/registry.json'
    tuples = {}
    def allow(reasons, resources, state):
        for reason in reasons.split():
            tuples[reason] = (state, set(resources))
    allow('registry_missing registry_path_unsafe entrypoint_path_unsafe style_asset_field_missing style_asset_path_unsafe', ['none'], 'style_assets_unavailable')
    allow('registry_target_invalid registry_unreadable registry_malformed registry_schema_unsupported registry_duplicate_style style_not_registered style_kind_invalid', [registry], 'style_assets_unavailable')
    allow('entrypoint_missing entrypoint_target_invalid entrypoint_unreadable manifest_malformed manifest_schema_unsupported manifest_identity_mismatch manifest_version_invalid', [root + 'manifest.json'], 'style_assets_unavailable')
    allow('style_asset_target_invalid style_asset_unreadable style_asset_malformed', [root + 'tokens.json', root + 'STYLE.md'], 'style_assets_unavailable')
    allow('style_asset_schema_unsupported', [root + 'tokens.json'], 'style_assets_unavailable')
    allow('prompt_path_unsafe prompt_snapshot_conflict', ['none'], 'generation_prompt_unavailable')
    allow('prompt_file_missing prompt_target_invalid prompt_unreadable prompt_template_invalid prompt_preflight_invalid', [root + 'prompt.md'], 'generation_prompt_unavailable')
    reason, resource = failure.reason, failure.resource
    if reason not in tuples or resource not in tuples[reason][1]:
        raise ValueError('blocker_tuple_invalid')
    if any(not isinstance(context.get(key), str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', context[key]) for key in ('storyboard_snapshot_id', 'theme_snapshot_id')):
        raise ValueError('canonical_owner_missing')
    return dict(context, state=tuples[reason][0], reason=reason, resource=resource,
                slide_id=slide_id, status='active')
