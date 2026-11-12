"""Deterministic *hypothetical* immediate-taker cost on a frozen L2 book.

This is an accounting scenario, not an order, fill prediction, or backtest.
"""
from decimal import Decimal, InvalidOperation
from book_replay import BookEvidenceError


def _positive(value, name, *, allow_zero=False):
    if isinstance(value, (bool, float)):
        raise BookEvidenceError(f"{name}: decimal string or integer required")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        raise BookEvidenceError(f"{name}: invalid decimal") from None
    if not number.is_finite() or number < 0 or (not allow_zero and number == 0):
        raise BookEvidenceError(f"{name}: out of range")
    return number


def hypothetical_taker(book, *, side, quantity, fee_bps, extra_slippage_bps=0):
    """Sweep visible L2 liquidity, then apply explicitly assumed costs.

    Quantity is base-asset units. fee/slippage are basis points of quote notional.
    No partial fill is reported as a completed transaction. This assumes all
    displayed liquidity is available at the modeled instant.
    """
    if side not in ("buy", "sell"):
        raise BookEvidenceError("side must be buy or sell")
    qty = _positive(quantity, "quantity")
    fee = _positive(fee_bps, "fee_bps", allow_zero=True)
    slip = _positive(extra_slippage_bps, "extra_slippage_bps", allow_zero=True)
    if fee > 10000 or slip > 10000:
        raise BookEvidenceError("assumed costs exceed 10000 bps")
    book.top()  # Fail closed if continuity was lost.
    levels = book.asks if side == "buy" else book.bids
    ordered = sorted(levels.items(), reverse=side == "sell")
    remaining, gross = qty, Decimal(0)
    for price, available in ordered:
        taken = min(remaining, available)
        gross += taken * price
        remaining -= taken
        if remaining == 0:
            break
    if remaining:
        raise BookEvidenceError("insufficient visible depth: no hypothetical full fill")
    fee_quote = gross * fee / Decimal(10000)
    slippage_quote = gross * slip / Decimal(10000)
    effective_quote = gross + fee_quote + slippage_quote if side == "buy" else gross - fee_quote - slippage_quote
    return {"status": "HYPOTHETICAL_ONLY", "side": side, "quantity": str(qty),
            "gross_quote": str(gross), "fee_quote": str(fee_quote),
            "extra_slippage_quote": str(slippage_quote),
            "effective_quote": str(effective_quote),
            "effective_price": str(effective_quote / qty),
            "assumptions": "visible levels fully executable; no queue, latency, impact or real fills"}


def hypothetical_delayed_taker(manifest, snapshot, events, *, snapshot_ts_ns,
                               submit_ts_ns, delay_ns, side, quantity, fee_bps,
                               extra_slippage_bps=0):
    """Compare frozen submit-time and arrival-time L2 depth, without future leakage.

    Times are declared UTC nanoseconds, NOT observed host/network timestamps.
    The last event must cover arrival; a later event is never applied. This
    remains a hypothetical immediate taker, not an exchange fill prediction.
    """
    from replay_provenance import ProvenanceReplay

    def timestamp(value, name):
        if type(value) is not int or not 0 <= value <= 2**63 - 1:
            raise BookEvidenceError(f"{name} must be unsigned-range UTC ns integer")
        return value

    start = timestamp(snapshot_ts_ns, "snapshot_ts_ns")
    submitted = timestamp(submit_ts_ns, "submit_ts_ns")
    delay = timestamp(delay_ns, "delay_ns")
    if submitted < start or submitted + delay > 2**63 - 1:
        raise BookEvidenceError("submission/arrival outside snapshot or timestamp range")
    arrival = submitted + delay
    if not events:
        raise BookEvidenceError("no event coverage for arrival time")
    timestamps = []
    last = start
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            raise BookEvidenceError(f"event {i} must be a dict")
        t = timestamp(event.get("exchange_ts_ns"), f"event {i} exchange_ts_ns")
        if t < last:
            raise BookEvidenceError(f"event {i} timestamp order violation")
        timestamps.append(t)
        last = t
    if arrival > last:
        raise BookEvidenceError("arrival not covered by frozen event timeline")
    replay = ProvenanceReplay(manifest, snapshot, events)
    before = None
    for event_time in timestamps:
        if before is None and event_time > submitted:
            before = hypothetical_taker(replay.book, side=side, quantity=quantity,
                                        fee_bps=fee_bps, extra_slippage_bps=extra_slippage_bps)
        if event_time > arrival:
            break
        replay.step()
    if before is None:
        before = hypothetical_taker(replay.book, side=side, quantity=quantity,
                                    fee_bps=fee_bps, extra_slippage_bps=extra_slippage_bps)
    # At this point the book contains only events with event_time <= arrival.
    after = hypothetical_taker(replay.book, side=side, quantity=quantity,
                               fee_bps=fee_bps, extra_slippage_bps=extra_slippage_bps)
    return {
        "status": "HYPOTHETICAL_ONLY",
        "submit_ts_ns": submitted,
        "arrival_ts_ns": arrival,
        "submission": before,
        "arrival": after,
        "effective_quote_change": str(
            Decimal(after["effective_quote"]) - Decimal(before["effective_quote"])
        ),
        "assumptions": "synthetic or verified frozen exchange event times; declared delay; "
                       "visible depth fully executable; no queue, cancel, real fills or network measurement",
    }
