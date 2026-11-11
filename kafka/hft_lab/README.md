# HFT research: latency evidence first

This KAFKA-owned, **research-only** component measures market-data reception delay. It does not start a bot, place orders, retrain a model or assert profitability.

## Input contract

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

The external hourly research automation, not a new GitHub Actions workflow, owns this cadence. Every invocation must (1) read canonical `master` and this ledger, (2) avoid re-running an unchanged experiment, (3) check source data availability and provenance, (4) run a bounded test or evidence audit if inputs permit, (5) save verified new results to `kafka/research/experiments/`, and (6) record exact blockers otherwise. Cross-bot findings may be linked from the central `investor` knowledge base only after independent validation.

Do not enable exchange credentials, live trading, deployment, secret access or an external paid data source from the research loop. Risk controls remain deterministic and independent of the LLM.
