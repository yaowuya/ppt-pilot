"""Validated JSON protocol for the optional Microsoft PowerPoint adapter."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Mapping, Optional, Sequence, Tuple

from .atomic_io import atomic_write_json
from .contract import validate_slide_id


REQUEST_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "capability_only",
        "protocol_dir",
        "candidate_path",
        "normalized_path",
        "geometry_candidate_path",
        "source_full_deck_path",
        "source_geometry_deck_path",
        "selected_svgs",
        "geometry_svgs",
        "render_directories",
        "ordered_slide_ids",
        "expected_counts",
        "config",
    }
)
RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "request_id",
        "capability",
        "powerpoint",
        "process",
        "stages",
        "counts",
        "renders",
        "normalized_path",
        "error",
        "exit_code",
    }
)
RENDER_KEYS = frozenset(
    {
        "source_full",
        "editable_full",
        "source_geometry",
        "editable_geometry",
    }
)
_EXPECTED_COUNT_KEYS = frozenset(
    {"slides", "top_level_shapes", "recursive_leaves", "recursive_groups"}
)
_REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class OfficeResult:
    capability: bool
    powerpoint_version: Optional[str]
    powerpoint_build: Optional[str]
    process_id: Optional[int]
    process_started_at: Optional[str]
    process_owned: bool
    stages: Tuple[Mapping[str, object], ...]
    counts: Mapping[str, int]
    renders: Mapping[str, Tuple[Mapping[str, str], ...]]
    normalized_path: Optional[str]
    error: Optional[Mapping[str, str]]
    exit_code: int


def _ordered_slide_ids(values: object) -> Tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("ordered_slide_ids must be a nonempty array")
    slide_ids = tuple(values)
    for slide_id in slide_ids:
        validate_slide_id(slide_id)
    if len(slide_ids) != len(set(slide_ids)):
        raise ValueError("ordered slide IDs must be unique")
    if slide_ids != tuple(sorted(slide_ids, key=lambda value: int(value[1:]))):
        raise ValueError("ordered slide IDs must use canonical numeric order")
    return slide_ids


def _validate_svg_entries(values: object, slide_ids: Sequence[str], label: str) -> None:
    if not isinstance(values, (list, tuple)) or len(values) != len(slide_ids):
        raise ValueError("{} must align with ordered slides".format(label))
    observed = []
    for entry in values:
        if not isinstance(entry, Mapping) or set(entry) != {"slide_id", "path"}:
            raise ValueError("{} entries are invalid".format(label))
        if not isinstance(entry.get("slide_id"), str) or not isinstance(entry.get("path"), str):
            raise ValueError("{} entries are invalid".format(label))
        if not entry["path"]:
            raise ValueError("{} path is empty".format(label))
        observed.append(entry["slide_id"])
    if tuple(observed) != tuple(slide_ids):
        raise ValueError("{} order differs from ordered slides".format(label))


def validate_office_request(request: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(request, Mapping) or set(request) != REQUEST_FIELDS:
        raise ValueError("office request fields must match schema exactly")
    if type(request.get("schema_version")) is not int or request.get("schema_version") != 1:
        raise ValueError("office request schema_version must equal integer 1")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise ValueError("office request_id is invalid")
    if type(request.get("capability_only")) is not bool:
        raise ValueError("capability_only must be boolean")
    for key in (
        "protocol_dir",
        "candidate_path",
        "normalized_path",
        "geometry_candidate_path",
        "source_full_deck_path",
        "source_geometry_deck_path",
    ):
        if not isinstance(request.get(key), str) or not request[key]:
            raise ValueError("{} must be a nonempty path".format(key))
    slide_ids = _ordered_slide_ids(request.get("ordered_slide_ids"))
    _validate_svg_entries(request.get("selected_svgs"), slide_ids, "selected_svgs")
    _validate_svg_entries(request.get("geometry_svgs"), slide_ids, "geometry_svgs")

    render_directories = request.get("render_directories")
    if not isinstance(render_directories, Mapping) or set(render_directories) != RENDER_KEYS:
        raise ValueError("render_directories fields are invalid")
    if any(not isinstance(value, str) or not value for value in render_directories.values()):
        raise ValueError("render_directories paths are invalid")

    counts = request.get("expected_counts")
    if not isinstance(counts, Mapping) or set(counts) != _EXPECTED_COUNT_KEYS:
        raise ValueError("expected_counts fields are invalid")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("expected_counts values are invalid")
    if counts["slides"] != len(slide_ids):
        raise ValueError("expected slide count differs from ordered slides")

    config = request.get("config")
    if not isinstance(config, Mapping) or set(config) != {"render_width", "render_height"}:
        raise ValueError("office config fields are invalid")
    if any(type(value) is not int or value <= 0 for value in config.values()):
        raise ValueError("office render dimensions are invalid")
    if (config["render_width"], config["render_height"]) != (1280, 720):
        raise ValueError("office render dimensions must equal 1280x720")
    return request


def _empty_renders():
    return {key: () for key in RENDER_KEYS}


def _unavailable_result(
    code: str,
    message: str,
    *,
    exit_code: int,
) -> OfficeResult:
    return OfficeResult(
        capability=False,
        powerpoint_version=None,
        powerpoint_build=None,
        process_id=None,
        process_started_at=None,
        process_owned=False,
        stages=(),
        counts={},
        renders=_empty_renders(),
        normalized_path=None,
        error={"code": code, "message": message, "stage": "capability"},
        exit_code=exit_code,
    )


def _validate_result_payload(
    payload: Mapping[str, object],
    request: Mapping[str, object],
) -> OfficeResult:
    if not isinstance(payload, Mapping) or set(payload) != RESULT_FIELDS:
        raise ValueError("office result fields must match schema exactly")
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        raise ValueError("office result schema_version is invalid")
    if payload.get("request_id") != request["request_id"]:
        raise ValueError("office result request_id differs")
    if type(payload.get("capability")) is not bool:
        raise ValueError("office result capability is invalid")
    if type(payload.get("exit_code")) is not int or payload["exit_code"] not in (0, 2, 3, 4):
        raise ValueError("office result exit_code is invalid")

    powerpoint = payload.get("powerpoint")
    process = payload.get("process")
    if not isinstance(powerpoint, Mapping) or set(powerpoint) != {"version", "build"}:
        raise ValueError("office result PowerPoint identity is invalid")
    if not isinstance(process, Mapping) or set(process) != {"pid", "started_at", "owned"}:
        raise ValueError("office result process identity is invalid")
    capability = payload["capability"]
    version = powerpoint.get("version")
    build = powerpoint.get("build")
    if capability:
        if not isinstance(version, str) or not version or not isinstance(build, str) or not build:
            raise ValueError("capable Office result lacks version/build identity")
    elif version is not None or build is not None:
        raise ValueError("unavailable Office result has version/build identity")
    if type(process.get("owned")) is not bool:
        raise ValueError("office result ownership is invalid")
    if process.get("pid") is not None and (
        type(process["pid"]) is not int or process["pid"] <= 0
    ):
        raise ValueError("office result PID is invalid")
    if process.get("started_at") is not None and not isinstance(process["started_at"], str):
        raise ValueError("office result process start time is invalid")
    if (process.get("pid") is None) != (process.get("started_at") is None):
        raise ValueError("office result PID/start-time pairing is invalid")
    if capability and process.get("pid") is None:
        raise ValueError("capable Office result lacks process identity")
    if process["owned"] and process.get("pid") is None:
        raise ValueError("office result ownership is impossible")

    stages = payload.get("stages")
    if not isinstance(stages, (list, tuple)):
        raise ValueError("office result stages are invalid")
    normalized_stages = []
    for stage in stages:
        if (
            not isinstance(stage, Mapping)
            or set(stage) != {"name", "status"}
            or not isinstance(stage.get("name"), str)
            or stage.get("status") not in ("pending", "running", "passed", "failed", "skipped")
        ):
            raise ValueError("office result stage is invalid")
        normalized_stages.append(dict(stage))

    counts = payload.get("counts")
    if not isinstance(counts, Mapping) or any(
        not isinstance(key, str) or type(value) is not int or value < 0
        for key, value in counts.items()
    ):
        raise ValueError("office result counts are invalid")
    success = payload["exit_code"] == 0 and capability
    capability_only = bool(request["capability_only"])
    if success and not capability_only and dict(counts) != dict(request["expected_counts"]):
        raise ValueError("office result counts differ from request")
    if success and capability_only and counts:
        raise ValueError("capability-only result must not report counts")
    renders = payload.get("renders")
    if not isinstance(renders, Mapping) or set(renders) != RENDER_KEYS:
        raise ValueError("office result render fields are invalid")
    normalized_renders = {}
    for key in RENDER_KEYS:
        entries = renders[key]
        if not isinstance(entries, (list, tuple)):
            raise ValueError("office result render list is invalid")
        normalized_entries = []
        for entry in entries:
            if (
                not isinstance(entry, Mapping)
                or set(entry) != {"slide_id", "path"}
                or not isinstance(entry.get("slide_id"), str)
                or not isinstance(entry.get("path"), str)
            ):
                raise ValueError("office result render entry is invalid")
            normalized_entries.append(dict(entry))
        normalized_renders[key] = tuple(normalized_entries)
    if success:
        if capability_only:
            if any(normalized_renders[key] for key in RENDER_KEYS):
                raise ValueError("capability-only result must not report renders")
        else:
            expected_ids = tuple(request["ordered_slide_ids"])
            for key in RENDER_KEYS:
                entries = normalized_renders[key]
                if tuple(entry["slide_id"] for entry in entries) != expected_ids:
                    raise ValueError("office result render order differs from request")
                expected_directory = Path(str(request["render_directories"][key])).absolute()
                for entry, slide_id in zip(entries, expected_ids):
                    expected_path = expected_directory / (slide_id + ".png")
                    if Path(entry["path"]).absolute() != expected_path:
                        raise ValueError("office result render path differs from request")

    error = payload.get("error")
    if error is not None and (
        not isinstance(error, Mapping)
        or set(error) != {"code", "message", "stage"}
        or any(not isinstance(error.get(key), str) for key in ("code", "message", "stage"))
    ):
        raise ValueError("office result error is invalid")
    normalized_path = payload.get("normalized_path")
    if normalized_path is not None and not isinstance(normalized_path, str):
        raise ValueError("office result normalized path is invalid")
    if payload["exit_code"] == 0:
        if capability and error is not None:
            raise ValueError("successful Office result contains an error")
        if not capability and (
            error is None or error.get("code") != "powerpoint_unavailable"
        ):
            raise ValueError("unavailable Office result lacks capability error")
    elif error is None:
        raise ValueError("failed Office result lacks structured error")
    if success and not capability_only:
        if normalized_path != request["normalized_path"]:
            raise ValueError("office result normalized path differs from request")
    elif capability_only and normalized_path is not None:
        raise ValueError("capability-only result must not report normalized path")

    return OfficeResult(
        capability=payload["capability"],
        powerpoint_version=powerpoint.get("version"),
        powerpoint_build=powerpoint.get("build"),
        process_id=process.get("pid"),
        process_started_at=process.get("started_at"),
        process_owned=process["owned"],
        stages=tuple(normalized_stages),
        counts=dict(counts),
        renders=normalized_renders,
        normalized_path=normalized_path,
        error=None if error is None else dict(error),
        exit_code=payload["exit_code"],
    )


def _generic_powershell_executable() -> Optional[str]:
    names = ("powershell.exe", "pwsh.exe") if os.name == "nt" else ("pwsh", "powershell")
    return next((value for name in names if (value := shutil.which(name))), None)


def _powershell_candidates_by_view() -> Tuple[Tuple[int, str], ...]:
    if os.name != "nt":
        return ()
    result = []
    generic = _generic_powershell_executable()
    native_view = 64 if sys.maxsize > 2**32 else 32
    if generic is not None:
        result.append((native_view, generic))
    if native_view == 64:
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        wow64 = system_root / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if wow64.is_file():
            result.append((32, str(wow64)))
    deduplicated = []
    seen = set()
    for view, executable in result:
        key = (view, os.path.normcase(os.path.abspath(executable)))
        if key not in seen:
            seen.add(key)
            deduplicated.append((view, executable))
    return tuple(deduplicated)


def _is_microsoft_powerpoint_server(server: object) -> bool:
    return bool(
        isinstance(server, str)
        and re.search(r"(?i)(?:^|[\\/\"'])POWERPNT\.EXE(?:[\"'\s]|$)", server)
    )


def _powershell_executable() -> Optional[str]:
    if os.name != "nt":
        return _generic_powershell_executable()
    for registry_view, executable in _powershell_candidates_by_view():
        if _is_microsoft_powerpoint_server(
            _powerpoint_local_server(registry_view)
        ):
            return executable
    return _generic_powershell_executable()


def invoke_office_verification(
    request: Mapping[str, object],
    script_path: Path,
    timeout_seconds: int,
) -> OfficeResult:
    validate_office_request(request)
    if type(timeout_seconds) is not int or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be a positive integer")
    script_path = Path(script_path)
    if not script_path.is_file():
        return _unavailable_result(
            "powerpoint_adapter_missing",
            "PowerPoint adapter script is missing",
            exit_code=4,
        )
    executable = _powershell_executable()
    if executable is None:
        return _unavailable_result(
            "powerpoint_unavailable",
            "PowerShell is unavailable",
            exit_code=0,
        )

    protocol_dir = Path(str(request["protocol_dir"]))
    request_path = protocol_dir / ("{}-request.json".format(request["request_id"]))
    result_path = protocol_dir / ("{}-result.json".format(request["request_id"]))
    ownership_path = Path(str(result_path) + ".owner.json")
    try:
        for stale_path in (result_path, ownership_path):
            if os.path.lexists(str(stale_path)):
                stale_path.unlink()
    except OSError as exc:
        return _unavailable_result(
            "powerpoint_protocol_failed",
            "stale PowerPoint result cannot be removed: {}".format(exc),
            exit_code=4,
        )
    atomic_write_json(request_path, request)
    command = [
        executable,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-RequestPath",
        str(request_path),
        "-ResultPath",
        str(result_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                _cleanup_claimed_powerpoint_process(ownership_path)
            except RuntimeError:
                pass
        return _unavailable_result(
            "powerpoint_timeout",
            "PowerPoint adapter timed out",
            exit_code=4,
        )
    except OSError as exc:
        return _unavailable_result(
            "powerpoint_launch_failed",
            "PowerPoint adapter cannot start: {}".format(exc),
            exit_code=4,
        )
    if not result_path.is_file():
        return _unavailable_result(
            "powerpoint_protocol_failed",
            "PowerPoint adapter produced no result: {}".format(completed.stderr.strip()),
            exit_code=4,
        )
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
        result = _validate_result_payload(payload, request)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return _unavailable_result(
            "powerpoint_protocol_failed",
            "PowerPoint result is invalid: {}".format(exc),
            exit_code=4,
        )
    if completed.returncode != result.exit_code:
        return _unavailable_result(
            "powerpoint_protocol_failed",
            "PowerPoint exit code differs from result payload",
            exit_code=4,
        )
    return result


def _powerpoint_local_server(registry_view: Optional[int] = None) -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    views = (registry_view,) if registry_view in (32, 64) else (64, 32)
    servers = []
    for view in views:
        access_flag = (
            winreg.KEY_WOW64_64KEY
            if view == 64
            else winreg.KEY_WOW64_32KEY
        )
        try:
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                r"PowerPoint.Application\CLSID",
                0,
                winreg.KEY_READ | access_flag,
            ) as key:
                clsid = winreg.QueryValue(key, None)
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                r"CLSID\{}\LocalServer32".format(clsid),
                0,
                winreg.KEY_READ | access_flag,
            ) as key:
                servers.append(str(winreg.QueryValue(key, None)))
        except OSError:
            continue
    return next(
        (
            server
            for server in servers
            if _is_microsoft_powerpoint_server(server)
        ),
        servers[0] if servers else None,
    )


def powerpoint_available() -> bool:
    if os.name != "nt" or _powershell_executable() is None:
        return False
    return _is_microsoft_powerpoint_server(_powerpoint_local_server())


def powerpoint_process_snapshot(
    *,
    strict: bool = False,
) -> Tuple[Tuple[int, str], ...]:
    executable = _powershell_executable()
    if os.name != "nt" or executable is None:
        if strict and os.name == "nt":
            raise RuntimeError("PowerShell is unavailable for process snapshot")
        return ()
    command = [
        executable,
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "$items=@(Get-Process -Name POWERPNT,wpp -ErrorAction SilentlyContinue | "
        "ForEach-Object { [pscustomobject]@{ pid=$_.Id; started_at=$_.StartTime.ToUniversalTime().ToString('o') } }); "
        "ConvertTo-Json -InputObject $items -Compress",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
            shell=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            raise RuntimeError("PowerPoint process snapshot command failed")
        value = json.loads(completed.stdout)
        entries = value if isinstance(value, list) else [value]
        result = []
        for entry in entries:
            if not (
                isinstance(entry, Mapping)
                and type(entry.get("pid")) is int
                and entry["pid"] > 0
                and isinstance(entry.get("started_at"), str)
                and entry["started_at"]
            ):
                raise RuntimeError("PowerPoint process snapshot payload is invalid")
            result.append((entry["pid"], entry["started_at"]))
        if len(result) != len(set(result)):
            raise RuntimeError("PowerPoint process snapshot contains duplicates")
        return tuple(sorted(result))
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        TypeError,
        RuntimeError,
    ) as exc:
        if strict:
            raise RuntimeError("unable to capture PowerPoint process snapshot: {}".format(exc)) from exc
        return ()


def _terminate_powerpoint_identity(process_id: int, started_at: str) -> None:
    executable = _powershell_executable()
    if os.name != "nt" or executable is None:
        return
    safe_started_at = started_at.replace("'", "''")
    script = (
        "$p=Get-Process -Id {} -ErrorAction Stop; "
        "if($p.StartTime.ToUniversalTime().ToString('o') -eq '{}')"
        "{{$p.Kill();[void]$p.WaitForExit(5000)}}"
    ).format(process_id, safe_started_at)
    completed = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "unable to clean timed-out PowerPoint process {}".format(process_id)
        )


def _cleanup_claimed_powerpoint_process(ownership_path: Path) -> None:
    if not os.path.lexists(str(ownership_path)):
        return
    if ownership_path.is_symlink() or not ownership_path.is_file():
        raise RuntimeError("PowerPoint ownership claim path is unsafe")
    try:
        claim = json.loads(ownership_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("PowerPoint ownership claim is unreadable") from exc
    if not isinstance(claim, Mapping) or set(claim) != {"pid", "started_at", "owned"}:
        raise RuntimeError("PowerPoint ownership claim fields are invalid")
    if claim.get("owned") is not True:
        return
    if (
        type(claim.get("pid")) is not int
        or claim["pid"] <= 0
        or not isinstance(claim.get("started_at"), str)
        or not claim["started_at"]
    ):
        raise RuntimeError("PowerPoint ownership claim identity is invalid")
    _terminate_powerpoint_identity(claim["pid"], claim["started_at"])
