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
