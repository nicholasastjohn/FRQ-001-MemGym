#!/usr/bin/env python3
"""Freeze real answer prompts for a future smoke test, without calling a model."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from reproduce import (PINNED_UPSTREAM, backend_check, git, reserve_output,
                       safe_env, sha256, verify_upstream, write_json)

REVISION = "02f8da42a1a771d1d58552274db1cbf46f0fc7b4"
MODEL = "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DATA = {
    "3hop": ("3hop_verified.jsonl", 161, "88be2c475fa80f754fac50e6d982a421684463777e3633a3ccb0e24fe6740939"),
    "4hop": ("4hop_paper_run.jsonl", 916, "e99eebf4c1c8cdb75428905b13409b02cfe610801599b48c9712d7fcc9091352"),
    "56hop": ("56hop_clean.jsonl", 117, "b740b88fa1044d11483a68220d0d8b68d27242fcd8518911080d9e28924fc781"),
}
SOURCES = (
    "src/memgym/pipelines/memgym_ir/eval/agent.py",
    "src/memgym/pipelines/memgym_ir/eval/memory.py",
    "src/memgym/pipelines/memgym_ir/llm/prompts.py",
    "src/memgym/pipelines/memgym_ir/types/schemas.py",
    "src/memgym/memory/base.py", "src/memgym/memory/ir/__init__.py",
    "src/memgym/memory/ir/ir_bm25.py",
)


def selected_row(path, expected_hash, expected_rows, row_index=0):
    """Verify the complete file, preserving row order and repeated instance IDs."""
    digest = hashlib.sha256()
    selected = None
    rows = 0
    with path.open("rb") as stream:
        for rows, line in enumerate(stream, 1):
            digest.update(line)
            if not line.strip():
                raise ValueError("Blank dataset row")
            if rows - 1 == row_index:
                selected = line
    if digest.hexdigest() != expected_hash or rows != expected_rows:
        raise ValueError("Dataset hash or row count differs from the pinned release")
    if selected is None:
        raise ValueError("Selected row does not exist")
    parsed = json.loads(selected)
    return parsed, {"dataset_sha256": expected_hash, "dataset_rows": rows,
                    "row_index": row_index, "instance_id": parsed["instance_id"],
                    "raw_line_sha256": hashlib.sha256(selected).hexdigest()}


class PromptCaptured(Exception):
    """Stop unchanged upstream evaluation at the first model boundary."""


class CaptureClient:
    def __init__(self):
        self.prompt = None

    def get_completion(self, prompt, **kwargs):
        if self.prompt is not None or kwargs != {"temperature": 0.0}:
            raise RuntimeError("Unexpected upstream answer call")
        self.prompt = prompt
        raise PromptCaptured()

    def get_json_completion(self, **kwargs):
        raise RuntimeError("A judge must never be called during preparation")


def capture_prompt(instance):
    from memgym.pipelines.memgym_ir.eval.agent import evaluate_with_manager
    client = CaptureClient()
    try:
        evaluate_with_manager(instance, client, strategy="ir_bm25")
    except PromptCaptured:
        if isinstance(client.prompt, str) and client.prompt:
            return client.prompt
    raise RuntimeError("Upstream did not reach the expected answer boundary")


def worker(request_path):
    from offline_worker import install_guard
    install_guard(42)
    import memgym.memory.ir  # Activate the unchanged upstream manager registry.
    from memgym.pipelines.memgym_ir.llm.prompts import ANSWER_JUDGE_PROMPT, ANSWER_JUDGE_SCHEMA
    from memgym.pipelines.memgym_ir.types.schemas import MemGymIRInstance
    import tiktoken

    request = json.loads(request_path.read_text())
    upstream, output = Path(request["upstream"]), request_path.parent
    verify_upstream(upstream, PINNED_UPSTREAM)
    encoder = tiktoken.get_encoding("cl100k_base")
    write_json(output / "tokenizer-contract.json", {
        "encoding": "cl100k_base", "package_version": tiktoken.__version__,
        "vocabulary_sha256": "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7",
        "vocabulary_url": "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
        "integrity": "The installed tiktoken constructor verifies this vocabulary hash before loading",
        "usage": "Offline upstream token counting and prompt-size diagnostics; not provider billing"})
    cells = []
    for cell in request["cells"]:
        parsed, identity = selected_row(Path(cell["dataset_path"]), cell["dataset_sha256"],
                                        cell["dataset_rows"])
        if identity != cell["identity"]:
            raise ValueError("Selected input identity changed")
        instance = MemGymIRInstance(**parsed)
        if not instance.turns:
            raise ValueError("Selected case has no search turns")
        prompt = capture_prompt(instance)
        path = output / (cell["stratum"] + "-ir_bm25-answer.txt")
        path.write_text(prompt, encoding="utf-8")
        cells.append({**cell, "strategy": "ir_bm25", "num_hops": instance.num_hops,
                      "answer_prompt": path.name, "prompt_sha256": sha256(path),
                      "prompt_characters": len(prompt), "prompt_utf8_bytes": path.stat().st_size,
                      "cl100k_tokens": len(encoder.encode(prompt)),
                      "token_count_note": "Offline diagnostic, not provider token count or a billing bound",
                      "provider_token_upper_bound": None,
                      "judge_inputs": {"gold_answer": instance.answer, "question": instance.question},
                      "judge_prompt_status": "Depends on the future captured answer; template and fixed inputs only"})
    write_json(output / "judge-contract.json", {
        "kind": "unfilled upstream judge template; no generated answer exists",
        "template": ANSWER_JUDGE_PROMPT, "response_format": ANSWER_JUDGE_SCHEMA,
        "template_sha256": hashlib.sha256(ANSWER_JUDGE_PROMPT.encode()).hexdigest(),
        "schema_canonical_json_sha256": hashlib.sha256(json.dumps(ANSWER_JUDGE_SCHEMA, sort_keys=True).encode()).hexdigest(),
        "required_substitutions": ["gold_answer", "predicted_answer", "question"],
        "model": MODEL, "temperature": 0.0})
    write_json(output / "prepared-cells.json", cells)
    verify_upstream(upstream, PINNED_UPSTREAM)


def prepare(args):
    upstream, output = Path(args.upstream).resolve(), Path(args.output).resolve()
    verify_upstream(upstream, PINNED_UPSTREAM)
    root = Path(__file__).resolve().parents[1]
    config_path = root / "configs/scored-smoke-plan.json"
    config = json.loads(config_path.read_text())
    if config != {"kind": "prepare_only_engineering_smoke", "model": MODEL,
                  "answer_and_judge_share_model": True, "temperature": 0.0,
                  "strategies": ["ir_bm25"], "row_index_per_stratum": 0,
                  "paid_execution_enabled": False, "approved_budget_usd": 0,
                  "paper_protocol_alignment": "unresolved"}:
        raise ValueError("Prepare-only configuration differs from the reviewed fixed plan")
    manifest_path = Path(args.dataset_manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("resolved_revision") != REVISION or manifest.get("repository") != "MemGym/memgym-dr-instances":
        raise ValueError("Dataset manifest does not identify the pinned release")
    cells = []
    for stratum in (args.stratum or list(DATA)):
        filename, rows, digest = DATA[stratum]
        entry = manifest["files"][filename]
        if entry.get("sha256") != digest or entry.get("rows") != rows:
            raise ValueError("Dataset manifest hash or count changed")
        path = Path(entry["local_path"]).resolve()
        _, identity = selected_row(path, digest, rows)
        cells.append({"stratum": stratum, "dataset_path": str(path),
                      "dataset_sha256": digest, "dataset_rows": rows, "identity": identity})
    reserve_output(output)
    write_json(output / "request.json", {"upstream": str(upstream), "cells": cells})
    presence = backend_check()
    write_json(output / "backend-presence.json", presence)
    for relative in ("scripts/prepare_scored_smoke.py", "scripts/reproduce.py",
                     "scripts/offline_worker.py", "scripts/tests/test_prepare_scored_smoke.py",
                     "configs/scored-smoke-plan.json"):
        target = output / "harness_source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    (output / "dataset-manifest.json").write_bytes(manifest_path.read_bytes())
    plan = {"kind": "prepare_only_engineering_smoke", "prepared_utc": datetime.now(timezone.utc).isoformat(),
            "status": "preparing", "upstream_sha": PINNED_UPSTREAM,
            "harness_sha": git(root, "rev-parse", "HEAD"),
            "harness_status": git(root, "status", "--porcelain"),
            "dataset_revision": REVISION, "configuration": config,
            "model_calls_made": 0, "network_calls_permitted": False,
            "maximum_logical_requests_for_future_complete_run": 2 * len(cells),
            "request_bound_note": "One answer and one judge per cell, only with retries disabled; not a billed-cost ceiling",
            "blockers": ["Backend credentials/access must be configured and verified",
                         "Original Bedrock Sonnet 4.5 is Legacy; account eligibility is unverified and credentials alone do not establish access",
                         "Spending budget is zero and paid execution is disabled",
                         "Paper protocol alignment remains unresolved; this engineering smoke would not reproduce the paper"],
            "historical_model_lifecycle": {"checked_date": "2026-11-01", "status": "Legacy since 2026-10-08",
                "end_of_life": "2027-04-08", "account_eligibility": "unverified",
                "source": "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle-legacy.html",
                "note": "New customers cannot use Legacy models; existing access may lapse after 15 days inactivity. No model substitution is authorized."},
            "source_hashes": {p: sha256(upstream / p) for p in SOURCES},
            "cells": cells}
    write_json(output / "plan.json", plan)
    command = [args.python, str(Path(__file__).resolve()), "--worker-plan", str(output / "request.json")]
    try:
        with (output / "preparation.log").open("w") as log:
            result = subprocess.run(command, env=safe_env(upstream, 42), cwd=upstream,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
        if result.returncode:
            raise RuntimeError("Guarded preparation worker failed; inspect preparation.log")
        verify_upstream(upstream, PINNED_UPSTREAM)
        plan.update(status="prepared_without_model_calls", cells=json.loads((output / "prepared-cells.json").read_text()))
    except Exception as exc:
        plan.update(status="failed", error_type=type(exc).__name__)
        raise
    finally:
        plan["artifacts"] = {str(p.relative_to(output)): {"sha256": sha256(p), "bytes": p.stat().st_size}
                             for p in sorted(output.rglob("*")) if p.is_file() and p.name != "plan.json"}
        write_json(output / "plan.json", plan)
    print(json.dumps({"output": str(output), "cells": len(cells), "model_calls_made": 0,
                      "status": plan["status"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream")
    parser.add_argument("--dataset-manifest")
    parser.add_argument("--output")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--stratum", action="append", choices=DATA)
    parser.add_argument("--worker-plan", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_plan:
        worker(args.worker_plan)
    elif all((args.upstream, args.dataset_manifest, args.output)):
        if args.stratum and len(set(args.stratum)) != len(args.stratum):
            parser.error("Each stratum may be selected only once")
        prepare(args)
    else:
        parser.error("--upstream, --dataset-manifest and --output are required")


if __name__ == "__main__":
    main()
