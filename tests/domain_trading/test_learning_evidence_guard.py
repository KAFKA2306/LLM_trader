"""Wave-5: a lesson needs PROOF — no evidence, no post-mortem, no brain update.

The 2026-09-21 incident wrote a lesson into the brain from a closure the bot could not
prove (an ``unknown`` booking with a corrupted local size). This suite pins the guard:

* a close whose exit fact is not proven (no evidence, unknown price/amount, a
  non-confirming source, no stable event id) must NOT ask the post-mortem and must NOT
  update the brain — the skip is logged explicitly as "Lesson skipped: no exit evidence";
* a post-mortem that fails (returns None or raises) must NOT produce a brain entry
  either — nothing is written that could pass for an analysis;
* a proven exit + a validated post-mortem teaches the brain exactly ONCE per exit
  event (idempotency), and the CLOSE row carries the FILL amount, not the local size.

Every test uses doubles and temporary paths: no live repo, no exchange, no credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.trading.executor_reconciliation import ExitEvidence
from src.trading.trading_strategy import TradingStrategy
from tests.conftest import (
    make_config,
    make_market_conditions,
    make_position,
    mock_brain,
    mock_persistence,
    mock_statistics,
    null_logger,
)

ENTRY_TIME = datetime(2026, 9, 21, 8, 12, 0, tzinfo=timezone.utc)


def proven_exit(**overrides: Any) -> ExitEvidence:
    """Evidence of a PROVEN exit (real fill price + amount + stable event id)."""
    values: dict[str, Any] = {
        "source": "executor_exit_journal",
        "price": 84500.0,
        "quantity": 0.00554,
        "event_id": "executor_exit_journal#event-1",
        "fee": 0.0,
        "fee_currency": "USDC",
    }
    values.update(overrides)
    return ExitEvidence(**values)


def _position(**overrides: Any):
    values: dict[str, Any] = {
        "symbol": "BTC/USDC",
        "direction": "LONG",
        "entry_price": 81200.45,
        "stop_loss": 78800.0,
        "take_profit": 84500.0,
        "size": 0.00554,
        "entry_time": ENTRY_TIME,
        "conditions_at_entry": make_market_conditions(),
    }
    values.update(overrides)
    return make_position(**values)


def _strategy(
    tmp_path: Path,
    position: Any | None = None,
    *,
    post_mortem_result: Any = "valid",
    entry_decision: bool = True,
    post_mortem_raises: bool = False,
) -> tuple[TradingStrategy, MagicMock, MagicMock, MagicMock]:
    """Real strategy with an isolated intent journal and scripted post-mortem.

    Returns ``(strategy, logger, persistence, post_mortem)``.
    """
    logger = null_logger()
    persistence = mock_persistence()
    persistence.async_save_trade_decision = AsyncMock(return_value=42)
    if entry_decision:
        entry = MagicMock()
        entry.reasoning = "Breakout continuation."
        persistence.get_entry_decision_for_position = MagicMock(return_value=entry)
    else:
        persistence.get_entry_decision_for_position = MagicMock(return_value=None)
    statistics = mock_statistics()
    statistics.get_current_capital.return_value = 10000.0
    brain = mock_brain()
    config = make_config(BOT_INTENT_JOURNAL_PATH=str(tmp_path / "bot_position_intents.jsonl"))
    strategy = TradingStrategy(
        logger=logger,
        persistence=persistence,
        brain_service=brain,
        statistics_service=statistics,
        memory_service=MagicMock(),
        risk_manager=MagicMock(),
        config=config,
        position_extractor=MagicMock(),
    )
    post_mortem = MagicMock()
    if post_mortem_raises:
        post_mortem.analyze_closed_trade = AsyncMock(side_effect=RuntimeError("llm down"))
    elif post_mortem_result == "valid":
        post_mortem.analyze_closed_trade = AsyncMock(return_value=MagicMock())
    else:
        post_mortem.analyze_closed_trade = AsyncMock(return_value=None)
    strategy.post_mortem_service = post_mortem
    if position is not None:
        strategy.current_position = position
    return strategy, logger, persistence, post_mortem


def _logged(logger: MagicMock, phrase: str) -> bool:
    """True when any log call (any level) carried ``phrase``."""
    for level in ("warning", "info", "critical", "error"):
        for call in getattr(logger, level).call_args_list:
            if phrase in str(call.args):
                return True
    return False


class TestNoEvidenceMeansNoLesson:
    """A close whose exit fact is unproven never reaches the post-mortem or the brain."""

    @pytest.mark.parametrize(
        "evidence",
        [
            pytest.param(None, id="no-evidence-at-all"),
            pytest.param(proven_exit(price=None), id="unknown-price"),
            pytest.param(proven_exit(quantity=None), id="unknown-quantity"),
            pytest.param(proven_exit(source="local_monitor"), id="local-monitor-source"),
            pytest.param(proven_exit(source="unknown"), id="unknown-source"),
            pytest.param(proven_exit(event_id=None), id="no-stable-event-id"),
        ],
    )
    async def test_unproven_close_skips_post_mortem_and_brain(self, tmp_path: Path, evidence: Any) -> None:
        position = _position()
        strategy, logger, persistence, post_mortem = _strategy(tmp_path, position)

        await strategy.close_position("stop_loss", 78800.0, make_market_conditions(), evidence=evidence)

        persistence.async_save_trade_decision.assert_awaited_once()
        assert strategy.current_position is None
        post_mortem.analyze_closed_trade.assert_not_awaited()
        strategy.brain_service.update_from_closed_trade.assert_not_called()
        assert _logged(logger, "Lesson skipped: no exit evidence")


class TestFailedPostMortemMeansNoLesson:
    """A post-mortem that did not produce a validated analysis produces no brain entry."""

    @pytest.mark.parametrize(
        ("post_mortem_result", "post_mortem_raises"),
        [
            pytest.param(None, False, id="post-mortem-returned-none"),
            pytest.param("valid", True, id="post-mortem-raised"),
        ],
    )
    async def test_failed_post_mortem_writes_no_lesson(
        self, tmp_path: Path, post_mortem_result: Any, post_mortem_raises: bool
    ) -> None:
        position = _position()
        strategy, logger, _, post_mortem = _strategy(
            tmp_path, position,
            post_mortem_result=post_mortem_result, post_mortem_raises=post_mortem_raises,
        )

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )

        post_mortem.analyze_closed_trade.assert_awaited_once()
        strategy.brain_service.update_from_closed_trade.assert_not_called()
        assert _logged(logger, "no confirmed post-mortem analysis")

    async def test_missing_entry_decision_blocks_the_lesson(self, tmp_path: Path) -> None:
        """Without the entry decision there is nothing to analyse — and nothing to teach."""
        position = _position()
        strategy, logger, _, post_mortem = _strategy(tmp_path, position, entry_decision=False)

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )

        post_mortem.analyze_closed_trade.assert_not_awaited()
        strategy.brain_service.update_from_closed_trade.assert_not_called()
        assert _logged(logger, "no confirmed post-mortem analysis")

    async def test_missing_post_mortem_service_blocks_the_lesson(self, tmp_path: Path) -> None:
        position = _position()
        strategy, logger, _, _ = _strategy(tmp_path, position)
        strategy.post_mortem_service = None

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )

        strategy.brain_service.update_from_closed_trade.assert_not_called()
        assert _logged(logger, "no confirmed post-mortem analysis")


class TestProvenExitTeachesOnce:
    """Evidence + validated post-mortem = exactly one brain entry per exit event."""

    async def test_the_brain_is_updated_with_the_exit_evidence(self, tmp_path: Path) -> None:
        position = _position()
        strategy, _, persistence, post_mortem = _strategy(tmp_path, position)

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )

        post_mortem.analyze_closed_trade.assert_awaited_once()
        brain = strategy.brain_service
        brain.update_from_closed_trade.assert_called_once()
        evidence = brain.update_from_closed_trade.call_args.kwargs["evidence"]
        assert (evidence.price, evidence.quantity) == (84500.0, 0.00554)
        assert evidence.event_id == "executor_exit_journal#event-1"
        assert evidence.source == "executor_exit_journal"
        decision = persistence.async_save_trade_decision.await_args.args[0]
        assert decision.quantity == pytest.approx(0.00554)
        assert decision.fee is None

    async def test_the_same_exit_event_is_taught_only_once(self, tmp_path: Path) -> None:
        """A re-entry of the close path for one exit event must not double-teach."""
        position = _position()
        strategy, logger, _, post_mortem = _strategy(tmp_path, position)

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )
        strategy.current_position = position
        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )

        assert post_mortem.analyze_closed_trade.await_count == 2
        assert strategy.brain_service.update_from_closed_trade.call_count == 1
        assert _logged(logger, "already processed")

    async def test_a_failed_brain_write_may_be_retried(self, tmp_path: Path) -> None:
        """The dedup key is not kept when the lesson did not land (retry still teaches)."""
        position = _position()
        strategy, _, _, _ = _strategy(tmp_path, position)
        brain = strategy.brain_service
        brain.update_from_closed_trade.side_effect = [RuntimeError("brain down"), None]

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )
        strategy.current_position = position
        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )

        assert brain.update_from_closed_trade.call_count == 2


class TestBookedAmountComesFromTheFill:
    """The CLOSE row carries the actual filled amount, never the local size alone."""

    async def test_the_evidence_amount_is_booked_without_an_explicit_quantity(self, tmp_path: Path) -> None:
        position = _position(size=0.045)
        strategy, logger, persistence, _ = _strategy(tmp_path, position)

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            evidence=proven_exit(quantity=0.00554),
        )

        decision = persistence.async_save_trade_decision.await_args.args[0]
        assert decision.quantity == pytest.approx(0.00554)
        assert decision.quantity != pytest.approx(0.045)
        assert "0.00554000" in decision.reasoning and "0.04500000" in decision.reasoning
        assert _logged(logger, "QUANTITY DIVERGENCE")

    async def test_without_any_quantity_the_legacy_local_size_is_kept(self, tmp_path: Path) -> None:
        """Backward compatibility: no evidence fields at all behaves exactly as before."""
        position = _position()
        strategy, _, persistence, post_mortem = _strategy(tmp_path, position)

        await strategy.close_position("take_profit", 84500.0, make_market_conditions())

        decision = persistence.async_save_trade_decision.await_args.args[0]
        assert decision.quantity == pytest.approx(position.size)
        assert "WARNING: the executor fill quantity" not in decision.reasoning
        post_mortem.analyze_closed_trade.assert_not_awaited()
        strategy.brain_service.update_from_closed_trade.assert_not_called()

    async def test_a_matching_fill_amount_adds_no_divergence_note(self, tmp_path: Path) -> None:
        position = _position()
        strategy, _, persistence, _ = _strategy(tmp_path, position)

        await strategy.close_position(
            "take_profit", 84500.0, make_market_conditions(),
            filled_quantity=0.00554, evidence=proven_exit(),
        )

        decision = persistence.async_save_trade_decision.await_args.args[0]
        assert decision.quantity == pytest.approx(0.00554)
        assert "WARNING: the executor fill quantity" not in decision.reasoning
