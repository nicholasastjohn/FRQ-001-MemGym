# Sonnet 4.6 three-case engineering smoke

All three frozen BM25 cases have scores. The first two completed on November 2, 2026. The 5/6-hop answer and judgment completed on November 6 with the same frozen row and answer prompt.

| Released stratum | Judge score (0–1) | Answer cap | Scored evidence |
|---|---:|---:|---|
| 3-hop | 1.0 | 1,024 tokens | [Original result](../results/raw/2026-11-02-sonnet46-partial-smoke/3hop/result.json) |
| 4-hop | 0.3 | 1,024 tokens | [Original result](../results/raw/2026-11-02-sonnet46-partial-smoke/4hop/result.json) |
| 5/6-hop | 0.7 | 4,096 tokens | [Retry result](../results/raw/2026-11-06-sonnet46-56hop/56hop/result.json) |

The engineering smoke covers one fixed row per stratum with BM25 and the approved Sonnet 4.6 substitution. The published MemGym comparison requires a separate matched run across its dataset and memory methods.

## Why the original 5/6-hop case failed

The runner rejected the first 5/6-hop answer because generation stopped without `end_turn`. It discarded the original response and exact stop reason. Anthropic’s usage report for November 3 UTC shows 111,391 input and 2,517 output tokens. The four saved responses account for 78,261 input and 1,493 output tokens. The difference is 33,130 input and **exactly 1,024 output tokens**, matching the old answer cap. This strongly suggests truncation. [Original failure](../results/raw/2026-11-02-sonnet46-partial-smoke/56hop/failure.json) · [Usage reconciliation](../results/reconciliation/2026-11-06-sonnet46-console.json) · [Anthropic stop reasons](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons)

The retry raised only the answer cap to 4,096. Its answer ended normally after **1,195 output tokens**. The judge ended normally after 200 output tokens using its 1,024-token cap. The original failed record still carries a missing score. [Retry trace](../results/raw/2026-11-06-sonnet46-56hop/request-trace.jsonl)

## Cost and verification

The Anthropic Console displayed $0.37 in historical organization usage. The observed token counts at standard rates imply $0.371928. The retry added $0.125046 in usage, for a cumulative token-priced estimate of **$0.496974**. The conservative accounting used $0.38 for historical usage and retained the $0.61536 hold for the original Sonnet 4.5 HTTP 404. Including the retry, the peak amount held during either new request was **$4.128035** and the ending amount held was **$1.120406**, within the authorized $5. [Anthropic Sonnet 4.6 pricing](https://platform.claude.com/docs/en/models/sonnet-4-6/overview) · [Retry usage](../results/raw/2026-11-06-sonnet46-56hop/usage.json)

Verification matched all 16 retry artifact hashes and byte counts, the source snapshot to commit `d39b221776bc75491ea7f2d926c506d1ecb9c99a`, the answer prompt byte for byte to the original, and the recorded 0.7 to the raw judge response. The pinned upstream checkout passed the post-run cleanliness check. The 50-test offline suite passed, including the frozen-plan mock evaluator and per-role budget checks. [Retry manifest](../results/raw/2026-11-06-sonnet46-56hop/manifest.json)
