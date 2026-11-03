"""No-network checks for the frozen smoke plan and credential/launch boundary."""

from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import run_scored_smoke as runner
from scored_client import StrictAnthropicClient, MODEL


class RunTests(unittest.TestCase):
    def test_original_failed_hold_is_carried_and_changed_ledger_is_rejected(self):
        recorded = SCRIPTS.parent / "results/raw/2026-11-02-initial-scored-smoke/request-trace.jsonl"
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "prior.jsonl"
            ledger.write_bytes(recorded.read_bytes())
            amount, digest = runner.prior_reservation(ledger)
            self.assertEqual(amount, Decimal("0.61536"))
            self.assertEqual(len(digest), 64)
            ledger.write_text(ledger.read_text()+"\n")
            with self.assertRaisesRegex(ValueError, "differs"):
                runner.prior_reservation(ledger)

    def test_private_key_file_is_local_only_and_insecure_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            path = Path(directory) / ".env.local"
            self.assertEqual(runner.load_api_key(path), "")
            path.write_text("ANTHROPIC_API_KEY=fixture-secret\n")
            path.chmod(0o600)
            self.assertEqual(runner.load_api_key(path), "fixture-secret")
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "private"):
                runner.load_api_key(path)
            path.unlink()
            os.mkfifo(path, 0o600)
            with self.assertRaisesRegex(ValueError, "regular file"):
                runner.load_api_key(path)

    def test_changed_answer_prompt_stops_before_client_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            client = SimpleNamespace(get_completion=lambda **kwargs: calls.append(kwargs))
            wrapped = runner.MatchedClient(client, "frozen question", Path(directory))
            with self.assertRaisesRegex(ValueError, "differs"):
                wrapped.get_completion("changed question", temperature=0)
            self.assertEqual(calls, [])

    def test_missing_key_does_not_create_a_budget_ledger_or_launch_worker(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            root = Path(directory)
            plan_path = root / "plan.json"
            plan_path.write_text("{}\n")
            args = SimpleNamespace(upstream=directory, plan=str(plan_path), output=str(root/"output"),
                api_key_file=str(root/"missing-key"), budget_usd="5", execute=True,
                authorization_ledger=str(root/"approval.jsonl"), python=sys.executable)
            with patch.object(runner, "validate_plan", return_value={"cells": [{}, {}, {}]}), \
                 patch.object(runner, "verify_upstream"), patch.object(runner, "git", return_value="fixture"), \
                 patch.object(runner.subprocess, "run") as launch:
                result = runner.run(args)
            self.assertEqual(result, 2)
            launch.assert_not_called()
            manifest = json.loads((root/"output/manifest.json").read_text())
            self.assertEqual(manifest["status"], "blocked_missing_api_key")
            self.assertEqual(manifest["model_calls_attempted"], 0)
            self.assertFalse((root/"approval.jsonl").exists())

    @unittest.skipUnless(os.environ.get("FRQ_TEST_PREPARED_PLAN") and os.environ.get("FRQ_TEST_UPSTREAM"),
                         "Set FRQ_TEST_PREPARED_PLAN and FRQ_TEST_UPSTREAM for frozen-plan integration")
    def test_real_frozen_plan_evaluates_with_mock_transport_and_rejects_tampering(self):
        plan_path = Path(os.environ["FRQ_TEST_PREPARED_PLAN"]).resolve()
        upstream = Path(os.environ["FRQ_TEST_UPSTREAM"]).resolve()
        plan = runner.validate_plan(plan_path, upstream)
        calls = []

        def transport(payload, _key):
            calls.append(payload)
            text = '{"answer":"Synthetic test fixture, not an experimental answer"}'
            if "system" in payload:
                text = '{"score":0.25,"explanation":"Synthetic fixture judgment for software testing only"}'
            return {"id": f"msg_test_{len(calls)}", "model": MODEL, "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": text}],
                    "usage": {"input_tokens": 10, "output_tokens": 20}}

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "mock-run"
            output.mkdir()
            client = StrictAnthropicClient(api_key="test-fixture", trace_path=Path(directory)/"ledger",
                                           max_cost_usd=Decimal("5"), transport=transport)
            results = runner.execute_cells(plan, plan_path, upstream, output, client)
            self.assertEqual(len(results), 3)
            self.assertEqual(len(calls), 6)
            self.assertTrue(all(row["status"] == "scored" for row in results))
            self.assertEqual(Decimal(client.summary()["reserved_cost_usd"]), Decimal("3.69216"))
            # These mock outputs live only in an ephemeral test directory.
            copied = Path(directory) / "tampered"
            shutil.copytree(plan_path.parent, copied)
            prompt = copied / plan["cells"][0]["answer_prompt"]
            prompt.write_text(prompt.read_text()+"changed")
            with self.assertRaisesRegex(ValueError, "artifact changed"):
                runner.validate_plan(copied/"plan.json", upstream)


if __name__ == "__main__":
    unittest.main()
