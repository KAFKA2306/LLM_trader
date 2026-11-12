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

## 2026-11-12: ISUCON-style bare/lite evaluation loop

Source (reviewed 2026-11-12): https://zenn.dev/luvtechno/articles/isucon2026-preparation

Before: the depth replay implementation had fixture correctness tests but no frozen repeated performance-evaluation contract. One fast run could be mistaken for progress.

After: `replay_benchmark.py` is a single-process, dependency-free evaluation harness over a generated fixed L2 case. It records the fixture SHA-256, full final-book-state hash, Python/platform fingerprint, all cold-run timing samples and median. A new book is created for each attempt. `compare` fails closed when input case, runtime fingerprint or final book state differs. Improvements smaller than measured run-to-run spread are `INCONCLUSIVE_WITHIN_VARIATION`; larger differences are only candidates for independent replication, never automatic adoption.

ISUCON lessons applied: (1) freeze the before/after workload, (2) repeat measurements instead of selecting peak scores, (3) validate the evaluator and restart state, (4) prefer bare/lite tools to a heavy agent harness, (5) retain a known-good revision and a concise handoff. The heuristic noise threshold is not statistical confidence; host load may differ even with an identical fingerprint. Synthetic input is only software/performance evidence, not exchange throughput or trading profitability.

Acceptance: three local evaluator contract tests passed and Python compilation passed on 2026-11-12. An unchanged-code before/after comparison with identical fixture produced `INCONCLUSIVE_WITHIN_VARIATION` as expected. Further work should vary replay shapes with frozen, independently checked fixtures before performance tuning.

## 2026-11-12 19:14 JST: irreversible continuity failure

Before: `DiffDepthBook.apply` raised on a missing update ID but left the instance usable. A caller that caught the exception could subsequently apply a later event or read a stale best bid/ask, contradicting the documented resnapshot requirement. This is a correctness failure, not a performance problem.

After: a sequence gap permanently sets `needs_resnapshot` on that instance. All subsequent `apply` and `top` calls reject until the caller constructs a new `DiffDepthBook` from a fresh snapshot. The last committed book state remains internally unchanged, but cannot be presented as current. Invalid decimal/crossed updates remain atomic and may be corrected without poisoning continuity, because the input is rejected before the state advances. This is a fail-closed software contract, not a claim of exchange correctness.

Acceptance: three local focused contract tests passed, including gap -> rejected recovery -> rejected read -> new snapshot success, and `py_compile` passed. No benchmark speedup is claimed; this change intentionally prioritizes safety over runtime. Rollback parent: `88f701c8b42d6e094541280009f8147277c62bc6`.
