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


## 2026-11-13: bounded hypothetical taker-cost scenario

Before: L2 replay reconstructed price levels, but no independent, explicit model could calculate the quote-currency cost of consuming a declared quantity. A top-of-book-only calculation would understate cost when requested quantity spans multiple price levels.

After: `execution_scenario.py` sweeps frozen visible levels with Decimal arithmetic and applies separately declared fee and extra-slippage basis points. It fails closed when depth is insufficient, input is invalid, or the book needs a resnapshot. It returns `HYPOTHETICAL_ONLY`, never a simulated observed fill or PnL. No queue position, latency, impact or real liquidity availability is inferred. The method does not modify the book.

Acceptance: fixed two-level fixture: buy 3 units costs gross 304 quote, fee 0.304 at 10 bps, extra slippage 0.152 at 5 bps, effective 304.456; sell 3 gross 296 and effective 295.704 at 10 bps. Rejection of insufficient depth, invalid costs and continuity-lost book is required. No speed improvement is claimed, so the L2 performance benchmark is not an adoption criterion. Baseline: e7feda0cf0c73ce3ad007e8dee6261dcb870d992. Source: self-contained accounting identity; no market dataset or rights assumption.

## 2026-11-13 01:14 JST: time-bounded hypothetical arrival-depth scenario

Before: `hypothetical_taker` evaluated one frozen book and had no way to distinguish depth visible at submission from depth at a declared later arrival. Using later depth at submission would introduce look-ahead bias.

After: `hypothetical_delayed_taker` accepts a provenance manifest, snapshot, complete ordered diff events carrying explicit `exchange_ts_ns`, snapshot time, submit time, and nonnegative assumed delay. It prechecks timestamp monotonicity and refuses arrival beyond the last frozen event. It validates the complete feed via `ProvenanceReplay`, then computes two independent hypothetical taker costs at submission and arrival using only events whose timestamps are <= the relevant boundary. No future event may influence the earlier cost. Delay is a scenario assumption, not a measured network statistic; L2 depth does not establish queue or fill probability.

Acceptance contract: on a synthetic snapshot with ask 101, an update at t=110 changing ask to 102 and a later update at t=130 changing ask to 103, submit t=100 and delay=10 gives 101 before and 102 after, while delay=0 gives no change. Reject out-of-coverage arrival and nonmonotonic timestamps. Baseline/rollback: `43bc86c6f3dbd0c192ef0b4d98dabe88a7905d03`. Source: explicit time-causal accounting on local synthetic fixtures. Exact repository tests and performance effects are UNVERIFIED until execution; no OOS or PnL claim.

## 2026-11-13: reject pre-snapshot depth timestamps in delayed cost scenarios

Before: the delayed-taker replay accepted a frozen depth update timestamped earlier than (or equal to) the declared snapshot clock, even though the snapshot already represents the book at that time. This permits reapplying a historical update to a later book, producing a causally inconsistent hypothetical quote without a sequence-ID gap.

After: require every event timestamp to be **strictly later** than the declared snapshot timestamp, in addition to monotonic ordering, and fail before creating a replay. The comparison model now rejects time windows that cannot be causally aligned. This is a conservative fixture contract, not a claim that all exchange snapshot timestamp semantics are equivalent. If a real source lacks a trustworthy snapshot clock, this delayed scenario remains UNVERIFIED; do not invent one.

Acceptance: existing delayed-taker contract tests plus a focused rejection test for events before/at snapshot time. No speedup or trading-PnL claim. Revert to prior master `8a6b5c2365990bf68632d3187996de56bbf71054` if integration fails. Source of timestamp discipline: Binance Spot official depth synchronization documentation https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md (rechecked against prior ledger 2026-11-13). This timestamp rule is a local model assumption, not asserted as an exchange requirement.

## 2026-11-13 03:14 JST: explicit hypothetical cancel-in-flight state

Before: delayed taker cost scenarios exist, but there is no distinct cancellation request versus effective cancellation state. Assuming cancellation is immediate would hide the interval of exposure between request and modeled effective time.

After: `order_lifecycle.py` models submit, acceptance, cancel request, cancellation effective and observation timestamps using caller-declared integer UTC nanoseconds and nonnegative delays. It distinguishes pending acceptance, live-unfilled assumption, and cancelled-unfilled assumption. It never infers a fill from a book quote; fills and queue position remain NOT_MODELED. Cancel effective before acceptance is rejected as ambiguous rather than inventing venue behavior. This is a standalone deterministic scenario, not a market-data claim. Acceptance: exact boundary transitions and impossible timelines verified in two focused contracts; no performance gain or PnL claimed. Rollback parent: `706fd818c6fa34891b507b37ae70c0ca498b6031`.

## 2026-11-13 04:14 JST: finite-grid cancel-delay sensitivity

Before: a single assumed cancellation delay produced one hypothetical order state; the model could not show how a declared jitter range changes the interval in which a live order remains exposed.

After: `hypothetical_cancel_delay_sensitivity` evaluates an explicitly supplied, bounded (1..256) finite grid of assumed cancellation delays using the existing state-transition contract. It reports each state, earliest/latest effective cancellation and minimum/maximum modeled live exposure. The entire comparison rejects invalid or ambiguous members, rather than silently discarding unfavorable scenarios. No probability distribution, queue position or fills are inferred. This is a small addition to the existing module, not a new execution engine.

Synthetic acceptance fixture: submit 100 ns, accept delay 10 ns, cancel request 120 ns, observation 145 ns, cancel delays [0,20,40] ns. States are [cancelled, cancelled, live]; exposure bounds [10,50] ns. Reject empty/duplicate/negative/bool/oversized grids. One isolated reconstructed-module contract test and syntax compilation passed; **exact GitHub code integration remains UNVERIFIED** due to local GitHub DNS failure. No benchmark or market profitability claim; this is a new sensitivity capability, not a runtime optimization. Rollback parent: `65ce878594b3e3a609a0fd293e55441c8006a47f`.


## 2026-11-13 05:14 JST: worst-case cancellation exposure stop gate

Before: cancellation-delay sensitivity returned an exposure interval but offered no deterministic stop decision. After: `hypothetical_cancel_risk_gate` evaluates the existing full grid, returns STOP if its maximum modeled live exposure exceeds an explicit nanosecond cap **or** any scenario remains live at observation. Otherwise ALLOW. A tie at the cap is allowed only if all scenarios are cancelled. Invalid grid or cap fails closed. This is an offline scenario gate, never a live order/cancel action. It does not model fills, queue or probability.

Acceptance fixture: submit 100, accept 110, cancel request 120, observation 145 ns. Grid [0,20] with cap 30 -> ALLOW; grid [0,20,40] -> STOP with both exposure and still-live reasons. Existing lifecycle semantics must remain unchanged. No L2 performance claim or market result. Baseline/rollback: `a1986b30ed62c10305e06115b7be0abd14c70ded`. Exact repository execution remains UNVERIFIED if not run.

## 2026-11-13 06:14 JST: fail-closed pending acceptance in cancel risk gate

Before: the gate returned ALLOW when observation preceded order acceptance, provided the modeled future exposure stayed within the cap. This incorrectly treated an unresolved pending order as safe. After: any PENDING_ACCEPT scenario returns STOP with ACCEPTANCE_PENDING_AT_OBSERVATION; existing live/exposure rules remain. Acceptance: synthetic submit=100, acceptance=150, observation=120, cancel request=150, delays [0,10], cap=100 must STOP. This is a correctness change only, no runtime or market-performance claim. Rollback parent: 44d5c35a2624067e34b066a9eac117ca35fcef38. Exact repository test execution: UNVERIFIED until run.
