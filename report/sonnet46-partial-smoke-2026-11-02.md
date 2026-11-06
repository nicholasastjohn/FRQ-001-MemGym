# Sonnet 4.6 partial engineering smoke

Run: November 2, 2026. Evidence verified: November 6, 2026.

Two selected BM25 cases completed with model answers and judgments. The third failed before its answer could be accepted. **The three-case smoke and the paper reproduction are incomplete.**

| Released stratum | Status | Judge score (0–1) |
|---|---|---:|
| 3-hop | Scored | 1.0 |
| 4-hop | Scored | 0.3 |
| 5/6-hop | Failed: `incomplete_or_refused_response` | Missing |

The final failure remains a missing score; it is not assigned zero. These are one fixed first row per stratum, BM25 only, using the explicitly approved Sonnet 4.6 replacement for unavailable Sonnet 4.5. They do not estimate benchmark accuracy or establish a memory-method comparison.

## Execution and recovery

There were six physical generation attempts across the approved work: one unavailable Sonnet 4.5 request, one Sonnet 4.6 answer initially rejected by the local JSON parser, and four Sonnet 4.6 continuation requests. The saved complete first answer was revalidated offline and replayed verbatim without generating it twice. The continuation completed the first judgment, second answer and second judgment, then stopped on the third answer. No third judgment was requested.

The final response's content, response ID, usage and exact stop reason were discarded by the runner before logging. The error therefore cannot distinguish truncation, refusal or another non-complete stop, and the answer cannot be recovered from these files. The November 6 diagnostic fix preserves selected rejected-response fields for future runs, redacts exact API-key values, and keeps rejection and full budget holds unchanged. It cannot restore the missing historical response.

## Budget accounting

Captured usage implies **USD 0.257178** for four saved Sonnet 4.6 responses. This is a usage-based estimate, not an invoice or the complete cost of all attempts. The original HTTP 404 request retains USD 0.61536, and the final rejected response retains USD 3.01536 because its usage is unknown. Total conservative budget held is **USD 3.887898 of USD 5**; this is not a confirmed charge.

Another full-context request would require USD 3.01536 and does not fit the remaining USD 1.112102 under the existing guard. No additional paid calls were made during the November 6 verification. Completion requires resolving the failed request's billing/evidence or a separately reviewed continuation that fits the remaining approval. The original holds must remain intact.

## Evidence verification

All 20 manifest artifact hashes and byte counts match. Exact answer prompts and dataset row identities match the frozen plan; the two scores match saved judge outputs; source snapshots match run commit `9b151820bf53ba1cb56d71fc7d401278e0fd8bd9`. The run recorded an unchanged pinned upstream checkout.

The [raw evidence](../results/raw/2026-11-02-sonnet46-partial-smoke) is copied byte for byte from the original output directory, including the original failed manifest and historical source. The [derived summary](../analysis/sonnet46-smoke-2026-11-02/verified-summary.json) records the independent verification. Original failure artifacts and ledgers were not edited.

All 47 post-run offline checks passed across the complete suite and a configured rerun of the runner integration tests. This includes the frozen-plan evaluator check with mock transport and truncation/refusal fixtures confirming no acceptance, settlement or retry, plus exact-key redaction. Both validation logs are preserved with the derived analysis.
