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

## Prepare the next scored smoke test

`prepare_scored_smoke.py` freezes three BM25 cells: row zero from each released
stratum. It verifies the immutable dataset revision, complete file hashes and row
counts, then records the full-file hash, row ordinal and exact raw-line hash for
each selected case. Duplicate instance IDs remain distinct rows.

```bash
"$PY" scripts/prepare_scored_smoke.py --upstream ../MemGym --python "$PY" \
  --dataset-manifest results/raw/my-run-dataset/dataset_manifest.json \
  --output /absolute/path/to/new-smoke-plan

# Include the pinned-source prompt integration check alongside all harness tests.
FRQ_TEST_UPSTREAM=/absolute/path/to/MemGym \
  "$PY" -m unittest discover -s scripts/tests -v
```

Use the audited dataset manifest when reusing the existing verified payloads; its
`local_path` entries must resolve to those files. Choose a new output directory
for every preparation. `--stratum 3hop` can prepare only that stratum; otherwise
all three are included. The plan and raw prompt files belong in the local run
evidence, not in a paper results table.

Set `TIKTOKEN_CACHE_DIR` to a cache containing the authentic `cl100k_base`
vocabulary before these offline commands if the default cache is empty. The
network guard deliberately rejects an automatic tokenizer download. The
installed tiktoken constructor verifies vocabulary SHA-256
`223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`;
the resulting plan records this contract. Do not replace token counting with a
fallback to make preparation pass.

The worker receives the existing environment allowlist and Python network guard.
It calls unchanged `evaluate_with_manager` with a capture client that raises at
the first answer request. It neither answers nor judges. Exact answer prompts,
their sizes/hashes, upstream source hashes, source/config snapshots, and the
unfilled judge template/schema are retained. The judge prompt itself depends on
a future captured answer and cannot be frozen yet. `cl100k_tokens` is an offline
diagnostic, not a Bedrock token count or billing bound.

A later successful three-cell run would use six logical requests with retries
disabled. That count is not a billed-cost ceiling. Backend access, an approved
budget, strict response/error handling, and prompt-limit checks are still needed
before a live runner can be used. No live launcher is included here.

As of November 1, 2026,
[AWS lists Sonnet 4.5 as Legacy since October 8](https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle-legacy.html),
with end of life April 8, 2027 in the listed regions. New customers cannot use
Legacy models, and existing access may lapse after 15 days of inactivity. Verify
the intended account/region before treating credentials as sufficient. A
provider/model substitution requires a separate, documented decision.

## Initial direct-Anthropic smoke runner

`run_scored_smoke.py` can execute the prepared BM25 cells with the same dated
Sonnet 4.5 model through Anthropic directly. This provider change, strict JSON
validation, no retries, and a 1,024-token output cap are recorded engineering
deviations. The upstream evaluator and data stay unchanged. A successful run is
an engineering check; unresolved paper-protocol questions still prevent an exact
reproduction claim.

For the initial test, the user approved a maximum of USD 5 on November 1, 2026.
The runner requires an explicit positive ceiling no greater than that amount.
It permits at most six physical requests: three answers and three judgments.
Each request reserves USD 0.61536 before transport, using the full 200,000-token
input window at USD 3/M and at most 1,024 output tokens at USD 15/M. Six attempts
reserve USD 3.69216. Reservations remain consumed after failures or ambiguous
billing; actual returned usage is reported separately. This bounds modeled
inference charges under the documented contract, not taxes, credit purchases,
other account activity, or provider billing errors.

An `ANTHROPIC_API_KEY` is required. Supply it through the environment, or a private
mode-600 `.env.local` in the repository containing only `ANTHROPIC_API_KEY=value`.
That file is ignored by Git and is never copied into run evidence. Missing keys
produce a blocked readiness manifest without spending or consuming the ledger.

```bash
# Check the frozen inputs and credential presence without calling a model.
"$PY" scripts/run_scored_smoke.py --plan /absolute/path/to/prepared/plan.json \
  --upstream ../MemGym --python "$PY" --budget-usd 5 \
  --output /absolute/path/to/new-readiness-check

# Only after credentials are configured: execute this one approved test.
"$PY" scripts/run_scored_smoke.py --plan /absolute/path/to/prepared/plan.json \
  --upstream ../MemGym --python "$PY" --budget-usd 5 --execute \
  --authorization-ledger /absolute/path/to/initial-test-authorization.jsonl \
  --output /absolute/path/to/new-scored-smoke
```

The authorization ledger is exclusively created. Never select a different ledger
to silently reset an existing approval; a failed or interrupted run requires
review of its reservations before another execution. Responses, errors, prompt
hashes, selected usage, and reservations are preserved without credential values
or raw transport errors. A timeout, malformed output, missing usage, refusal,
truncation, unexpected model, or unsupported billing component stops the run;
none becomes a scientific score zero. A genuine valid judged zero remains zero.

The client pins API version `2023-06-01` to retain `temperature=0`, uses standard
service only, and sends no tools, caching, thinking or beta options. Sonnet 4.5
remains deprecated, with direct-API retirement listed for November 30, 2026.
Account access and credits must be verified at execution time.

Sources checked November 1, 2026: [pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[model lifecycle](https://platform.claude.com/docs/en/about-claude/model-deprecations),
[API versions](https://platform.claude.com/docs/en/api/versioning), and
[message contract](https://platform.claude.com/docs/en/api/messages/create).

### Approved Sonnet 4.6 continuation

The first live Sonnet 4.5 request returned HTTP 404. An authenticated model list
confirmed that the account exposes Sonnet 4.6 but not the dated Sonnet 4.5 ID.
The failed attempt and its full USD 0.61536 hold are preserved in
[`results/raw/2026-11-02-initial-scored-smoke`](../results/raw/2026-11-02-initial-scored-smoke).
On November 2, 2026 the user explicitly approved a Sonnet 4.6 engineering test
within the same total USD 5 budget. This is a model deviation, not an exact
reproduction of the original experiment.

Sonnet 4.6 has a 1M-token context window at the same standard USD 3/M input and
USD 15/M output rates. Each sequential request therefore reserves USD 3.01536
before transport. Only after the complete response and its answer/judge contract
validate does a persisted settlement replace that request's hold with returned
usage cost. Errors retain the full hold and stop the run. Before each next call,
the prior failed hold, settled costs, and next full reservation must together fit
within USD 5. Gross reservations over time are not a charge or simultaneous
exposure. Thinking is explicitly disabled, with temperature zero and API version
`2023-06-01` retained.

```bash
"$PY" scripts/run_scored_smoke.py --plan /absolute/path/to/prepared/plan.json \
  --upstream ../MemGym --python "$PY" --budget-usd 5 --execute \
  --model claude-sonnet-4-6 \
  --prior-authorization-ledger /absolute/path/to/original-failed-authorization.jsonl \
  --authorization-ledger /absolute/path/to/sonnet46-continuation.jsonl \
  --output /absolute/path/to/new-sonnet46-engineering-smoke
```

The prior ledger must exactly match the preserved original failure; it is never
overwritten. The continuation gets a separate exclusively created ledger, six
new generation attempts at most, and cumulative budget accounting. The input
case selection and exact answer prompts remain frozen from the original plan.

Sources checked November 2, 2026: [Sonnet 4.6 specification](https://platform.claude.com/docs/en/models/sonnet-4-6/overview)
and [standard long-context pricing](https://platform.claude.com/docs/en/about-claude/pricing#long-context-pricing).

