# FRQ-001 validation report — 2026-10-25

**Outcome: installation, tests and offline MEMGYM-DR wiring passed. The published result has not yet been reproduced or refuted.** No LLM inference requests were made and LLM API cost was $0. FRQ-001 remains an independent study adjacent to Persistent Agency.

## What actually ran

Upstream tested, with no tracked or nonignored untracked changes: `50b404e6ae4e1fcd453d3e07963eb3e6312cbded`. Starting FRQ commit: `36fefda6a18e4eb3e2a1f7b674a61366cb1f483e`.

Python **3.12.14**, macOS **26.6.2 ARM64**, iMac21,1, 8 logical CPUs, 8 GiB RAM. The default system Python was 3.14.6; validation explicitly used a separate Python 3.12 environment. Full installed versions, commands, UTC timestamps, stdout/stderr, exit codes and hardware are retained.

| Executed check | Observed result |
|---|---|
| Clean environment, pip/uv bootstrap | Exit 0 |
| Editable upstream `.[dev,eval,swe,memory-eval]` install | Exit 0; no reduced-extras fallback |
| `pytest tests/unit/test_imports.py` | 4 passed |
| Six documented release-critical test files | 67 passed |
| Full `tests/unit/` | 298 passed, 4 skipped, 2 warnings |
| Full suite repeated with `-rs` to identify skips | Same result |
| DR module help, benchmark runner help, memory registry | Exit 0 |
| `pip check` | No broken requirements |
| Synthetic v2 dataset, `--dataset synthetic --dry-run --limit 2`, one worker | 2 placeholder instances, exit 0, no inference |
| Released-data offline replay, first row in each of three files | 3 schema/adaptor replays passed; see below |
| Harness safety/provenance tests | 6 passed; captured in final checks |
| Hardened runner validation | Imports/release suite/help/registry rerun with network guard; retained separately |

The full-suite documentation's 301-passed/1-skipped baseline assumes optional all-track components. Three observed skips require `minisweagent`, which the installed `swe` extra does not declare. The fourth is a real-LLM integration requiring credentials and explicit activation. No test failed. The full suite was repeated only to recover exact skip reasons.

The actual freeze contains 185 distributions, including memgym 0.2.0, pytest 9.1.1, torch 2.14.1, numpy 2.5.4, litellm 1.106.4 and sentence-transformers 6.2.0. It pins the editable upstream VCS revision. This is an observed platform-specific version snapshot, not a hash-locked or historical paper environment. The preflight evidence README's editable-local-path caution is generic; inspect the actual freeze, which uses a pinned Git URL.

## Released dataset provenance and identity

Anonymous download resolved `MemGym/memgym-dr-instances` to immutable revision **`02f8da42a1a771d1d58552274db1cbf46f0fc7b4`**. All three files match the HF LFS SHA-256 values.

| File | Rows / hop distribution | Bytes | SHA-256 |
|---|---|---:|---|
| 3hop_verified.jsonl | 161 / all 3-hop | 119330319 | `88be2c475fa80f754fac50e6d982a421684463777e3633a3ccb0e24fe6740939` |
| 4hop_paper_run.jsonl | 916 / all 4-hop | 909471804 | `e99eebf4c1c8cdb75428905b13409b02cfe610801599b48c9712d7fcc9091352` |
| 56hop_clean.jsonl | 117 / 57 five-hop + 60 six-hop | 123518977 | `b740b88fa1044d11483a68220d0d8b68d27242fcd8518911080d9e28924fc781` |

**4-hop IDs are not unique:** 916 rows contain 909 unique IDs, with six collision groups (one triple, five pairs). Colliding raw lines have different hashes. This establishes ID collisions, not necessarily semantic independence of every row. No rows were deduplicated or changed. Pair by dataset file hash + zero-based row index + exact raw-line hash. The audited manifest retains every ordered row, ID and digest.

The initial downloader stopped at the collision check, leaving its failed manifest and payloads intact. The revised harness records collisions and reuses those verified payloads read-only, then downloads the missing 5/6-hop file. The initial failed run used validation seed 0 and predates exact harness source snapshots; its intermediate code bytes were not archived. Subsequent runs record source/config snapshots and seed 42. No model RNG was exercised in either case.

Large public payloads remain local and ignored by Git. The repository retains immutable URLs/revision, metadata, row identities and hashes to retrieve them again. Small synthetic fixture payloads are retained and explicitly marked as placeholders.

## Smallest executed DR path

The offline worker uses the unmodified upstream `_get_ir_manager`, `_build_visible_docs` and `IRMemoryAdapter.process_turn`. It applies each row's full-eviction policy and replays every turn through BM25 and passthrough. It stops before answer generation and judging.

| File / row 0 instance | Turns | BM25 indexed chunks | Retrieved characters |
|---|---:|---:|---:|
| 3-hop / memgym_ir__research3__02865 | 3 | 160 | 29725 |
| 4-hop / memgym_ir__research__40424 | 4 | 223 | 30995 |
| 5/6-hop / memgym_ir__research__11213 (5-hop) | 5 | 223 | 30079 |

All three produced nonempty retrieval. The manifests contain observation/retrieval hashes, visible document windows and exact row identities. These are structural checks, **not accuracy, fact recall, a three-case model benchmark, or a representative sample**. Only these three released rows were validated through the complete schema and adapters; the full corpus audit checked JSON structure, counts, hop fields and identity, not every row through the complete schema.

Passthrough retained 462298 / 670531 / 631434 characters respectively across all observations. That directly verifies the current artifact's accumulation behavior despite full eviction.

## Blockers and corrections

The [published paper](https://arxiv.org/abs/2605.20833v1) labels the target **Figure 3(b)**, with detailed intervals in Appendix C.6 Table 8. Upstream calls it Figure 2b. The main comparison has seven methods and all 1,194 cases; 50 per stratum is a pilot default. The metric is a continuous judge score in [0,1], not binary exact-match accuracy. See the [primary-source audit](../experiments/protocol-audit.md).

Paper-faithful execution still needs resolution of:

1. Paper no-memory control versus current passthrough retaining all observations.
2. MemoryBank registered but absent from shared evaluator routing.
3. SimpleMem's GPT-4o-mini default versus the paper's matched-Haiku claim; the summarizer CLI option does not configure every backend.
4. Historical answerer/judge configurations, original case identity and paper-era software/prompt/embedding settings.
5. Upstream exceptions and exhausted API requests becoming zero scores or `{}` while the process succeeds. Real runs require transport evidence, raw answers/judgments and usage accounting.
6. LightMem's separate Python <3.12 environment and strategy-specific dependencies/configuration. Successful registry import does not establish backend readiness.

Credential-presence checks found no OpenAI, Anthropic or AWS/Bedrock credentials or standard AWS credential/config files. These are local presence checks, not an account-entitlement probe. No live smoke was attempted; there is no API error transcript or empirical score table to report. No account configuration was changed. No author email was sent.

## Next actions

First recover/clarify the original control, routing and backend configuration; implement any necessary study-side adapter with explicit deviations while preserving upstream. Establish Bedrock model access, region and a spending ceiling. Then run one genuine BM25 case with one worker, capture transport/answer/judge/usage, and estimate the full budget from measured calls, including memory ingestion.

Freeze model, data, prompts, failure handling and the analysis criteria in [REPRODUCTION.md](../REPRODUCTION.md) before the full 1,194 × seven-method evaluation. Repeated executions and stratified sampling sensitivity are modest later extensions. A full-dataset run itself already belongs to the original target. No completed-reproduction tag or results paper is justified by the present validation.

## Evidence index

- [Install/tests/environment](../results/raw/2026-10-25-preflight/README.md): 18 exact commands, raw logs, freeze, summary and checksums.
- [Initial failed data audit](../results/raw/2026-10-25-dataset/manifest.json): preserved collision failure.
- [Audited immutable dataset](../results/raw/2026-10-25-dataset-audited/dataset_manifest.json): verified hashes, every row identity and collision records.
- [Synthetic dry run](../results/raw/2026-10-25-synthetic-dry-run/manifest.json): explicit no-LLM placeholders.
- [Released offline smoke](../results/raw/2026-10-25-offline-smoke/manifest.json): three real released rows, two local adapters.
- [Guarded validation](../results/raw/2026-10-25-guarded-validation/manifest.json): free upstream checks under the hardened runner.
- [Final checks](../results/raw/2026-10-25-final-checks/manifest.json): final environment/source hashes, safety tests and dependency consistency.

Run manifests cover their artifacts. Final publication additionally verifies committed evidence hashes and omits large cache payloads. Upstream remained untouched throughout.
