#!/usr/bin/env python3
"""Check or execute the approved three-case engineering smoke; never a paper run."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from prepare_scored_smoke import DATA, REVISION, SOURCES, selected_row
from reproduce import PINNED_UPSTREAM, git, reserve_output, safe_env, sha256, verify_upstream, write_json

DIRECT_MODEL = "claude-sonnet-4-5-20250929"
PLAN_COMMIT = "565e23da788dc124935d5978ed3b1a392dad349c"
APPROVED_CEILING = Decimal("5")


def now():
    return datetime.now(timezone.utc).isoformat()


def load_api_key(path):
    """Read only the requested local key file; never print or snapshot its value."""
    inherited = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if inherited:
        return inherited
    path = Path(path)
    if not path.exists():
        return ""
    mode = path.stat().st_mode
    if path.is_symlink() or not stat.S_ISREG(mode) or mode & 0o077:
        raise ValueError("API key file must be a private regular file (mode 600)")
    lines = path.read_text().splitlines()
    if len(lines) != 1 or not lines[0].startswith("ANTHROPIC_API_KEY="):
        raise ValueError("API key file must contain only ANTHROPIC_API_KEY=value")
    value = lines[0].split("=", 1)[1]
    if not value or any(c.isspace() for c in value):
        raise ValueError("API key file contains a blank or malformed value")
    return value


def validate_plan(plan_path, upstream):
    """Fail before a model connection if any frozen artifact or row has changed."""
    plan_path, upstream = Path(plan_path).resolve(), Path(upstream).resolve()
    root = plan_path.parent
    plan = json.loads(plan_path.read_text())
    verify_upstream(upstream, PINNED_UPSTREAM)
    if (plan.get("status") != "prepared_without_model_calls"
            or plan.get("harness_sha") != PLAN_COMMIT or plan.get("harness_status") != ""
            or plan.get("upstream_sha") != PINNED_UPSTREAM
            or plan.get("dataset_revision") != REVISION):
        raise ValueError("Plan does not match the reviewed frozen baseline")
    for relative, meta in plan["artifacts"].items():
        path = root / relative
        if Path(relative).is_absolute() or ".." in Path(relative).parts or path.is_symlink():
            raise ValueError("Unsafe plan artifact path")
        if sha256(path) != meta["sha256"] or path.stat().st_size != meta["bytes"]:
            raise ValueError("Prepared artifact changed")
    if set(plan.get("source_hashes", {})) != set(SOURCES):
        raise ValueError("Missing pinned evaluator source hashes")
    for relative, digest in plan["source_hashes"].items():
        if sha256(upstream / relative) != digest:
            raise ValueError("Pinned upstream source changed")
    cells = plan.get("cells", [])
    if not 1 <= len(cells) <= 3 or len({c["stratum"] for c in cells}) != len(cells):
        raise ValueError("Expected one distinct case per selected stratum")
    if plan.get("maximum_logical_requests_for_future_complete_run") != 2 * len(cells):
        raise ValueError("Unexpected request count")
    for cell in cells:
        _, count, digest = DATA[cell["stratum"]]
        if (cell.get("strategy") != "ir_bm25" or cell["dataset_sha256"] != digest
                or cell["dataset_rows"] != count or cell["identity"]["row_index"] != 0):
            raise ValueError("Unexpected smoke matrix or input identity")
        _, identity = selected_row(Path(cell["dataset_path"]), digest, count)
        if identity != cell["identity"]:
            raise ValueError("Selected row changed")
        prompt_path = root / cell["answer_prompt"]
        if (Path(cell["answer_prompt"]).name != cell["answer_prompt"]
                or cell["answer_prompt"] not in plan["artifacts"]
                or sha256(prompt_path) != cell["prompt_sha256"]):
            raise ValueError("Frozen prompt changed")
    return plan


class MatchedClient:
    """Bind each unchanged evaluator call to its frozen answer prompt."""

    def __init__(self, client, expected_prompt, output):
        self.client, self.expected_prompt, self.output = client, expected_prompt, output
        self.phase = "answer"

    def get_completion(self, prompt, **kwargs):
        if self.phase != "answer" or prompt != self.expected_prompt:
            raise ValueError("Evaluator answer prompt differs from the prepared plan")
        self.phase = "judge"
        return self.client.get_completion(prompt=prompt, **kwargs)

    def get_json_completion(self, prompt, **kwargs):
        if self.phase != "judge":
            raise ValueError("Unexpected judge request")
        self.phase = "finished"
        (self.output / "judge-prompt.txt").write_text(prompt, encoding="utf-8")
        return self.client.get_json_completion(prompt=prompt, **kwargs)


def execute_cells(plan, plan_path, upstream, output, client):
    import memgym.memory.ir  # Register the unchanged BM25 adapter.
    from memgym.pipelines.memgym_ir.eval.agent import evaluate_with_manager
    from memgym.pipelines.memgym_ir.types.schemas import MemGymIRInstance
    from scored_client import SmokeClientError

    results = []
    for cell in plan["cells"]:
        case_output = output / cell["stratum"]
        case_output.mkdir()
        row, identity = selected_row(Path(cell["dataset_path"]), cell["dataset_sha256"], cell["dataset_rows"])
        expected = (plan_path.parent / cell["answer_prompt"]).read_text(encoding="utf-8")
        (case_output / "answer-prompt.txt").write_text(expected, encoding="utf-8")
        wrapped = MatchedClient(client, expected, case_output)
        record = {"stratum": cell["stratum"], "identity": identity, "strategy": "ir_bm25"}
        try:
            result = evaluate_with_manager(MemGymIRInstance(**row), wrapped, strategy="ir_bm25")
            if wrapped.phase != "finished":
                raise ValueError("Evaluator did not complete both strict model boundaries")
            record.update(status="scored", result=result)
            write_json(case_output / "result.json", record)
            results.append(record)
        except Exception as error:
            failure = {**record, "status": "failed", "score": None,
                       "error_type": type(error).__name__,
                       "error_code": error.args[0] if isinstance(error, SmokeClientError) else "evaluation_failed"}
            write_json(case_output / "failure.json", failure)
            results.append(failure)
            write_json(output / "cases.json", results)
            raise
        write_json(output / "cases.json", results)
    verify_upstream(upstream, PINNED_UPSTREAM)
    return results


def worker(request_path):
    """Only this explicit worker path can instantiate the live client."""
    from scored_client import StrictAnthropicClient
    request = json.loads(request_path.read_text())
    upstream, output = Path(request["upstream"]), request_path.parent
    plan_path = Path(request["plan_path"])
    plan = validate_plan(plan_path, upstream)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    client = StrictAnthropicClient(api_key=key, trace_path=Path(request["authorization_ledger"]),
                                   max_cost_usd=Decimal(request["budget_usd"]),
                                   max_calls=2 * len(plan["cells"]))
    try:
        execute_cells(plan, plan_path, upstream, output, client)
    finally:
        write_json(output / "usage.json", client.summary())


def run(args):
    upstream, plan_path, output = Path(args.upstream).resolve(), Path(args.plan).resolve(), Path(args.output).resolve()
    plan = validate_plan(plan_path, upstream)
    budget = Decimal(args.budget_usd)
    if not budget.is_finite() or budget <= 0 or budget > APPROVED_CEILING:
        raise ValueError("The approved test ceiling is positive and no greater than USD 5")
    # Check key presence without printing or snapshotting the value.
    root = Path(__file__).resolve().parents[1]
    key = load_api_key(args.api_key_file or root / ".env.local")
    key_present = bool(key)
    reserve_output(output)
    manifest = {"kind": "initial_scored_engineering_smoke", "started_utc": now(),
                "status": "checking", "model": DIRECT_MODEL, "provider": "anthropic_direct",
                "api_version": "2023-06-01", "approved_budget_usd": str(budget),
                "approval_scope": "User approved USD 5 for this initial test in the current task on 2026-11-01",
                "maximum_physical_attempts": 2 * len(plan["cells"]),
                "maximum_output_tokens_per_request": 1024,
                "full_window_reservation_usd_per_attempt": "0.61536",
                "api_key_present": key_present, "plan_sha256": sha256(plan_path),
                "harness_sha": git(root, "rev-parse", "HEAD"),
                "harness_status": git(root, "status", "--porcelain"),
                "upstream_sha": PINNED_UPSTREAM, "dataset_revision": REVISION,
                "paper_reproduction": False, "model_calls_attempted": 0,
                "deviations": ["Direct Anthropic provider instead of Bedrock; same dated model ID",
                               "1024-token output cap; strict JSON validation; fail fast with no retries",
                               "Judge schema checked locally; JSON system instruction instead of provider response_format",
                               "Three selected BM25 cases are an engineering smoke, not a paper comparison"]}
    for relative in ("scripts/run_scored_smoke.py", "scripts/scored_client.py",
                     "scripts/prepare_scored_smoke.py", "scripts/reproduce.py"):
        target = output / "harness_source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    (output / "prepared-plan.json").write_bytes(plan_path.read_bytes())
    ledger = None
    try:
        if not key_present:
            manifest["status"] = "blocked_missing_api_key"
        elif not args.execute:
            manifest["status"] = "ready_not_executed"
        else:
            if not args.authorization_ledger:
                raise ValueError("Live execution requires a single-use authorization ledger path")
            ledger = Path(args.authorization_ledger).resolve()
            if ledger.exists():
                raise FileExistsError("Authorization ledger already exists; budget cannot be reset")
            request = {"upstream": str(upstream), "plan_path": str(plan_path),
                       "budget_usd": str(budget), "authorization_ledger": str(ledger)}
            write_json(output / "request.json", request)
            env = safe_env(upstream, 42)
            env["ANTHROPIC_API_KEY"] = key
            # This dedicated worker has no other inherited provider credentials or custom endpoints.
            command = [args.python, str(Path(__file__).resolve()), "--worker-request", str(output / "request.json")]
            result = subprocess.run(command, cwd=upstream, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200, check=False)
            manifest["status"] = "scored" if result.returncode == 0 else "failed"
            manifest["worker_returncode"] = result.returncode
    except Exception as error:
        manifest.update(status="failed", error_type=type(error).__name__)
        # Never put transport exception strings or a traceback into public evidence.
    finally:
        if ledger is not None and ledger.is_file():
            raw_trace = ledger.read_bytes()
            (output / "request-trace.jsonl").write_bytes(raw_trace)
            # Preserve reservations even if the worker timed out before saving usage.
            records = []
            for line in raw_trace.splitlines():
                try:
                    records.append(json.loads(line))
                except (ValueError, TypeError):
                    manifest["trace_incomplete"] = True
            requests = [r for r in records if r.get("kind") == "request"]
            manifest["model_calls_attempted"] = len(requests)
            manifest["reserved_cost_usd"] = str(sum(
                (Decimal(r["reserved_cost_usd"]) for r in requests), Decimal("0")))
            manifest["billing_uncertain"] = True
        if (output / "usage.json").is_file():
            manifest["usage"] = json.loads((output / "usage.json").read_text())
            manifest["model_calls_attempted"] = manifest["usage"]["attempted_calls"]
            manifest["billing_uncertain"] = manifest["usage"]["billing_uncertain"]
        try:
            verify_upstream(upstream, PINNED_UPSTREAM)
            manifest["upstream_clean_after_run"] = True
        except Exception as error:
            manifest.update(status="failed", upstream_clean_after_run=False,
                            upstream_verification_error_type=type(error).__name__)
        manifest["finished_utc"] = now()
        manifest["artifacts"] = {str(p.relative_to(output)): {"sha256": sha256(p), "bytes": p.stat().st_size}
                                 for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"}
        write_json(output / "manifest.json", manifest)
    print(json.dumps({"output": str(output), "status": manifest["status"],
                      "model_calls_attempted": manifest["model_calls_attempted"],
                      "approved_budget_usd": str(budget)}, indent=2))
    return 0 if manifest["status"] in {"scored", "ready_not_executed"} else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan")
    parser.add_argument("--upstream")
    parser.add_argument("--output")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--budget-usd", default="0")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-ledger")
    parser.add_argument("--api-key-file")
    parser.add_argument("--worker-request", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_request:
        worker(args.worker_request)
        return 0
    if not all((args.plan, args.upstream, args.output)):
        parser.error("--plan, --upstream and --output are required")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
