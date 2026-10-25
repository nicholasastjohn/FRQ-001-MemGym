# MEMGYM-DR paper and released-artifact audit

Audit date: 2026-10-25. This is a source audit, not an empirical reproduction result. FRQ-001 is an independent reproducibility study adjacent to Persistent Agency; Persistent Agency is not part of its scientific claim.

## Target identity and provenance

- Paper: Xu et al., *MemGym: a Long-Horizon Memory Environment for LLM Agents*, [arXiv:2605.20833v1](https://arxiv.org/abs/2605.20833v1), submitted 2026-05-20. The arXiv submission history lists only v1 as of the audit.
- Primary artifact: [versioned PDF](https://arxiv.org/pdf/2605.20833v1), retrieved 2026-10-25. SHA-256: `b8894814b03fa0c7b6bdce48ecc8575a5226d6d639f5c3cf04ce84085007e2a2` (independently checked against the downloaded file).
- **The versioned PDF labels the MEMGYM-DR results Figure 3(b), page 8, not Figure 2(b).** Figure 2, page 4, is architecture. Current [upstream track documentation](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/docs/tracks.md#L12) still calls the DR result Fig. 2b. FRQ-001 preserves that historical label only as an alias.
- Upstream audited commit: [`50b404e6ae4e1fcd453d3e07963eb3e6312cbded`](https://github.com/WujiangXu/MemGym/commit/50b404e6ae4e1fcd453d3e07963eb3e6312cbded), committed 2026-06-01. This postdates the paper. No claim is made that it is the exact paper-run commit.

## Published numeric target

The following are **published reference values**, transcribed from Figure 3(b) and Appendix C.6, Table 8 (PDF p22). They are not measurements produced by FRQ-001. Entries are mean judge score with the paper's 95% CI half-width, calculated there as `1.96 × SE`.

| Paper strategy | Intended registry name | 3-hop, n=161 | 4-hop, n=916 | 5/6-hop, n=117 |
|---|---|---:|---:|---:|
| None / Passthrough (no memory) | `ir_passthrough` — semantics conflict below | 0.330 ± 0.049 | 0.290 ± 0.014 | 0.009 ± 0.011 |
| BM25 | `ir_bm25` | 0.808 ± 0.037 | 0.555 ± 0.017 | 0.425 ± 0.048 |
| Naive RAG | `ir_naive_rag` | 0.753 ± 0.039 | 0.537 ± 0.016 | 0.442 ± 0.045 |
| A-Mem | `ir_amem` | 0.709 ± 0.043 | 0.540 ± 0.016 | 0.518 ± 0.037 |
| LightMem | `ir_lightmem` | 0.610 ± 0.049 | 0.467 ± 0.017 | 0.400 ± 0.043 |
| MemoryBank | `ir_memorybank` — routing gap below | 0.699 ± 0.043 | 0.537 ± 0.016 | 0.482 ± 0.041 |
| SimpleMem | `ir_simplemem` — CI absent from Table 8 | 0.614 | 0.467 | 0.415 |

Structured summary is excluded from the main figure: Appendix C.2/C.6 explicitly identify its `gpt-4o-mini` summarizer as contamination. Do not include it in the headline reproduction target. Rolling summarization may be a separate comparison, not a published DR Figure 3(b) cell.

The paper specifies a 100K-token target; Haiku 4.5 worker, Sonnet 4.5 verifier/judge; fictionalization; four distractor tiers. It reports 1,194 instances. The legacy filtered multihop-QA v2 generator is excluded from reported results (Appendix D). These statements do not recover unreported seeds or exact historical API configuration.

## Current implementation, verified by static code inspection

All links below pin the audited upstream commit. These observations describe the current artifact, not an inference that the paper ran this exact code.

### Model roles must be recorded separately

The [generation defaults](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/config.py#L242-L244) are:

```text
worker_model   = bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
verifier_model = bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

The benchmark [CLI defaults](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/examples/memgym_dr/run_ir_benchmark.py#L189-L199) use Sonnet for `--model` and Haiku for `--summarization-model`. The same evaluation client **both answers and judges** in [`evaluate_with_manager`](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/eval/agent.py#L197-L225), with temperature 0.0 on both calls. Thus generation worker, benchmark answerer, judge, and memory backend are different roles; calling all of them “worker” would conceal a protocol ambiguity. Confirm historical answerer identity with the authors before calling the run exact.

The judge [prompt](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/llm/prompts.py#L27-L39) awards 1 for semantic correctness, 0 for wrong answers, and partial credit 0.3–0.7. This is a continuous LLM judgment, not exact-match accuracy. `note_fact_recall` is a separate lexical diagnostic, [implemented with term overlap/intermediate-answer matches](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/eval/memory.py#L270-L303), not the published headline metric.

### Blocking discrepancies for paper-faithful execution

| Observation in current artifact | Consequence / required handling |
|---|---|
| [`IRPassThrough`](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/__init__.py#L20-L57) appends every turn observation and returns all accumulated text. The [answer phase](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/eval/agent.py#L179-L204) inserts this as retained notes. | Conflicts with Appendix E's no-retained-notes control. Label current `ir_passthrough` as raw accumulated context; do not claim it reproduces paper None. Recover the paper control or implement an explicitly separate, reviewed FRQ control without changing upstream. |
| [`_get_ir_manager`](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/eval/agent.py#L38-L71) lacks `ir_memorybank`, although [the adapter is registered](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_memorybank.py#L113). | The stock benchmark cannot run the complete published grid. Fail preflight; document any FRQ routing adapter as a deviation. |
| [`IRSimpleMemMemory`](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_simplemem.py#L22-L50) defaults to `gpt-4o-mini`; the router passes only `question`. | `--summarization-model` does not override this backend. Conflicts with the paper's uniform Haiku claim for uncontaminated cells. Recover recorded backend configs; never assume one CLI option configures every memory system. |
| [Default strategy list](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/examples/memgym_dr/run_ir_benchmark.py#L37-L45) includes contaminated Structured and omits SimpleMem/MemoryBank. | Provide an explicit strategy list after resolving the above gaps. |
| [Default limit is 50 and selection is the file prefix](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/examples/memgym_dr/run_ir_benchmark.py#L48-L56). | A default run cannot reproduce all 161/916/117 observations. Freeze source file hashes and ordered instance IDs for every stratum. |
| [`dataset` dispatches the v2 pipeline](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/__main__.py#L73-L77), defaulting to [MuSiQue](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/config.py#L239-L244). | The earlier chat's `dataset --limit 2` command can test installation, but it does not regenerate the paper's active deep-research corpus. Prefer pinned released DR rows for smoke testing. |

### Error handling can manufacture apparently valid zero scores

The [benchmark outer handler](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/examples/memgym_dr/run_ir_benchmark.py#L100-L138) converts exceptions to score 0 and includes those zeros in the mean. More subtly, [`LLMClient.get_completion`](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/llm/client.py#L78-L101) retries eight times, prints a transport error, and returns `{}`; the [evaluation parser](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/eval/agent.py#L204-L225) can then turn an absent answer or judge score into zero without an error field.

Process exit 0, a saved JSON, and an `error`-free row therefore do not establish a completed model evaluation. Retain provider response/failure events and raw answer/judge material; count attempted, successful, failed, retried, empty and malformed responses separately. A blocked or failed API call is not a wrong empirical answer. Do not publish aggregate scores from an error-bearing smoke run.

### Exposure, randomness, and evidence retention

- BM25 and Naive RAG default to 512-sized chunks, top-k 10; Naive RAG embeds with `all-MiniLM-L6-v2` ([BM25](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_bm25.py#L25-L38), [RAG](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_naive_rag.py#L22-L44)). Pin the embedding checkpoint revision and cache hashes before treating it as fixed.
- Current [A-Mem](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_amem.py#L154-L166), [LightMem](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_lightmem.py#L222-L231), [SimpleMem](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_simplemem.py#L64-L71), and [MemoryBank](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/memory/ir/ir_memorybank.py#L59-L72) ingest at most the first 15,000 characters of each observation. This is not a 100K-token memory allocation. Record corpus length, actual ingested characters/tokens, retrieved context, and final prompt length separately.
- The stock benchmark exposes no seed option. File selection is deterministic prefix selection, while [parallel output uses completion order](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/examples/memgym_dr/run_ir_benchmark.py#L121-L131). Serial execution avoids output-order ambiguity but does not make a remote model deterministic. Any FRQ seed is a new wrapper choice, not a recovered paper seed.
- The evaluator [returns predicted answers and manager stats](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/eval/agent.py#L233-L244), but [the benchmark discards them](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/examples/memgym_dr/run_ir_benchmark.py#L107-L111). Preserve full per-instance material in FRQ evidence rather than relying on its reduced output.
- The public [data catalog](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/docs/data.md#L18-L25) describes released DR rows as synthetic `deep_research` content, with no Wikipedia passages. The [HF card](https://huggingface.co/datasets/MemGym/memgym-dr-instances) also has legacy 2Wiki language. Determine origin from pinned row metadata and file inventory; do not regenerate MuSiQue and assume equivalent inputs. Dataset pins/checksums belong in the run manifest.

## What remains unresolved before a paper claim

1. Recover the exact paper-era commit, ordered per-stratum ID lists, raw per-instance outputs and strategy configurations; confirm that the public 1,194 rows are precisely the scored rows.
2. Obtain the actual no-memory implementation and explain the passthrough discrepancy; confirm benchmark answerer identity and SimpleMem's historical storage model.
3. Recover provider region, inference-profile identifiers, model/access dates, prompts, package/embedding revisions, seeds, repeat counts, error/retry policy and cost accounting. Current defaults are not proof of historical settings.
4. With an authorized working backend, run a one- or two-instance smoke, inspect the actual requests, answers and judges, then a small preregistered pilot. Estimate full cost from measured token usage; do not extrapolate from an unexecuted command.
5. Freeze the reproduction configuration before scaling to the published strata and grid. Compare paired instance-level deltas, uncertainty and missingness; predefine a practical tolerance rather than accepting any matching rank.

## Modest extensions after reproduction is frozen

These are proposed analyses, not results: repeat the fixed grid over model sampling runs; bootstrap paired A-Mem-minus-baseline deltas by stratum; check instance-order/distractor-order sensitivity; and compare matched ingestion/retrieval budgets. Restrict the initial extension to one or two such axes. A high point estimate alone does not establish a statistically resolved ranking; paired outputs are needed. Treat a changed backend or prompt as a robustness experiment, not an exact rerun.
