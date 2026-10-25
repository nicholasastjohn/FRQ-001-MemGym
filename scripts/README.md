# Reproducibility harness

`reproduce.py` uses the standard library and refuses a wrong upstream SHA,
tracked upstream changes, nonignored untracked upstream files, or an existing
output directory. It records commands,
return codes, timing, logs, hashes, fixed seed and input instance IDs. Exact harness
code/config snapshots and FRQ Git HEAD/status are recorded at run start. Failures
remain failures. No command here answers questions, invokes an LLM, or produces
paper task scores.

Use a separate, clean upstream checkout and a separate virtual environment.
The complete requested upstream extras are `[dev,eval,swe,memory-eval]`; install
attempts and any dependency conflicts belong in the evidence record. The DR
pipeline additionally lists dependencies in
`src/memgym/pipelines/memgym_ir/requirements.txt`. For an isolated minimum DR
environment, core + `[dev,swe]` plus `pyyaml`, `boto3`, `arxiv`, and `rank-bm25`
cover this harness; this reduced installation is a deviation from the complete
extras request. Do not silently treat optional methods as installed.

From the FRQ repository, with `PY` set to the absolute environment interpreter:

```bash
PY=/absolute/path/to/venv/bin/python

# Presence booleans only; never print keys or read credential file contents.
"$PY" scripts/reproduce.py backend-check

# Capture source hashes, interpreter, exact installed versions and pip check.
"$PY" scripts/reproduce.py preflight --upstream ../MemGym \
  --python "$PY" --output results/raw/my-run-preflight

# Authors' import suite, selected unit suite, CLI help and IR registry.
"$PY" scripts/reproduce.py validate --upstream ../MemGym \
  --python "$PY" --output results/raw/my-run-tests

# Public released data: use the audited immutable revision.
"$PY" scripts/reproduce.py download-data --upstream ../MemGym \
  --revision 02f8da42a1a771d1d58552274db1cbf46f0fc7b4 \
  --output results/raw/my-run-dataset

# Actual released schemas + local memory adapters, first one row per stratum.
"$PY" scripts/reproduce.py offline-smoke --upstream ../MemGym --python "$PY" \
  --output results/raw/my-run-adapters \
  --dataset results/raw/my-run-dataset/3hop_verified.jsonl \
  --dataset results/raw/my-run-dataset/4hop_paper_run.jsonl \
  --dataset results/raw/my-run-dataset/56hop_clean.jsonl

# Separate placeholder-generation check of upstream dataset pipeline.
"$PY" scripts/reproduce.py dry-run --upstream ../MemGym \
  --python "$PY" --output results/raw/my-run-synthetic

# Safety/provenance tests need no MemGym installation.
"$PY" -m unittest discover -s scripts/tests -v
```

The validation seed defaults to `42`. The pinned SHA defaults to
`50b404e6ae4e1fcd453d3e07963eb3e6312cbded`.
Use `--expected-sha` only for an explicitly documented new artifact baseline.
The dataset revision above is the audited release. Resolving `main` is supported
for an explicitly versioned new baseline; the resolved SHA is recorded before any
payload download. Input files are never altered.

To reuse payloads from an earlier or failed download without copying or
redownloading them, add `--cache-dir results/raw/earlier-download` and choose a new
`--output`. Existing cache files are read only and their exact SHA256 must match
the immutable Hugging Face LFS metadata before JSONL parsing. Missing files are
downloaded into the new output. Each `dataset_manifest.json` file entry records
the actual `local_path`; use those paths for `offline-smoke`. The initial failed
download and its original failure manifest remain intact.

The audited 4-hop release has 916 rows and 909 distinct `instance_id` values:
six collision groups, including one triple and five pairs. All rows are retained.
Join outputs by dataset file SHA256, zero-based row ordinal, and raw-line SHA256,
including the newline. `ordered_rows` and `instance_id_collisions` in the dataset
manifest preserve those keys and original order. Never deduplicate or aggregate
results solely by `instance_id`.

The three large released payload filenames are ignored by Git. Their immutable
revision, LFS verification, full-file hashes, row identities and audit logs remain
committed. Small synthetic fixture JSONLs and command JSONLs remain committable.

Validation workers receive an environment allowlist, without provider keys,
custom endpoints, or inherited Python startup settings. They block Python
DNS/connect/sendto operations and disable Hugging Face network access and
LiteLLM's online cost map. This protects against accidental Python API calls;
it is not an OS sandbox for arbitrary native extensions. Downloads are separate
anonymous HTTPS operations and require internet access. The preflight version,
package-freeze and dependency-check commands do not use the Python network guard.

Tokenizer vocabulary data may need to be cached before running strict offline
checks. If absent, the guard produces a visible failure; do not patch token
counting or pass off a fallback tokenizer as identical. Preserve the download URL
and vocabulary hash if priming this cache.

The synthetic dry run emits upstream placeholder verification values used for
pipeline wiring. Those values are not empirical results and must never enter a
paper comparison. The released adapter smoke reuses upstream manager dispatch,
visible-document eviction and turn-formatting/context adapters. It emits only
schema validation, visible-window traces, chunk counts, output lengths/hashes and
selected IDs. It does not run the
upstream benchmark, answer model, or judge.

No live benchmark launcher is provided while the protocol gaps in
`configs/reproduction.yaml` and the protocol audit remain unresolved. In
particular, current `ir_passthrough` retains every turn, MemoryBank lacks manager
dispatch, SimpleMem defaults to another model, and benchmark exceptions become
zeros. A successful install or local adapter smoke does not resolve these gaps.

