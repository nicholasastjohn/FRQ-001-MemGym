#!/usr/bin/env python3
"""Run only zero-cost validation, blocking Python outbound socket operations.

This guard prevents accidental Python network calls. It is not an OS sandbox
for arbitrary untrusted code or native extensions. Never use it as a live runner.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random
import runpy
import sys


def block_network(event, arguments):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError(f"FRQ offline network guard blocked {event}")


def install_guard(seed):
    sys.addaudithook(block_network)
    random.seed(seed)
    # Seed numpy if installed. Tests can run without it to expose install gaps.
    try:
        import numpy
        numpy.random.seed(seed)
    except ImportError:
        pass


def smoke(args):
    import memgym.memory.ir  # noqa: F401; activate evaluator's registry
    from memgym.pipelines.memgym_ir.eval.agent import (
        IRMemoryAdapter, _build_visible_docs, _get_ir_manager,
    )
    from memgym.pipelines.memgym_ir.types.schemas import MemGymIRInstance, EvictionPolicy

    dataset = Path(args.dataset)
    digest = hashlib.sha256()
    with dataset.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    rows = []
    with dataset.open() as stream:
        for index, line in enumerate(stream):
            if index >= args.limit:
                break
            instance = MemGymIRInstance(**json.loads(line))
            managers = {strategy: _get_ir_manager(strategy, question=instance.question)
                        for strategy in ("ir_passthrough", "ir_bm25")}
            adapters = {strategy: IRMemoryAdapter(manager, question=instance.question)
                        for strategy, manager in managers.items()}
            policy = instance.eviction_policy or EvictionPolicy()
            observations = []
            turn_trace = []
            for turn_index, turn in enumerate(instance.turns):
                visible_docs, visible_start = _build_visible_docs(instance, turn_index, policy)
                for adapter in adapters.values():
                    adapter.process_turn(turn, visible_docs)
                # Capture actual upstream formatting and replay its context flow.
                observation = adapters["ir_passthrough"]._context[-1]
                observations.append(observation)
                turn_trace.append({"turn_index": turn_index,
                                   "visible_start": visible_start,
                                   "visible_document_count": len(visible_docs),
                                   "observation_characters": len(observation),
                                   "observation_sha256": hashlib.sha256(observation.encode()).hexdigest()})
            if not instance.turns or not any(turn["visible_document_count"] for turn in turn_trace):
                raise ValueError(f"No documents reached adapters: {instance.instance_id}")
            text = adapters["ir_passthrough"].get_notes_text()
            if text != "\n".join(observations):
                raise AssertionError("PassThrough did not retain the supplied observation stream")
            retrieval = managers["ir_bm25"].retrieve_for_question(instance.question)
            chunks = managers["ir_bm25"].get_stats()["num_chunks"]
            if chunks <= 0:
                raise AssertionError("BM25 did not index any chunks")
            rows.append({"instance_id": instance.instance_id, "input_row_index": index,
                         "num_hops": instance.num_hops, "num_turns": len(instance.turns),
                         "eviction_policy": policy.model_dump(), "turn_trace": turn_trace,
                         "adapters": {"ir_passthrough": {"retained_characters": len(text),
                                                          "retains_all_turns": True},
                                      "ir_bm25": {"indexed_chunks": chunks,
                                                  "retrieved_characters": len(retrieval),
                                                  "nonempty_retrieval": retrieval != "(no relevant chunks found)",
                                                  "retrieval_sha256": hashlib.sha256(retrieval.encode()).hexdigest()}}})
            print(f"Parsed and indexed {instance.instance_id}: hops={instance.num_hops}, turns={len(instance.turns)}, chunks={chunks}")
    if not rows:
        raise ValueError("No input rows were available")
    result = {"kind": "offline evaluator eviction and adapter wiring check; no task answering or judging",
              "upstream_replay_functions": ["eval.agent._get_ir_manager", "eval.agent._build_visible_docs",
                                            "eval.agent.IRMemoryAdapter.process_turn"],
              "empirical_benchmark": False, "model_calls_made": 0, "seed": args.seed,
              "dataset_path": str(dataset.resolve()), "dataset_sha256": digest.hexdigest(),
              "selection": "first N file rows, unchanged order", "limit": args.limit,
              "schema_validated_rows": len(rows), "instances": rows,
              "notes": ["PassThrough retains all observations in current upstream; this differs from the paper's no-memory condition.",
                        "BM25 retrieval output length and hash are wiring evidence, not accuracy or fact recall.",
                        "No generated answers, rubric scores, or benchmark accuracy values are produced."]}
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    sub = parser.add_subparsers(dest="mode", required=True)
    module = sub.add_parser("module")
    module.add_argument("name")
    module.add_argument("arguments", nargs=argparse.REMAINDER)
    sub.add_parser("registry")
    check = sub.add_parser("smoke")
    check.add_argument("--dataset", required=True)
    check.add_argument("--limit", type=int, default=1)
    check.add_argument("--output", required=True)
    args = parser.parse_args()
    install_guard(args.seed)
    if args.mode == "module":
        sys.argv = [args.name] + args.arguments
        runpy.run_module(args.name, run_name="__main__", alter_sys=True)
    elif args.mode == "registry":
        import memgym.memory.ir  # noqa: F401; activate IR registry before listing
        from memgym.memory.base import list_memory_models
        print(json.dumps(sorted(list_memory_models()), indent=2))
    elif args.mode == "smoke":
        smoke(args)


if __name__ == "__main__":
    main()
