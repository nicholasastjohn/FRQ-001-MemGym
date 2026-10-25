#!/usr/bin/env python3
"""Capture reproducibility evidence without performing any model calls.

Standard library only. See scripts/README.md for installation and scope.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request

PINNED_UPSTREAM = "50b404e6ae4e1fcd453d3e07963eb3e6312cbded"
DATA_REPO = "MemGym/memgym-dr-instances"
DATA_FILES = {"3hop_verified.jsonl": 161, "4hop_paper_run.jsonl": 916,
              "56hop_clean.jsonl": 117}
SECRET_NAMES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE",
                "AWS_BEARER_TOKEN_BEDROCK", "BEDROCK_API_KEY", "AWS_REGION", "AWS_DEFAULT_REGION",
                "AZURE_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                "OPENAI_API_BASE", "OPENAI_BASE_URL", "LITELLM_API_KEY",
                "LITELLM_API_BASE", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_env(upstream, seed):
    # Construct an allowlist instead of attempting to enumerate every secret.
    keep = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL",
            "SYSTEMROOT", "TIKTOKEN_CACHE_DIR", "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.update({"PYTHONPATH": str(upstream / "src"), "PYTHONHASHSEED": str(seed),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
                "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                "AWS_EC2_METADATA_DISABLED": "true", "TOKENIZERS_PARALLELISM": "false"})
    return env


def git(upstream, *args):
    return subprocess.check_output(["git", "-C", str(upstream), *args], text=True).strip()


def verify_upstream(upstream, expected_sha):
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("--expected-sha must be a full lowercase commit SHA")
    actual = git(upstream, "rev-parse", "HEAD")
    if actual != expected_sha:
        raise ValueError(f"Upstream SHA mismatch: expected {expected_sha}, found {actual}")
    dirty = git(upstream, "status", "--porcelain", "--untracked-files=normal")
    if dirty:
        raise ValueError("Upstream has tracked modifications or nonignored untracked files; use a clean checkout")
    return actual


def reserve_output(path):
    # Never overwrite a prior run, including failed runs.
    path.mkdir(parents=True, exist_ok=False)


class Evidence:
    def __init__(self, args):
        self.args = args
        self.upstream = Path(args.upstream).resolve()
        self.output = Path(args.output).resolve()
        actual = verify_upstream(self.upstream, args.expected_sha)
        reserve_output(self.output)
        self.manifest = {"schema_version": 1, "started_utc": utc_now(),
                         "operation": args.operation, "upstream_sha": actual,
                         "upstream_path": str(self.upstream), "seed": args.seed,
                         "python_executable": args.python,
                         "model_calls_permitted": False, "model_calls_made": 0,
                         "empirical_benchmark": False, "commands": [],
                         "invocation": sys.argv, "status": "running"}
        harness_root = Path(__file__).resolve().parents[1]
        self.manifest["harness_git_head"] = git(harness_root, "rev-parse", "HEAD")
        self.manifest["harness_git_status_at_start"] = git(
            harness_root, "status", "--porcelain", "--untracked-files=normal")
        self.manifest["harness_source_at_start"] = {}
        # Preserve exact code/config bytes as well as hashes when running from a
        # working tree that has not yet been committed.
        for relative in ("scripts/reproduce.py", "scripts/offline_worker.py",
                         "scripts/tests/test_safety.py", "configs/reproduction.yaml"):
            source = harness_root / relative
            destination = self.output / "harness_source" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            self.manifest["harness_source_at_start"][relative] = {
                "sha256": sha256(destination), "bytes": destination.stat().st_size,
                "snapshot": str(destination.relative_to(self.output))}
        self.save()

    def save(self):
        write_json(self.output / "manifest.json", self.manifest)

    def command(self, label, command, offline=True):
        index = len(self.manifest["commands"]) + 1
        log = self.output / f"{index:02d}_{label}.log"
        record = {"label": label, "argv": command, "cwd": str(self.upstream),
                  "started_utc": utc_now(), "log": log.name,
                  "python_network_guard": offline}
        self.manifest["commands"].append(record)
        self.save()
        start = time.monotonic()
        print(f"[{label}] {shlex.join(command)}", flush=True)
        try:
            with log.open("w") as stream:
                result = subprocess.run(command, cwd=self.upstream,
                                        env=safe_env(self.upstream, self.args.seed),
                                        stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=self.args.timeout, check=False)
            record["returncode"] = result.returncode
        except subprocess.TimeoutExpired:
            record["returncode"] = 124
            record["timed_out"] = True
        record["elapsed_seconds"] = round(time.monotonic() - start, 4)
        record["finished_utc"] = utc_now()
        record["log_sha256"] = sha256(log)
        self.save()
        print(f"[{label}] exit={record['returncode']}; log={log}", flush=True)
        return record["returncode"]

    def worker(self, label, mode, *arguments):
        return self.command(label, [self.args.python,
                            str(Path(__file__).with_name("offline_worker.py")),
                            "--seed", str(self.args.seed), mode, *map(str, arguments)])

    def finish(self):
        verify_upstream(self.upstream, self.args.expected_sha)
        self.manifest["finished_utc"] = utc_now()
        self.manifest["status"] = "passed" if all(
            record["returncode"] == 0 for record in self.manifest["commands"]
        ) else "failed"
        self.manifest["artifacts"] = {
            str(path.relative_to(self.output)): {"sha256": sha256(path),
                                                    "bytes": path.stat().st_size}
            for path in sorted(self.output.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        }
        self.save()
        return 0 if self.manifest["status"] == "passed" else 1


def backend_check():
    return {"checked_utc": utc_now(),
            "environment_variable_present": {key: bool(os.environ.get(key)) for key in SECRET_NAMES},
            "aws_config_file_present": (Path.home() / ".aws/config").exists(),
            "aws_credentials_file_present": (Path.home() / ".aws/credentials").exists(),
            "network_probe_performed": False,
            "credentials_validated": False,
            "note": "Presence is not proof of access; absence does not rule out managed credentials."}


def snapshot(run):
    args = run.args
    write_json(run.output / "system.json", {"captured_utc": utc_now(),
               "system": platform.system(), "release": platform.release(),
               "machine": platform.machine(), "platform": platform.platform(),
               "cpu_count": os.cpu_count(), "harness_python": sys.version,
               "seed_scope": "random and numpy seeds plus PYTHONHASHSEED; no provider RNG is exercised"})
    write_json(run.output / "backend_presence.json", backend_check())
    files = subprocess.check_output(["git", "-C", str(run.upstream), "ls-files", "-z"]).split(b"\0")
    hashes = {}
    for name in files:
        if not name:
            continue
        relative = os.fsdecode(name)
        path = run.upstream / relative
        if path.is_symlink():
            hashes[relative] = {"symlink_target": os.readlink(path)}
        elif path.is_file():
            hashes[relative] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    write_json(run.output / "upstream_files.json", hashes)
    run.command("python_version", [args.python, "--version"], offline=False)
    run.command("pip_freeze", [args.python, "-m", "pip", "freeze", "--all"], offline=False)
    run.command("pip_check", [args.python, "-m", "pip", "check"], offline=False)


def jsonl_audit(path):
    count = 0
    hops = Counter()
    ids = []
    rows = []
    by_id = {}
    with path.open("rb") as stream:
        for index, line in enumerate(stream):
            if not line.strip():
                raise ValueError(f"Blank JSONL row in {path.name}")
            row = json.loads(line)
            ids.append(row["instance_id"])
            identity = {"row_index": index, "instance_id": row["instance_id"],
                        "line_sha256": hashlib.sha256(line).hexdigest()}
            rows.append(identity)
            by_id.setdefault(row["instance_id"], []).append(identity)
            hops[str(row["num_hops"])] += 1
            count += 1
    collisions = {instance_id: entries for instance_id, entries in by_id.items() if len(entries) > 1}
    return {"rows": count, "hops": dict(sorted(hops.items())),
            "ordered_instance_ids": ids, "sha256": sha256(path),
            "bytes": path.stat().st_size, "unique_instance_ids": len(by_id),
            "instance_id_collisions": collisions, "ordered_rows": rows,
            "row_identity": "dataset file SHA256 + zero-based row index + exact raw line SHA256 (including newline)",
            "warning": "Instance ID collisions preserved; never deduplicate or key results solely by instance_id" if collisions else None}


def download_data(run):
    # Anonymous requests only. All file URLs resolve an immutable dataset SHA.
    revision = urllib.parse.quote(run.args.revision, safe="")
    metadata_url = f"https://huggingface.co/api/datasets/{DATA_REPO}/revision/{revision}?blobs=true"
    with urllib.request.urlopen(metadata_url, timeout=60) as response:
        metadata_bytes = response.read()
    (run.output / "hf_metadata.json").write_bytes(metadata_bytes)
    metadata = json.loads(metadata_bytes)
    resolved = metadata["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise ValueError("HF API did not return an immutable SHA")
    siblings = {row["rfilename"]: row for row in metadata.get("siblings", [])}
    provenance = {"repository": DATA_REPO, "requested_revision": run.args.revision,
                  "resolved_revision": resolved, "metadata_url": metadata_url,
                  "retrieved_utc": utc_now(), "files": {}}
    write_json(run.output / "dataset_manifest.json", provenance)
    for filename, expected_rows in DATA_FILES.items():
        if filename not in siblings:
            raise ValueError(f"Required dataset file missing: {filename}")
        url = f"https://huggingface.co/datasets/{DATA_REPO}/resolve/{resolved}/{filename}"
        destination = run.output / filename
        lfs = siblings[filename].get("lfs", {})
        expected_hash = lfs.get("sha256") or lfs.get("oid")
        cache_file = Path(run.args.cache_dir).resolve() / filename if run.args.cache_dir else None
        reused = bool(cache_file and cache_file.is_file())
        if reused:
            # The cache is read-only: adding or repairing prior raw evidence is forbidden.
            if not expected_hash:
                raise ValueError(f"Cannot reuse {filename}: immutable HF metadata lacks a SHA256")
            destination = cache_file
            print(f"Reusing {filename} from {cache_file}", flush=True)
        else:
            temporary = destination.with_suffix(".jsonl.part")
            written = 0
            print(f"Downloading {filename} at {resolved}", flush=True)
            with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    written += len(chunk)
                    if written > run.args.max_file_bytes:
                        raise ValueError("Dataset file exceeded the declared size limit")
                    stream.write(chunk)
            temporary.rename(destination)
        # Verify exact upstream payload bytes before parsing, counting or identifying rows.
        actual_hash = sha256(destination)
        if expected_hash and expected_hash != actual_hash:
            raise ValueError(f"HF LFS SHA256 mismatch for {filename}")
        audit = jsonl_audit(destination)
        audit.update({"url": url, "expected_rows": expected_rows,
                      "retrieved_utc": utc_now(), "local_path": str(destination.resolve()),
                      "reused_readonly_cache": reused, "hf_lfs_sha256": expected_hash,
                      "hf_lfs_integrity_verified": bool(expected_hash)})
        provenance["files"][filename] = audit
        write_json(run.output / "dataset_manifest.json", provenance)
        if audit["rows"] != expected_rows:
            raise ValueError(f"Row count mismatch for {filename}: {audit['rows']} != {expected_rows}")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("operation", choices=("backend-check", "preflight", "validate",
                                               "download-data", "dry-run", "offline-smoke"))
    result.add_argument("--upstream", default="../MemGym")
    result.add_argument("--expected-sha", default=PINNED_UPSTREAM)
    result.add_argument("--output", help="New directory; existing runs are never overwritten")
    result.add_argument("--python", default=sys.executable)
    result.add_argument("--seed", type=int, default=42)
    result.add_argument("--timeout", type=int, default=600)
    result.add_argument("--dataset", action="append", default=[], help="Repeat for multiple strata")
    result.add_argument("--limit", type=int, default=1, help="First N rows per offline-smoke input file")
    result.add_argument("--revision", default="main", help="HF revision; resolved SHA is recorded before downloads")
    result.add_argument("--cache-dir", help="Read-only existing payload directory; reuse only after immutable HF SHA256 verification")
    result.add_argument("--max-file-bytes", type=int, default=1024 * 1024 * 1024)
    return result


def main():
    args = parser().parse_args()
    if args.operation == "backend-check":
        print(json.dumps(backend_check(), indent=2, sort_keys=True))
        return 0
    if not args.output:
        raise SystemExit("--output is required")
    if args.seed < 0 or args.seed > 2**32 - 1 or args.limit < 1:
        raise SystemExit("seed must be uint32; limit must be positive")
    args.python = str(Path(args.python).absolute())
    args.dataset = [str(Path(path).resolve()) for path in args.dataset]
    run = Evidence(args)
    try:
        if args.operation == "preflight":
            snapshot(run)
        elif args.operation == "validate":
            run.worker("imports", "module", "pytest", "tests/unit/test_imports.py", "-q")
            run.worker("unit_tests", "module", "pytest", "tests/unit/test_imports.py",
                       "tests/unit/test_rm_eval.py", "tests/unit/test_world_model.py",
                       "tests/unit/test_memory_strategies_roundtrip.py", "tests/unit/test_known_bugs.py",
                       "tests/unit/test_memory_eval.py", "-q")
            run.worker("cli_help", "module", "memgym.pipelines.memgym_ir", "--help")
            run.worker("registry", "registry")
        elif args.operation == "download-data":
            download_data(run)
        elif args.operation == "dry-run":
            run.worker("synthetic_dry_run", "module", "memgym.pipelines.memgym_ir", "dataset",
                       "--dataset", "synthetic", "--dry-run", "--limit", "2", "--min-hops", "3",
                       "--max-concurrent", "1", "--no-resume", "--output", run.output / "synthetic")
            path = run.output / "synthetic/memgym_ir_instances.jsonl"
            if not path.exists():
                raise ValueError("Upstream dry-run did not produce the expected fixture file")
            write_json(run.output / "fixture_manifest.json", {
                "kind": "upstream synthetic dry-run placeholders; not empirical data",
                "audit": jsonl_audit(path)})
        elif args.operation == "offline-smoke":
            if not args.dataset:
                raise ValueError("offline-smoke requires at least one --dataset FILE")
            for index, path in enumerate(args.dataset):
                run.worker(f"adapter_smoke_{index}", "smoke", "--dataset", path,
                           "--limit", args.limit, "--output", run.output / f"adapter_smoke_{index}.json")
        return run.finish()
    except Exception as exc:
        run.manifest.update({"status": "failed", "finished_utc": utc_now(),
                             "error_type": type(exc).__name__, "error": str(exc)})
        run.save()
        print(f"Failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
