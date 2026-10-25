# Reproduction protocol

Revision: 2026-10-25, before collection of empirical task scores. This independent study is adjacent to Persistent Agency; that architecture and new memory methods are outside its scientific claim.

## 1. Target

Reproduce **arXiv:2605.20833v1 Figure 3(b)**, with additional numerical evidence in Appendix C.6 Table 8. Upstream calls this Figure 2b. The strata contain 161 / 916 / 117 cases (3 / 4 / 5–6 hops); seven uncontaminated methods are reported. See [the source audit](experiments/protocol-audit.md) for means, available confidence intervals, model roles, and code discrepancies.

Primary estimand: mean per-instance task score within each hop stratum, matching the paper's grading rule. Secondary diagnostics: note-fact recall, infrastructure errors, tokens, latency and billed cost. Compare methods on identical row keys: dataset file SHA-256, zero-based row position and exact raw-line SHA-256. Released 4-hop instance IDs collide, so never join or deduplicate by instance_id alone. Hop strata also change content and trajectory characteristics; differences do not isolate a causal effect of horizon.

## 2. Execution tiers

1. **Free validation:** clean environment, documented install, imports, release unit suite, full unit suite, CLI help and registry. Preserve command logs, dependency versions, errors and source status.
2. **Free structural smoke:** synthetic v2 `--dry-run` plus offline replay of pinned released instances through schema, eviction and memory adapters. No model answers, judging or continuous judge score. The paper says legacy v2 generation was unused for reported results.
3. **Backend smoke:** once backend access and spending scope are established, use one released case, BM25, one worker and matched answer/judge models. Retain responses, prompts, notes, transport status and usage. An API failure blocks the smoke; it is not a zero-accuracy result.
4. **Artifact pilot:** optional first-N run of the current example script, explicitly labeled with its deviations.
5. **Paper reproduction:** after resolving the gates below, all 1,194 cases × seven matched methods, analysis, verdict and baseline freeze.

## 3. Gates before a paid paper comparison

- **Control semantics:** current `ir_passthrough` retains all observations. The paper's control has no retained notes. Resolve this rather than labeling full context “no memory.”
- **MemoryBank:** registered but rejected by current `_get_ir_manager`. Resolve routing in a versioned study adapter or obtain the historical runner.
- **Backend configuration:** `--summarization-model` does not reach every strategy; SimpleMem defaults to GPT-4o-mini. Match backend-specific models and exclude contaminated structured summary.
- **Answer versus judge:** the current runner uses Sonnet for both. Distinguish this from Haiku's worker/memory role in the paper. Verify historical assignments, temperatures, token caps, embeddings, retrieval/ingest settings and truncation.
- **Historical case identity:** verify public files and ordered IDs match the published experiment; equal counts alone cannot establish this.
- **Backend and budget:** establish access, region, model IDs, spend ceiling and usage accounting. No silent provider substitution.
- **Failure transparency:** collect transport evidence outside the untouched upstream checkout. The client can turn failed API calls into `{}`; the runner can turn exceptions into zero scores and still exit successfully. An `error` field alone cannot certify success.

Any study adapter must be versioned, tested and declared as a deviation, while preserving original behavior for audit. Unknown historical settings remain unknown. Do not claim exact reproduction from defaults.

## 4. Manifest and immutability

Use a new output directory for each run and never edit raw outputs. Retain UTC timestamps; study/upstream commits and clean status; Python, OS, architecture/hardware; installer and dependency snapshot; data revision, URLs, sizes, hashes and ordered IDs; source/config/prompt hashes; method and embedding settings; provider/region/model IDs; temperature, limits, concurrency and retry policy; seeds; commands, stdout/stderr and exit codes; per-instance model outputs and usage.

Hash files at run completion, excluding the checksum manifest itself. An editable-install freeze contains a local path; preserve it as observed evidence, not a portable lock. Keep payloads in an ignored local cache when immutable revisions, IDs and hashes support retrieval.

The upstream benchmark has **no seed argument**, selects a file prefix, and can emit results in completion order. Start with one worker. Record Python, NumPy and PYTHONHASHSEED values as study choices (validation seed 42), not paper-recovered seeds. Temperature zero does not guarantee deterministic remote responses. Repeated execution IDs are not independently controlled model seeds unless supported by the provider.

## 5. Failure and cost accounting

Retain literal upstream aggregates, then independently report `n_expected`, `n_attempted`, `n_succeeded`, `n_failed`, `n_missing` and error types. Show all-attempt and success-only summaries with their denominators. Hidden or unclassified API failures make a comparison inconclusive until reconciled.

Before execution, freeze bounded retries and handling of unrecoverable cases. Record every attempt with its case/method and attempt number. Reconcile swallowed `{}` against transport records. Exit code zero and score zero are not evidence of successful inference.

Measure input/output/cache tokens and dollars for **all** calls, including memory ingestion and judging. A-Mem, LightMem and SimpleMem may call an LLM across multiple turns, so final answer/judge calls alone underestimate cost. This validation makes zero LLM API calls and incurs zero LLM API charges; no invented dollar amount is assigned to local compute or downloads.

## 6. Analysis rules declared before scores exist

Report published mean/available 95% interval, reproduced mean, absolute difference and uncertainty per method/stratum. Reconstruct the paper's stated `1.96 × SE` intervals for direct comparison. Also use paired case bootstrap intervals for method differences (10,000 resamples, analysis seed 20261025), resampling cases jointly across methods within each stratum. Overlap of marginal intervals alone does not settle pairwise significance.

Proposed equivalence margin: **±0.05 absolute task score per cell**. Require a 90% interval for reproduced-minus-published difference to lie within that margin. This is an independent study choice, not the authors' criterion. Published per-instance outputs/covariances are unavailable; use reported SE where available, declare the independent-estimates approximation, and treat missing uncertainty or boundary cases as inconclusive. A nearby point estimate alone is insufficient. Report all 21 cells; predeclare multiplicity handling before any global equivalence claim. Unadjusted cellwise intervals do not establish that all cells reproduced.

Report qualitative trend agreement separately from equivalence, with ties and uncertainty. Do not assume that A-Mem versus MemoryBank at high depth is significantly different. Verdicts are **reproduced**, **partially reproduced**, **not reproduced**, or **inconclusive**, supported at cell level and qualified by configuration fidelity. No results or unresolved fidelity implies inconclusive, not not reproduced.

## 7. Freeze and modest extensions

Commit inputs, evidence, analysis, figures and report; tag a completed baseline only after an actual verdict. Environment validation earns no completed-reproduction tag.

Then run (a) three executions of the fixed full protocol for run-to-run variation and (b) stratified sampling sensitivity comparing a predeclared 50-case pilot to the full target. Preserve paired comparisons; repeated calls are not extra independent dataset cases. All 1,194 cases already belong to the core reproduction. A second reasoner or new architecture requires a separate protocol/version.

A methods brief can precede results. Do not claim reproduction or expansion to authors before authentic tables exist. Collect protocol questions locally for later authorized outreach.
