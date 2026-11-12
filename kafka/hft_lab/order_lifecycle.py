"""Deterministic hypothetical order/cancel timeline; never predicts exchange fills.

Cancellation is an instruction that becomes effective only after its declared delay.
No order is treated as filled merely because a price crossed a limit.
"""
from book_replay import BookEvidenceError


def _ns(value, name):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise BookEvidenceError(f"{name} must be nonnegative UTC nanoseconds")
    return value


def hypothetical_cancel_timeline(*, submit_ts_ns, accept_delay_ns,
                                 cancel_ts_ns, cancel_delay_ns,
                                 observation_ts_ns):
    """Report observable order state, not fill probability.

    Ties are resolved conservatively: cancel becomes effective at the same
    timestamp as acceptance only if it was requested after submission.
    All delays are declared scenario assumptions, not measured latencies.
    """
    submitted = _ns(submit_ts_ns, "submit_ts_ns")
    accept_delay = _ns(accept_delay_ns, "accept_delay_ns")
    cancel = _ns(cancel_ts_ns, "cancel_ts_ns")
    cancel_delay = _ns(cancel_delay_ns, "cancel_delay_ns")
    observed = _ns(observation_ts_ns, "observation_ts_ns")
    if cancel < submitted:
        raise BookEvidenceError("cancel request precedes submission")
    if observed < submitted:
        raise BookEvidenceError("observation precedes submission")
    if submitted + accept_delay > 2**63 - 1 or cancel + cancel_delay > 2**63 - 1:
        raise BookEvidenceError("timestamp overflow")
    accepted = submitted + accept_delay
    cancelled = cancel + cancel_delay
    # Cancellation before acceptance is a model ambiguity, not proof of an
    # exchange-level cancelled order. Reject instead of inventing semantics.
    if cancelled < accepted:
        raise BookEvidenceError("cancel arrival precedes acceptance: undefined model")
    if observed < accepted:
        state = "PENDING_ACCEPT"
    elif observed < cancelled:
        state = "LIVE_UNFILLED_ASSUMPTION"
    else:
        state = "CANCELLED_UNFILLED_ASSUMPTION"
    return {
        "status": "HYPOTHETICAL_ONLY",
        "state": state,
        "accepted_ts_ns": accepted,
        "cancel_effective_ts_ns": cancelled,
        "observation_ts_ns": observed,
        "fill_status": "NOT_MODELED",
        "assumptions": "zero fills assumed for state illustration; no queue, acknowledgement, exchange cancellation or realized PnL",
    }
