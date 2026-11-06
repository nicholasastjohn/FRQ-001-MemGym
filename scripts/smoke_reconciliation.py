"""Validate the fixed historical reconciliation for the single 5/6-hop retry."""

from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

from reproduce import sha256
from scored_client import INPUT_USD_PER_MILLION, OUTPUT_USD_PER_MILLION, SONNET46_MODEL


ROOT = Path(__file__).resolve().parents[1]
PREDECESSOR = ROOT / "results/raw/2026-11-02-sonnet46-partial-smoke"
EVIDENCE_PATH = ROOT / "results/reconciliation/2026-11-06-sonnet46-console.json"
EVIDENCE_SHA = "c0a8b26cd0e4a9d9465174327af277969ff3c33c70f91e484142a72ac3854bba"
PREDECESSOR_SHA = "be644d0adaaafd61eec28832a1bca0350150dfaa5d5a8512394cc78b198b9f1c"


def validate_reconciled_continuation(plan_path, plan):
    """Bind the single-use retry to the observed costs and original failed cell."""
    manifest_path = PREDECESSOR / "manifest.json"
    if sha256(manifest_path) != PREDECESSOR_SHA or sha256(EVIDENCE_PATH) != EVIDENCE_SHA:
        raise ValueError("The historical manifest or console reconciliation changed")
    manifest = json.loads(manifest_path.read_text())
    evidence = json.loads(EVIDENCE_PATH.read_text())
    for name, meta in manifest["artifacts"].items():
        path = PREDECESSOR / name
        if path.is_symlink() or path.stat().st_size != meta["bytes"] or sha256(path) != meta["sha256"]:
            raise ValueError("The original run evidence changed")
    if (evidence["predecessor_manifest_sha256"] != PREDECESSOR_SHA
            or sha256(plan_path) != manifest["plan_sha256"]
            or manifest["model"] != SONNET46_MODEL or manifest["status"] != "failed"):
        raise ValueError("Continuation does not match the original run")

    def trace(name):
        return [json.loads(line) for line in (PREDECESSOR / name).read_text().splitlines()]

    original = trace("prior-request-trace.jsonl")
    saved = trace("recovered-answer-source-trace.jsonl")
    partial = trace("request-trace.jsonl")
    failure = json.loads((PREDECESSOR / "56hop/failure.json").read_text())
    cells = [cell for cell in plan["cells"] if cell["stratum"] == "56hop"]
    if (len(cells) != 1 or cells[0]["identity"] != failure["identity"]
            or cells[0]["prompt_sha256"] != sha256(PREDECESSOR / "56hop/answer-prompt.txt")
            or failure["status"] != "failed" or failure["score"] is not None
            or failure["error_code"] != "incomplete_or_refused_response"
            or partial[-1].get("error_code") != failure["error_code"]):
        raise ValueError("Expected the frozen, unscored 5/6-hop cell")

    requests = [row for row in original + saved + partial if row["kind"] == "request"]
    responses = [row for row in saved + partial if row["kind"] == "response"]
    if (len(requests) != evidence["historical_attempts"] or len(responses) != 4
            or [row["kind"] for row in original] != ["request", "error"]
            or original[1]["error_code"] != "http_404"):
        raise ValueError("Historical attempt accounting differs")
    inputs = sum(row["usage"]["input_tokens"] for row in responses)
    outputs = sum(row["usage"]["output_tokens"] for row in responses)
    observed_cost = (evidence["input_tokens"] * INPUT_USD_PER_MILLION
                     + evidence["output_tokens"] * OUTPUT_USD_PER_MILLION) / Decimal(1000000)
    upper_bound = Decimal(evidence["historical_charge_upper_bound_usd"])
    original_hold = Decimal(original[0]["reserved_cost_usd"])
    prior = upper_bound + original_hold
    if (evidence["sole_nonzero_usage_day_utc"] != datetime.fromisoformat(manifest["started_utc"]).date().isoformat()
            or evidence["model"] != SONNET46_MODEL
            or (evidence["input_tokens"] - inputs, evidence["output_tokens"] - outputs) != (33130, 1024)
            or not Decimal(evidence["displayed_organization_total_cost_usd"]) <= observed_cost <= upper_bound
            or upper_bound != Decimal(evidence["displayed_organization_total_cost_usd"]) + Decimal("0.01")
            or original_hold != Decimal(evidence["initial_404_reservation_retained_usd"])
            or prior != Decimal(evidence["prior_reservation_usd"])):
        raise ValueError("Console observation and historical accounting do not reconcile")
    return {**evidence, "evidence_sha256": EVIDENCE_SHA,
            "predecessor_hold_usd": manifest["reserved_cost_usd"],
            "console_token_priced_cost_usd": str(observed_cost)}
