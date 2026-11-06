# FRQ-001 — Independent MemGym-DR reproducibility study

Can an independent researcher reproduce the published long-horizon memory comparison using the authors' released artifacts?

**The three-case Sonnet 4.6 engineering smoke is complete.** The fixed BM25 cases scored 1.0 (3-hop), 0.3 (4-hop), and 0.7 (5/6-hop). The published MemGym comparison still needs a matched evaluation. [Verified smoke report](report/sonnet46-completed-smoke-2026-11-06.md)

## The verified target

The published [MemGym paper, arXiv:2605.20833v1](https://arxiv.org/abs/2605.20833v1) reports MEMGYM-DR in **Figure 3(b)**. Appendix C.6 Table 8 supplies additional results and intervals. The upstream documentation's “Figure 2b” label disagrees with the published numbering.

The reported evaluation uses **161 three-hop, 916 four-hop, and 117 five/six-hop cases**, and seven methods: None, Naive RAG, BM25, A-Mem, LightMem, SimpleMem, and MemoryBank. Structured summary is excluded from the main comparison because the authors identified contamination. The example script's first 50 rows and default method list are a pilot configuration, not the full published protocol.

The pinned code also differs from the paper's description: `ir_passthrough` retains all observations, MemoryBank cannot be selected through the shared evaluator, and SimpleMem defaults to GPT-4o-mini. Read the [protocol audit](experiments/protocol-audit.md) before any paid run. Passing installation tests does not resolve these mismatches.

## Run the free checks

Use Python 3.12 in a dedicated environment. Downloads use network access; the validation and offline smoke never invoke an LLM. Keep the upstream checkout outside this repository.

```bash
git clone https://github.com/WujiangXu/MemGym.git ../MemGym
git -C ../MemGym checkout --detach 50b404e6ae4e1fcd453d3e07963eb3e6312cbded
python3.12 -m venv ../memgym-venv
../memgym-venv/bin/python -m pip install --upgrade pip
../memgym-venv/bin/python -m pip install -e '../MemGym[dev,eval,swe,memory-eval]'
```

See [scripts/README.md](scripts/README.md) for evidence-capturing commands, immutable dataset download, guarded synthetic dry run, and offline replay of released instances. The observed environment and dependency snapshot are preserved with each run; upstream dependency ranges alone are not a lock.

## Evidence and protocol

- [Execution report](report/validation-2026-10-25.md): what ran, failures, limitations, and next actions.
- [Completed scored smoke](report/sonnet46-completed-smoke-2026-11-06.md) with all three scores, the failure diagnosis, and cumulative budget accounting.
- [Reproduction protocol](REPRODUCTION.md): decision gates, failure accounting, analysis, and extensions.
- [Upstream provenance](UPSTREAM.md): pinned source, paper, and data.
- [Configuration](configs/reproduction.yaml): machine-readable target and unresolved differences.
- `results/raw/` contains commands, logs, environment snapshots, manifests, offline checks, and both stages of the scored smoke.

Never commit credentials. Raw outputs must not be manually edited. Downloaded dataset payloads stay outside version control; retain immutable revision, ordered instance IDs, and SHA-256 manifests.

## Three-case scored smoke

The prepare-only planner freezes the first released row from each hop stratum
and captures its exact BM25 answer prompt through the unchanged upstream
evaluator. It stops before the model boundary and preserves the judge template
and fixed inputs separately. The November 2 execution scored two cases and
stopped at the third answer. The November 6 continuation used the original
5/6-hop prompt and a 4,096-token answer cap to complete that case.
[Planner instructions](scripts/README.md#prepare-the-next-scored-smoke-test)

The historical Sonnet 4.5 model is now
[Legacy on AWS Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle-legacy.html)
(checked November 1, 2026). New Bedrock customers cannot use Legacy models.
Verify account access and approve a spending ceiling before live execution.
The planner does not substitute a model or enable paid execution.

A separate [strict smoke runner](scripts/README.md#initial-direct-anthropic-smoke-runner)
now supports that same dated model through Anthropic directly. The initial test
has a user-approved USD 5 ceiling, at most six physical requests, and a single-use
authorization ledger. Sonnet 4.5 returned HTTP 404, and the user approved the
available Sonnet 4.6 replacement within the same total budget. Anthropic’s
reported historical usage and the retry together imply USD 0.496974 in usage.
The cumulative budget hold finished at USD 1.120406, including a conservative
hold for the initial 404. [Run and cost evidence](report/sonnet46-completed-smoke-2026-11-06.md)

## Completion standard

The published comparison requires resolution of the protocol gaps and a complete matched evaluation. Compare continuous judge scores and uncertainty against the paper, keeping infrastructure errors separate from task failures. Freeze the baseline before extensions.

The first extensions are repeated executions of the fixed dataset and a predeclared stratified sampling sensitivity analysis. All 1,194 cases already belong to the paper target; a full-dataset run is not a new extension. New memory architectures and cross-model generalization are outside this initial scope.
