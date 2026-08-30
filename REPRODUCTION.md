# Reproduction Protocol

## 1. Claim to reproduce

Reproduce the MEMGYM-DR long-horizon memory comparison reported by Xu et al. in *MemGym: a Long-Horizon Memory Environment for LLM Agents*, focusing on how memory strategy performance changes with increasing multi-hop / trajectory depth.

## 2. Before running anything

Record the following before the first experiment:

- Upstream repository commit SHA
- Paper version / arXiv version
- Dataset revision or generation seed
- Python version
- OS / hardware
- Model provider and exact model identifier
- API date/version where applicable
- Temperature and sampling settings
- Prompt/config hashes
- Memory strategy configuration
- Evaluation metric definitions
- Estimated and actual token/API cost

Do not update the upstream dependency during a reproduction run.

## 3. Experimental matrix

Populate this table only after verifying the exact upstream configuration.

| Dimension | Planned values |
|---|---|
| Track | MEMGYM-DR |
| Horizon / hop bins | Verify against upstream Figure 2b configuration |
| Memory strategies | Verify exact upstream strategy names |
| Agent/model | Pin one exact model/configuration |
| Seeds | >=3 where supported and materially stochastic |
| Metric | Match upstream primary metric exactly |

## 4. Execution rule

All runs must write immutable raw outputs under `results/raw/` using a run identifier containing at least:

`date_model_strategy_horizon_seed`

Never manually edit raw result files.

## 5. Analysis rule

All transformations from raw outputs to tables/figures must be implemented in code under `analysis/` or `scripts/`.

The reproduction report must show:

- upstream reported value / curve
- reproduced value / curve
- absolute difference
- relative difference where meaningful
- uncertainty across seeds
- deviations from the upstream setup

## 6. Reproduction verdict

Use one of these labels:

- **Reproduced** — central qualitative claim and reported effect size are consistent within a predeclared tolerance.
- **Partially reproduced** — qualitative trend holds but effect size/ranking materially differs.
- **Not reproduced** — central trend/ranking fails under the closest feasible configuration.
- **Inconclusive** — implementation, provider drift, missing artifacts, or cost constraints prevent a valid test.

The tolerance must be declared before inspecting final aggregate results.

## 7. Freeze rule

Once the reproduction verdict is written:

1. Commit all code, configs, processed metrics, figures, and report.
2. Record the final commit SHA.
3. Tag/freeze the reproduction baseline.
4. Only then create the extension branch/version.

## 8. Planned post-reproduction extension

Hypothesis:

> Explicit structured persistent-state memory will show a smaller performance decline as task horizon increases than semantic retrieval or summarization memory.

This hypothesis is intentionally out of scope for v1 execution.

