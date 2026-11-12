# HFT research architecture (2026-11-12)

## Verified capability vs planned capability

| Layer | Current capability | Evidence limit |
| --- | --- | --- |
| Event identity/time | Explicit ms/us/ns normalization, trade vs aggTrade namespaces | CODE_VERIFIED fixtures; not exchange-equivalence proof |
| Feed delay | Offline historical/live matching utility, parked | Requires excluded private receive logs; not a live metric |
| L2 book | `book_replay.py`: snapshot + ordered Binance Spot diff-depth U/u updates; Decimal levels; reject gaps/crossed book | CODE_VERIFIED fixtures only; no historical L2 dataset or real queue |
| Orders/fills/fees | Not implemented | Do not infer fills, queue position, slippage or PnL |
| OOS/strategy | Not implemented | No market profitability claims |

## This run: architecture change

Before: timestamp normalization existed, but no independently testable state transition from a snapshot and diff-depth events. Treating unordered/gapped depth updates as a valid order book would silently corrupt all downstream simulated execution.

After: a deterministic **fail-closed L2 state machine** in `book_replay.py`. The caller supplies a verified snapshot and buffered, chronological diff events. Pre-snapshot stale events are discarded; the first applicable update must bridge `lastUpdateId + 1`; subsequent updates must also cover the next ID. Duplicate/out-of-order, missing ranges, invalid quantities, and locked/crossed states reject without changing committed state. A rejected gap requires a new snapshot rather than silent continuation. This is deliberately a research-only simplified Binance Spot continuity contract; feed-version-specific semantics must be rechecked before using a new source.

Expected testable effect: identical fixtures reconstruct identical best bid/ask; malformed/gapped updates never silently advance the book. Acceptance: three focused contract tests pass; no real trading inference.

Official reference (reviewed 2026-11-12): https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md (How to manage a local order book correctly).

Next independent design increment: explicit replay event provenance/sequence manifest and snapshot-to-diff input validation, then bounded, clearly assumed order/fee scenarios. No live trading, private feed, paid API, or claim of observed performance.
