"""Deterministic Binance Spot diff-depth book reconstruction; no network or orders.

Requires a caller-supplied snapshot and chronologically ordered diff events.
The caller must buffer events during snapshot acquisition; this module does not
assert that public archives contain a complete historical depth feed.
"""

from decimal import Decimal, InvalidOperation


class BookEvidenceError(ValueError):
    """A book cannot be reconstructed without continuity and valid levels."""


def _integer(value, name):
    if type(value) is not int or value < 0:
        raise BookEvidenceError(f"{name} must be a nonnegative integer")
    return value


def _levels(rows):
    if not isinstance(rows, list):
        raise BookEvidenceError("levels must be a list")
    result = {}
    for pair in rows:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise BookEvidenceError("each level must be [price, quantity]")
        try:
            price, qty = (Decimal(x) for x in pair)
        except (InvalidOperation, ValueError, TypeError):
            raise BookEvidenceError("invalid decimal level") from None
        if not price.is_finite() or not qty.is_finite() or price <= 0 or qty < 0:
            raise BookEvidenceError("invalid price or quantity")
        if price in result:
            raise BookEvidenceError("duplicate price in one update")
        result[price] = qty
    return result


class DiffDepthBook:
    """Fail-closed L2 state with Binance Spot U/u update-ID continuity."""

    def __init__(self, snapshot):
        self.last_id = _integer(snapshot["lastUpdateId"], "lastUpdateId")
        self.bids = {p: q for p, q in _levels(snapshot["bids"]).items() if q}
        self.asks = {p: q for p, q in _levels(snapshot["asks"]).items() if q}
        self.started = False
        self.needs_resnapshot = False
        self._check(self.bids, self.asks)

    @staticmethod
    def _check(bids, asks):
        if bids and asks and max(bids) >= min(asks):
            raise BookEvidenceError("crossed or locked book")

    def apply(self, event):
        if self.needs_resnapshot:
            raise BookEvidenceError("resnapshot required: book continuity lost")
        first = _integer(event["U"], "U")
        last = _integer(event["u"], "u")
        if first > last:
            raise BookEvidenceError("inverted update interval")
        if last <= self.last_id:
            if self.started:
                raise BookEvidenceError("out-of-order or duplicate event")
            return False  # buffered event older than snapshot
        expected = self.last_id + 1
        if not first <= expected <= last:
            self.needs_resnapshot = True
            raise BookEvidenceError("missing diff-depth update: resnapshot required")
        bids_delta, asks_delta = _levels(event["b"]), _levels(event["a"])
        bids, asks = self.bids.copy(), self.asks.copy()
        for target, changes in ((bids, bids_delta), (asks, asks_delta)):
            for price, quantity in changes.items():
                if quantity == 0:
                    target.pop(price, None)
                else:
                    target[price] = quantity
        self._check(bids, asks)
        self.bids, self.asks = bids, asks
        self.last_id = last
        self.started = True
        return True

    def top(self):
        if self.needs_resnapshot:
            raise BookEvidenceError("resnapshot required: book continuity lost")
        return (max(self.bids) if self.bids else None,
                min(self.asks) if self.asks else None)
