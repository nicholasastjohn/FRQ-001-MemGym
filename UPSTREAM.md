# Upstream provenance

Verified on 2026-10-25. No tracked upstream source was edited for validation.

| Artifact | Pinned identity |
|---|---|
| Study repository starting commit | `36fefda6a18e4eb3e2a1f7b674a61366cb1f483e` |
| Official code | [WujiangXu/MemGym](https://github.com/WujiangXu/MemGym) |
| Upstream commit tested | [`50b404e6ae4e1fcd453d3e07963eb3e6312cbded`](https://github.com/WujiangXu/MemGym/commit/50b404e6ae4e1fcd453d3e07963eb3e6312cbded) |
| Commit date | 2026-06-01T21:31:47-07:00 |
| Package version | `memgym==0.2.0` |
| Paper | Xu et al., *MemGym: a Long-Horizon Memory Environment for LLM Agents* |
| Paper version | [arXiv:2605.20833v1](https://arxiv.org/abs/2605.20833v1), submitted 2026-05-20 |
| PDF | [Versioned PDF](https://arxiv.org/pdf/2605.20833v1) |
| Retrieved PDF SHA-256 | `b8894814b03fa0c7b6bdce48ecc8575a5226d6d639f5c3cf04ce84085007e2a2` |
| Paper target | Figure 3(b), Appendix C.6 Table 8; upstream docs call it Figure 2b |
| Released dataset | [MemGym/memgym-dr-instances](https://huggingface.co/datasets/MemGym/memgym-dr-instances) |
| Dataset revision and file hashes | Run-specific `dataset_manifest.json` under `results/raw/` |

This audits **currently released artifacts at a pinned June 1 commit**, not an established match to the May 20 paper execution. Repository history does not identify a paper-experiment tag or complete historical execution manifest. The initial public commit is dated May 18; later changes include reproduction fixes. Do not silently substitute the initial commit or future `main`.

The PDF was downloaded for verification, not redistribution. The digest identifies retrieved versioned bytes; arXiv may rebuild PDFs.

## Primary source anchors

- [Track mapping](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/docs/tracks.md#memgym-dr)
- [Testing guide](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/docs/testing.md)
- [Dataset catalog](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/docs/data.md#3-memgym-dr--deep-research-instances)
- [Benchmark runner](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/examples/memgym_dr/run_ir_benchmark.py)
- [Shared evaluator](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/eval/agent.py)
- [LLM client/error handling](https://github.com/WujiangXu/MemGym/blob/50b404e6ae4e1fcd453d3e07963eb3e6312cbded/src/memgym/pipelines/memgym_ir/llm/client.py)

The [audit](experiments/protocol-audit.md) distinguishes paper facts, code facts, and proposed independent study choices. Older scaffold hypotheses are superseded.
