# MemGym initial scored smoke: model unavailable

The initial live smoke stopped on its first answer request. Anthropic returned HTTP 404 for `claude-sonnet-4-5-20250929`. No model response, judgment, case score, or reproduction result was produced.

A separate authenticated, read-only availability check returned HTTP 200 for the account model list, with Sonnet 4.6 and Sonnet 5.5 present. The exact Sonnet 4.5 model metadata endpoint returned HTTP 404. The key therefore authenticates successfully, but the intended model is unavailable to this account.

One generation request was attempted. No token usage or charge was returned. The original ledger conservatively retains USD 0.61536 against the approved USD 5 ceiling; known usage-based cost is USD 0, with billing unconfirmed. This reservation must not be reset or treated as an invoice charge.

All recorded artifact hashes were verified and upstream source remained clean. A different available model could validate the engineering path, but its results must be explicitly labeled as a model deviation and cannot reproduce the original Sonnet 4.5 comparison.
