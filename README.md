# FRQ-001-MemGym

**Frontier Result Quarterly #001 — Reproducing Long-Horizon Agent Memory in MemGym**

Status: **v1 reproduction scaffold — no experimental results have been generated yet.**

## Objective

Independently reproduce the MemGym deep-research (MEMGYM-DR) long-horizon memory result associated with Figure 2b of the MemGym paper, then freeze the reproduction before proposing or implementing any extension.

Primary question:

> As research trajectories become longer and require more intermediate information, do explicit memory mechanisms reproduce the reported advantage over simple context/passthrough baselines?

## Upstream work

- Paper: *MemGym: a Long-Horizon Memory Environment for LLM Agents* (Xu et al., 2026)
- arXiv: https://arxiv.org/abs/2605.20833
- Upstream code: https://github.com/WujiangXu/MemGym

## Reproduction target

The initial target is MEMGYM-DR across increasing reasoning depth / trajectory horizon, with a fixed agent/model configuration and multiple memory strategies. At minimum:

- passthrough / no dedicated memory baseline
- BM25 retrieval
- naive RAG
- summarization
- one stronger memory architecture if supported by the upstream release

The exact strategy names, model, prompts, dataset revision, seeds, and evaluation commands will be copied from a pinned upstream commit before execution. Nothing in this repository should silently substitute a different configuration.

## Reproduction standard

A result counts as reproduced only if:

1. The upstream commit and dataset revision are pinned.
2. The environment is reconstructible.
3. The exact experimental commands are recorded.
4. Raw outputs are retained unchanged.
5. Processing from raw outputs to reported metrics is scripted.
6. The comparison to the paper distinguishes exact reproduction from unavoidable deviations.
7. Multiple seeds are used where stochasticity materially affects the reported result.
8. Cost, model/API version, date, and relevant provider settings are recorded.

## Repository layout

```text
FRQ-001-MemGym/
├── README.md
├── REPRODUCTION.md
├── UPSTREAM.md
├── requirements.txt
├── configs/
├── experiments/
├── results/
│   ├── raw/
│   └── processed/
├── figures/
├── analysis/
├── scripts/
└── report/
```

## Version boundary

`v1` is reproduction-only. No persistent-state-memory extension belongs in the reproduction baseline.

After the reproduction is complete and frozen, the planned extension is to test whether **structured persistent state memory** degrades more slowly than retrieval/summarization baselines as task horizon increases. That extension must begin from a later version/branch so it cannot contaminate the baseline.

