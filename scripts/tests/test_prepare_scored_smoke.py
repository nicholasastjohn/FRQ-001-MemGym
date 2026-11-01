"""Checks for the prepare-only model boundary and frozen case provenance."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("frq_prepare", SCRIPTS / "prepare_scored_smoke.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class PrepareTests(unittest.TestCase):
    def test_changed_dataset_hash_or_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_bytes(b'{"instance_id":"first"}\n')
            with self.assertRaisesRegex(ValueError, "hash or row count"):
                planner.selected_row(path, "0" * 64, 1)
            with self.assertRaisesRegex(ValueError, "hash or row count"):
                planner.selected_row(path, planner.sha256(path), 2)

    def test_colliding_ids_retain_distinct_raw_row_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_bytes(b'{"instance_id":"same","question":"A"}\n'
                             b'{"instance_id":"same","question":"B"}\n')
            digest = planner.sha256(path)
            _, a = planner.selected_row(path, digest, 2, 0)
            _, b = planner.selected_row(path, digest, 2, 1)
            self.assertEqual(a["instance_id"], b["instance_id"])
            self.assertNotEqual(a["row_index"], b["row_index"])
            self.assertNotEqual(a["raw_line_sha256"], b["raw_line_sha256"])

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "output"
            planner.reserve_output(path)
            marker = path / "prior-evidence.txt"
            marker.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                planner.reserve_output(path)
            self.assertEqual(marker.read_bytes(), b"original")

    def test_capture_stops_before_any_answer_or_judge_exists(self):
        client = planner.CaptureClient()
        with self.assertRaises(planner.PromptCaptured):
            client.get_completion(prompt="exact answer prompt", temperature=0.0)
        self.assertEqual(client.prompt, "exact answer prompt")
        with self.assertRaises(RuntimeError):
            client.get_json_completion(prompt="must not run")
        with self.assertRaises(RuntimeError):
            client.get_completion(prompt="second attempt", temperature=0.0)

    def test_guard_blocks_a_real_socket_attempt_in_worker_environment(self):
        code = (f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); "
                "from offline_worker import install_guard; install_guard(42); "
                "import socket; socket.create_connection(('127.0.0.1', 1))")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                env=planner.safe_env(Path("/tmp/unused"), 42), timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FRQ offline network guard blocked", result.stderr)

    @unittest.skipUnless(os.environ.get("FRQ_TEST_UPSTREAM"), "Set FRQ_TEST_UPSTREAM for pinned-source integration")
    def test_captured_prompt_matches_real_upstream_adapter_construction(self):
        upstream = Path(os.environ["FRQ_TEST_UPSTREAM"]).resolve()
        planner.verify_upstream(upstream, planner.PINNED_UPSTREAM)
        code = '''
import sys
sys.path.insert(0, SCRIPTS)
from offline_worker import install_guard
install_guard(42)
import memgym.memory.ir
from prepare_scored_smoke import capture_prompt
from memgym.pipelines.memgym_ir.types.schemas import MemGymIRInstance, EvictionPolicy
from memgym.pipelines.memgym_ir.eval.agent import IRMemoryAdapter, _get_ir_manager, _build_visible_docs, _format_documents
from memgym.pipelines.memgym_ir.llm.prompts import EVICTED_ANSWER_PROMPT
row = dict(instance_id="fixture", base_instance="fixture", source_dataset="synthetic_test_only",
           question="What color is the archive?", original_question="What color is the archive?",
           answer="blue", num_hops=3, turns=[dict(turn_index=i, sub_query="archive color",
           documents=[dict(title="Archive", text="The archive is blue.")]) for i in range(3)])
instance = MemGymIRInstance(**row)
manager = _get_ir_manager("ir_bm25", question=instance.question)
adapter = IRMemoryAdapter(manager, question=instance.question)
policy = instance.eviction_policy or EvictionPolicy()
for i, turn in enumerate(instance.turns):
    docs, _ = _build_visible_docs(instance, i, policy)
    adapter.process_turn(turn, docs)
docs, _ = _build_visible_docs(instance, len(instance.turns)-1, policy)
visible = "Documents still visible from recent turns:\\n" + _format_documents(docs)
expected = EVICTED_ANSWER_PROMPT.format(question=instance.question,
    notes=manager.retrieve_for_question(instance.question), visible_documents_section=visible)
assert capture_prompt(instance) == expected
print("Exact answer prompt matches unchanged upstream adapters and template")
'''.replace("SCRIPTS", repr(str(SCRIPTS)))
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                env=planner.safe_env(upstream, 42), cwd=upstream, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Exact answer prompt matches", result.stdout)
        planner.verify_upstream(upstream, planner.PINNED_UPSTREAM)


if __name__ == "__main__":
    unittest.main()
