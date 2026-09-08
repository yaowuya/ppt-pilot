"""Single read-only artifact policy shared by gates and runtime entry points."""
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

CODE_SUFFIXES = frozenset(('py pyw pyc pyo ps1 psm1 psd1 js mjs cjs jsx ts tsx '
    'sh bash zsh fish bat cmd vbs vbe wsf wsh hta rb pl php lua r jar exe com scr '
    'msi dll html htm css scss less').split())
FORBIDDEN_DIRECTORIES = frozenset('node_modules __pycache__ .venv venv env vendor'.split())
DOCUMENTS = frozenset(('简报.md 研究.md 来源.md 大纲.md 故事板.md 文稿审查.md 质量检查报告.md '
    'brief.md research.md sources.md outline.md storyboard.md manuscript-review.md qa-report.md '
    'run.json theme.json 源稿清单.json 源页映射.json 导入检查点.json').split())
DIRECTORY_TYPES = {
    'slides': {'.svg'}, 'slides/.candidates': {'.svg'}, 'samples': {'.svg'},
    '.ppt-pilot/samples': {'.svg'}, '.ppt-pilot/renders': {'.png'},
    '.ppt-pilot/generation-prompts': {'.md'}, '.ppt-pilot/redesign-prompts': {'.md'},
    '.ppt-pilot/visual-briefs': {'.md', '.json'},
    '.ppt-pilot/visual-generation-transactions': {'.json'},
    '.ppt-pilot/visual-generation-batches': {'.json'},
    '.ppt-pilot/visual-generation-dispatches': {'.json'},
    '.ppt-pilot/visual-generation-recoveries': {'.json'},
    '.ppt-pilot/runtime-inputs': {'.json', '.txt'},
}
INTERNAL = frozenset(('dashboard.json', 'dashboard.lock', 'dashboard.log', 'runtime.lock'))
DATA_TYPES = frozenset(('.md', '.json', '.svg', '.png', '.txt'))


def _base_name(name):
    # Data writers use either owner.ext.tmp or owner.ext.<random>.tmp.
    base = re.sub(r'(\.(?:json|md|svg|png|txt|lock|log|pptx))(?:\.[A-Za-z0-9_-]+)?\.tmp$',
                  r'\1', name) if name.endswith('.tmp') else name
    if base != name and PurePosixPath(base).name.startswith('.'):
        path = PurePosixPath(base)
        base = str(path.with_name(path.name[1:]))
    return base


def _bound_paths(run, owners):
    """Read only canonical owners; arbitrary JSON cannot grant itself permission."""
    result = set()
    def add(value, internal=False):
        if not isinstance(value, str) or '\\' in value or ':' in value:
            return
        path = PurePosixPath(value)
        if path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
            return
        if path.suffix.lower() in DATA_TYPES:
            result.add(('.ppt-pilot/' if internal and '/' not in value else '') + value)
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('path', 'output', 'latest_report'):
                    add(item, key == 'latest_report')
                elif key in ('files', 'file_hashes'):
                    for name in item if isinstance(item, (dict, list)) else ():
                        add(name)
                if isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(run.get('manuscript_review', {}))
    walk(run.get('anchor', {}))
    source = run.get('source_deck', {})
    if isinstance(source, dict):
        for key in ('inventory', 'mapping', 'evidence'):
            add(source.get(key), True)
        evidence = source.get('evidence')
        if isinstance(evidence, str):
            name = '.ppt-pilot/' + evidence if '/' not in evidence else evidence
            if name in owners:
                walk(owners[name])
    return result


def audit_artifacts(root, stage='brief', source_path=None):
    """Return deterministic structured errors without following links or writing."""
    errors = {}
    def reject(code, name):
        errors.setdefault(code, set()).add(name)
    root = Path(os.path.abspath(str(root)))
    entries = []
    try:
        for component in (root,) + tuple(root.parents):
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                reject('unsafe_evidence_path', '.')
                break
        if not errors:
            pending = [root]
            while pending:
                directory = pending.pop()
                try:
                    children = list(directory.iterdir())
                except OSError:
                    reject('unsafe_evidence_path', directory.relative_to(root).as_posix())
                    continue
                for path in children:
                    name = path.relative_to(root).as_posix()
                    try:
                        info = path.lstat()
                    except OSError:
                        reject('unsafe_evidence_path', name)
                        continue
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                        reject('unsafe_evidence_path', name)
                        continue
                    directory_entry = stat.S_ISDIR(info.st_mode)
                    if directory_entry and path.name.lower() in FORBIDDEN_DIRECTORIES:
                        reject('runtime_code_artifact', name)
                        continue
                    if not directory_entry and CODE_SUFFIXES.intersection(s[1:].lower() for s in path.suffixes):
                        reject('runtime_code_artifact', name)
                    elif directory_entry or stat.S_ISREG(info.st_mode):
                        entries.append((name, path, directory_entry))
                    else:
                        reject('unsafe_evidence_path', name)
                    if directory_entry:
                        pending.append(path)
    except (OSError, ValueError):
        reject('unsafe_evidence_path', '.')

    owners = {}
    files = {name: path for name, path, directory in entries if not directory}
    def read_owner(name):
        if name not in files:
            return {}
        try:
            value = files[name].read_text(encoding='utf-8-sig')
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, RecursionError):
            return {}  # Schema validation belongs to the owning gate.
        except OSError:
            reject('unsafe_evidence_path', name)
            return {}
    run = read_owner('.ppt-pilot/run.json' if '.ppt-pilot/run.json' in files else 'run.json')
    source = run.get('source_deck', {})
    if isinstance(source, dict) and isinstance(source.get('evidence'), str):
        name = source['evidence']
        name = '.ppt-pilot/' + name if '/' not in name else name
        owners[name] = read_owner(name)
    bound = _bound_paths(run, owners)
    allowed_dirs = {'.ppt-pilot', 'delivery', 'delivery/editable'} | set(DIRECTORY_TYPES)
    for name in bound:
        allowed_dirs.update(p.as_posix() for p in PurePosixPath(name).parents if p.as_posix() != '.')
    source_name = (os.path.normcase(os.path.abspath(str(source_path)))
                   if source_path and Path(source_path).is_absolute() else None)
    if source_path and Path(source_path).is_absolute():
        try:
            relative_source = Path(source_path).relative_to(root)
            allowed_dirs.update(p.as_posix() for p in relative_source.parents if p.as_posix() != '.')
        except ValueError:
            pass
    for name, path, directory in entries:
        if directory:
            allowed = name in allowed_dirs or (stage == 'complete' and
                (name in ('delivery/editable/.tmp', 'delivery/editable/quarantine') or
                 name.startswith(('delivery/editable/.tmp/', 'delivery/editable/quarantine/'))))
        else:
            base = _base_name(name)
            p = PurePosixPath(base)
            if p.suffix.lower() == '.pptx':
                if path.suffix.lower() == '.pptx' and source_name == os.path.normcase(str(path)):
                    continue
                if stage != 'complete':
                    reject('precomplete_pptx', name)
                elif not name.startswith('delivery/editable/'):
                    reject('pptx_outside_delivery', name)
                continue
            allowed = (base in bound or
                (p.parent.as_posix() in ('.', '.ppt-pilot') and p.name in DOCUMENTS) or
                (p.parent.as_posix() == '.ppt-pilot' and p.name in INTERNAL) or
                p.suffix.lower() in DIRECTORY_TYPES.get(p.parent.as_posix(), set()))
            if stage == 'complete' and name.startswith('delivery/editable/'):
                allowed = (base in ('delivery/editable/editable-result.json', 'delivery/editable/.editable.lock') or
                    (name.startswith(('delivery/editable/.tmp/', 'delivery/editable/quarantine/')) and
                     p.suffix.lower() in DATA_TYPES | {'.pptx'}))
        if not allowed:
            reject('unexpected_run_artifact', name)
    actions = {
        'unsafe_evidence_path': 'Replace unsafe or unreadable entries with owned regular files, then repeat the gate.',
        'runtime_code_artifact': 'Quarantine unexpected runtime code outside this run, then repeat the same gate.',
        'unexpected_run_artifact': 'Quarantine unrecognized artifacts outside this run, then repeat the same gate.',
        'precomplete_pptx': 'Quarantine premature PPTX output and resume theme -> anchor -> production -> qa.',
        'pptx_outside_delivery': 'Keep post-complete PPTX delivery only under delivery/editable/.',
    }
    return [dict(code=code, reentry_stage=('theme' if code == 'precomplete_pptx' else
                 'complete' if code == 'pptx_outside_delivery' else stage),
                 next_action=actions[code], artifacts=sorted(errors[code]))
            for code in ('unsafe_evidence_path', 'runtime_code_artifact', 'precomplete_pptx',
                         'pptx_outside_delivery', 'unexpected_run_artifact') if code in errors]
