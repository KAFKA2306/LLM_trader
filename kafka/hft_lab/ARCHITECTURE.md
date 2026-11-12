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

## 2026-11-12 20:14 JST: frozen replay provenance boundary

Before: `DiffDepthBook` validated update continuity but did not bind the snapshot and diff sequence to a declared venue/symbol or frozen input. A caller could accidentally mix feeds or modify the input between construction and replay.

After: `replay_provenance.py` adds a minimal offline `ProvenanceReplay` wrapper. It requires a schema version, exact venue/symbol/source labels and SHA-256 of snapshot and ordered events. It checks each event's venue/symbol and rechecks event-list integrity before each state transition. Mismatches fail before mutating the book. This is a *declared* provenance contract, not cryptographic authenticity, vendor equivalence or permission verification. For large real feeds, an immutable streaming manifest/verified chunk design will be required rather than hashing the whole event list per step.

Acceptance: three fixture tests for frozen replay, mixed symbol, snapshot mismatch and post-validation mutation; existing book contracts remain required. No claim of real exchange data, speedup or trading returns. Rollback parent: `3b61116444ef7f1e0716d24b97cb65940f52feeb`.

## 2026-11-12 21:17 JST: one-time provenance verification and owned replay inputs

Before: `ProvenanceReplay.step()` serialized and SHA-256-hashed the entire event list on **every event**, making a replay of N events quadratic in the number of events, while keeping mutable caller-owned input references. A mutation was detected only at the next step.

After: verify the manifest's snapshot and ordered event hashes once at construction, deep-copy both validated inputs, and replay only the private copy. Caller mutations cannot alter the running replay. Each step still checks venue/symbol and the underlying book's sequence/crossing rules. This reduces repeated input-hash work from O(N²) to O(N) for a fixed-size event schema, at the cost of O(N) additional owned-event memory. The manifest remains a caller declaration, not authenticity evidence. Direct modification of private Python attributes is outside the contract.

Acceptance: a changed manifest input is rejected; nested caller mutations after initialization cannot alter replay results; existing book continuity guards remain. Focused reconstructed-contract test (3 cases) and syntax check passed locally, but the exact repository modules and full suite could not be run in the local environment because repository network clone was unavailable. Runtime speedup is **UNVERIFIED**, not claimed. Baseline: `12e324e1ffb0e6eb79d4ef0d010fd2cabfb5c659`. Next design step: bounded streaming chunks if large public feed access is independently established; avoid another full-list scan per event.

## 2026-11-12 22:18 JST: reject mixed feeds before partial replay

Before: a frozen event list was hashed once, but the venue/symbol contract was checked only as each event was applied. A mixed-symbol event late in the list could leave a partially advanced, externally readable book after a caller caught the exception. This is a correctness boundary, not a speed optimization.

After: `ProvenanceReplay.__init__` validates the identity and mapping type of **every** event before constructing a replayable book. A late mixed-symbol event rejects the entire input upfront. Per-step checks remain defensive. The preflight adds one O(N) scan but no per-step rehash; it does not assert cryptographic authenticity, full feed validity or actual exchange semantics.

Acceptance: late mixed-symbol fixture rejects during construction; valid fixture and post-construction caller mutation remain supported. Isolated contract reproduction: 4 tests and syntax compilation passed with a simplified local `DiffDepthBook` stub; **full repository tests and exact GitHub module integration are UNVERIFIED** because the container could not reach GitHub. No benchmark speedup claim. Rollback parent: `184d3519ccda0720edf87c5b4139cc3208cf6659`.

## 2026-11-12 23:17 JST: complete sequence preflight before replay

Before: manifest hashes and venue/symbol were checked before construction, but a late update-ID gap or crossed book was discovered only during replay. Catching the error could leave earlier events visible as a partial replay. After: construct a disposable `DiffDepthBook` over the frozen input and validate the entire sequence before publishing the actual replay book. Reject late gaps and crossed updates with the failing event index. This deliberately trades an additional O(N) pass and temporary book for all-or-nothing input acceptance; it is not a speed optimization. No new infrastructure or market data is needed.

Acceptance: reconstructed local book/provenance contracts passed 3 focused tests (valid, late gap, late crossed), and Python compilation passed. Exact repository module integration and complete regression suite remain UNVERIFIED because container GitHub clone was unavailable. No HFT speed or PnL claim. Rollback parent: `63196134912e88f880c1325cb3103a6565504a83`.
