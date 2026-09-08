"""Strict, reviewed Markdown data owners used by the visual runtime.

Only an explicit ppt-pilot-json fence or explicit bold fields is parsed. Prose
never supplies narrative decisions, review verdicts, or source mappings.
"""
import re
from _run_store import parse_json, canonical, sha
import _prompt_runtime as prompt
from _generation_runtime import _require_sha256

SNAPSHOTS = {'storyboard_snapshot_id', 'theme_snapshot_id', 'source_audit_snapshot_id',
             'generation_prompt_template_snapshot_id'}
NARRATIVE = {'argument_framework', 'opening_framework', 'sequence_template',
             'narrative_id', 'narrative_choice_reason', 'narrative_step1_bullets'}


def markdown_owner(raw):
    text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    fences = re.findall(r'^```ppt-pilot-json\n(.*?)\n```$', text, re.M | re.S)
    fields = re.findall(r'^- \*\*([a-z][a-z0-9_]*)\*\*[：:]\s*(.+)$', text, re.M)
    if fences:
        if len(fences) != 1 or fields:
            raise ValueError('canonical_owner_ambiguous')
        value = parse_json(fences[0].encode())
    else:
        value = {}
        for key, item in fields:
            if key in value:
                raise ValueError('canonical_owner_ambiguous')
            value[key] = parse_json(item.encode()) if item.startswith(('[', '{', '"')) else item
        bullets = re.findall(r'^### narrative_step1_bullets\n(.*?)(?=^#|\Z)', text, re.M | re.S)
        if bullets:
            if len(bullets) != 1 or 'narrative_step1_bullets' in value:
                raise ValueError('canonical_owner_ambiguous')
            value['narrative_step1_bullets'] = bullets[0].strip('\n') + '\n'
    if not isinstance(value, dict) or not value:
        raise ValueError('canonical_owner_missing')
    return value


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_slide(slide, previous, following):
    required = {'slide_id', 'role', 'assertion_title', 'audience_takeaway', 'source_ids',
        'forbidden_claims', 'content_blocks', 'visual_intent', 'layout_family',
        'density_budget', 'previous_link', 'next_link'}
    if not isinstance(slide, dict) or set(slide) != required:
        raise ValueError('storyboard_fact_mismatch')
    if (not re.fullmatch(r'S[0-9]+', slide['slide_id']) or
        slide['previous_link'] != previous or slide['next_link'] != following or
        any(not nonempty(slide[k]) for k in ('role', 'assertion_title', 'audience_takeaway',
                                           'visual_intent', 'layout_family')) or
        not isinstance(slide['forbidden_claims'], list) or
        any(not nonempty(item) for item in slide['forbidden_claims'])):
        raise ValueError('storyboard_fact_mismatch')
    blocks = slide['content_blocks']
    if not isinstance(blocks, list) or not blocks:
        raise ValueError('storyboard_fact_mismatch')
    union, ids = [], set()
    for index, block in enumerate(blocks, 1):
        if not isinstance(block, dict) or set(block) != {'block_id', 'display_copy', 'priority',
                 'reading_order', 'claim_id', 'source_ids', 'qualifiers', 'metric'}:
            raise ValueError('storyboard_fact_mismatch')
        bid = block['block_id']
        if (not isinstance(bid, str) or not re.fullmatch(slide['slide_id'] + r'-B[1-9][0-9]*', bid)
                or bid in ids or type(block['reading_order']) is not int or block['reading_order'] != index
                or block['priority'] not in ('core', 'support') or not nonempty(block['display_copy'])
                or not nonempty(block['claim_id'])):
            raise ValueError('storyboard_fact_mismatch')
        ids.add(bid)
        sources = block['source_ids']
        if (not isinstance(sources, list) or any(not isinstance(s, str) or not re.fullmatch(r'SRC-[0-9]+', s) for s in sources)
                or len(sources) != len(set(sources)) or (block['claim_id'] == 'none') != (sources == [])):
            raise ValueError('fact_source_mismatch')
        for source in sources:
            if source not in union:
                union.append(source)
        qualifiers = block['qualifiers']
        if not isinstance(qualifiers, list):
            raise ValueError('storyboard_fact_mismatch')
        for item in qualifiers:
            if (not isinstance(item, dict) or set(item) != {'display_text', 'confidence', 'scope', 'causality'}
                    or item['confidence'] not in ('high', 'medium', 'low', 'unverified')
                    or any(not nonempty(v) for v in item.values())):
                raise ValueError('storyboard_fact_mismatch')
        metric = block['metric']
        if metric != 'none' and (not isinstance(metric, dict) or set(metric) !=
              {'display_value', 'number_text', 'unit', 'period', 'comparator', 'baseline'} or
              any(not nonempty(v) for v in metric.values())):
            raise ValueError('storyboard_fact_mismatch')
    if slide['source_ids'] != union:
        raise ValueError('fact_source_mismatch')


class Owners:
    def __init__(self, store, run):
        self.store, self.run = store, run
        review = run.get('manuscript_review', {})
        if (run.get('stage') not in ('anchor', 'production', 'qa', 'complete') or
                review.get('state') != 'manuscript_approved' or review.get('status') != 'PASSED'
                or review.get('open_blocking_findings') != []):
            raise ValueError('manuscript_not_approved')
        history = review.get('review_history', [])
        if not history or not isinstance(history, list):
            raise ValueError('review_history_missing')
        latest = history[-1]
        if (latest.get('verdict') != 'PASS' or latest.get('round') != review.get('round') or
                latest.get('cycle', 1) != review.get('cycle', 1)):
            raise ValueError('review_not_latest_pass')
        frozen = latest.get('reviewed_file_snapshot', {})
        files = frozen.get('files', [])
        hashes = frozen.get('file_hashes', {})
        chinese = ['.ppt-pilot/简报.md', '.ppt-pilot/研究.md', '.ppt-pilot/来源.md', '大纲.md', '.ppt-pilot/故事板.md']
        english = ['.ppt-pilot/brief.md', '.ppt-pilot/research.md', '.ppt-pilot/sources.md', 'outline.md', '.ppt-pilot/storyboard.md']
        if (not isinstance(files, list) or len(files) != 5 or set(files) not in (set(chinese), set(english))
                or set(hashes) != set(files) or not nonempty(frozen.get('snapshot_id'))):
            raise ValueError('review_snapshot_mismatch')
        for name in files:
            if store.hash(name).removeprefix('sha256:') != hashes[name]:
                raise ValueError('manuscript_stale')
        names = chinese if set(files) == set(chinese) else english
        self.outline = markdown_owner(store.read_bytes(names[3]))
        self.storyboard = markdown_owner(store.read_bytes(names[4]))
        report_name = review.get('latest_report')
        if not nonempty(report_name):
            raise ValueError('review_report_mismatch')
        report_name = '.ppt-pilot/' + report_name if '/' not in report_name else report_name
        report = markdown_owner(store.read_bytes(report_name))
        if report != latest:
            raise ValueError('review_report_mismatch')
        # Reuse the full independent-review validator for all ordinary runs too.
        from _workflow_gate import Gate
        from _workflow_evidence import manuscript
        gate = Gate(store.root)
        gate.run = run
        gate.evidence = {'manuscript': {'files': hashes, 'report': {'path': report_name,
            'sha256': store.hash(report_name).removeprefix('sha256:')}, 'review_snapshot_id': frozen['snapshot_id']}}
        manuscript(gate)
        if not NARRATIVE <= set(self.outline) or any(not nonempty(self.outline[k]) for k in NARRATIVE):
            raise ValueError('canonical_owner_missing')
        outline_id = _require_sha256(self.outline.get('outline_snapshot_id'), 'outline_snapshot_id')
        if self.storyboard.get('outline_snapshot_id') != outline_id:
            raise ValueError('prompt_snapshot_conflict')
        if run.get('mode') == 'guided':
            approvals = [v for v in run.get('interaction_history', {}).values() if
                         v.get('kind') == 'approval' and v.get('checkpoint') == 'outline']
            if not approvals or max(approvals, key=lambda v: v.get('approval_attempt', 0)).get('artifact_snapshot_id') != outline_id:
                raise ValueError('approval_stale')
            latest_approval = max(approvals, key=lambda v: v.get('approval_attempt', 0))
            if latest_approval.get('decision') != 'approve' or latest_approval.get('status') != 'applied':
                raise ValueError('approval_missing')
        self.theme = store.read_json('.ppt-pilot/theme.json')
        style_id = self.theme.get('selected_style_id')
        storyboard_id = _require_sha256(self.storyboard.get('storyboard_snapshot_id'), 'storyboard_snapshot_id')
        if not isinstance(style_id, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', style_id):
            raise ValueError('canonical_owner_missing')
        context = {'selected_style_id': style_id, 'storyboard_snapshot_id': storyboard_id,
                   'theme_snapshot_id': store.hash('.ppt-pilot/theme.json')}
        try:
            self.template_path, self.template = prompt.runtime_style_assets(style_id)
        except prompt.AssetFailure as error:
            error.canonical_context = context
            raise
        pack = prompt.skill_root() / 'assets/styles' / style_id
        manifest = parse_json(prompt._read_regular_asset(pack / 'manifest.json', path_reason='style_asset_path_unsafe',
            missing_reason='style_asset_target_invalid', target_reason='style_asset_target_invalid', unreadable_reason='style_asset_unreadable'))
        for key, expected in {'selected_style_display_name': manifest['display_name'],
                               'style_kind': manifest['kind'], 'style_manifest_version': manifest['version']}.items():
            if self.theme.get(key) != expected:
                raise ValueError('style_identity_mismatch')
        tokens = parse_json(prompt._read_regular_asset(pack / 'tokens.json', path_reason='style_asset_path_unsafe',
            missing_reason='style_asset_target_invalid', target_reason='style_asset_target_invalid', unreadable_reason='style_asset_unreadable'))
        self.baseline = prompt.normalize_lf(prompt._style_verifier().render_prompt_style_directives(tokens).encode())
        slides = self.storyboard.get('slides')
        if not isinstance(slides, list) or not slides:
            raise ValueError('canonical_owner_missing')
        self.slides = {}
        for index, slide in enumerate(slides):
            validate_slide(slide, 'START' if index == 0 else slides[index-1]['slide_id'],
                           'END' if index == len(slides)-1 else slides[index+1]['slide_id'])
            if slide['slide_id'] in self.slides:
                raise ValueError('canonical_owner_ambiguous')
            self.slides[slide['slide_id']] = slide
        self.revisions, self.projection = prompt.project_active_visual_revisions({'storyboard': self.storyboard, 'run': dict(run, interaction_history=run.get('interaction_history', {}))})
        self.snapshots = {'storyboard_snapshot_id': _require_sha256(self.storyboard.get('storyboard_snapshot_id'), 'storyboard_snapshot_id'),
            'theme_snapshot_id': store.hash('.ppt-pilot/theme.json'),
            'source_audit_snapshot_id': store.hash(names[2]),
            'generation_prompt_template_snapshot_id': sha(self.template)}
        if run.get('source_deck'):
            from _workflow_gate import Gate, STAGES
            from _workflow_evidence import check_stages
            source_gate = Gate(store.root)
            source_gate.run = run
            source_gate.import_binding()
            check_stages(source_gate, STAGES.index('anchor' if run.get('stage') == 'anchor' else 'production'))
            self.snapshots['source_audit_snapshot_id'] = sha(canonical(source_gate.evidence['source_audit']).rstrip(b'\n'))

    def compile(self, operation):
        sid = operation['slide_id']
        slide = self.slides[sid]
        for revision in parse_json(self.projection):
            scope = revision['affected_scope']
            if scope not in ('deck', 'anchor') and sid not in scope:
                continue
            for field, value in revision['normalized_changes'].items():
                ensure_value = slide.get(field, self.theme.get(field))
                if ensure_value != value or not isinstance(value, str):
                    raise ValueError('prompt_snapshot_conflict')
        intent, trigger = operation['generation_intent'], operation['generation_trigger_id']
        if intent == 'initial_generation':
            if trigger != 'initial:' + sid + ':' + self.snapshots['storyboard_snapshot_id']:
                raise ValueError('prompt_snapshot_conflict')
            request = 'initial generation from approved storyboard and theme'
        elif intent == 'user_recompose':
            revision = trigger.removeprefix('interaction:')
            if not trigger.startswith('interaction:') or revision not in self.revisions:
                raise ValueError('prompt_snapshot_conflict')
            record = self.run['interaction_history'][revision]
            if record.get('affected_scope') not in ('deck', 'anchor') and sid not in record.get('affected_scope', []):
                raise ValueError('prompt_snapshot_conflict')
            request = '; '.join(str(k) + '=' + str(v) for k, v in sorted(record['normalized_changes'].items()))
        elif intent == 'deterministic_fallback' and re.fullmatch(r'fallback:' + sid + r':[0-9a-f]{64}:2', trigger):
            request = 'deterministic single-column or two-column fallback after two failed patches'
        else:
            raise ValueError('prompt_snapshot_conflict')
        lines = [self.outline['narrative_step1_bullets'].rstrip('\n')]
        for field in ('role', 'assertion_title', 'audience_takeaway', 'visual_intent', 'layout_family'):
            lines.append('- ' + field + ': ' + slide[field])
        for block in slide['content_blocks']:
            lines.append('- block_id: ' + block['block_id'])
            lines.append('  - display_copy: ' + block['display_copy'])
            for qualifier in block['qualifiers']:
                lines.append('  - ' + '；'.join(qualifier[key] for key in ('display_text', 'confidence', 'scope', 'causality')))
            if block['metric'] != 'none':
                lines.append('  - ' + '；'.join(block['metric'].values()))
        lines.extend('- 禁止主张：' + item for item in slide['forbidden_claims'])
        if intent != 'initial_generation':
            lines.append('- 视觉请求：' + request)
        body = prompt.compile_style_prompt(('\n'.join(lines) + '\n').encode(), self.template,
                    tuple(block['block_id'].encode() for block in slide['content_blocks']))
        payload = dict(self.snapshots)
        del payload['source_audit_snapshot_id']
        payload.update(applied_visual_revision_ids=self.revisions, compiled_prompt_sha256=sha(body),
            format='creative-brief-v1', generation_intent=intent, generation_trigger_id=trigger,
            outline_snapshot_id=self.outline['outline_snapshot_id'], resolved_generation_prompt_template_path=self.template_path,
            selected_style_id=self.theme['selected_style_id'], style_baseline_snapshot_id=sha(self.baseline),
            style_kind=self.theme['style_kind'], style_manifest_version=self.theme['style_manifest_version'])
        identity = sha(prompt.canonical_json_bytes(payload))
        metadata = dict(slide_id=sid, storyboard_snapshot_id=self.snapshots['storyboard_snapshot_id'],
            theme_snapshot_id=self.snapshots['theme_snapshot_id'], applied_visual_revision_ids=self.revisions,
            prompt_snapshot_id=identity, user_page_request=request, expected_output='恰好一个 xml 代码围栏中的完整 SVG',
            workspace_output_path='slides/' + sid + '.svg', format='creative-brief-v1')
        return identity, sha(body), prompt.render_generation_prompt(metadata, body, sid)
