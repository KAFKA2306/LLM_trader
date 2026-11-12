# HFT research: autonomous offline verification

This KAFKA-owned, **research-only** component measures market-data reception delay. It does not start a bot, place orders, retrain a model or assert profitability.

## Current scope: self-contained research (2026-11-12)

The autonomous research loop is **not** a production-HFT project. Its work is restricted to outcomes that the connected agent can complete and verify with repository code, deterministic local tests, and permitted free public market data. A run must select at most one bounded, nonduplicate improvement.

| IN_SCOPE: independently executable | OUT_OF_SCOPE: excluded, not recurring blockers |
| --- | --- |
| Validate market-event identity, schema, timestamp units, duplication and provenance | Acquire private production-host receive logs, exchange order/fill history or VPS access |
| Explicitly convert official historical/live timestamp units into one declared unit; reject ambiguous input | Infer real network jitter or clock error without a measured private host |
| Deterministic offline event/LOB replay and scenarios driven by fixtures or permitted public historical data | Place orders, connect accounts, manage secrets, deploy a trading bot |
| Simulate declared fees, delays, jitter, queue/fill assumptions, slippage and downside; label assumptions and uncertainty | Claim actual account fee tier, fill probability, realized PnL or validated live MM profitability |
| Fix and verify existing KAFKA-owned research code with minimum necessary tests | Buy data, bypass usage restrictions, create new CI pipelines or duplicate ledger entries |

**Evidence labels:** `CODE_VERIFIED` proves software behaviour on fixtures only; `PUBLIC_DATA_VERIFIED` requires source, rights, immutable inputs, dates and reproducible evaluation; `UNVERIFIED` describes unmeasured claims, not a task queue. If no useful independent change remains, return `FIXED_POINT` without a commit.

**Implemented first autonomous target:** `timestamp_normalization.py` explicitly converts `ms/us/ns` to signed-64-bit-safe UTC nanoseconds, requires mapping field names, namespaces `trade` and `aggTrade` IDs and rejects undeclared units. It is a pure offline library; vendor event equivalence and clock accuracy are not implied. Five focused fixture contract tests passed locally on 2026-11-12; this is `CODE_VERIFIED`, not market-performance evidence.

### Legacy live-reception calibration (excluded from the hourly loop)

The existing `latency_calibration.py` remains a research utility. Its private host inputs are **not** required to advance the current self-contained work. The original empirical reception-latency hypothesis is parked as `OUT_OF_SCOPE`; retain its source history, do not repeatedly request these inputs, and do not turn simulated delays into measured values.

## Input contract for the parked calibration utility

Capture overlapping data for the **same venue, symbol, event identity and exchange UTC timestamp**:

- `historical.jsonl`: `{ "venue": "...", "symbol": "...", "event_id": "...", "exchange_ts_ns": 123 }`
- `live.jsonl`: same keys plus `recv_ts_ns` (UTC nanoseconds when the intended bot actually received the event).
- Event IDs must be unambiguous across the two data sources. Different vendor normalization, timestamp resolution or missing IDs require a verified mapping first. Do not infer matches from price alone.
- The operator must measure and supply the worst-case **clock synchronization error**. The script does not measure clock accuracy or separate clock skew from network delay.

Never commit raw licensed market feeds, private fills, credentials or identifying order events. Keep raw input in an access-controlled data lake and record its hashes in the experiment ledger.

## Run

```bash
python kafka/hft_lab/latency_calibration.py \
  --historical /private/overlap/historical.jsonl \
  --live /private/overlap/live.jsonl \
  --clock-error-ms 0.5 > /private/results/latency.json
python -m unittest discover -s kafka/hft_lab -p 'test_*.py'
```

Default minimum evidence: **100 matching events, 95% historical coverage**. Invalid IDs, incompatible exchange timestamps, duplicate events or clock violations produce `UNVERIFIED`, with nonzero exit status. Valid output is only a **calibrated observation** with SHA-256 provenance, p50/p95/p99 delay and jitter.

The calibration is not a backtest. A later, separately verified backtester must simulate actual arrival times, order latency, acknowledgments, queue position, fees, slippage, market impact and partial fills. Freeze train / validation / out-of-sample periods; no strategy is promoted from in-sample PnL or a synthetic fixture.

## Hourly research loop

The external hourly research automation, not a new GitHub Actions workflow, owns this cadence. Every invocation must (1) read canonical `master` and this ledger, (2) avoid duplicate experiments, (3) choose one independently executable code/data/replay verification, (4) run only relevant tests and verify exact output, (5) record reproducible new evidence in the existing `kafka/research/experiments/` ledger, and (6) stop at `FIXED_POINT` when no independent work remains. Do **not** repeat requests for the excluded private live-host inputs. Cross-bot findings may be linked from the central `investor` knowledge base only after independent validation.

Do not enable exchange credentials, live trading, deployment, secret access or an external paid data source from the research loop. Risk controls remain deterministic and independent of the LLM.
