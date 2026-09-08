"""Phase evidence checks used by the additive source workflow gate."""
from _run_store import anchor_snapshot_id
from _workflow_gate import MANUSCRIPT_FILES, object_value, require, string, string_list


def section(gate, name, stage):
    gate.stage = stage
    require(name in gate.evidence, name + '_missing', stage, 'Complete and freeze the ' + name + ' evidence.')
    return object_value(gate.evidence[name], stage)


def approval(gate, stage, filename=None, anchor=None):
    gate.stage = stage
    history = gate.history()
    relevant = [item for item in history if item.get('kind') == 'approval' and item.get('checkpoint') == stage]
    require(bool(relevant), 'approval_missing', stage, 'Obtain and apply approval at the current ' + stage + ' checkpoint.')
    require(all(type(item.get('approval_attempt')) is int and item['approval_attempt'] > 0 for item in relevant) and
            len({item['approval_attempt'] for item in relevant}) == len(relevant),
            'invalid_approval_history', stage, 'Retain unique positive approval_attempt numbers for this checkpoint.')
    latest = max(relevant, key=lambda item: item['approval_attempt'])
    require(latest.get('status') == 'applied' and latest.get('decision') == 'approve',
            'approval_missing', stage, 'Apply the latest checkpoint approval before continuing.')
    if anchor is None:
        approvals = object_value(gate.evidence.get('approvals'), stage)
        binding = object_value(approvals.get(stage), stage)
        interaction_id = binding.get('interaction_id')
        gate.bound(filename, binding.get('artifact_sha256'), 'approval_stale')
    else:
        binding = anchor
        interaction_id = anchor.get('approval_interaction_id')
    require(interaction_id == latest.get('id') and string(binding.get('artifact_snapshot_id')) and
            binding['artifact_snapshot_id'] == latest.get('artifact_snapshot_id'),
            'approval_stale', stage, 'Reapprove the current artifact snapshot and record its applied interaction.')


def manuscript(gate):
    value = section(gate, 'manuscript', 'manuscript_review')
    files = gate.files(value.get('files'), 'manuscript_stale')
    require(set(files) == set(MANUSCRIPT_FILES), 'manuscript_files_invalid', 'manuscript_review',
            'Freeze exactly the current brief, research, sources, root outline and storyboard.')
    report = object_value(value.get('report'), gate.stage)
    gate.bound(report.get('path'), report.get('sha256'), 'review_report_stale')
    review = object_value(gate.run.get('manuscript_review'), gate.stage)
    require(review.get('required') is True and review.get('state') == 'manuscript_approved' and review.get('status') == 'PASSED' and
            review.get('open_blocking_findings') == [], 'manuscript_not_approved', gate.stage,
            'Finish the formal manuscript review and resolve every blocking finding.')
    history = review.get('review_history')
    require(isinstance(history, list) and history, 'review_history_missing', gate.stage,
            'Retain the completed formal review round and execution evidence.')
    history = [object_value(item, gate.stage) for item in history]
    counters = []
    for item in history:
        cycle, round_number = item.get('cycle', 1), item.get('round')
        require(type(cycle) is int and cycle > 0 and type(round_number) is int and 1 <= round_number <= 3,
                'review_not_latest_pass', gate.stage, 'Retain valid positive review cycles and formal rounds 1 through 3.')
        counters.append((cycle, round_number))
    require(counters == sorted(set(counters)) and type(review.get('cycle', 1)) is int and review.get('cycle', 1) > 0,
            'review_not_latest_pass', gate.stage, 'Resolve duplicate, reversed, or contradictory formal review counters.')
    latest = history[-1]
    require(type(latest.get('round')) is int and latest['round'] > 0 and
            type(review.get('round')) is int and latest['round'] == review['round'] and
            latest.get('cycle', 1) == review.get('cycle', 1) and latest.get('verdict') == 'PASS',
            'review_not_latest_pass', gate.stage, 'Bind the latest actual formal PASS review round.')
    blockers = {}
    for item in history:
        findings = item.get('findings')
        require(isinstance(findings, list), 'invalid_schema', gate.stage, 'Supply the formal review findings list.')
        for finding in findings:
            finding = object_value(finding, gate.stage)
            if finding.get('severity') in ('BLOCKER', 'HIGH'):
                require(string(finding.get('id')), 'review_blocking_findings', gate.stage,
                        'Retain stable finding IDs and resolve all BLOCKER/HIGH findings through formal review.')
                blockers[finding['id']] = finding.get('status')
    require(all(status == 'RESOLVED' for status in blockers.values()),
            'review_blocking_findings', gate.stage, 'Resolve every historical BLOCKER/HIGH finding; do not silently drop it.')
    mode = latest.get('review_mode', 'subagent' if 'delegation_evidence' in latest else None)
    require(mode in ('subagent', 'inline_fallback'), 'review_execution_missing', gate.stage,
            'Retain formal review execution evidence.')
    if mode == 'subagent':
        execution = object_value(latest.get('delegation_evidence'), gate.stage)
        require('fallback_evidence' not in latest and
                all(string(execution.get(key)) for key in ('child_context_id', 'completion_event_id', 'result_context_id')) and
                execution['child_context_id'] == execution['result_context_id'],
                'review_execution_missing', gate.stage, 'Record the actual completed child review context and event.')
    else:
        execution = object_value(latest.get('fallback_evidence'), gate.stage)
        require('delegation_evidence' not in latest and execution.get('delegation_attempted') is True and
                execution.get('reason') in ('child_context_unavailable', 'child_start_failed', 'completion_event_missing',
                                            'result_context_mismatch', 'delegation_capability_unavailable') and
                string(execution.get('host_detail')), 'review_execution_missing', gate.stage,
                'Record the failed delegation and formal inline fallback execution.')
    frozen = object_value(latest.get('reviewed_file_snapshot'), gate.stage)
    frozen_files = frozen.get('files')
    require(string_list(frozen_files) and len(frozen_files) == 5 and set(frozen_files) == set(files) and
            isinstance(frozen.get('file_hashes'), dict) and frozen['file_hashes'] == files,
            'review_snapshot_mismatch', gate.stage, 'Use the exact five files frozen for the latest review.')
    require(string(value.get('review_snapshot_id')) and value['review_snapshot_id'] == frozen.get('snapshot_id'),
            'review_snapshot_mismatch', gate.stage, 'Use the existing review snapshot ID, never retrofit a new snapshot to old review.')
    latest_report = review.get('latest_report')
    require(string(latest_report), 'review_report_mismatch', gate.stage, 'Bind the formal latest_report path.')
    if '/' not in latest_report:
        latest_report = '.ppt-pilot/' + latest_report
    require(report['path'] == latest_report, 'review_report_mismatch', gate.stage,
            'Bind the current formal review report, not a different report file.')
    gate.review_snapshot_id = value['review_snapshot_id']


def style(gate):
    value = section(gate, 'style', 'theme')
    files = gate.files(value.get('files'), 'style_stale')
    require('.ppt-pilot/theme.json' in files, 'style_theme_missing', gate.stage,
            'Bind the current target product theme.json in style evidence.')
    theme = gate.read_json('.ppt-pilot/theme.json')
    require(string(value.get('selected_style_id')) and string(value.get('style_manifest_version')) and
            value['selected_style_id'] == theme.get('selected_style_id') and
            value['style_manifest_version'] == theme.get('style_manifest_version'),
            'style_identity_mismatch', gate.stage, 'Resolve and validate the selected target style identity.')
    gate.style_hash = files['.ppt-pilot/theme.json']


def anchor(gate):
    value = section(gate, 'anchor', 'anchor')
    files = gate.files(value.get('files'), 'anchor_stale')
    require(len(files) >= min(2, len(gate.targets)) and
            all(name.startswith('.ppt-pilot/samples/') and name.endswith('.svg') for name in files),
            'anchor_files_invalid', gate.stage, 'Bind at least two current sample SVGs (all pages for a one-page deck).')
    for name in files:
        gate.svg(name)
    require(value.get('style_sha256') == gate.style_hash and
            value.get('review_snapshot_id') == gate.review_snapshot_id,
            'anchor_binding_stale', gate.stage, 'Recreate anchors from the current target theme and approved manuscript.')
    expected = 'approved' if gate.run['mode'] == 'guided' else 'validated'
    require(value.get('status') == expected, 'anchor_not_approved', gate.stage,
            'Approve guided anchors or record validated auto anchors.')
    if gate.run['mode'] == 'guided':
        snapshot_id = anchor_snapshot_id(value)
        require(value.get('artifact_snapshot_id') == snapshot_id, 'approval_stale', gate.stage,
                'Reapprove the digest of the current sample files, target theme and reviewed manuscript.')
        approval(gate, 'anchor', anchor=value)


def qa(gate):
    value = section(gate, 'qa', 'qa')
    require(value.get('status') == 'PASS', 'qa_not_passed', gate.stage, 'Complete the final visual QA review.')
    report = object_value(value.get('report'), gate.stage)
    gate.bound(report.get('path'), report.get('sha256'), 'qa_report_stale')
    slides = value.get('slides')
    require(isinstance(slides, list), 'invalid_schema', gate.stage, 'Supply one final QA record per target page.')
    seen = []
    for item in slides:
        item = object_value(item, gate.stage)
        slide_id = item.get('slide_id')
        require(string(slide_id), 'invalid_schema', gate.stage, 'Supply a stable QA slide ID.')
        seen.append(slide_id)
        svg = object_value(item.get('svg'), gate.stage)
        render = object_value(item.get('render'), gate.stage)
        require(svg.get('path') == 'slides/' + slide_id + '.svg', 'qa_svg_path_invalid', gate.stage,
                'Bind the final SVG under slides/<slide_id>.svg.')
        svg_hash = gate.bound(svg['path'], svg.get('sha256'), 'qa_svg_stale')
        require(item.get('render_input_sha256') == svg_hash, 'qa_render_input_stale', gate.stage,
                'Render the current final SVG and record its input SHA-256.')
        gate.bound(render.get('path'), render.get('sha256'), 'qa_render_stale')
        gate.png(render.get('path'))
        require(render['path'] != svg['path'] and not render['path'].endswith('.svg') and
                string(item.get('renderer')) and item.get('visual_review') == 'PASS',
                'qa_visual_review_missing', gate.stage, 'Render the SVG and record completed visual review PASS with renderer identity.')
    require(len(seen) == len(set(seen)) and set(seen) == set(gate.targets),
            'qa_coverage', gate.stage, 'Review every target SVG and current render exactly once.')
    require(gate.run.get('dirty_slides') == [], 'dirty_slides', 'production',
            'Regenerate or repair dirty slides and repeat their final QA before completion.')


def check_stages(gate, index):
    gate.stage = 'brief'
    gate.file_hash(MANUSCRIPT_FILES[0])
    if gate.run['mode'] == 'guided':
        approval(gate, 'brief', MANUSCRIPT_FILES[0])
    if index < 1:
        return
    audit = section(gate, 'source_audit', 'research')
    reviewed, visual = audit.get('reviewed_slide_ids'), audit.get('visual_checked_slide_ids')
    require(audit.get('status') == 'complete' and audit.get('inventory_sha256') == gate.inventory_hash and
            string_list(reviewed) and len(reviewed) == len(set(reviewed)) and set(reviewed) == set(gate.source_ids) and
            string_list(visual) and len(visual) == len(set(visual)) and set(visual) <= set(gate.source_ids) and
            set(gate.warned_ids) <= set(visual) and string(audit.get('notes')),
            'source_audit_incomplete', gate.stage, 'Audit every source page and visually check all warned pages; bind the current inventory hash.')
    gate.file_hash(MANUSCRIPT_FILES[1])
    gate.file_hash(MANUSCRIPT_FILES[2])
    if index < 2:
        return
    gate.stage = 'outline'
    gate.file_hash(MANUSCRIPT_FILES[3])
    if gate.run['mode'] == 'guided':
        approval(gate, 'outline', MANUSCRIPT_FILES[3])
    if index < 3:
        return
    gate.stage = 'storyboard'
    gate.file_hash(MANUSCRIPT_FILES[4])
    # target_slide_ids was checked against mapping for every source-import gate.
    if index >= 4:
        manuscript(gate)
    if index >= 5:
        style(gate)
    if index >= 6:
        anchor(gate)
    if index >= 7:
        gate.stage = 'production'
        for slide_id in gate.targets:
            gate.svg('slides/' + slide_id + '.svg')
    if index >= 8:
        qa(gate)
