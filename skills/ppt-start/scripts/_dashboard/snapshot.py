"""Bounded, read-only projection of the durable PPT Pilot run artifacts.

The dashboard is an observer, never a workflow owner. A recorded active stage
does not constitute a process heartbeat, and an SVG does not prove QA passed.
"""
import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


MAX_PAGES = 1000
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_SVG_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
SLIDE_ID = re.compile(r"S[0-9]{2,6}\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
STAGES = (
    ("brief", "需求确认"), ("research", "资料解析与研究"),
    ("outline", "演示大纲"), ("storyboard", "逐页故事板"),
    ("manuscript_review", "内容审查"), ("theme", "主题设计"),
    ("anchor", "锚点样例"), ("production", "正式页面生成"),
    ("qa", "质量检查"), ("complete", "交付完成"),
)
CHECKPOINTS = {
    "brief_approved": "brief", "research_approved": "research",
    "outline_approved": "outline", "storyboard_approved": "storyboard",
    "manuscript_approved": "manuscript_review", "theme_approved": "theme",
    "anchor_approved": "anchor", "qa_approved": "qa",
}
BLOCKED_STAGES = {"manuscript_blocked": "manuscript_review", "review_unavailable": "manuscript_review"}
TX_STATES = {"compiling", "compiled", "generating", "candidate_written",
             "validated", "promoted", "failed"}
OBSERVED_DOCUMENTS = (
    ".ppt-pilot/简报.md", ".ppt-pilot/研究.md", ".ppt-pilot/来源.md",
    ".ppt-pilot/文稿审查.md", ".ppt-pilot/theme.json", ".ppt-pilot/质量检查报告.md",
    "大纲.md", "简报.md", "研究.md", "来源.md", "文稿审查.md", "质量检查报告.md",
    "brief.md", "research.md", "sources.md", "outline.md", "manuscript-review.md", "qa-report.md", "theme.json",
    ".ppt-pilot/brief.md", ".ppt-pilot/research.md", ".ppt-pilot/sources.md",
    ".ppt-pilot/manuscript-review.md", ".ppt-pilot/qa-report.md",
)


def _digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _time(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _relative(value):
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError("invalid_relative_path")
    if any(char in value for char in ("\\", ":", "%", "\x00")):
        raise ValueError("invalid_relative_path")
    parts = value.split("/")
    if any(part in ("", ".", "..") or part.endswith((" ", ".")) for part in parts):
        raise ValueError("invalid_relative_path")
    if any(ord(char) < 32 for char in value):
        raise ValueError("invalid_relative_path")
    return parts


def _plain(info, directory=False):
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("links_and_reparse_points_are_not_allowed")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError("expected_directory" if directory else "expected_regular_file")


def _checked_path(root, relative, directory=False):
    """Check every ancestor without resolving away a symlink or junction."""
    path = Path(os.path.abspath(str(root)))
    ancestors = list(reversed(path.parents)) + [path]
    for ancestor in ancestors:
        _plain(ancestor.lstat(), directory=True)
    parts = _relative(relative)
    for index, part in enumerate(parts):
        path = path / part
        _plain(path.lstat(), directory=directory or index < len(parts) - 1)
    return path


@contextmanager
def _open_regular(root, relative):
    """Keep directory handles open so concurrent renames cannot redirect reads.

    POSIX uses openat/O_NOFOLLOW. Windows opens reparse points themselves and
    pins ancestors without FILE_SHARE_DELETE until the safe leaf is open.
    """
    path = _checked_path(root, relative)
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        getinfo = kernel.GetFileInformationByHandleEx
        getinfo.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        getinfo.restype = wintypes.BOOL
        class Attributes(ctypes.Structure):
            _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]
        handles = []
        descriptor = None
        try:
            for item in list(reversed(path.parents)) + [path]:
                directory = item != path
                # The leaf may be atomically replaced while this observer reads
                # its old handle. Ancestors stay pinned to prevent redirection.
                handle = create(str(item), 0 if directory else 0x80000000,
                                3 if directory else 7, None, 3, 0x00200000 | 0x02000000, None)
                if handle == wintypes.HANDLE(-1).value:
                    raise OSError("artifact_open_failed")
                handles.append(handle)
                attributes = Attributes()
                if not getinfo(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
                    raise OSError("artifact_attributes_unavailable")
                if attributes.attributes & 0x400:
                    raise ValueError("links_and_reparse_points_are_not_allowed")
                if bool(attributes.attributes & 0x10) != directory:
                    raise ValueError("artifact_type_changed")
            descriptor = msvcrt.open_osfhandle(handles[-1], os.O_RDONLY | os.O_BINARY)
            handles.pop()  # The file descriptor now owns the leaf handle.
            # The verified leaf handle cannot be redirected by later ancestor
            # renames; release directory pins before observing its contents.
            for handle in reversed(handles):
                close(handle)
            handles.clear()
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = None
                yield stream
        finally:
            if descriptor is not None:
                os.close(descriptor)
            for handle in reversed(handles):
                close(handle)
    else:
        descriptors = []
        try:
            current = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(current)
            for part in path.parts[1:-1]:
                current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                descriptors.append(current)
            leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
            with os.fdopen(leaf, "rb") as stream:
                _plain(os.fstat(stream.fileno()))
                yield stream
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


def _read(root, relative, limit):
    with _open_regular(root, relative) as stream:
        before = os.fstat(stream.fileno())
        _plain(before)
        if before.st_size > limit:
            raise ValueError("artifact_size_limit_exceeded")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(data) > limit:
            raise ValueError("artifact_size_limit_exceeded")
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise ValueError("artifact_changed_during_read")
        return data, _time(after.st_mtime)


def _svg(data):
    # DTDs/entity expansion are unnecessary for generated slides.
    text = data.decode("utf-8-sig")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
        raise ValueError("svg_declarations_are_not_allowed")
    root = ElementTree.fromstring(text)
    if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
        raise ValueError("not_an_svg")


class _Reader:
    def __init__(self, root):
        self.root = root
        self.artifacts = {}
        self.warnings = []
        self.bytes = 0

    def warn(self, message):
        if len(self.warnings) < 100 and message not in self.warnings:
            self.warnings.append(message)

    def exists(self, relative):
        try:
            _checked_path(self.root, relative)
            return True
        except FileNotFoundError:
            return False
        except (OSError, ValueError):
            self.warn(relative + ": 路径不可读取，禁止链接或重解析点")
            return False

    def read(self, relative, limit=MAX_JSON_BYTES):
        if self.bytes >= MAX_TOTAL_BYTES:
            raise ValueError("snapshot_total_size_limit_exceeded")
        data, timestamp = _read(self.root, relative, min(limit, MAX_TOTAL_BYTES - self.bytes))
        self.bytes += len(data)
        self.artifacts[relative] = {"path": relative, "updated_at": timestamp, "digest": _digest(data)}
        return data

    def json(self, relative):
        def unique(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError("duplicate_json_key")
                obj[key] = value
            return obj
        value = json.loads(self.read(relative).decode("utf-8-sig"), object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise ValueError("expected_json_object")
        return value

    def preview(self, relative, kind, expected=None):
        try:
            data = self.read(relative, MAX_SVG_BYTES)
            _svg(data)
            version = _digest(data)
            if expected is not None and version != expected:
                raise ValueError("candidate_hash_mismatch")
            return {"preview_path": relative, "preview_kind": kind, "version": version,
                    "updated_at": self.artifacts[relative]["updated_at"]}
        except (OSError, ValueError, ElementTree.ParseError):
            self.warn(relative + ": SVG 不可读取、格式无效或候选摘要不匹配")
            return None


def _storyboard(reader):
    result = {}
    for relative in (".ppt-pilot/故事板.md", ".ppt-pilot/storyboard.md", "storyboard.md", "故事板.md"):
        if not reader.exists(relative):
            continue
        try:
            text = reader.read(relative).decode("utf-8-sig")
            current = None
            for line in text.splitlines():
                plain = line.replace("`", "").replace("**", "").strip()
                explicit = re.search(r"(?:^|[-\s])slide_id\s*[:：]\s*(S[0-9]{2,6})\b", plain)
                heading = re.match(r"#{1,6}\s+(S[0-9]{2,6})\b", plain)
                if explicit or heading:
                    current = (explicit or heading).group(1)
                    if current not in result and len(result) >= MAX_PAGES:
                        reader.warn("故事板页数超过显示上限")
                        break
                    result.setdefault(current, "")
                title = re.search(r"(?:^|[-\s])assertion_title\s*[:：]\s*(.+)", plain)
                if current and title:
                    result[current] = title.group(1).strip()[:500]
            return result
        except (OSError, ValueError):
            reader.warn(relative + ": 故事板暂时不可解析")
            return result
    return result


def _batch(reader, run):
    pointer = run.get("active_visual_generation_batch")
    legacy = run.get("visual_generation_transaction")
    if legacy:
        reader.warn("旧版生成事务等待工作流迁移；面板不执行迁移")
    if pointer is None:
        return {}, bool(legacy)
    result = {}
    try:
        if not isinstance(pointer, dict) or pointer.get("schema_version") != 2:
            raise ValueError("invalid_batch_pointer")
        batch_id = pointer.get("batch_id")
        if not isinstance(batch_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", batch_id):
            raise ValueError("invalid_batch_id")
        relative = ".ppt-pilot/visual-generation-batches/" + batch_id + ".json"
        if pointer.get("manifest_path") != relative:
            raise ValueError("batch_path_mismatch")
        manifest = reader.json(relative)
        ids, refs = manifest.get("ordered_slide_ids"), manifest.get("transaction_refs")
        if (manifest.get("schema_version") != 2 or manifest.get("kind") != "visual_generation_batch"
                or manifest.get("batch_id") != batch_id or not isinstance(ids, list)
                or not isinstance(refs, list) or not 1 <= len(ids) <= MAX_PAGES
                or len(ids) != len(refs) or not all(isinstance(sid, str) and SLIDE_ID.fullmatch(sid) for sid in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("invalid_batch_manifest")
        for sid, ref in zip(ids, refs):
            if not isinstance(ref, str) or not re.fullmatch(
                    r"\.ppt-pilot/visual-generation-transactions/" + sid + r"-[0-9a-f]{64}\.json", ref):
                raise ValueError("invalid_transaction_ref")
            tx = reader.json(ref)
            identity = "sha256:" + ref.rsplit("/", 1)[1][len(sid) + 1:-5]
            if (tx.get("schema_version") != 2 or tx.get("kind") != "visual_generation_transaction"
                    or tx.get("batch_id") != batch_id or tx.get("slide_id") != sid
                    or tx.get("transaction_id") != identity or tx.get("prompt_snapshot_id") != identity
                    or tx.get("state") not in TX_STATES
                    or tx.get("candidate_path") != "slides/.candidates/" + sid + "-" + identity[7:] + ".svg"
                    or tx.get("final_path") != "slides/" + sid + ".svg"):
                raise ValueError("transaction_owner_mismatch")
            result[sid] = tx
        return result, bool(legacy)
    except (OSError, ValueError, TypeError, RecursionError):
        reader.warn("当前生成批次或事务缺失、不可解析，或与运行指针不一致")
        return {}, True


def _files(reader, folder):
    result = []
    try:
        directory = _checked_path(reader.root, folder, directory=True)
        with os.scandir(directory) as entries:
            for index, entry in enumerate(entries):
                if index >= MAX_PAGES * 2:
                    reader.warn(folder + ": 文件数量超过显示上限")
                    break
                if re.fullmatch(r"S[0-9]{2,6}\.svg", entry.name):
                    result.append(entry.name[:-4])
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        reader.warn(folder + ": 目录不可读取，禁止链接或重解析点")
    return sorted(result, key=lambda sid: (int(sid[1:]), sid))


def _step_details(snapshot, review, storyboard_count):
    paths = [item["path"] for item in snapshot["artifacts"]]

    def document(label, *names):
        path = next((path for path in paths if path.rsplit("/", 1)[-1] in names), None)
        return label + "已记录：" + path if path else "尚未发现" + label + "产物"

    slides = snapshot["slides"]
    progress = snapshot["progress"]
    pages = "正式页 {done} / {total} 页".format(**progress) if progress["total"] else "尚未确定页面任务"
    dirty = sum(slide["dirty"] for slide in slides)
    active = sum(slide["status"] == "running" for slide in slides)
    blocked = sum(slide["status"] == "blocked" for slide in slides)
    samples = sum(slide["preview_kind"] == "sample" for slide in slides)
    details = {
        "brief": "确认用途、受众、页数和交付约束。\n" + document("简报", "简报.md", "brief.md"),
        "research": "解析资料、梳理事实并核对来源。\n" + document("研究", "研究.md", "research.md") + "；" + document("来源", "来源.md", "sources.md"),
        "outline": "组织论点、章节顺序和叙事主线。\n" + document("大纲", "大纲.md", "outline.md"),
        "storyboard": "细化每页标题、内容与证据安排。\n" + document("故事板", "故事板.md", "storyboard.md"),
        "manuscript_review": "审查内容逻辑与证据，解决阻断问题。\n" + document("文稿审查报告", "文稿审查.md", "manuscript-review.md"),
        "theme": "确定配色、字体和版式规范。\n" + document("主题配置", "theme.json"),
        "anchor": "制作样张，确认整套演示的视觉方向。\n可预览样张 %d 页；样张不计入正式交付" % samples,
        "production": "逐页生成、验证并保存正式 SVG。\n" + pages + "；待更新 %d 页；已记录处理中 %d 页；受阻 %d 页" % (dirty, active, blocked),
        "qa": "检查页面内容、视觉呈现与兼容性。\n" + document("质量检查报告", "质量检查报告.md", "qa-report.md") + "；文件存在不代表检查通过",
        "complete": "核对全部正式页与质量结论后交付。\n" + pages + "；" + ("已记录交付完成" if snapshot["status"] == "complete" else "尚未确认交付完成"),
    }
    if storyboard_count:
        details["storyboard"] += "；已解析 %d 页" % storyboard_count
    if isinstance(review, dict):
        for key, label in (("cycle", "审查周期"), ("round", "轮")):
            value = review.get(key)
            if type(value) is int and 0 < value <= 10000:
                details["manuscript_review"] += "；第 %d %s" % (value, label)
        findings = review.get("open_blocking_findings")
        if isinstance(findings, list):
            details["manuscript_review"] += "；未解决阻断 %d 项" % len(findings)
        pending = review.get("pending_round")
        if isinstance(pending, dict) and pending.get("status") not in {"completed", "applied"}:
            details["manuscript_review"] += "；等待本轮内容审查结果"
        elif review.get("state") in {"manuscript_blocked", "review_unavailable"}:
            details["manuscript_review"] += "；内容审查阻断，等待工作流处理"
    return details


def _tasks(snapshot, review=None, storyboard_count=0):
    stage, status = snapshot["stage"], snapshot["status"]
    details = _step_details(snapshot, review, storyboard_count)
    mapped = CHECKPOINTS.get(stage, BLOCKED_STAGES.get(stage, stage))
    names = [item[0] for item in STAGES]
    index = names.index(mapped) if mapped in names else -1
    checkpoint = stage in CHECKPOINTS
    result = []
    for position, (name, label) in enumerate(STAGES):
        state = "pending"
        if 0 <= position < index or position == index and checkpoint:
            state = "complete"
        elif position == index:
            state = status
        detail = details[name]
        if position == index and snapshot["notice"] and status in {"waiting", "blocked"}:
            detail += "\n需要处理：" + snapshot["notice"]["message"]
        result.append({"id": name, "label": label, "status": state, "detail": detail})
    return result


def _recovery_records(reader, run):
    records = {}
    invalid = False
    for name in ("pending_interaction", "manuscript_review", "visual_generation_blocker"):
        value = run.get(name)
        valid = value is None or isinstance(value, dict)
        if isinstance(value, dict):
            valid = all(value.get(field) is None or isinstance(value.get(field), str)
                        for field in ("status", "state", "reason", "question", "prompt"))
            if name == "pending_interaction" and value.get("status") not in (None, "pending", "answered", "applied", "cancelled"):
                valid = False
            pending_round = value.get("pending_round")
            if name == "manuscript_review" and pending_round is not None:
                valid = valid and isinstance(pending_round, dict)
                if isinstance(pending_round, dict):
                    valid = valid and (pending_round.get("status") is None or isinstance(pending_round.get("status"), str))
        if not valid:
            reader.warn(name + ": 恢复状态字段无效")
            invalid = True
            value = None
        records[name] = value
    return records, invalid


def _finish(reader, result, review=None, storyboard_count=0):
    artifacts = list(reader.artifacts.values())
    result["updated_at"] = max((item["updated_at"] for item in artifacts), default=None)
    result["artifacts"] = [{"path": item["path"], "updated_at": item["updated_at"]} for item in artifacts]
    result["warnings"] = reader.warnings
    result["tasks"] = _tasks(result, review, storyboard_count)
    basis = {"snapshot": result, "digests": [(item["path"], item["digest"]) for item in artifacts]}
    result["revision"] = _digest(json.dumps(basis, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return result


def build_snapshot(run_dir):
    """Return public state using only documented artifacts beneath ``run_dir``."""
    reader = _Reader(Path(run_dir))
    result = {"schema_version": 1, "deck_id": None, "mode": None, "stage": None,
              "status": "waiting", "slides": [], "progress": {"done": 0, "total": 0},
              "notice": {"kind": "initializing", "message": "等待工作流写入 run.json"}}
    paths = [path for path in (".ppt-pilot/run.json", "run.json") if reader.exists(path)]
    if len(paths) == 2:
        reader.warn("发现两个 run.json，无法确定唯一运行状态")
        result.update(status="blocked", notice={"kind": "state_conflict", "message": "运行状态文件冲突"})
        return _finish(reader, result)
    if not paths:
        if reader.warnings:
            result.update(status="unknown", notice={"kind": "unreadable_state", "message": "运行状态暂时不可读取"})
        return _finish(reader, result)
    if reader.warnings:
        result.update(status="unknown", notice={"kind": "unreadable_state", "message": "运行状态路径不安全，无法选定唯一状态文件"})
        return _finish(reader, result)
    try:
        run = reader.json(paths[0])
        stage = run.get("stage")
        if stage is not None and not isinstance(stage, str):
            raise ValueError("invalid_stage")
        for field in ("deck_id", "mode"):
            if run.get(field) is not None and not isinstance(run[field], str):
                raise ValueError("invalid_run_identity")
        result.update(deck_id=run.get("deck_id"), mode=run.get("mode"), stage=stage, notice=None)
    except (OSError, ValueError, TypeError, RecursionError):
        reader.warn(paths[0] + ": JSON 暂时不可解析、过大或字段无效；稍后自动重试")
        result.update(status="unknown", notice={"kind": "unreadable_state", "message": "运行状态暂时不可解析"})
        return _finish(reader, result)

    # Observe only this fixed activity allowlist; never enumerate source files
    # or return their text. Same-stage document work must still refresh the UI.
    for relative in OBSERVED_DOCUMENTS:
        if reader.exists(relative):
            try:
                reader.read(relative)
            except (OSError, ValueError):
                reader.warn(relative + ": 活动文件暂时不可读取或超过大小上限")
    planned = _storyboard(reader)
    storyboard_count = len(planned)
    raw_slides = run.get("slides")
    if isinstance(raw_slides, list):
        for item in raw_slides[:MAX_PAGES]:
            sid = item.get("slide_id", item.get("id")) if isinstance(item, dict) else item
            if isinstance(sid, str) and SLIDE_ID.fullmatch(sid):
                title = item.get("assertion_title", item.get("title", "")) if isinstance(item, dict) else ""
                planned.setdefault(sid, title[:500] if isinstance(title, str) else "")
    count = run.get("slide_count", run.get("count", raw_slides if type(raw_slides) is int else None))
    if count is not None and (type(count) is not int or count < 0):
        reader.warn("运行页数无效")
        count = None
    if count is not None and count > MAX_PAGES:
        reader.warn("运行页数超过显示上限 1000")
        count = MAX_PAGES
    if count and len(planned) < count:
        for number in range(1, count + 1):
            planned.setdefault("S%02d" % number, "")
            if len(planned) >= count:
                break
    transactions, batch_error = _batch(reader, run)
    finals = _files(reader, "slides")
    samples = {}
    for folder in (".ppt-pilot/samples", "samples"):
        for sid in _files(reader, folder):
            samples.setdefault(sid, folder + "/" + sid + ".svg")
    ids = list(planned)
    for sid in list(transactions) + finals + list(samples):
        if sid not in ids:
            ids.append(sid)
    dirty = run.get("dirty_slides", [])
    if not isinstance(dirty, list) or not all(isinstance(sid, str) and SLIDE_ID.fullmatch(sid) for sid in dirty):
        reader.warn("dirty_slides 状态无效")
        dirty = []
        batch_error = True
    for sid in dirty[:MAX_PAGES]:
        if sid not in ids:
            ids.append(sid)
    if len(ids) > MAX_PAGES:
        reader.warn("逐页任务数量超过显示上限 1000")
        ids = ids[:MAX_PAGES]
    done = 0
    has_active = False
    for sid in ids:
        slide = {"id": sid, "title": planned.get(sid) or sid, "status": "pending", "dirty": sid in dirty,
                 "preview_path": None, "preview_kind": None, "version": None, "updated_at": None,
                 "detail": "等待页面产物"}
        final = reader.preview("slides/" + sid + ".svg", "final") if sid in finals else None
        sample = reader.preview(samples[sid], "sample") if sid in samples and not final else None
        if final:
            slide.update(final)
            slide.update(status="complete", detail="正式页面已产出；不代表质量检查已通过")
            if not slide["dirty"]:
                done += 1
        elif sample:
            slide.update(sample)
            slide.update(status="waiting", detail="锚点样例可预览，尚非正式页面")
        tx = transactions.get(sid)
        if tx:
            tx_state = tx["state"]
            if final and not slide["dirty"] and tx_state != "promoted":
                done -= 1
            if tx_state in {"candidate_written", "validated"}:
                expected = tx.get("candidate_sha256")
                candidate = reader.preview(tx["candidate_path"], "candidate", expected) if isinstance(expected, str) and SHA256.fullmatch(expected) else None
                if candidate is None:
                    reader.warn(sid + ": 已持久化候选缺失或摘要不匹配")
                    batch_error = True
                    slide.update(status="blocked", detail="候选不可预览：摘要验证失败")
                else:
                    slide.update(candidate)
                    slide.update(status="running", detail="候选已持久化，等待验证或正式晋升")
                has_active = True
            elif tx_state == "failed":
                slide.update(status="blocked", detail="生成事务失败：" + str(tx.get("failure_reason") or "原因未记录")[:300])
                batch_error = True
            elif tx_state != "promoted":
                has_active = True
                slide.update(status="running", detail="已记录生成事务：" + tx_state + "；宿主活性未验证")
            elif not final:
                reader.warn(sid + ": 晋升事务缺少可读取的正式页面")
                slide.update(status="blocked", detail="正式页面缺失")
                batch_error = True
        if slide["dirty"]:
            if not tx or tx["state"] == "promoted":
                slide["status"] = "waiting"
            slide["detail"] += "；页面已标记待更新，已有正式预览可能过期"
        result["slides"].append(slide)
    result["progress"] = {"done": done, "total": len(ids)}

    recovery, invalid_recovery = _recovery_records(reader, run)
    batch_error = batch_error or invalid_recovery
    known_stage = stage in {item[0] for item in STAGES} or stage in CHECKPOINTS or stage in BLOCKED_STAGES
    result["status"] = "running" if known_stage else "unknown"
    if stage in BLOCKED_STAGES:
        result.update(status="blocked", notice={"kind": "pending_review", "message": "内容审查阻断，等待工作流处理"})
    if not known_stage:
        reader.warn("流程阶段未记录或无法识别")
    if stage == "complete":
        if ids and done == len(ids) and not has_active and not reader.warnings and not batch_error:
            result["status"] = "complete"
        else:
            result.update(status="blocked", notice={"kind": "incomplete_delivery", "message": "已记录完成，但正式页缺失、过期或仍有待处理状态"})
    if batch_error:
        result.update(status="blocked", notice={"kind": "generation_state", "message": "生成事务需要工作流检查"})

    pending = recovery["pending_interaction"]
    review = recovery["manuscript_review"]
    blocker = recovery["visual_generation_blocker"]
    if isinstance(blocker, dict) and blocker and blocker.get("status") not in {"resolved", "cleared"}:
        result.update(status="blocked", notice={"kind": "visual_generation_blocker", "message": "视觉生成阻断：" + str(blocker.get("reason") or "等待处理")[:300]})
    if isinstance(review, dict):
        if review.get("state") in {"manuscript_blocked", "review_unavailable"}:
            result.update(status="blocked", notice={"kind": "pending_review", "message": "内容审查阻断，等待工作流处理"})
        if isinstance(review.get("pending_round"), dict) and review["pending_round"].get("status") not in {"completed", "applied"}:
            result.update(status="waiting", notice={"kind": "pending_review", "message": "等待本轮内容审查结果"})
    if isinstance(pending, dict) and pending and pending.get("status") not in {"applied", "cancelled"}:
        message = "已回答，等待工作流应用答案" if pending.get("status") == "answered" else str(pending.get("question") or pending.get("prompt") or "等待确认或回答")[:2000]
        result.update(status="waiting", notice={"kind": "pending_interaction", "message": message})
    return _finish(reader, result, review, storyboard_count)


def read_preview(run_dir, relative):
    """Read only a currently authorized preview, then verify those exact bytes."""
    _relative(relative)
    snapshot = build_snapshot(Path(run_dir))
    match = next((slide for slide in snapshot["slides"] if slide["preview_path"] == relative), None)
    if match is None:
        raise FileNotFoundError("preview_not_in_current_allowlist")
    data, _ = _read(Path(run_dir), relative, MAX_SVG_BYTES)
    if _digest(data) != match["version"]:
        raise ValueError("preview_changed_during_read")
    # Exact bytes were already parsed by build_snapshot. Checking the digest
    # first also makes a malformed concurrent rewrite a handled HTTP error.
    return data
