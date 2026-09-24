# AGENTS.md — Order Governance Pipeline

Scope: `src/trading/guards/`. Root [`AGENTS.md`](../../../AGENTS.md) stays canonical for system-wide policy; this file adds package-specific detail and never overrides it.

## Trading Guards

### 🛡️ Order Governance Pipeline

> **Module path:** `src/trading/guards/`
> **Type:** Pre-execution guard chain for trading signal validation

---

#### Agent Persona & Role

The Governance Pipeline is the **last line of defense before any order signal reaches the simulated market.** It enforces declarative, configurable rules that every trading signal must pass before execution: symbol whitelist checks and position size limits.

The pipeline follows the **Chain of Responsibility pattern** — guards run sequentially and fail fast. If any guard fails, the order is blocked and an audit rejection is recorded.

---

#### Pipeline Architecture

```
TradingStrategy → GuardPipeline.evaluate(intent, capital, config)
    ├── ConfiguredSymbolGuard     (whitelist check)
    └── MaxPositionSizeGuard       (explicit requested size cap)
         ↓
    Result: pass → TradingStrategy proceeds
            fail → audit rejection recorded
```

##### GuardPipeline (`pipeline.py`)
- Runs guards in order and stops at the first failure
- Returns `list[GuardResult]` for the guards that were evaluated
- All guards must pass for order execution
- First failure short-circuits remaining guards (fail-fast)

---

#### Guard: ConfiguredSymbolGuard (`configured_symbol.py`)

**Purpose:** Ensures the trading signal targets a configured symbol.

**Logic:**
- Signal must reference `config.CRYPTO_PAIR`
- Prevents phantom pairs or misconfigured symbols

**Edge Cases:**
- Unknown symbol → blocked with reason "does not match configured trading pair"

---

#### Guard: MaxPositionSizeGuard (`max_position_size.py`)

**Purpose:** Rejects an explicitly requested position size that exceeds the configured cap.

**Logic:**
- Reads `MAX_POSITION_SIZE` from config and validates it is positive and finite
- If AI provides a positive finite `position_size`, it must be ≤ `MAX_POSITION_SIZE` (default 10%)
- Missing, non-finite, or non-positive requested sizes pass through so `RiskManager` can apply fallback sizing

**Edge Cases:**
- Missing `position_size` → passes with reason that RiskManager fallback sizing will apply
- Non-finite requested size → passes with reason that RiskManager fallback sizing will apply
- Invalid `MAX_POSITION_SIZE` config → fails closed

---

#### Friction Recording

Risk and strategy-level blocked trade feedback is recorded through vector memory:

```
VectorMemoryService.store_blocked_trade(...)
```

This is currently used for RiskManager frictions, R:R minimum blocks, and premature SL-tightening blocks. Guard-pipeline failures are audit-recorded before risk calculation and do not call vector memory directly.

Stored blocked-trade feedback feeds the Brain Agent's `get_context()` which shows the LLM:
- Recent blocked trades (last 5, max 168h old)
- Guard type + reason for each block
- Enables the LLM to understand why previous similar signals were rejected

---

#### Configuration

All guard parameters are set in `config/config.ini`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_position_size` | 0.10 (10%) | Maximum explicit/requested position size; RiskManager also clamps fallback sizing to this cap |
| `timeframe` | 4h | Analysis and exit-check timeframe |
| `crypto_pair` | BTC/USDC | Single configured trading pair |

Guards are **declarative** — they can be reviewed and modified without reading any code paths.
