import base64
import copy
import hashlib
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import read_text, repo_root, skill_root


STYLE_IDENTITY_FIELDS = (
    "selected_style_id",
    "selected_style_display_name",
    "style_kind",
    "style_manifest_version",
)


STABLE_RESOLVER_REASONS = (
    "registry_missing",
    "registry_path_unsafe",
    "registry_target_invalid",
    "registry_unreadable",
    "registry_malformed",
    "registry_schema_unsupported",
    "registry_duplicate_style",
    "style_not_registered",
    "style_kind_invalid",
    "entrypoint_missing",
    "entrypoint_path_unsafe",
    "entrypoint_target_invalid",
    "legacy_entrypoint_malformed",
    "legacy_identity_mismatch",
    "manifest_malformed",
    "manifest_schema_unsupported",
    "manifest_identity_mismatch",
    "manifest_version_invalid",
    "style_asset_field_missing",
    "style_asset_path_unsafe",
    "style_asset_target_invalid",
    "style_asset_unreadable",
    "prompt_field_missing",
    "prompt_path_unsafe",
    "prompt_file_missing",
    "prompt_target_invalid",
    "prompt_unreadable",
    "prompt_template_invalid",
    "prompt_snapshot_conflict",
)


BLOCKER_CASE_IDS = {
    "create-blocker-on-missing-prompt",
    "sanitize-unsafe-resource-to-none",
    "refresh-same-slide-blocker",
    "serialize-other-slide-blocker-first",
    "still-failing-skips-generator-and-svg",
    "durable-prompt-keeps-compiling-blocker-before-commit",
    "compiling-crash-recovers-by-compiled-and-clears-blocker",
    "precedence-unselected-pack-root-before-selected-prompt",
    "precedence-selected-tokens-before-prompt",
}


DUAL_DEFECT_EXPECTATIONS = {
    "precedence-unselected-pack-root-before-selected-prompt": {
        "defects": {"unselected_pack_root_invalid", "selected_prompt_invalid"},
        "reason": "entrypoint_path_unsafe",
    },
    "precedence-selected-tokens-before-prompt": {
        "defects": {"selected_tokens_target_invalid", "selected_prompt_invalid"},
        "reason": "style_asset_target_invalid",
    },
}


SAFE_RESOURCE_PREFIX = "assets/styles/"

REQUIRED_TRANSACTION_FIELDS = {
    "transaction_id",
    "slide_id",
    "generation_intent",
    "generation_trigger_id",
    "prompt_path",
    "prompt_snapshot_id",
    "compiled_prompt_sha256",
    "candidate_path",
    "final_path",
    "state",
    "generation_attempt",
    "candidate_sha256",
    "failure_reason",
}

TRANSACTION_STATES = (
    "compiling",
    "compiled",
    "generating",
    "candidate_written",
    "validated",
    "promoted",
    "failed",
)

TRANSACTION_FAILURE_REASONS = (
    "generator_unavailable",
    "generator_refused",
    "generator_timeout",
    "generator_output_malformed",
    "candidate_write_failed",
    "candidate_hash_mismatch",
    "svg_contract_failed",
    "locked_content_mismatch",
    "visual_qa_failed",
    "final_promotion_conflict",
    "transaction_state_conflict",
)

NORMAL_TRANSACTION_EDGES = (
    ("compiling", "compiled"),
    ("compiled", "generating"),
    ("generating", "candidate_written"),
    ("candidate_written", "validated"),
    ("validated", "promoted"),
)

FAILURE_TRANSACTION_EDGES = (
    ("generating", "failed"),
    ("candidate_written", "failed"),
    ("validated", "failed"),
)

RECOVERY_TRANSACTION_EDGES = (
    ("failed", "generating"),
    ("failed", "validated"),
)

TRANSACTION_CRASH_CASE_IDS = {
    "compiling-durable-prompt-match-commits-compiled",
    "compiling-durable-prompt-mismatch-recompiles",
    "generating-orphan-candidate-is-never-adopted",
    "candidate-written-hash-match-continues-validation",
    "candidate-written-hash-mismatch-fails",
    "validated-final-hash-match-promotes",
    "validated-final-conflict-fails",
    "illegal-recovery-transition-fails",
    "promoted-final-qa-cleans-transaction-and-dirty-slide",
}

EXPECTED_OPERATION_FIELDS = (
    "first_action",
    "stop",
    "resolver_calls",
    "generator_calls",
    "svg_writes",
    "stage_scan_calls",
    "style_fallback_calls",
    "patch_downgrade_calls",
)


V2_TRANSACTION_FIELDS = {
    "schema_version",
    "kind",
    "batch_id",
    "transaction_id",
    "slide_id",
    "generation_intent",
    "generation_trigger_id",
    "prompt_path",
    "prompt_snapshot_id",
    "compiled_prompt_sha256",
    "candidate_path",
    "final_path",
    "prior_final_sha256",
    "state",
    "generation_attempt",
    "candidate_sha256",
    "failure_reason",
    "dispatch_epoch",
    "host_attribution_id",
    "host_task_id",
    "validation",
    "timing",
}
V2_MANIFEST_FIELDS = {
    "schema_version",
    "kind",
    "batch_id",
    "batch_width",
    "ordered_slide_ids",
    "storyboard_snapshot_id",
    "theme_snapshot_id",
    "source_audit_snapshot_id",
    "generation_prompt_template_snapshot_id",
    "transaction_refs",
    "dispatch_epoch",
    "promotion_cursor",
    "blocker_cursor",
    "active_blocker_ref",
    "state",
    "created_at",
    "updated_at",
    "telemetry_summary",
}
V2_TRANSACTION_STATES = {
    "compiling",
    "compiled",
    "generating",
    "candidate_written",
    "validated",
    "promoted",
    "failed",
}
V2_MANIFEST_STATES = {"prepared", "active", "blocked", "completed"}
V2_FAILURE_REASONS = {
    "prompt_write_failed",
    "generator_unavailable",
    "generator_refused",
    "generator_timeout",
    "generator_output_malformed",
    "candidate_write_failed",
    "candidate_hash_mismatch",
    "svg_contract_failed",
    "locked_content_mismatch",
    "fact_source_mismatch",
    "visual_qa_failed",
    "final_promotion_conflict",
    "transaction_state_conflict",
}
V2_VALIDATION_CHECKS = {
    "xml",
    "office",
    "geometry_text",
    "fact_source",
    "narrative",
    "visual",
}
GENERATION_PROMPT_METADATA_FIELDS = (
    "slide_id",
    "storyboard_snapshot_id",
    "theme_snapshot_id",
    "applied_visual_revision_ids",
    "prompt_snapshot_id",
    "user_page_request",
    "expected_output",
    "workspace_output_path",
    "format",
)
TELEMETRY_SPAN_FIELDS = {
    "span_id",
    "parent_span_id",
    "critical_path_parent_ids",
    "run_id",
    "deck_id",
    "batch_id",
    "slide_id",
    "transaction_id",
    "attempt",
    "dispatch_epoch",
    "phase",
    "status",
    "error_reason",
    "host",
    "capability",
    "provider",
    "model",
    "isolation_mode",
    "fallback_mode",
    "host_attribution_id",
    "host_task_id",
    "wall_started_at",
    "wall_finished_at",
    "monotonic_started_ns",
    "monotonic_finished_ns",
    "duration_ms",
    "queue_ms",
    "timeout_ms",
    "input_tokens",
    "output_tokens",
    "finish_reason",
}
TELEMETRY_PHASES = {"compile", "model", "render", "qa", "promotion"}
_SHA256_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SLIDE_ID_RE = re.compile(r"^S[0-9]+$")
_BATCH_ID_RE = re.compile(r"^[0-9a-z][0-9a-z-]*$")


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_ID_RE.fullmatch(value) is None:
        raise ValueError("{} must be a sha256 identity".format(label))
    return value


def _transaction_ref(transaction: dict) -> str:
    suffix = transaction["transaction_id"].removeprefix("sha256:")
    return (
        ".ppt-pilot/visual-generation-transactions/"
        "{}-{}.json".format(transaction["slide_id"], suffix)
    )


def validate_v2_transaction(transaction: dict) -> None:
    if not isinstance(transaction, dict) or set(transaction) != V2_TRANSACTION_FIELDS:
        raise ValueError("v2 transaction fields differ")
    if transaction["schema_version"] != 2 or transaction["kind"] != "visual_generation_transaction":
        raise ValueError("v2 transaction identity differs")
    if (
        not isinstance(transaction["batch_id"], str)
        or _BATCH_ID_RE.fullmatch(transaction["batch_id"]) is None
    ):
        raise ValueError("v2 transaction batch ID is invalid")
    slide_id = transaction["slide_id"]
    if not isinstance(slide_id, str) or _SLIDE_ID_RE.fullmatch(slide_id) is None:
        raise ValueError("v2 transaction slide ID is invalid")
    transaction_id = _require_sha256(transaction["transaction_id"], "transaction_id")
    if transaction["prompt_snapshot_id"] != transaction_id:
        raise ValueError("transaction and prompt identities differ")
    _require_sha256(transaction["compiled_prompt_sha256"], "compiled_prompt_sha256")
    if transaction["generation_intent"] not in {
        "initial_generation",
        "user_recompose",
        "deterministic_fallback",
    }:
        raise ValueError("generation intent is invalid")
    if not isinstance(transaction["generation_trigger_id"], str) or not transaction[
        "generation_trigger_id"
    ]:
        raise ValueError("generation trigger is invalid")
    suffix = transaction_id.removeprefix("sha256:")
    if transaction["prompt_path"] != "generation-prompts/{}.md".format(slide_id):
        raise ValueError("prompt path differs")
    if transaction["candidate_path"] != "slides/.candidates/{}-{}.svg".format(
        slide_id,
        suffix,
    ):
        raise ValueError("candidate path differs")
    if transaction["final_path"] != "slides/{}.svg".format(slide_id):
        raise ValueError("final path differs")
    prior = transaction["prior_final_sha256"]
    if prior != "none":
        _require_sha256(prior, "prior_final_sha256")
    state = transaction["state"]
    if state not in V2_TRANSACTION_STATES:
        raise ValueError("transaction state is invalid")
    if type(transaction["generation_attempt"]) is not int or transaction[
        "generation_attempt"
    ] < 0:
        raise ValueError("generation attempt is invalid")
    candidate_sha256 = transaction["candidate_sha256"]
    if candidate_sha256 is not None:
        _require_sha256(candidate_sha256, "candidate_sha256")
    if state in {"compiling", "compiled", "generating"} and candidate_sha256 is not None:
        raise ValueError("candidate hash is premature")
    if state in {"candidate_written", "validated", "promoted"} and candidate_sha256 is None:
        raise ValueError("candidate hash is missing")
    if state == "failed":
        if transaction["failure_reason"] not in V2_FAILURE_REASONS:
            raise ValueError("failed transaction reason is invalid")
        if (
            transaction["failure_reason"] == "locked_content_mismatch"
            and not transaction["batch_id"].startswith("migration-")
        ):
            raise ValueError("legacy failure reason is migration-only")
    elif transaction["failure_reason"] is not None:
        raise ValueError("nonfailed transaction has a failure reason")
    if type(transaction["dispatch_epoch"]) is not int or transaction["dispatch_epoch"] < 0:
        raise ValueError("dispatch epoch is invalid")
    host_values = (
        transaction["host_attribution_id"],
        transaction["host_task_id"],
    )
    if (host_values[0] is None) != (host_values[1] is None) or any(
        value is not None and (not isinstance(value, str) or not value)
        for value in host_values
    ):
        raise ValueError("host task identity is invalid")
    validation = transaction["validation"]
    if (
        not isinstance(validation, dict)
        or set(validation) != {"state", "checks"}
        or validation["state"] not in {"pending", "running", "passed", "failed"}
        or not isinstance(validation["checks"], dict)
        or set(validation["checks"]) != V2_VALIDATION_CHECKS
        or any(
            value not in {"pending", "passed", "failed", "not_rendered"}
            for value in validation["checks"].values()
        )
    ):
        raise ValueError("validation payload is invalid")
    validation_state = validation["state"]
    checks = validation["checks"]
    if state in {"compiling", "compiled", "generating"} and validation_state != "pending":
        raise ValueError("validation state is premature")
    if state == "candidate_written" and validation_state not in {"pending", "running"}:
        raise ValueError("candidate validation state differs")
    if state in {"validated", "promoted"} and (
        validation_state != "passed"
        or any(
            checks[key] != "passed"
            for key in V2_VALIDATION_CHECKS - {"visual"}
        )
        or checks["visual"] not in {"passed", "not_rendered"}
    ):
        raise ValueError("validated transaction lacks passing checks")
    if state == "failed" and validation_state == "passed":
        raise ValueError("failed transaction claims passing validation")
    failure_reason = transaction["failure_reason"]
    if failure_reason == "svg_contract_failed" and (
        validation_state != "failed"
        or not any(
            checks[key] == "failed"
            for key in ("xml", "office", "geometry_text")
        )
    ):
        raise ValueError("SVG contract failure lacks a failed hard check")
    qa_failure_check = {
        "fact_source_mismatch": "fact_source",
        "locked_content_mismatch": "fact_source",
        "visual_qa_failed": "visual",
    }.get(failure_reason)
    if qa_failure_check is not None and (
        validation_state != "failed" or checks[qa_failure_check] != "failed"
    ):
        raise ValueError("QA failure lacks matching failed check")
    if not isinstance(transaction["timing"], list):
        raise ValueError("timing payload is invalid")


def validate_v2_manifest(manifest: dict, transactions: dict[str, dict]) -> None:
    if not isinstance(manifest, dict) or set(manifest) != V2_MANIFEST_FIELDS:
        raise ValueError("v2 manifest fields differ")
    if manifest["schema_version"] != 2 or manifest["kind"] != "visual_generation_batch":
        raise ValueError("v2 manifest identity differs")
    if (
        not isinstance(manifest["batch_id"], str)
        or _BATCH_ID_RE.fullmatch(manifest["batch_id"]) is None
    ):
        raise ValueError("v2 manifest batch ID is invalid")
    width = manifest["batch_width"]
    if type(width) is not int or width not in {3, 4}:
        raise ValueError("batch width is invalid")
    slide_ids = manifest["ordered_slide_ids"]
    if not isinstance(slide_ids, list) or not 1 <= len(slide_ids) <= width:
        raise ValueError("batch slide count is invalid")
    if (
        any(not isinstance(value, str) or _SLIDE_ID_RE.fullmatch(value) is None for value in slide_ids)
        or len(slide_ids) != len(set(slide_ids))
        or slide_ids != sorted(slide_ids, key=lambda value: int(value[1:]))
    ):
        raise ValueError("ordered slide IDs are invalid")
    for key in (
        "storyboard_snapshot_id",
        "theme_snapshot_id",
        "source_audit_snapshot_id",
        "generation_prompt_template_snapshot_id",
    ):
        _require_sha256(manifest[key], key)
    refs = manifest["transaction_refs"]
    if not isinstance(refs, list) or len(refs) != len(slide_ids):
        raise ValueError("transaction refs are invalid")
    if set(transactions) != set(refs):
        raise ValueError("transaction inventory differs from refs")
    for slide_id, ref in zip(slide_ids, refs):
        transaction = transactions.get(ref)
        if transaction is None:
            raise ValueError("transaction ref is missing")
        validate_v2_transaction(transaction)
        if (
            transaction["batch_id"] != manifest["batch_id"]
            or transaction["slide_id"] != slide_id
            or ref != _transaction_ref(transaction)
        ):
            raise ValueError("transaction ref alignment differs")
    if type(manifest["dispatch_epoch"]) is not int or manifest["dispatch_epoch"] < 0:
        raise ValueError("manifest dispatch epoch is invalid")
    for key in ("promotion_cursor", "blocker_cursor"):
        if type(manifest[key]) is not int or not 0 <= manifest[key] <= len(slide_ids):
            raise ValueError("manifest cursor is untrusted")
    blocker_ref = manifest["active_blocker_ref"]
    if blocker_ref is not None and blocker_ref not in refs:
        raise ValueError("active blocker ref is invalid")
    if manifest["state"] not in V2_MANIFEST_STATES:
        raise ValueError("manifest state is invalid")
    for key in ("created_at", "updated_at"):
        if not isinstance(manifest[key], str) or not manifest[key]:
            raise ValueError("manifest timestamp is invalid")
    if not isinstance(manifest["telemetry_summary"], dict):
        raise ValueError("telemetry summary is invalid")


def rebuild_batch_cursors(
    manifest: dict,
    transactions: dict[str, dict],
) -> tuple[int, int]:
    promotion_cursor = 0
    for ref in manifest["transaction_refs"]:
        if transactions[ref]["state"] != "promoted":
            break
        promotion_cursor += 1
    blocker_cursor = len(manifest["transaction_refs"])
    for index, ref in enumerate(manifest["transaction_refs"]):
        if transactions[ref]["state"] == "failed":
            blocker_cursor = index
            break
    return promotion_cursor, blocker_cursor


def validated_final_outcome(
    transaction: dict,
    observed_final_sha256: str,
) -> str:
    validate_v2_transaction(transaction)
    if transaction["state"] != "validated":
        raise ValueError("transaction is not validated")
    if observed_final_sha256 == transaction["candidate_sha256"]:
        return "commit_promoted"
    if observed_final_sha256 == transaction["prior_final_sha256"]:
        return "retry_atomic_promotion"
    return "final_promotion_conflict"


def canonical_v2_json_bytes(value: dict) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _migration_sha(transaction_id: str, label: str) -> str:
    return "sha256:" + hashlib.sha256(
        ("v1-migration\0" + transaction_id + "\0" + label).encode("utf-8")
    ).hexdigest()


def _migration_validation(state: str, has_candidate: bool) -> dict:
    if state in {"validated", "promoted"}:
        validation_state = "passed"
        check_state = "passed"
    elif state == "failed" and has_candidate:
        validation_state = "failed"
        check_state = "failed"
    else:
        validation_state = "pending"
        check_state = "pending"
    return {
        "state": validation_state,
        "checks": {
            key: check_state
            for key in sorted(V2_VALIDATION_CHECKS)
        },
    }


def _migration_conflict(run: dict) -> dict:
    return {
        "status": "visual_generation_state_conflict",
        "run": copy.deepcopy(run),
        "transaction": None,
        "manifest": None,
        "transaction_bytes": None,
        "manifest_bytes": None,
        "run_bytes": canonical_v2_json_bytes(run),
        "write_order": [],
        "writes": 0,
        "generator_calls": 0,
    }


def migrate_v1_run_to_v2(run: dict, corpus_case: dict) -> dict:
    source_run = copy.deepcopy(run)
    has_v1 = "visual_generation_transaction" in source_run
    has_v2 = "active_visual_generation_batch" in source_run
    if has_v1 and has_v2:
        return _migration_conflict(source_run)
    if has_v2:
        existing_transaction = corpus_case.get("existing_transaction")
        existing_manifest = corpus_case.get("existing_manifest")
        pointer = source_run.get("active_visual_generation_batch")
        try:
            if not isinstance(existing_transaction, dict) or not isinstance(
                existing_manifest,
                dict,
            ):
                raise ValueError("v2 durable files are missing")
            existing_ref = _transaction_ref(existing_transaction)
            validate_v2_manifest(
                existing_manifest,
                {existing_ref: existing_transaction},
            )
            if (
                not isinstance(pointer, dict)
                or set(pointer) != {"schema_version", "batch_id", "manifest_path"}
                or pointer["schema_version"] != 2
                or pointer["batch_id"] != existing_manifest["batch_id"]
                or pointer["manifest_path"]
                != ".ppt-pilot/visual-generation-batches/{}.json".format(
                    existing_manifest["batch_id"]
                )
            ):
                raise ValueError("v2 pointer differs from durable manifest")
        except (KeyError, TypeError, ValueError):
            return _migration_conflict(source_run)
        return {
            "status": "no_op",
            "run": source_run,
            "transaction": copy.deepcopy(existing_transaction),
            "manifest": copy.deepcopy(existing_manifest),
            "transaction_bytes": canonical_v2_json_bytes(existing_transaction),
            "manifest_bytes": canonical_v2_json_bytes(existing_manifest),
            "run_bytes": canonical_v2_json_bytes(source_run),
            "write_order": [],
            "writes": 0,
            "generator_calls": 0,
        }
    if not has_v1:
        return _migration_conflict(source_run)
    if "observed_prior_final_sha256" not in corpus_case:
        return _migration_conflict(source_run)

    legacy = source_run["visual_generation_transaction"]
    transaction_id = legacy["transaction_id"]
    batch_id = "migration-" + transaction_id.removeprefix("sha256:")[:24]
    candidate_sha256 = legacy["candidate_sha256"]
    transaction = {
        "schema_version": 2,
        "kind": "visual_generation_transaction",
        "batch_id": batch_id,
        "transaction_id": transaction_id,
        "slide_id": legacy["slide_id"],
        "generation_intent": legacy["generation_intent"],
        "generation_trigger_id": legacy["generation_trigger_id"],
        "prompt_path": legacy["prompt_path"],
        "prompt_snapshot_id": legacy["prompt_snapshot_id"],
        "compiled_prompt_sha256": legacy["compiled_prompt_sha256"],
        "candidate_path": legacy["candidate_path"],
        "final_path": legacy["final_path"],
        "prior_final_sha256": corpus_case["observed_prior_final_sha256"],
        "state": legacy["state"],
        "generation_attempt": legacy["generation_attempt"],
        "candidate_sha256": candidate_sha256,
        "failure_reason": legacy["failure_reason"],
        "dispatch_epoch": 0,
        "host_attribution_id": None,
        "host_task_id": None,
        "validation": _migration_validation(
            legacy["state"],
            candidate_sha256 is not None,
        ),
        "timing": [],
    }
    validate_v2_transaction(transaction)
    transaction_ref = _transaction_ref(transaction)
    promoted = 1 if transaction["state"] == "promoted" else 0
    failed = transaction["state"] == "failed"
    manifest = {
        "schema_version": 2,
        "kind": "visual_generation_batch",
        "batch_id": batch_id,
        "batch_width": 4,
        "ordered_slide_ids": [transaction["slide_id"]],
        "storyboard_snapshot_id": _migration_sha(transaction_id, "storyboard"),
        "theme_snapshot_id": _migration_sha(transaction_id, "theme"),
        "source_audit_snapshot_id": _migration_sha(transaction_id, "source-audit"),
        "generation_prompt_template_snapshot_id": _migration_sha(
            transaction_id,
            "generation-prompt-template",
        ),
        "transaction_refs": [transaction_ref],
        "dispatch_epoch": 0,
        "promotion_cursor": promoted,
        "blocker_cursor": 0 if failed else 1,
        "active_blocker_ref": transaction_ref if failed else None,
        "state": "completed" if promoted else ("blocked" if failed else "active"),
        "created_at": "1970-01-01T00:00:00Z",
        "updated_at": "1970-01-01T00:00:00Z",
        "telemetry_summary": {"migration": "v1"},
    }
    validate_v2_manifest(manifest, {transaction_ref: transaction})
    migrated_run = copy.deepcopy(source_run)
    del migrated_run["visual_generation_transaction"]
    migrated_run["active_visual_generation_batch"] = {
        "schema_version": 2,
        "batch_id": batch_id,
        "manifest_path": ".ppt-pilot/visual-generation-batches/{}.json".format(
            batch_id
        ),
    }
    transaction_bytes = canonical_v2_json_bytes(transaction)
    manifest_bytes = canonical_v2_json_bytes(manifest)
    durable = corpus_case.get("durable", {})
    encoded_transaction = durable.get("transaction_bytes_base64")
    encoded_manifest = durable.get("manifest_bytes_base64")
    if encoded_manifest is not None and encoded_transaction is None:
        return _migration_conflict(source_run)
    try:
        durable_transaction_bytes = (
            None
            if encoded_transaction is None
            else base64.b64decode(encoded_transaction, validate=True)
        )
        durable_manifest_bytes = (
            None
            if encoded_manifest is None
            else base64.b64decode(encoded_manifest, validate=True)
        )
    except (TypeError, ValueError):
        return _migration_conflict(source_run)
    if (
        durable_transaction_bytes is not None
        and durable_transaction_bytes != transaction_bytes
    ):
        return _migration_conflict(source_run)
    if durable_manifest_bytes is not None and durable_manifest_bytes != manifest_bytes:
        return _migration_conflict(source_run)
    write_order = []
    if durable_transaction_bytes is None:
        write_order.append("transaction")
    if durable_manifest_bytes is None:
        write_order.append("manifest")
    write_order.append("run")
    return {
        "status": "migrated",
        "run": migrated_run,
        "transaction": transaction,
        "manifest": manifest,
        "transaction_bytes": transaction_bytes,
        "manifest_bytes": manifest_bytes,
        "run_bytes": canonical_v2_json_bytes(migrated_run),
        "write_order": write_order,
        "writes": len(write_order),
        "generator_calls": 0,
    }


def negotiate_host_capability(
    case: dict,
    configured_width: int = 4,
) -> dict:
    width = case.get("configured_width", configured_width)
    if type(width) is not int or width not in {3, 4}:
        raise ValueError("configured batch width must be 3 or 4")
    capability = case["capability"]
    required_fields = {
        "native_fresh_isolation",
        "remote_fresh_isolation",
        "concurrent_tasks",
        "durable_lookup",
        "prompt_by_value",
        "fresh_history",
        "filesystem_none",
        "tools_none",
        "attribution",
        "nested_cli_required",
        "credential_probe_required",
        "current_context_only",
    }
    if not isinstance(capability, dict) or set(capability) != required_fields:
        raise ValueError("host capability fields differ")
    forbidden = any(
        capability[key]
        for key in (
            "nested_cli_required",
            "credential_probe_required",
            "current_context_only",
        )
    )
    safe_interface = all(
        capability[key]
        for key in (
            "prompt_by_value",
            "fresh_history",
            "filesystem_none",
            "tools_none",
            "attribution",
        )
    )
    if forbidden or not safe_interface:
        return {
            "mode": None,
            "selected_width": 0,
            "error": "generator_unavailable",
            "lookup_permitted": False,
        }
    if capability["native_fresh_isolation"]:
        mode = "native"
    elif capability["remote_fresh_isolation"]:
        mode = "remote"
    else:
        return {
            "mode": None,
            "selected_width": 0,
            "error": "generator_unavailable",
            "lookup_permitted": False,
        }
    selected_width = (
        width
        if capability["concurrent_tasks"] and capability["durable_lookup"]
        else 1
    )
    result_error = {
        None: None,
        "completed": None,
        "refused": "generator_refused",
        "timeout": "generator_timeout",
        "unknown": "generator_unavailable",
    }.get(case.get("task_result"), "generator_unavailable")
    return {
        "mode": mode,
        "selected_width": selected_width,
        "error": result_error,
        "lookup_permitted": bool(capability["durable_lookup"]),
    }


def _validate_prompt_by_value(prompt: object, transaction: dict) -> str:
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("complete prompt bytes are required by value")
    separator = "## Compiled Prompt\n\n"
    if prompt.count(separator) != 1:
        raise ValueError("prompt envelope separator is invalid")
    prefix, body = prompt.split(separator, 1)
    lines = prefix.splitlines()
    expected_title = "# {} 页面生成 Prompt".format(transaction["slide_id"])
    if (
        len(lines) != 13
        or lines[0] != expected_title
        or lines[1] != ""
        or lines[2] != "## Snapshot metadata"
        or lines[-1] != ""
    ):
        raise ValueError("prompt metadata envelope is incomplete")
    metadata = {}
    for line, field in zip(lines[3:12], GENERATION_PROMPT_METADATA_FIELDS):
        marker = "- **{}**：".format(field)
        if not line.startswith(marker) or not line[len(marker) :]:
            raise ValueError("prompt metadata fields differ")
        metadata[field] = line[len(marker) :]
    if (
        metadata["slide_id"] != transaction["slide_id"]
        or metadata["prompt_snapshot_id"] != transaction["prompt_snapshot_id"]
        or metadata["workspace_output_path"] != transaction["final_path"]
        or metadata["format"] != "creative-brief-v1"
        or not body.startswith("# Role")
        or not body.endswith("\n")
        or body.endswith("\n\n")
    ):
        raise ValueError("prompt envelope is incomplete")
    body_sha256 = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    if body_sha256 != transaction["compiled_prompt_sha256"]:
        raise ValueError("prompt body hash differs from transaction")
    return prompt


def schedule_epoch(
    manifest: dict,
    transactions: dict[str, dict],
    capability: dict,
) -> list[dict]:
    validate_v2_manifest(manifest, transactions)
    if capability.get("error") is not None:
        return []
    width = capability.get("selected_width")
    if type(width) is not int or width < 1:
        return []
    prompt_bytes_by_slide = capability.get("prompt_bytes_by_slide")
    if not isinstance(prompt_bytes_by_slide, dict):
        raise ValueError("prompt bytes by slide are required")
    tasks = []
    for slide_id, ref in zip(
        manifest["ordered_slide_ids"],
        manifest["transaction_refs"],
    ):
        transaction = transactions[ref]
        if transaction["state"] != "compiled":
            continue
        already_scheduled = bool(
            transaction["dispatch_epoch"] == manifest["dispatch_epoch"]
            and transaction["host_task_id"] is not None
        )
        if already_scheduled:
            continue
        prompt = _validate_prompt_by_value(
            prompt_bytes_by_slide.get(slide_id),
            transaction,
        )
        tasks.append(
            {
                "slide_id": slide_id,
                "transaction_id": transaction["transaction_id"],
                "dispatch_epoch": manifest["dispatch_epoch"],
                "prompt_by_value": prompt,
                "fresh_history": True,
                "filesystem": "none",
                "tools": "none",
                "output": "text",
                "expected_fence": "xml",
                "timeout_ms": 120000,
                "cancellation": True,
            }
        )
        if len(tasks) == width:
            break
    return tasks


def eligible_promotions(
    manifest: dict,
    transactions: dict[str, dict],
) -> list[str]:
    validate_v2_manifest(manifest, transactions)
    return [
        slide_id
        for slide_id, ref in zip(
            manifest["ordered_slide_ids"],
            manifest["transaction_refs"],
        )
        if transactions[ref]["state"] == "validated"
    ]


def lowest_eligible_blocker(
    manifest: dict,
    transactions: dict[str, dict],
):
    validate_v2_manifest(manifest, transactions)
    return next(
        (
            slide_id
            for slide_id, ref in zip(
                manifest["ordered_slide_ids"],
                manifest["transaction_refs"],
            )
            if transactions[ref]["state"] == "failed"
        ),
        None,
    )


def promote_in_order(
    manifest: dict,
    transactions: dict[str, dict],
    observed_final_sha256_by_slide: dict[str, str],
) -> list[dict]:
    refs_by_slide = dict(
        zip(manifest["ordered_slide_ids"], manifest["transaction_refs"])
    )
    decisions = []
    for slide_id in eligible_promotions(manifest, transactions):
        transaction = transactions[refs_by_slide[slide_id]]
        observed = observed_final_sha256_by_slide.get(slide_id)
        if not isinstance(observed, str):
            raise ValueError("observed final hash is required")
        decisions.append(
            {
                "slide_id": slide_id,
                "outcome": validated_final_outcome(transaction, observed),
                "candidate_sha256": transaction["candidate_sha256"],
                "prior_final_sha256": transaction["prior_final_sha256"],
            }
        )
    return decisions


_VISIBLE_INTERNAL_SOURCE_ID = re.compile(r"\bSRC-[0-9]+\b", re.IGNORECASE)


def fact_source_visible_text_result(
    svg_text: str,
    *,
    human_readable_citation_requested: bool = False,
):
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return "svg_contract_failed"
    visible = " ".join(
        "".join(element.itertext())
        for element in root.iter()
        if isinstance(element.tag, str)
        and element.tag.rsplit("}", 1)[-1] == "text"
    )
    if _VISIBLE_INTERNAL_SOURCE_ID.search(visible):
        return "fact_source_mismatch"
    human_citation_visible = re.search(
        r"(?i)(?:来源\s*[:：]|source\s*:)",
        visible,
    ) is not None
    if human_citation_visible and not human_readable_citation_requested:
        return "fact_source_mismatch"
    return None


def validate_span(span: dict) -> None:
    if not isinstance(span, dict) or set(span) != TELEMETRY_SPAN_FIELDS:
        raise ValueError("telemetry span fields differ")
    for key in ("span_id", "run_id", "deck_id", "batch_id"):
        if not isinstance(span[key], str) or not span[key]:
            raise ValueError("telemetry identity is invalid")
    if span["parent_span_id"] is not None and (
        not isinstance(span["parent_span_id"], str) or not span["parent_span_id"]
    ):
        raise ValueError("telemetry parent is invalid")
    parents = span["critical_path_parent_ids"]
    if (
        not isinstance(parents, list)
        or any(not isinstance(parent, str) or not parent for parent in parents)
        or len(parents) != len(set(parents))
        or span["span_id"] in parents
    ):
        raise ValueError("critical path parents are invalid")
    if span["phase"] not in TELEMETRY_PHASES:
        raise ValueError("telemetry phase is invalid")
    if span["status"] not in {"passed", "failed", "cancelled"}:
        raise ValueError("telemetry status is invalid")
    if span["status"] == "failed":
        if not isinstance(span["error_reason"], str) or not span["error_reason"]:
            raise ValueError("failed telemetry span lacks reason")
    elif span["error_reason"] is not None:
        raise ValueError("successful telemetry span has error reason")
    for key in ("attempt", "dispatch_epoch", "duration_ms", "queue_ms"):
        if type(span[key]) is not int or span[key] < 0:
            raise ValueError("telemetry integer is invalid")
    started = span["monotonic_started_ns"]
    finished = span["monotonic_finished_ns"]
    if (
        type(started) is not int
        or type(finished) is not int
        or started < 0
        or finished < started
        or (finished - started) % 1_000_000
        or span["duration_ms"] != (finished - started) // 1_000_000
    ):
        raise ValueError("telemetry duration differs")
    if span["phase"] == "model" and span["queue_ms"] > span["duration_ms"]:
        raise ValueError("model queue exceeds duration")
    for key in ("timeout_ms", "input_tokens", "output_tokens"):
        if span[key] is not None and (type(span[key]) is not int or span[key] < 0):
            raise ValueError("optional telemetry integer is invalid")
    for key in (
        "slide_id",
        "transaction_id",
        "host",
        "capability",
        "provider",
        "model",
        "isolation_mode",
        "fallback_mode",
        "host_attribution_id",
        "host_task_id",
        "finish_reason",
    ):
        if span[key] is not None and (
            not isinstance(span[key], str) or not span[key]
        ):
            raise ValueError("optional telemetry text is invalid")
    for key in ("wall_started_at", "wall_finished_at"):
        if not isinstance(span[key], str) or not span[key]:
            raise ValueError("wall timestamp is invalid")


def _deduplicated_spans(spans: list[dict]) -> dict[str, dict]:
    result = {}
    for span in spans:
        validate_span(span)
        existing = result.get(span["span_id"])
        if existing is not None and existing != span:
            raise ValueError("replayed span bytes differ")
        result[span["span_id"]] = span
    if not result:
        raise ValueError("telemetry spans are empty")
    return result


def critical_path_duration_ms(spans: list[dict]) -> int:
    indexed = _deduplicated_spans(spans)
    for span in indexed.values():
        references = [*span["critical_path_parent_ids"]]
        if span["parent_span_id"] is not None:
            references.append(span["parent_span_id"])
        if any(reference not in indexed for reference in references):
            raise ValueError("telemetry parent is missing")
        if any(
            indexed[parent_id]["monotonic_finished_ns"]
            > span["monotonic_started_ns"]
            for parent_id in span["critical_path_parent_ids"]
        ):
            raise ValueError("critical dependency overlaps its child")
    hierarchy_visiting = set()
    hierarchy_done = set()

    def validate_hierarchy(span_id):
        if span_id in hierarchy_done:
            return
        if span_id in hierarchy_visiting:
            raise ValueError("telemetry parent hierarchy has a cycle")
        hierarchy_visiting.add(span_id)
        parent_id = indexed[span_id]["parent_span_id"]
        if parent_id is not None:
            validate_hierarchy(parent_id)
        hierarchy_visiting.remove(span_id)
        hierarchy_done.add(span_id)

    for span_id in indexed:
        validate_hierarchy(span_id)
    promotions = [
        span
        for span in indexed.values()
        if span["phase"] == "promotion"
    ]
    if (
        any(
            not isinstance(span["slide_id"], str)
            or _SLIDE_ID_RE.fullmatch(span["slide_id"]) is None
            for span in promotions
        )
        or len({span["slide_id"] for span in promotions}) != len(promotions)
    ):
        raise ValueError("promotion slide order is invalid")
    promotions.sort(key=lambda span: int(span["slide_id"][1:]))
    for previous, current in zip(promotions, promotions[1:]):
        if previous["span_id"] not in current["critical_path_parent_ids"]:
            raise ValueError("promotion spans do not form a serial dependency chain")
    visiting = set()
    memo = {}

    def duration(span_id):
        if span_id in memo:
            return memo[span_id]
        if span_id in visiting:
            raise ValueError("telemetry dependency graph has a cycle")
        visiting.add(span_id)
        span = indexed[span_id]
        parent_duration = max(
            (
                duration(parent_id)
                for parent_id in span["critical_path_parent_ids"]
            ),
            default=0,
        )
        value = parent_duration + span["duration_ms"]
        visiting.remove(span_id)
        memo[span_id] = value
        return value

    return max(duration(span_id) for span_id in indexed)


def batch_wall_duration_ms(spans: list[dict]) -> int:
    indexed = _deduplicated_spans(spans)
    started = min(span["monotonic_started_ns"] for span in indexed.values())
    finished = max(span["monotonic_finished_ns"] for span in indexed.values())
    if (finished - started) % 1_000_000:
        raise ValueError("batch wall duration is not an integer millisecond")
    return (finished - started) // 1_000_000


def evaluate_telemetry_non_authoritatively(
    transaction: dict,
    spans: list[dict],
) -> dict:
    validate_v2_transaction(transaction)
    preserved = copy.deepcopy(transaction)
    try:
        metrics = {
            "critical_path_ms": critical_path_duration_ms(spans),
            "batch_wall_ms": batch_wall_duration_ms(spans),
        }
        diagnostic = None
    except ValueError:
        metrics = None
        diagnostic = "telemetry_diagnostic_failed"
    return {
        "transaction": preserved,
        "diagnostic": diagnostic,
        "metrics": metrics,
    }


def parse_brief_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for section_fields in parse_brief_sections(path).values():
        fields.update(section_fields)
    return fields


def parse_brief_sections(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in read_text(path).splitlines():
        if line.startswith("## "):
            current = line.removeprefix("## ").strip()
            sections[current] = {}
            continue
        stripped = line.strip()
        if current is None or not stripped.startswith("- ") or ":" not in stripped:
            continue
        key, value = stripped.removeprefix("- ").split(":", 1)
        sections[current][key.strip()] = value.strip()
    return sections


class VisualGenerationContractTests(unittest.TestCase):
    REQUIRED_BRIEF_HEADINGS = {
        "来源与版本",
        "锁定内容",
        "信息层级",
        "构图",
        "视觉系统",
        "修订模式",
        "输出与质量要求",
    }

    def setUp(self) -> None:
        self.reference = skill_root() / "references" / "visual-brief-and-generation.md"
        self.skill = skill_root() / "SKILL.md"
        self.workflow = skill_root() / "references" / "workflow.md"
        self.artifact = skill_root() / "references" / "artifact-contract.md"
        self.qa = skill_root() / "references" / "qa-and-revision.md"
        self.brief = repo_root() / "tests" / "fixtures" / "visual-briefs" / "S05.md"
        self.style_manifest = (
            skill_root()
            / "assets"
            / "styles"
            / "canway-midyear-review"
            / "manifest.json"
        )
        self.precedence = repo_root() / "tests" / "fixtures" / "visual-revision-precedence.json"
        self.blocker = repo_root() / "tests" / "fixtures" / "style-prompt-blocker-cases.json"
        self.transaction = repo_root() / "tests" / "fixtures" / "visual-generation-transaction-cases.json"
        self.batch_v2 = repo_root() / "tests" / "fixtures" / "visual-generation-batch-v2-cases.json"
        self.host_capabilities = repo_root() / "tests" / "fixtures" / "visual-generation-host-capability-cases.json"
        self.timing_cases = repo_root() / "tests" / "fixtures" / "visual-generation-timing-cases.json"

    def test_telemetry_span_schema_and_dag_critical_path(self):
        self.assertTrue(self.timing_cases.is_file(), f"missing fixture: {self.timing_cases}")
        payload = json.loads(read_text(self.timing_cases))
        self.assertEqual(set(payload["span_schema"]), TELEMETRY_SPAN_FIELDS)
        self.assertEqual(
            payload["case_ids"],
            [
                "serial-baseline-4x1000ms-model",
                "parallel-width4-4x1000ms-model",
                "parallel-width3-8-slides",
                "out-of-order-qa",
                "recovery-replayed-span",
                "telemetry-corrupt",
            ],
        )
        for case_id in payload["case_ids"][:-1]:
            case = payload["cases"][case_id]
            with self.subTest(case=case_id):
                for value in case["spans"]:
                    validate_span(value)
                self.assertEqual(
                    critical_path_duration_ms(case["spans"]),
                    case["expected"]["critical_path_ms"],
                )
                self.assertEqual(
                    batch_wall_duration_ms(case["spans"]),
                    case["expected"]["batch_wall_ms"],
                )
        serial = payload["cases"]["serial-baseline-4x1000ms-model"]
        parallel = payload["cases"]["parallel-width4-4x1000ms-model"]
        width_three = payload["cases"]["parallel-width3-8-slides"]
        self.assertEqual(serial["expected"]["critical_path_ms"], 4400)
        self.assertEqual(parallel["expected"]["critical_path_ms"], 1400)
        self.assertEqual(width_three["expected"]["critical_path_ms"], 3400)
        replay = payload["cases"]["recovery-replayed-span"]
        self.assertGreater(len(replay["spans"]), len({span["span_id"] for span in replay["spans"]}))

        cycle = copy.deepcopy(parallel["spans"][:2])
        cycle[0]["critical_path_parent_ids"] = [cycle[1]["span_id"]]
        cycle[1]["critical_path_parent_ids"] = [cycle[0]["span_id"]]
        with self.assertRaises(ValueError):
            critical_path_duration_ms(cycle)
        hierarchy_cycle = copy.deepcopy(parallel["spans"][:2])
        hierarchy_cycle[0]["parent_span_id"] = hierarchy_cycle[1]["span_id"]
        hierarchy_cycle[1]["parent_span_id"] = hierarchy_cycle[0]["span_id"]
        with self.assertRaises(ValueError):
            critical_path_duration_ms(hierarchy_cycle)
        overlap = copy.deepcopy(parallel["spans"][:2])
        overlap[1]["critical_path_parent_ids"] = [overlap[0]["span_id"]]
        with self.assertRaises(ValueError):
            critical_path_duration_ms(overlap)
        broken_promotion_chain = copy.deepcopy(parallel["spans"])
        promotions = [
            span for span in broken_promotion_chain if span["phase"] == "promotion"
        ]
        promotions[1]["critical_path_parent_ids"] = []
        with self.assertRaises(ValueError):
            critical_path_duration_ms(broken_promotion_chain)
        reversed_slide_order = copy.deepcopy(parallel["spans"])
        reversed_promotions = [
            span for span in reversed_slide_order if span["phase"] == "promotion"
        ]
        reversed_promotions[0]["slide_id"], reversed_promotions[1]["slide_id"] = (
            reversed_promotions[1]["slide_id"],
            reversed_promotions[0]["slide_id"],
        )
        with self.assertRaises(ValueError):
            critical_path_duration_ms(reversed_slide_order)

    def test_telemetry_corruption_is_diagnostic_and_never_changes_correctness(self):
        payload = json.loads(read_text(self.timing_cases))
        case = payload["cases"]["telemetry-corrupt"]
        batch = json.loads(read_text(self.batch_v2))["cases"][
            "four-way-out-of-order-two-pass-two-fail"
        ]
        ref_by_slide = dict(
            zip(batch["manifest"]["ordered_slide_ids"], batch["manifest"]["transaction_refs"])
        )
        transaction = copy.deepcopy(batch["transactions"][ref_by_slide["S03"]])
        before = copy.deepcopy(transaction)
        result = evaluate_telemetry_non_authoritatively(
            transaction,
            case["spans"],
        )
        self.assertEqual(result["diagnostic"], "telemetry_diagnostic_failed")
        self.assertIsNone(result["metrics"])
        self.assertEqual(result["transaction"], before)
        self.assertEqual(transaction, before)
        self.assertEqual(result["transaction"]["state"], "validated")
        self.assertEqual(result["transaction"]["validation"]["state"], "passed")
        self.assertEqual(case["expected"]["correctness_outcome"], "validated")

    def test_telemetry_contract_is_non_authoritative_and_separates_durations(self):
        combined = "\n".join(
            read_text(path)
            for path in (
                self.artifact,
                self.qa,
                skill_root() / "references" / "redesign-prompt.md",
                repo_root() / "docs" / "acceptance.md",
            )
        )
        for token in (
            "telemetry_diagnostic_failed",
            "critical_path_parent_ids",
            "monotonic_started_ns",
            "monotonic_finished_ns",
            "duration_ms",
            "queue_ms",
            "input_tokens",
            "output_tokens",
            "compile",
            "model",
            "render",
            "qa",
            "promotion",
            "非权威",
            "不能授权 promotion",
            "width 4",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_host_capability_matrix_is_portable_and_fail_closed(self):
        self.assertTrue(
            self.host_capabilities.is_file(),
            f"missing fixture: {self.host_capabilities}",
        )
        payload = json.loads(read_text(self.host_capabilities))
        expected_ids = [
            "native-concurrent-durable-lookup-width-4",
            "remote-concurrent-durable-lookup-width-3",
            "native-isolated-no-concurrency-width-1",
            "native-isolated-no-lookup-width-1",
            "non-git-workspace-native-width-4",
            "no-fresh-isolation-generator-unavailable",
            "filesystem-required-rejected",
            "tools-required-rejected",
            "nested-cli-only-rejected",
            "credential-dependent-only-rejected",
            "current-context-only-rejected",
            "missing-attribution-rejected",
            "refused-result",
            "timeout-result",
            "unknown-durable-result",
        ]
        self.assertEqual(payload["case_ids"], expected_ids)
        cases = {case["id"]: case for case in payload["cases"]}
        self.assertEqual(set(cases), set(expected_ids))
        for case_id in expected_ids:
            case = cases[case_id]
            with self.subTest(case=case_id):
                self.assertEqual(negotiate_host_capability(case), case["expected"])
                if case["expected"]["error"] is not None:
                    self.assertIn(case["expected"]["error"], V2_FAILURE_REASONS)
                if case["expected"]["error"] == "generator_unavailable":
                    self.assertEqual(
                        case["expected_side_effects"],
                        {
                            "prompt_writes": 0,
                            "transaction_writes": 0,
                            "candidate_writes": 0,
                            "generator_calls": 0,
                        },
                    )
        preferred = cases["native-concurrent-durable-lookup-width-4"]
        self.assertTrue(preferred["capability"]["native_fresh_isolation"])
        self.assertTrue(preferred["capability"]["remote_fresh_isolation"])
        self.assertEqual(preferred["expected"]["mode"], "native")
        self.assertEqual(
            cases["non-git-workspace-native-width-4"]["expected"]["selected_width"],
            4,
        )
        self.assertEqual(
            cases["native-isolated-no-concurrency-width-1"]["expected"]["selected_width"],
            1,
        )
        self.assertEqual(
            cases["native-isolated-no-lookup-width-1"]["expected"]["selected_width"],
            1,
        )

    def test_schedule_epoch_dispatches_each_transaction_once_with_prompt_by_value(self):
        batch_payload = json.loads(read_text(self.batch_v2))
        batch = batch_payload["cases"]["four-slide-active"]
        host_payload = json.loads(read_text(self.host_capabilities))
        host_case = next(
            case
            for case in host_payload["cases"]
            if case["id"] == "native-concurrent-durable-lookup-width-4"
        )
        capability = dict(host_case["expected"])
        scheduled_transactions = copy.deepcopy(batch["transactions"])
        prompts = {}
        refs_by_slide = dict(
            zip(
                batch["manifest"]["ordered_slide_ids"],
                batch["manifest"]["transaction_refs"],
            )
        )
        for slide_id, ref in refs_by_slide.items():
            transaction = scheduled_transactions[ref]
            body = "# Role\nComplete prompt body for {}.\n".format(slide_id)
            metadata = {
                "slide_id": slide_id,
                "storyboard_snapshot_id": _migration_sha(
                    transaction["transaction_id"],
                    "storyboard",
                ),
                "theme_snapshot_id": _migration_sha(
                    transaction["transaction_id"],
                    "theme",
                ),
                "applied_visual_revision_ids": "[]",
                "prompt_snapshot_id": transaction["prompt_snapshot_id"],
                "user_page_request": "none (initial generation)",
                "expected_output": "恰好一个 xml 代码围栏中的完整 SVG",
                "workspace_output_path": transaction["final_path"],
                "format": "creative-brief-v1",
            }
            prefix_lines = [
                "# {} 页面生成 Prompt".format(slide_id),
                "",
                "## Snapshot metadata",
                *[
                    "- **{}**：{}".format(field, metadata[field])
                    for field in GENERATION_PROMPT_METADATA_FIELDS
                ],
            ]
            prompt = "\n".join(prefix_lines) + "\n\n## Compiled Prompt\n\n" + body
            prompts[slide_id] = prompt
            transaction["compiled_prompt_sha256"] = (
                "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
            )
        capability["prompt_bytes_by_slide"] = prompts
        tasks = schedule_epoch(
            batch["manifest"],
            scheduled_transactions,
            capability,
        )
        self.assertEqual(len(tasks), 4)
        self.assertEqual(
            [task["slide_id"] for task in tasks],
            batch["manifest"]["ordered_slide_ids"],
        )
        self.assertEqual(
            len({(task["transaction_id"], task["dispatch_epoch"]) for task in tasks}),
            4,
        )
        for task in tasks:
            self.assertEqual(
                set(task),
                {
                    "slide_id",
                    "transaction_id",
                    "dispatch_epoch",
                    "prompt_by_value",
                    "fresh_history",
                    "filesystem",
                    "tools",
                    "output",
                    "expected_fence",
                    "timeout_ms",
                    "cancellation",
                },
            )
            self.assertTrue(task["fresh_history"])
            self.assertEqual(task["filesystem"], "none")
            self.assertEqual(task["tools"], "none")
            self.assertEqual(task["output"], "text")
            self.assertEqual(task["expected_fence"], "xml")
            self.assertNotIn("prompt_path", task)
            self.assertEqual(
                task["prompt_by_value"],
                prompts[task["slide_id"]],
            )

        committed = copy.deepcopy(scheduled_transactions)
        for task in tasks:
            transaction = committed[refs_by_slide[task["slide_id"]]]
            transaction["host_attribution_id"] = "attr-" + task["slide_id"]
            transaction["host_task_id"] = "task-" + task["slide_id"]
        self.assertEqual(
            schedule_epoch(batch["manifest"], committed, capability),
            [],
        )
        width_one = dict(capability, selected_width=1)
        self.assertEqual(
            len(schedule_epoch(batch["manifest"], scheduled_transactions, width_one)),
            1,
        )
        truncated = copy.deepcopy(capability)
        truncated["prompt_bytes_by_slide"]["S03"] = "# S03 页面生成 Prompt\n"
        with self.assertRaises(ValueError):
            schedule_epoch(batch["manifest"], scheduled_transactions, truncated)

    def test_host_contract_documents_safe_degradation_and_forbidden_fallbacks(self):
        combined = "\n".join(
            read_text(path)
            for path in (
                self.skill,
                self.workflow,
                self.artifact,
                self.qa,
                skill_root() / "references" / "redesign-prompt.md",
            )
        )
        for token in (
            "spawn_isolated_text_task",
            "get_isolated_text_task_result",
            "prompt_by_value",
            "fresh_history=true",
            "filesystem=none",
            "tools=none",
            "batch_width",
            "width 1",
            "generator_unavailable",
            "host_attribution_id",
            "host_task_id",
            "非 Git",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)
        for forbidden in (
            "nested Claude CLI",
            "nested Codex CLI",
            "nested DeepSeek CLI",
            "probe credentials",
            "probe profiles",
            "current-context generator fallback",
        ):
            self.assertNotIn(forbidden, combined)

    def test_v2_batch_fixture_validates_exact_schema_paths_and_order(self):
        self.assertTrue(self.batch_v2.is_file(), f"missing fixture: {self.batch_v2}")
        payload = json.loads(read_text(self.batch_v2))
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["default_batch_width"], 4)
        self.assertEqual(
            payload["valid_batches"],
            ["four-slide-active", "three-slide-active", "one-slide-final"],
        )
        for case_id in payload["valid_batches"]:
            case = payload["cases"][case_id]
            with self.subTest(case=case_id):
                validate_v2_manifest(case["manifest"], case["transactions"])
                self.assertEqual(
                    rebuild_batch_cursors(case["manifest"], case["transactions"]),
                    tuple(case["expected"]["rebuilt_cursors"]),
                )
                self.assertEqual(
                    set(case["run"]["active_visual_generation_batch"]),
                    {"schema_version", "batch_id", "manifest_path"},
                )
                self.assertEqual(
                    case["run"]["active_visual_generation_batch"]["manifest_path"],
                    ".ppt-pilot/visual-generation-batches/{}.json".format(
                        case["manifest"]["batch_id"]
                    ),
                )

    def test_v2_invalid_cases_fail_closed(self):
        payload = json.loads(read_text(self.batch_v2))
        expected_ids = {
            "width-two",
            "width-five",
            "duplicate-slide",
            "unsorted-slides",
            "ref-order-mismatch",
            "manifest-copies-transaction-state",
            "transaction-batch-mismatch",
            "transaction-id-mismatch",
            "candidate-path-mismatch",
            "untrusted-cursor",
        }
        self.assertEqual(set(payload["invalid_cases"]), expected_ids)
        for case_id in payload["invalid_cases"]:
            case = payload["cases"][case_id]
            with self.subTest(case=case_id):
                with self.assertRaises(ValueError):
                    validate_v2_manifest(case["manifest"], case["transactions"])
                self.assertEqual(case["expected"]["writes"], 0)
                self.assertEqual(case["expected"]["error"], "visual_generation_state_conflict")
        legacy_reason = copy.deepcopy(
            next(iter(payload["cases"]["four-slide-active"]["transactions"].values()))
        )
        legacy_reason["state"] = "failed"
        legacy_reason["candidate_sha256"] = _migration_sha(
            legacy_reason["transaction_id"],
            "candidate",
        )
        legacy_reason["failure_reason"] = "locked_content_mismatch"
        legacy_reason["validation"] = _migration_validation("failed", True)
        with self.assertRaises(ValueError):
            validate_v2_transaction(legacy_reason)
        inconsistent = copy.deepcopy(
            next(iter(payload["cases"]["four-slide-active"]["transactions"].values()))
        )
        inconsistent["state"] = "validated"
        inconsistent["candidate_sha256"] = _migration_sha(
            inconsistent["transaction_id"],
            "validated-candidate",
        )
        with self.assertRaises(ValueError):
            validate_v2_transaction(inconsistent)
        inconsistent["validation"]["state"] = "passed"
        for check in inconsistent["validation"]["checks"]:
            inconsistent["validation"]["checks"][check] = "passed"
        inconsistent["validation"]["checks"]["fact_source"] = "failed"
        with self.assertRaises(ValueError):
            validate_v2_transaction(inconsistent)
        geometry_failure = copy.deepcopy(
            next(iter(payload["cases"]["four-slide-active"]["transactions"].values()))
        )
        geometry_failure["state"] = "failed"
        geometry_failure["candidate_sha256"] = _migration_sha(
            geometry_failure["transaction_id"],
            "geometry-failure-candidate",
        )
        geometry_failure["failure_reason"] = "svg_contract_failed"
        geometry_failure["validation"]["state"] = "failed"
        for check in geometry_failure["validation"]["checks"]:
            geometry_failure["validation"]["checks"][check] = "passed"
        geometry_failure["validation"]["checks"]["geometry_text"] = "failed"
        validate_v2_transaction(geometry_failure)
        geometry_failure["validation"]["checks"]["geometry_text"] = "passed"
        with self.assertRaises(ValueError):
            validate_v2_transaction(geometry_failure)

    def test_v2_recovery_cases_use_pointer_last_and_candidate_hash_evidence(self):
        payload = json.loads(read_text(self.batch_v2))
        expected_ids = {
            "pointer-before-files-fails-closed",
            "prepared-files-before-pointer-reusable",
            "candidate-before-candidate-written-is-orphan",
            "candidate-written-hash-match-resumes",
            "validated-final-is-candidate-commits",
            "validated-final-is-prior-retries",
            "validated-final-third-hash-conflicts",
        }
        self.assertEqual(set(payload["recovery_cases"]), expected_ids)
        for case_id in payload["recovery_cases"]:
            case = payload["cases"][case_id]
            validate_v2_manifest(case["manifest"], case["transactions"])
            expected = case["expected"]
            durable = case["durable"]
            with self.subTest(case=case_id):
                if case_id == "pointer-before-files-fails-closed":
                    self.assertTrue(durable["pointer"])
                    self.assertFalse(durable["manifest"])
                    self.assertEqual(expected["outcome"], "visual_generation_state_conflict")
                    self.assertEqual(expected["writes"], 0)
                elif case_id == "prepared-files-before-pointer-reusable":
                    self.assertFalse(durable["pointer"])
                    self.assertTrue(durable["manifest"])
                    self.assertEqual(
                        set(durable["transaction_refs"]),
                        set(case["manifest"]["transaction_refs"]),
                    )
                    self.assertEqual(expected["outcome"], "publish_pointer_only")
                elif case_id == "candidate-before-candidate-written-is-orphan":
                    transaction = next(iter(case["transactions"].values()))
                    self.assertEqual(transaction["state"], "generating")
                    self.assertEqual(expected["candidate_action"], "isolate")
                    self.assertFalse(expected["adopt_candidate"])
                elif case_id == "candidate-written-hash-match-resumes":
                    transaction = next(iter(case["transactions"].values()))
                    self.assertEqual(transaction["state"], "candidate_written")
                    self.assertEqual(
                        case["observed_candidate_sha256"],
                        transaction["candidate_sha256"],
                    )
                    self.assertEqual(expected["outcome"], "resume_validation")
                else:
                    transaction = next(iter(case["transactions"].values()))
                    self.assertEqual(
                        validated_final_outcome(
                            transaction,
                            case["observed_final_sha256"],
                        ),
                        expected["outcome"],
                    )

    def test_v2_mixed_outcome_fixture_never_copies_transaction_state(self):
        payload = json.loads(read_text(self.batch_v2))
        self.assertEqual(
            payload["mixed_outcome_cases"],
            ["four-way-out-of-order-two-pass-two-fail"],
        )
        case = payload["cases"][payload["mixed_outcome_cases"][0]]
        validate_v2_manifest(case["manifest"], case["transactions"])
        self.assertFalse(
            any(
                key in case["manifest"]
                for key in ("transactions", "transaction_states", "completion_order")
            )
        )
        self.assertEqual(
            case["completion_order"],
            ["S06", "S04", "S03", "S05"],
        )
        self.assertEqual(case["expected"]["promotion_order"], ["S03", "S05"])
        self.assertEqual(case["expected"]["visible_blocker"], "S04")

    def test_out_of_order_completion_uses_ordered_promotion_and_lowest_blocker(self):
        payload = json.loads(read_text(self.batch_v2))
        case = payload["cases"]["four-way-out-of-order-two-pass-two-fail"]
        manifest = copy.deepcopy(case["manifest"])
        transactions = copy.deepcopy(case["transactions"])
        before = copy.deepcopy(transactions)
        self.assertEqual(case["completion_order"], ["S06", "S04", "S03", "S05"])
        self.assertEqual(
            eligible_promotions(manifest, transactions),
            case["expected"]["promotion_order"],
        )
        self.assertEqual(
            lowest_eligible_blocker(manifest, transactions),
            case["expected"]["visible_blocker"],
        )
        observed = {
            slide_id: transaction["prior_final_sha256"]
            for slide_id, ref in zip(
                manifest["ordered_slide_ids"],
                manifest["transaction_refs"],
            )
            for transaction in (transactions[ref],)
            if transaction["state"] == "validated"
        }
        decisions = promote_in_order(manifest, transactions, observed)
        self.assertEqual(
            [decision["slide_id"] for decision in decisions],
            ["S03", "S05"],
        )
        self.assertTrue(
            all(decision["outcome"] == "retry_atomic_promotion" for decision in decisions)
        )
        self.assertEqual(transactions, before)
        for slide_id in case["expected"]["preserve_previous_finals"]:
            ref = dict(zip(manifest["ordered_slide_ids"], manifest["transaction_refs"]))[
                slide_id
            ]
            self.assertEqual(
                transactions[ref]["prior_final_sha256"],
                before[ref]["prior_final_sha256"],
            )
        untrusted = copy.deepcopy(manifest)
        untrusted["promotion_cursor"] = len(untrusted["ordered_slide_ids"])
        untrusted["blocker_cursor"] = len(untrusted["ordered_slide_ids"])
        self.assertEqual(eligible_promotions(untrusted, transactions), ["S03", "S05"])
        self.assertEqual(lowest_eligible_blocker(untrusted, transactions), "S04")

    def test_visible_internal_source_ids_fail_before_validation_commit(self):
        payload = json.loads(read_text(self.batch_v2))
        expected_ids = [
            "visible-internal-source-cn",
            "visible-internal-source-en",
            "visible-internal-source-only",
            "machine-metadata-only",
            "explicit-human-readable-source",
        ]
        self.assertEqual(payload["fact_source_cases"], expected_ids)
        for case_id in expected_ids:
            case = payload["cases"][case_id]
            transaction = copy.deepcopy(case["transaction"])
            before = copy.deepcopy(transaction)
            reason = fact_source_visible_text_result(
                case["svg"],
                human_readable_citation_requested=case[
                    "human_readable_citation_requested"
                ],
            )
            with self.subTest(case=case_id):
                self.assertEqual(reason, case["expected"]["failure_reason"])
                self.assertTrue(case["expected"]["preserve_previous_final"])
                self.assertEqual(case["expected"]["text_deletions"], 0)
                self.assertEqual(case["expected"]["raster_fallbacks"], 0)
                if reason is not None:
                    transaction["state"] = "failed"
                    transaction["failure_reason"] = reason
                    transaction["validation"]["state"] = "failed"
                    transaction["validation"]["checks"]["fact_source"] = "failed"
                    self.assertEqual(transaction["prior_final_sha256"], before["prior_final_sha256"])
                    self.assertEqual(transaction["candidate_sha256"], before["candidate_sha256"])
                else:
                    transaction["state"] = "validated"
                    transaction["validation"]["state"] = "passed"
                    for check in transaction["validation"]["checks"]:
                        transaction["validation"]["checks"][check] = "passed"
                self.assertEqual(transaction["state"], case["expected"]["next_state"])
        explicit = payload["cases"]["explicit-human-readable-source"]
        self.assertEqual(
            fact_source_visible_text_result(
                explicit["svg"],
                human_readable_citation_requested=False,
            ),
            "fact_source_mismatch",
        )

    def test_parallel_validation_and_serial_publication_are_documented_exactly(self):
        qa = read_text(self.qa)
        workflow = read_text(self.workflow)
        artifact = read_text(self.artifact)
        combined = "\n".join((qa, workflow, artifact))
        for token in (
            '"state": "pending|running|passed|failed"',
            '"xml": "pending|passed|failed"',
            '"office": "pending|passed|failed"',
            '"geometry_text": "pending|passed|failed"',
            '"fact_source": "pending|passed|failed"',
            '"narrative": "pending|passed|failed"',
            '"visual": "pending|passed|failed|not_rendered"',
            "fact_source_mismatch",
            "ordered_slide_ids",
            "completion order",
            "只有 coordinator",
            "previous final",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)
        self.assertIn("不能授权", artifact)
        self.assertIn("最低", workflow)

    def test_v2_documents_define_pointer_last_activation_and_state_ownership(self):
        artifact = read_text(self.artifact)
        redesign = read_text(skill_root() / "references" / "redesign-prompt.md")
        workflow = read_text(self.workflow)
        combined = "\n".join((artifact, redesign, workflow))
        for token in (
            "active_visual_generation_batch",
            ".ppt-pilot/visual-generation-transactions/<slide-id>-<tx64>.json",
            ".ppt-pilot/visual-generation-batches/<batch-id>.json",
            "candidate_written",
            "prior_final_sha256",
            "transaction_refs",
            "pointer-last",
            "promotion_cursor",
            "blocker_cursor",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)
        self.assertIn("先写入并复读每页 transaction", artifact)
        self.assertIn("再写入并复读 batch manifest", artifact)
        self.assertIn("最后原子替换 `run.json`", artifact)
        self.assertIn("manifest 不复制 transaction state", artifact)
        self.assertIn("只是可重建提示", artifact)

    def _assert_serialized_migration_result(self, result, expected):
        self.assertEqual(result["status"], expected["status"])
        self.assertEqual(result["run"], expected["run"])
        self.assertEqual(result["transaction"], expected["transaction"])
        self.assertEqual(result["manifest"], expected["manifest"])
        self.assertEqual(result["write_order"], expected["write_order"])
        self.assertEqual(result["writes"], expected["writes"])
        self.assertEqual(result["generator_calls"], expected["generator_calls"])
        for result_key, expected_key in (
            ("transaction_bytes", "transaction_bytes_base64"),
            ("manifest_bytes", "manifest_bytes_base64"),
            ("run_bytes", "run_bytes_base64"),
        ):
            encoded = expected[expected_key]
            self.assertEqual(
                result[result_key],
                None if encoded is None else base64.b64decode(encoded),
            )

    def test_v1_migration_matrix(self):
        v1 = json.loads(read_text(self.transaction))
        v2 = json.loads(read_text(self.batch_v2))
        self.assertEqual(
            v2["migration_state_cases"],
            ["migration-state-" + state for state in v1["states"]],
        )
        self.assertEqual(
            v2["migration_failure_cases"],
            ["migration-failure-" + reason for reason in v1["failure_reasons"]],
        )
        for case_id in [
            *v2["migration_state_cases"],
            *v2["migration_failure_cases"],
        ]:
            case = v2["cases"][case_id]
            before = copy.deepcopy(case["before_run"])
            result = migrate_v1_run_to_v2(before, case["corpus_case"])
            with self.subTest(case=case_id):
                self._assert_serialized_migration_result(result, case["expected"])
                self.assertEqual(result["generator_calls"], 0)
                self.assertEqual(before, case["before_run"])
                self.assertNotIn("visual_generation_transaction", result["run"])
                pointer = result["run"]["active_visual_generation_batch"]
                self.assertEqual(pointer["schema_version"], 2)
                self.assertEqual(result["transaction"]["dispatch_epoch"], 0)
                self.assertEqual(
                    result["transaction"]["prior_final_sha256"],
                    case["corpus_case"]["observed_prior_final_sha256"],
                )
                for key, value in case["expected_legacy_fields"].items():
                    self.assertEqual(result["transaction"][key], value, key)
                self.assertEqual(
                    result["run"].get("dirty_slides", []),
                    case["before_run"].get("dirty_slides", []),
                )

    def test_v1_migration_crash_split_brain_and_idempotency(self):
        payload = json.loads(read_text(self.batch_v2))
        expected_ids = [
            "v1-only-migrates",
            "v2-only-no-op",
            "v1-plus-v2-conflicts",
            "crash-after-transaction-reuses-bytes",
            "crash-after-manifest-reuses-bytes",
            "crash-before-run-pointer-completes-pointer-only",
            "prepared-bytes-differ-fails-closed",
            "second-complete-migration-is-byte-identical-no-op",
        ]
        self.assertEqual(payload["migration_recovery_cases"], expected_ids)
        results = {}
        for case_id in expected_ids:
            case = payload["cases"][case_id]
            result = migrate_v1_run_to_v2(
                copy.deepcopy(case["before_run"]),
                copy.deepcopy(case["corpus_case"]),
            )
            results[case_id] = result
            with self.subTest(case=case_id):
                self._assert_serialized_migration_result(result, case["expected"])
                self.assertEqual(result["generator_calls"], 0)
        self.assertEqual(
            results["v1-only-migrates"]["write_order"],
            ["transaction", "manifest", "run"],
        )
        self.assertEqual(results["v2-only-no-op"]["status"], "no_op")
        self.assertEqual(
            results["v1-plus-v2-conflicts"]["status"],
            "visual_generation_state_conflict",
        )
        self.assertEqual(
            results["crash-after-transaction-reuses-bytes"]["write_order"],
            ["manifest", "run"],
        )
        self.assertEqual(
            results["crash-after-manifest-reuses-bytes"]["write_order"],
            ["run"],
        )
        self.assertEqual(
            results["crash-before-run-pointer-completes-pointer-only"]["write_order"],
            ["run"],
        )
        self.assertEqual(
            results["prepared-bytes-differ-fails-closed"]["status"],
            "visual_generation_state_conflict",
        )
        different_case = payload["cases"]["prepared-bytes-differ-fails-closed"]
        durable_bytes = base64.b64decode(
            different_case["corpus_case"]["durable"]["transaction_bytes_base64"]
        )
        canonical_bytes = results["v1-only-migrates"]["transaction_bytes"]
        self.assertNotEqual(durable_bytes, canonical_bytes)
        self.assertEqual(
            json.loads(durable_bytes.decode("utf-8")),
            json.loads(canonical_bytes.decode("utf-8")),
        )
        self.assertEqual(
            results["second-complete-migration-is-byte-identical-no-op"]["status"],
            "no_op",
        )
        v2_only = payload["cases"]["v2-only-no-op"]
        incomplete_corpus = copy.deepcopy(v2_only["corpus_case"])
        del incomplete_corpus["existing_manifest"]
        incomplete = migrate_v1_run_to_v2(
            copy.deepcopy(v2_only["before_run"]),
            incomplete_corpus,
        )
        self.assertEqual(incomplete["status"], "visual_generation_state_conflict")
        self.assertEqual(incomplete["writes"], 0)
        v1_only = payload["cases"]["v1-only-migrates"]
        missing_prior = copy.deepcopy(v1_only["corpus_case"])
        del missing_prior["observed_prior_final_sha256"]
        missing_prior_result = migrate_v1_run_to_v2(
            copy.deepcopy(v1_only["before_run"]),
            missing_prior,
        )
        self.assertEqual(
            missing_prior_result["status"],
            "visual_generation_state_conflict",
        )
        self.assertEqual(missing_prior_result["writes"], 0)

    def test_generation_blocker_lifecycle_is_atomic_and_preflight_has_zero_dispatch(self):
        payload = json.loads(read_text(self.blocker))
        self.assertEqual({case["id"] for case in payload["blocker_cases"]}, BLOCKER_CASE_IDS)
        for case in payload["blocker_cases"]:
            expected = case["expected"]
            if not expected["active_blocker"]:
                continue
            with self.subTest(case=case["id"]):
                self.assertEqual(expected["generator_calls"], 0)
                self.assertEqual(expected["svg_writes"], 0)
                self.assertEqual(expected["stage_scan_calls"], 0)
                self.assertTrue(expected["stop"])
                self.assertEqual(
                    case["after_run"]["stage"],
                    case["before_run"]["stage"],
                )
                self.assertEqual(
                    case["after_run"]["interaction_history"],
                    case["before_run"]["interaction_history"],
                )
                self.assertNotIn(
                    "active_visual_generation_batch",
                    case["after_run"],
                )

    def test_v1_prompt_and_transaction_migration_is_read_only_deterministic_and_zero_call(self):
        payload = json.loads(read_text(self.batch_v2))
        case = payload["cases"][payload["migration_state_cases"][0]]
        before = copy.deepcopy(case["before_run"])
        first = migrate_v1_run_to_v2(before, case["corpus_case"])
        second = migrate_v1_run_to_v2(
            copy.deepcopy(case["before_run"]),
            copy.deepcopy(case["corpus_case"]),
        )
        self.assertEqual(before, case["before_run"])
        self.assertEqual(first["generator_calls"], 0)
        self.assertEqual(first["transaction_bytes"], second["transaction_bytes"])
        self.assertEqual(first["manifest_bytes"], second["manifest_bytes"])
        self.assertEqual(first["run_bytes"], second["run_bytes"])

    def test_visual_revisions_are_durable_and_project_into_storyboard_theme_owners(self):
        payload = json.loads(read_text(self.precedence))
        owners = set()
        for record in payload["history"]:
            self.assertTrue(record["normalized_changes"])
            self.assertIn("affected_scope", record)
            self.assertIsInstance(record["supersedes"], list)
            self.assertEqual(record["status"], "applied")
            owners.add(record["artifact_owner"])
        self.assertEqual(owners, {"theme.json", ".ppt-pilot/故事板.md"})
        self.assertNotIn("visual-briefs/", json.dumps(payload, ensure_ascii=False))
        self.assertEqual(payload["before_run"]["dirty_slides"], [])
        self.assertEqual(payload["after_run"]["dirty_slides"], payload["slide_ids"])
        transitions = {
            case["id"]: case for case in payload["dirty_transition_cases"]
        }
        page_case = transitions["page-scoped-revision-dirties-only-s05"]
        self.assertEqual(page_case["before_run"]["dirty_slides"], [])
        self.assertEqual(page_case["after_run"]["dirty_slides"], ["S05"])

    def test_production_resume_and_revision_semantics_use_batch_pointer_and_per_slide_transactions(self):
        payload = json.loads(read_text(self.batch_v2))
        migrated = payload["cases"]["v1-only-migrates"]["expected"]
        self.assertNotIn("visual_generation_transaction", migrated["run"])
        pointer = migrated["run"]["active_visual_generation_batch"]
        self.assertEqual(set(pointer), {"schema_version", "batch_id", "manifest_path"})
        self.assertEqual(migrated["transaction"]["schema_version"], 2)
        pointer_only = payload["cases"][
            "crash-before-run-pointer-completes-pointer-only"
        ]["expected"]
        self.assertEqual(pointer_only["write_order"], ["run"])
        self.assertEqual(pointer_only["generator_calls"], 0)

    def test_v1_migration_documents_order_ownership_and_zero_model_calls(self):
        artifact = read_text(self.artifact)
        redesign = read_text(skill_root() / "references" / "redesign-prompt.md")
        combined = artifact + "\n" + redesign
        for token in (
            "v1 → v2",
            "先原子写入并复读 one-slide v2 transaction",
            "再写入并复读 one-slide batch manifest",
            "同一次 `run.json` 原子替换删除 `visual_generation_transaction`",
            "`generator_calls` 永远为 0",
            "不得从 SVG",
            "split brain",
            "prepared bytes",
            "byte-identical no-op",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_skill_requires_visual_brief_contract_before_svg(self):
        self.assertTrue(self.reference.exists())
        skill = read_text(self.skill)
        self.assertIn("visual-brief-and-generation.md", skill)
        self.assertLess(skill.index("visual-brief-and-generation.md"), skill.index("SVG 契约"))

    def test_fixture_has_every_required_brief_section(self):
        text = read_text(self.brief)
        headings = {
            line.removeprefix("## ").strip()
            for line in text.splitlines()
            if line.startswith("## ")
        }
        self.assertEqual(headings, self.REQUIRED_BRIEF_HEADINGS)
        for token in (
            "storyboard_snapshot_id",
            "theme_snapshot_id",
            "applied_visual_revision_ids",
            "selected_style_id",
            "selected_style_display_name",
            "style_manifest_version",
            "style_token_path",
            "style_guidance_path",
            "primary_message",
            "reading_order",
            "layout_family",
            "focal_object",
            "typography_ladder",
            "prohibited_motifs",
            "mode: recompose",
            "office_safe_svg",
        ):
            self.assertIn(token, text)
        self.assertNotIn("style_reference_path", text)
        manifest = json.loads(read_text(self.style_manifest))
        self.assertIn(f"style_manifest_version: {manifest['version']}", text)

    def test_fixture_has_complete_style_identity_and_generation_owner(self):
        sections = parse_brief_sections(self.brief)
        source = sections["来源与版本"]
        revision = sections["修订模式"]
        expected_identity = {
            "selected_style_id": "canway-midyear-review",
            "selected_style_display_name": "嘉为年中总结风格",
            "style_kind": "style_pack",
            "style_manifest_version": "1.3.0",
        }
        expected_owner = {
            "generation_intent": "user_recompose",
            "generation_trigger_id": "interaction:visual-revision-3",
        }
        self.assertEqual({field: source.get(field) for field in STYLE_IDENTITY_FIELDS}, expected_identity)
        for field in expected_owner:
            self.assertNotIn(field, source)
        for field, value in expected_owner.items():
            with self.subTest(field=field):
                self.assertEqual(revision.get(field), value)
        for field in STYLE_IDENTITY_FIELDS:
            self.assertNotIn(field, revision)

    def test_s05_and_theme_fixture_share_style_identity(self):
        theme_fixture = repo_root() / "tests" / "fixtures" / "theme-canway-S05.json"
        self.assertTrue(theme_fixture.is_file(), f"missing fixture: {theme_fixture}")
        brief_fields = parse_brief_fields(self.brief)
        theme = json.loads(read_text(theme_fixture))
        self.assertEqual(theme["schema_version"], 1)
        for field in STYLE_IDENTITY_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(theme.get(field), brief_fields.get(field))

    def test_visual_generation_transaction_fixture_models_legal_transitions_and_crashes(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(tuple(payload["states"]), TRANSACTION_STATES)
        self.assertEqual(tuple(payload["failure_reasons"]), TRANSACTION_FAILURE_REASONS)
        self.assertEqual(set(payload["transaction_schema"]), REQUIRED_TRANSACTION_FIELDS)

        legal = payload["legal_transitions"]
        self.assertEqual(
            tuple((edge["from"], edge["to"]) for edge in legal["normal"]),
            NORMAL_TRANSACTION_EDGES,
        )
        self.assertEqual(
            tuple((edge["from"], edge["to"]) for edge in legal["failure"]),
            FAILURE_TRANSACTION_EDGES,
        )
        self.assertEqual(
            tuple((edge["from"], edge["to"]) for edge in legal["recovery"]),
            RECOVERY_TRANSACTION_EDGES,
        )
        self.assertEqual(
            payload["replacement_rules"],
            [
                {
                    "from_state": "failed",
                    "to_new_state": "compiling",
                    "same_transaction_edge": False,
                    "when": "authoritative_inputs_changed_or_deterministic_fallback",
                }
            ],
        )

        crash_cases = {case["id"]: case for case in payload["transaction_cases"]}
        self.assertEqual(set(crash_cases), TRANSACTION_CRASH_CASE_IDS)

        def assert_transaction_schema(transaction: dict, label: str) -> None:
            self.assertEqual(set(transaction), REQUIRED_TRANSACTION_FIELDS, label)
            self.assertEqual(transaction["transaction_id"], transaction["prompt_snapshot_id"], label)
            self.assertRegex(transaction["transaction_id"], r"^sha256:[0-9a-f]{64}$", label)
            candidate_hex = transaction["transaction_id"].removeprefix("sha256:")
            self.assertEqual(
                transaction["candidate_path"],
                f"slides/.candidates/{transaction['slide_id']}-{candidate_hex}.svg",
                label,
            )
            self.assertEqual(transaction["prompt_path"], f"generation-prompts/{transaction['slide_id']}.md", label)
            self.assertEqual(transaction["final_path"], f"slides/{transaction['slide_id']}.svg", label)
            self.assertIn(transaction["state"], TRANSACTION_STATES, label)
            if transaction["state"] == "failed":
                self.assertIn(transaction["failure_reason"], TRANSACTION_FAILURE_REASONS, label)
            else:
                self.assertIsNone(transaction["failure_reason"], label)
            if transaction["state"] in {"compiling", "compiled", "generating"}:
                self.assertIsNone(transaction["candidate_sha256"], label)
            if transaction["state"] in {"candidate_written", "validated", "promoted"}:
                self.assertRegex(transaction["candidate_sha256"], r"^sha256:[0-9a-f]{64}$", label)

        for case in crash_cases.values():
            before_tx = case["before_run"].get("visual_generation_transaction")
            after_tx = case["after_run"].get("visual_generation_transaction")
            if before_tx is not None:
                assert_transaction_schema(before_tx, f"{case['id']} before transaction")
            if after_tx is not None:
                assert_transaction_schema(after_tx, f"{case['id']} after transaction")

            slide_id = case["slide_id"]
            if before_tx and before_tx["state"] != "promoted":
                self.assertIn(
                    slide_id,
                    case["after_run"].get("dirty_slides", []),
                    f"{case['id']} clears dirty before promoted final QA",
                )

        compiling_match = crash_cases["compiling-durable-prompt-match-commits-compiled"]
        self.assertEqual(compiling_match["before_run"]["visual_generation_transaction"]["state"], "compiling")
        self.assertEqual(compiling_match["after_run"]["visual_generation_transaction"]["state"], "compiled")
        self.assertNotIn("visual_generation_blocker", compiling_match["after_run"])
        self.assertEqual(
            compiling_match["durable_prompt"],
            {
                "path": compiling_match["before_run"]["visual_generation_transaction"]["prompt_path"],
                "prompt_snapshot_id": compiling_match["before_run"]["visual_generation_transaction"]["prompt_snapshot_id"],
                "compiled_prompt_sha256": compiling_match["before_run"]["visual_generation_transaction"]["compiled_prompt_sha256"],
            },
        )

        compiling_mismatch = crash_cases["compiling-durable-prompt-mismatch-recompiles"]
        self.assertEqual(compiling_mismatch["expected"]["first_action"], "recompile_prompt")
        self.assertEqual(compiling_mismatch["expected"]["generator_calls"], 0)
        self.assertNotEqual(
            compiling_mismatch["durable_prompt"]["compiled_prompt_sha256"],
            compiling_mismatch["before_run"]["visual_generation_transaction"]["compiled_prompt_sha256"],
        )

        generating_orphan = crash_cases["generating-orphan-candidate-is-never-adopted"]
        self.assertEqual(generating_orphan["before_run"]["visual_generation_transaction"]["state"], "generating")
        self.assertEqual(generating_orphan["orphan_candidate"]["path"], generating_orphan["before_run"]["visual_generation_transaction"]["candidate_path"])
        self.assertFalse(generating_orphan["expected"]["adopt_orphan_candidate"])
        self.assertIn(generating_orphan["expected"]["orphan_candidate_action"], {"delete", "isolate"})
        self.assertEqual(generating_orphan["expected"]["generator_calls"], 1)

        candidate_match = crash_cases["candidate-written-hash-match-continues-validation"]
        self.assertEqual(candidate_match["observed_candidate_sha256"], candidate_match["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(candidate_match["after_run"]["visual_generation_transaction"]["state"], "validated")

        candidate_mismatch = crash_cases["candidate-written-hash-mismatch-fails"]
        self.assertNotEqual(candidate_mismatch["observed_candidate_sha256"], candidate_mismatch["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(candidate_mismatch["after_run"]["visual_generation_transaction"]["state"], "failed")
        self.assertEqual(candidate_mismatch["after_run"]["visual_generation_transaction"]["failure_reason"], "candidate_hash_mismatch")

        final_match = crash_cases["validated-final-hash-match-promotes"]
        self.assertEqual(final_match["observed_final_sha256"], final_match["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(final_match["after_run"]["visual_generation_transaction"]["state"], "promoted")

        final_conflict = crash_cases["validated-final-conflict-fails"]
        self.assertNotEqual(final_conflict["observed_final_sha256"], final_conflict["before_run"]["visual_generation_transaction"]["candidate_sha256"])
        self.assertEqual(final_conflict["after_run"]["visual_generation_transaction"]["state"], "failed")
        self.assertEqual(final_conflict["after_run"]["visual_generation_transaction"]["failure_reason"], "final_promotion_conflict")

        illegal = crash_cases["illegal-recovery-transition-fails"]
        self.assertEqual(illegal["requested_transition"], {"from": "compiled", "to": "promoted"})
        self.assertEqual(illegal["after_run"]["visual_generation_transaction"]["state"], "failed")
        self.assertEqual(illegal["after_run"]["visual_generation_transaction"]["failure_reason"], "transaction_state_conflict")

        cleanup = crash_cases["promoted-final-qa-cleans-transaction-and-dirty-slide"]
        self.assertEqual(cleanup["before_run"]["visual_generation_transaction"]["state"], "promoted")
        self.assertTrue(cleanup["expected"]["final_qa_passed"])
        self.assertNotIn("visual_generation_transaction", cleanup["after_run"])
        self.assertNotIn(cleanup["slide_id"], cleanup["after_run"].get("dirty_slides", []))

    def test_failed_transaction_reasons_have_one_complete_consumer(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        self.assertEqual(tuple(payload["failure_reasons"]), TRANSACTION_FAILURE_REASONS)
        self.assertEqual(tuple(payload["covered_failure_reasons"]), TRANSACTION_FAILURE_REASONS)

        consumer_cases = payload["failed_consumer_cases"]
        reasons = [case["reason"] for case in consumer_cases]
        self.assertEqual(set(reasons), set(TRANSACTION_FAILURE_REASONS))
        self.assertEqual(len(reasons), len(set(reasons)), "each reason must have exactly one consumer case")

        retry_reasons = {
            "generator_unavailable",
            "generator_refused",
            "generator_timeout",
            "generator_output_malformed",
            "candidate_write_failed",
            "candidate_hash_mismatch",
        }
        qa_reasons = {"svg_contract_failed", "locked_content_mismatch", "visual_qa_failed"}
        conflict_reasons = {"final_promotion_conflict", "transaction_state_conflict"}

        for case in consumer_cases:
            with self.subTest(reason=case["reason"]):
                before_tx = case["before_run"]["visual_generation_transaction"]
                after_tx = case["after_run"].get("visual_generation_transaction")
                self.assertEqual(before_tx["state"], "failed")
                self.assertEqual(before_tx["failure_reason"], case["reason"])
                self.assertIn(case["slide_id"], case["after_run"].get("dirty_slides", []))

                if case["reason"] in retry_reasons:
                    self.assertEqual(case["consumer"], "explicit_resume_retry_same_transaction")
                    self.assertIsNotNone(after_tx)
                    self.assertEqual(after_tx["transaction_id"], before_tx["transaction_id"])
                    self.assertEqual(after_tx["state"], "generating")
                    self.assertIsNone(after_tx["failure_reason"])
                    self.assertEqual(after_tx["generation_attempt"], before_tx["generation_attempt"] + 1)
                    self.assertEqual(after_tx["generation_trigger_id"], before_tx["generation_trigger_id"])
                    self.assertEqual(case["expected"]["generator_calls"], 1)
                    self.assertEqual(case["expected"]["max_generator_calls_per_host_call"], 1)
                    self.assertIn(case["expected"]["orphan_candidate_action"], {"delete", "isolate"})
                elif case["reason"] in qa_reasons:
                    self.assertIn(case["consumer"], {"persist_defect_then_patch", "persist_defect_then_deterministic_fallback"})
                    self.assertTrue(case["expected"]["defect_persisted_before_next_action"])
                    self.assertIn(case["expected"]["next_action"], {"patch", "new_deterministic_fallback_transaction"})
                    if case["expected"]["next_action"] == "new_deterministic_fallback_transaction":
                        self.assertIsNotNone(after_tx)
                        self.assertNotEqual(after_tx["transaction_id"], before_tx["transaction_id"])
                        self.assertEqual(after_tx["state"], "compiling")
                        self.assertEqual(after_tx["generation_intent"], "deterministic_fallback")
                else:
                    self.assertIn(case["reason"], conflict_reasons)
                    self.assertEqual(case["consumer"], "production_blocker_then_user_resolution")
                    self.assertIsNotNone(after_tx)
                    self.assertEqual(after_tx, before_tx)
                    blocker = case["after_run"]["pending_interaction"]
                    self.assertEqual(blocker["stage"], "production")
                    self.assertEqual(blocker["kind"], "blocker")
                    self.assertEqual(blocker["status"], "pending")
                    self.assertTrue(case["expected"]["retain_failed_transaction_until_user_resolution"])

                    branches = {branch["id"]: branch for branch in case["post_user_resolution_branches"]}
                    self.assertEqual(set(branches), {"unchanged-valid-candidate", "authoritative-inputs-changed"})

                    unchanged = branches["unchanged-valid-candidate"]
                    unchanged_pending = unchanged["before_run"]["pending_interaction"]
                    self.assertEqual(unchanged_pending["status"], "answered")
                    self.assertTrue(unchanged_pending["answer"].strip())
                    self.assertEqual(unchanged_pending["decision"], "accept_candidate_after_review")
                    unchanged_after = unchanged["after_run"]["visual_generation_transaction"]
                    self.assertEqual(unchanged["before_run"]["visual_generation_transaction"], before_tx)
                    self.assertEqual(unchanged_after["transaction_id"], before_tx["transaction_id"])
                    self.assertEqual(unchanged_after["state"], "validated")
                    self.assertIsNone(unchanged_after["failure_reason"])
                    self.assertEqual(unchanged_after["candidate_sha256"], before_tx["candidate_sha256"])
                    self.assertTrue(unchanged["expected"]["promotion_retry"])

                    changed = branches["authoritative-inputs-changed"]
                    changed_pending = changed["before_run"]["pending_interaction"]
                    self.assertEqual(changed_pending["status"], "answered")
                    self.assertTrue(changed_pending["answer"].strip())
                    self.assertEqual(changed_pending["decision"], "restart_from_updated_inputs")
                    self.assertEqual(changed["before_run"]["visual_generation_transaction"], before_tx)
                    self.assertTrue(changed["durable_choice"]["old_failed_transaction_retained_until_choice"])
                    changed_after = changed["after_run"]["visual_generation_transaction"]
                    self.assertNotEqual(changed_after["transaction_id"], before_tx["transaction_id"])
                    self.assertEqual(changed_after["state"], "compiling")
                    self.assertIsNone(changed_after["failure_reason"])

    def test_precedence_fixture_keeps_history_and_one_active_value(self):

        payload = json.loads(read_text(self.precedence))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["history"]), 3)
        self.assertEqual(payload["expected_active_contract"]["title_rail"], "none")
        self.assertEqual(payload["expected_active_contract"]["layout_family"], "hierarchical-bento")
        self.assertIn("visual-revision-1:title_rail", payload["expected_superseded_rules"])

    def test_transaction_negative_invariants_preserve_final_dirty_and_active_owner(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        cases = {case["id"]: case for case in payload["negative_invariant_cases"]}
        self.assertEqual(
            set(cases),
            {
                "generation-failure-preserves-pre-existing-final",
                "qa-failure-preserves-pre-existing-final",
                "promotion-failure-preserves-pre-existing-final",
                "promoted-page-qa-pending-retains-transaction-and-dirty",
                "promoted-page-qa-failing-retains-transaction-and-dirty",
                "promoted-deck-qa-pending-retains-transaction-and-dirty",
                "promoted-deck-qa-failing-retains-transaction-and-dirty",
                "new-operation-nonterminal-transaction-recovers-stops-no-replace",
                "arbitrary-cancel-delete-request-rejected",
            },
        )

        final_preserving = {
            "generation-failure-preserves-pre-existing-final",
            "qa-failure-preserves-pre-existing-final",
            "promotion-failure-preserves-pre-existing-final",
            "arbitrary-cancel-delete-request-rejected",
        }
        for case_id in final_preserving:
            case = cases[case_id]
            with self.subTest(case=case_id):
                self.assertEqual(case["after_run"]["final_svg"], case["before_run"]["final_svg"])
                self.assertEqual(case["after_run"]["final_svg"], case["expected"]["retained_final_svg"])
                self.assertIn(case["slide_id"], case["after_run"].get("dirty_slides", []))
                self.assertFalse(case["expected"].get("final_overwritten"))

        for case_id in (
            "promoted-page-qa-pending-retains-transaction-and-dirty",
            "promoted-page-qa-failing-retains-transaction-and-dirty",
            "promoted-deck-qa-pending-retains-transaction-and-dirty",
            "promoted-deck-qa-failing-retains-transaction-and-dirty",
        ):
            case = cases[case_id]
            with self.subTest(case=case_id):
                before_tx = case["before_run"]["visual_generation_transaction"]
                after_tx = case["after_run"]["visual_generation_transaction"]
                self.assertEqual(before_tx["state"], "promoted")
                self.assertEqual(after_tx, before_tx)
                self.assertIn(case["slide_id"], case["after_run"].get("dirty_slides", []))
                self.assertIn(case["expected"]["qa_status"], {"pending", "failed"})
                self.assertIn(case["expected"]["qa_scope"], {"page", "deck"})
                self.assertTrue(case["expected"]["retain_transaction"])

        active = cases["new-operation-nonterminal-transaction-recovers-stops-no-replace"]
        before_tx = active["before_run"]["visual_generation_transaction"]
        after_tx = active["after_run"]["visual_generation_transaction"]
        self.assertNotEqual(before_tx["state"], "promoted")
        self.assertNotEqual(before_tx["state"], "failed")
        self.assertEqual(after_tx["transaction_id"], before_tx["transaction_id"])
        self.assertEqual(after_tx["generation_trigger_id"], before_tx["generation_trigger_id"])
        self.assertTrue(active["expected"]["recover_or_stop_before_new_operation"])
        self.assertFalse(active["expected"]["replace_active_transaction"])

        cancel = cases["arbitrary-cancel-delete-request-rejected"]
        self.assertEqual(cancel["after_run"]["visual_generation_transaction"], cancel["before_run"]["visual_generation_transaction"])
        self.assertEqual(cancel["after_run"]["final_svg"], cancel["before_run"]["final_svg"])
        self.assertIn(cancel["slide_id"], cancel["after_run"].get("dirty_slides", []))
        self.assertFalse(cancel["expected"]["cancelled"])
        self.assertFalse(cancel["expected"]["deleted_transaction"])

    def test_qa_failure_consumers_persist_structured_defect_before_next_action(self):
        self.assertTrue(self.transaction.is_file(), f"missing fixture: {self.transaction}")
        payload = json.loads(read_text(self.transaction))
        cases = {
            case["reason"]: case
            for case in payload["failed_consumer_cases"]
            if case["reason"] in {"svg_contract_failed", "locked_content_mismatch", "visual_qa_failed"}
        }
        self.assertEqual(set(cases), {"svg_contract_failed", "locked_content_mismatch", "visual_qa_failed"})

        for reason, case in cases.items():
            with self.subTest(reason=reason):
                before_tx = case["before_run"]["visual_generation_transaction"]
                defect = case["expected"]["durable_defect"]
                self.assertRegex(defect["id"], rf"^{case['slide_id']}-{reason}-[0-9a-f]{{12}}$")
                self.assertIn(defect["artifact_owner"], {f"visual-briefs/{case['slide_id']}.md", f"qa/{case['slide_id']}.md"})
                self.assertEqual(defect["slide_id"], case["slide_id"])
                self.assertEqual(defect["failure_reason"], reason)
                self.assertEqual(defect["candidate_sha256"], before_tx["candidate_sha256"])
                self.assertEqual(defect["transaction_id"], before_tx["transaction_id"])
                self.assertTrue(case["expected"]["defect_persisted_before_next_action"])
                self.assertIn(case["expected"]["next_action"], {"patch", "new_deterministic_fallback_transaction"})

    def test_references_define_recoverable_transaction_contract_and_consumers(self):
        combined = "\n".join(
            read_text(path)
            for path in (self.artifact, self.reference, self.workflow, self.qa, skill_root() / "references" / "redesign-prompt.md")
            if path.exists()
        )
        required_tokens = (
            "visual_generation_transaction",
            "transaction_id == prompt_snapshot_id",
            "compiling -> compiled -> generating -> candidate_written -> validated -> promoted",
            "generating | candidate_written | validated -> failed",
            "failed -> generating",
            "failed -> validated",
            "failed transaction -> new compiling transaction",
            "slides/.candidates/<slide-id>-<64hex>.svg",
            "candidate_sha256",
            "generator_unavailable",
            "generator_refused",
            "generator_timeout",
            "generator_output_malformed",
            "candidate_write_failed",
            "candidate_hash_mismatch",
            "svg_contract_failed",
            "locked_content_mismatch",
            "visual_qa_failed",
            "final_promotion_conflict",
            "transaction_state_conflict",
            "generation_attempt + 1",
            "每次宿主调用最多 generator 1 次",
            "orphan candidate",
            "never adopted",
            "previous final SVG",
            "dirty_slides",
            "promoted transaction",
            "production `blocker`",
            "unchanged valid candidate",
            "authoritative inputs changed",
            "No arbitrary delete/cancel",
        )
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, combined)

if __name__ == "__main__":
    unittest.main()
