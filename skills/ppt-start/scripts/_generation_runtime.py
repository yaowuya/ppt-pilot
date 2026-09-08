"""Packaged deterministic generation_runtime operations."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re

V1_MIGRATION_STATES = (
    "compiling",
    "compiled",
    "generating",
    "candidate_written",
    "validated",
    "promoted",
    "failed",
)


V1_MIGRATION_FAILURE_REASONS = (
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


V1_TRANSACTION_FIELDS = {
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
    if type(width) is not int or not 3 <= width <= 10:
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
    if manifest["state"] not in V2_MANIFEST_STATES:
        raise ValueError("manifest state is invalid")
    rebuilt_promotion_cursor, rebuilt_blocker_cursor = rebuild_batch_cursors(
        manifest, transactions
    )
    if (
        manifest["promotion_cursor"] != rebuilt_promotion_cursor
        or manifest["blocker_cursor"] != rebuilt_blocker_cursor
    ):
        raise ValueError("manifest cursor is untrusted")
    expected_blocker_ref = (
        refs[rebuilt_blocker_cursor]
        if rebuilt_blocker_cursor < len(refs)
        else None
    )
    blocker_ref = manifest["active_blocker_ref"]
    if blocker_ref != expected_blocker_ref:
        raise ValueError("active blocker ref is invalid")
    if (manifest["state"] == "blocked") != (expected_blocker_ref is not None):
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


def clear_repaired_blocker_before_v1_migration(run: dict) -> dict:
    """Commit only blocker removal; the legacy owner remains for next resume."""
    if not {
        "visual_generation_blocker",
        "visual_generation_transaction",
    }.issubset(run):
        raise ValueError("visual_generation_state_conflict")
    cleared = copy.deepcopy(run)
    del cleared["visual_generation_blocker"]
    return cleared


def validate_v1_migration_transaction(legacy: dict) -> None:
    if not isinstance(legacy, dict) or set(legacy) != V1_TRANSACTION_FIELDS:
        raise ValueError("v1 transaction schema differs")
    transaction_id = _require_sha256(legacy["transaction_id"], "transaction_id")
    if legacy["prompt_snapshot_id"] != legacy["transaction_id"]:
        raise ValueError("transaction and prompt identities differ")
    _require_sha256(legacy["compiled_prompt_sha256"], "compiled_prompt_sha256")
    slide_id = legacy["slide_id"]
    if not isinstance(slide_id, str) or re.fullmatch(r"S[0-9]+", slide_id) is None:
        raise ValueError("slide id is invalid")
    if legacy["generation_intent"] not in {
        "initial_generation",
        "user_recompose",
        "deterministic_fallback",
    }:
        raise ValueError("generation intent is invalid")
    if not isinstance(legacy["generation_trigger_id"], str) or not legacy[
        "generation_trigger_id"
    ]:
        raise ValueError("generation trigger is invalid")
    if legacy["prompt_path"] != f"generation-prompts/{slide_id}.md":
        raise ValueError("prompt path differs")
    if legacy["candidate_path"] != (
        f"slides/.candidates/{slide_id}-{transaction_id.removeprefix('sha256:')}.svg"
    ):
        raise ValueError("candidate path differs")
    if legacy["final_path"] != f"slides/{slide_id}.svg":
        raise ValueError("final path differs")
    if legacy["state"] not in V1_MIGRATION_STATES:
        raise ValueError("transaction state is invalid")
    attempt = legacy["generation_attempt"]
    if isinstance(attempt, bool) or not isinstance(attempt, int) or not 0 <= attempt <= 3:
        raise ValueError("generation attempt is invalid")
    candidate_sha256 = legacy["candidate_sha256"]
    if candidate_sha256 is not None:
        _require_sha256(candidate_sha256, "candidate_sha256")
    failure_reason = legacy["failure_reason"]
    if legacy["state"] == "failed":
        if failure_reason not in V1_MIGRATION_FAILURE_REASONS:
            raise ValueError("failure reason is invalid")
    elif failure_reason is not None:
        raise ValueError("nonfailed transaction has a failure reason")


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
    try:
        validate_v1_migration_transaction(legacy)
    except (KeyError, TypeError, ValueError):
        return _migration_conflict(source_run)
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
    reserved = {
        ref for ref, transaction in transactions.items()
        if transaction["state"] == "generating" or
        (transaction["state"] == "compiled" and
         (transaction["host_task_id"] is not None or transaction["host_attribution_id"] is not None))
    }
    available_slots = max(0, width - len(reserved))
    if not available_slots:
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
        # Old-epoch reservations remain occupied until durable host lookup
        # resolves them; a new epoch alone never authorizes another spawn.
        if ref in reserved:
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
                "data_tools": "none",
                "output": "text",
                "expected_fence": "xml",
                "timeout_ms": 120000,
                "cancellation": True,
            }
        )
        if len(tasks) == available_slots:
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
