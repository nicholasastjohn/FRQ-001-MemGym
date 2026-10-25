"""Safety and provenance checks for the zero-cost harness (stdlib unittest)."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("frq_reproduce", SCRIPTS / "reproduce.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class SafetyTests(unittest.TestCase):
    def test_arbitrary_secret_variables_do_not_reach_children(self):
        with patch.dict(os.environ, {"SOME_FUTURE_PROVIDER_SECRET": "test-sensitive-value",
                                     "OPENAI_API_KEY": "test-sensitive-value",
                                     "OPENAI_BASE_URL": "https://test-sensitive-value.example"}):
            env = harness.safe_env(Path("/tmp/upstream"), 0)
            self.assertNotIn("test-sensitive-value", json.dumps(env))
            presence = harness.backend_check()
            self.assertTrue(presence["environment_variable_present"]["OPENAI_API_KEY"])
            self.assertNotIn("test-sensitive-value", json.dumps(presence))

    def test_network_guard_blocks_dns_and_connections(self):
        # Test in a separate interpreter because audit hooks cannot be removed.
        code = (
            "import sys, socket; "
            f"sys.path.insert(0, {str(SCRIPTS)!r}); "
            "from offline_worker import install_guard; install_guard(0); "
            "socket.create_connection(('127.0.0.1', 1))"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                text=True, timeout=30,
                                env=harness.safe_env(Path("/tmp/upstream"), 0))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FRQ offline network guard blocked", result.stderr)

    def test_output_directory_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            harness.reserve_output(output)
            record = output / "raw.json"
            record.write_text('{"unchanged": true}')
            with self.assertRaises(FileExistsError):
                harness.reserve_output(output)
            self.assertEqual(record.read_text(), '{"unchanged": true}')

    def test_wrong_or_dirty_upstream_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            tracked = repo / "source.py"
            tracked.write_text("original\n")
            subprocess.run(["git", "-C", str(repo), "add", "source.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=FRQ Test",
                            "-c", "user.email=frq-test@example.invalid", "commit", "-qm", "fixture"], check=True)
            actual = harness.git(repo, "rev-parse", "HEAD")
            self.assertEqual(harness.verify_upstream(repo, actual), actual)
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                harness.verify_upstream(repo, "0" * 40)
            tracked.write_text("modified\n")
            with self.assertRaisesRegex(ValueError, "tracked modifications"):
                harness.verify_upstream(repo, actual)

    def test_duplicate_dataset_ids_preserve_distinct_row_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "rows.jsonl"
            first = json.dumps({"instance_id": "same", "num_hops": 3, "question": "First case"}) + "\n"
            second = json.dumps({"instance_id": "same", "num_hops": 3, "question": "Different case"}) + "\n"
            dataset.write_text(first + second)
            audit = harness.jsonl_audit(dataset)
            self.assertEqual(audit["rows"], 2)
            self.assertEqual(audit["unique_instance_ids"], 1)
            collision = audit["instance_id_collisions"]["same"]
            self.assertEqual([row["row_index"] for row in collision], [0, 1])
            self.assertNotEqual(collision[0]["line_sha256"], collision[1]["line_sha256"])
            self.assertEqual(len(audit["ordered_rows"]), 2)

    def test_untracked_source_rejected_ignored_cache_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / ".gitignore").write_text("cache/\n")
            subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=FRQ Test",
                            "-c", "user.email=frq-test@example.invalid", "commit", "-qm", "fixture"], check=True)
            actual = harness.git(repo, "rev-parse", "HEAD")
            (repo / "cache").mkdir()
            (repo / "cache/tokenizer").write_text("cached data")
            self.assertEqual(harness.verify_upstream(repo, actual), actual)
            (repo / "conftest.py").write_text("raise RuntimeError('untracked injection')\n")
            with self.assertRaisesRegex(ValueError, "nonignored untracked files"):
                harness.verify_upstream(repo, actual)


if __name__ == "__main__":
    unittest.main()
