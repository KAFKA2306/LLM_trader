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


def hypothetical_cancel_delay_sensitivity(*, submit_ts_ns, accept_delay_ns,
                                          cancel_ts_ns, cancel_delay_ns_grid,
                                          observation_ts_ns):
    """Evaluate an explicit finite delay grid, not a probability distribution.

    The caller declares every delay. Reject the whole grid if any scenario
    is invalid; never silently drop an adverse case. No fill is modeled.
    """
    if not isinstance(cancel_delay_ns_grid, (tuple, list)) or not cancel_delay_ns_grid:
        raise BookEvidenceError("nonempty delay grid required")
    if len(cancel_delay_ns_grid) > 256:
        raise BookEvidenceError("delay grid exceeds 256 scenarios")
    if len(set(map(str, cancel_delay_ns_grid))) != len(cancel_delay_ns_grid):
        raise BookEvidenceError("duplicate delays in grid")
    scenarios = []
    for delay in cancel_delay_ns_grid:
        result = hypothetical_cancel_timeline(
            submit_ts_ns=submit_ts_ns, accept_delay_ns=accept_delay_ns,
            cancel_ts_ns=cancel_ts_ns, cancel_delay_ns=delay,
            observation_ts_ns=observation_ts_ns)
        scenarios.append({"cancel_delay_ns": delay, "state": result["state"],
                          "cancel_effective_ts_ns": result["cancel_effective_ts_ns"],
                          "fill_status": result["fill_status"]})
    effective = [s["cancel_effective_ts_ns"] for s in scenarios]
    accepted = _ns(submit_ts_ns, "submit_ts_ns") + _ns(accept_delay_ns, "accept_delay_ns")
    return {
        "status": "HYPOTHETICAL_ONLY",
        "scenarios": scenarios,
        "earliest_cancel_effective_ts_ns": min(effective),
        "latest_cancel_effective_ts_ns": max(effective),
        "min_live_exposure_ns": min(effective) - accepted,
        "max_live_exposure_ns": max(effective) - accepted,
        "fill_status": "NOT_MODELED",
        "assumptions": "declared finite delay grid, no probabilities, queue or fills",
    }


def hypothetical_cancel_risk_gate(*, submit_ts_ns, accept_delay_ns,
                                  cancel_ts_ns, cancel_delay_ns_grid,
                                  observation_ts_ns, max_live_exposure_ns):
    """Conservative research gate: reject if ANY assumed delay exceeds the cap.

    A STOP is a scenario decision, not an exchange cancel instruction.
    """
    cap = _ns(max_live_exposure_ns, "max_live_exposure_ns")
    sensitivity = hypothetical_cancel_delay_sensitivity(
        submit_ts_ns=submit_ts_ns, accept_delay_ns=accept_delay_ns,
        cancel_ts_ns=cancel_ts_ns, cancel_delay_ns_grid=cancel_delay_ns_grid,
        observation_ts_ns=observation_ts_ns)
    breached = sensitivity["max_live_exposure_ns"] > cap
    still_live = any(s["state"] == "LIVE_UNFILLED_ASSUMPTION"
                     for s in sensitivity["scenarios"])
    pending_accept = any(s["state"] == "PENDING_ACCEPT"
                         for s in sensitivity["scenarios"])
    return {
        "status": "HYPOTHETICAL_ONLY",
        "decision": "STOP" if breached or still_live or pending_accept else "ALLOW",
        "reasons": (["EXPOSURE_LIMIT_EXCEEDED"] if breached else [])
                   + (["POSSIBLY_LIVE_AT_OBSERVATION"] if still_live else [])
                   + (["ACCEPTANCE_PENDING_AT_OBSERVATION"] if pending_accept else []),
        "max_live_exposure_ns": sensitivity["max_live_exposure_ns"],
        "max_allowed_live_exposure_ns": cap,
        "fill_status": "NOT_MODELED",
    }


def hypothetical_acceptance_jitter_gate(*, submit_ts_ns, accept_delay_ns_grid,
                                        cancel_ts_ns, cancel_delay_ns_grid,
                                        observation_ts_ns, max_live_exposure_ns):
    """Worst-case gate over explicit acceptance AND cancellation delay scenarios.

    Every Cartesian-product scenario must be valid and ALLOW. No probabilities,
    fills, exchange acknowledgements or live risk controls are inferred.
    """
    if not isinstance(accept_delay_ns_grid, (list, tuple)) or not accept_delay_ns_grid:
        raise BookEvidenceError("nonempty acceptance delay grid required")
    if len(accept_delay_ns_grid) > 256:
        raise BookEvidenceError("acceptance delay grid exceeds 256 scenarios")
    for delay in accept_delay_ns_grid:
        _ns(delay, "accept_delay_ns")
    if len(set(accept_delay_ns_grid)) != len(accept_delay_ns_grid):
        raise BookEvidenceError("duplicate acceptance delays")
    # Validate cancellation grid before iteration, including a bounded product.
    if not isinstance(cancel_delay_ns_grid, (list, tuple)) or not cancel_delay_ns_grid:
        raise BookEvidenceError("nonempty cancellation delay grid required")
    if len(accept_delay_ns_grid) * len(cancel_delay_ns_grid) > 256:
        raise BookEvidenceError("combined scenario grid exceeds 256")
    results = [hypothetical_cancel_risk_gate(
        submit_ts_ns=submit_ts_ns, accept_delay_ns=accept_delay,
        cancel_ts_ns=cancel_ts_ns, cancel_delay_ns_grid=cancel_delay_ns_grid,
        observation_ts_ns=observation_ts_ns,
        max_live_exposure_ns=max_live_exposure_ns)
        for accept_delay in accept_delay_ns_grid]
    reasons = sorted({reason for result in results for reason in result["reasons"]})
    return {
        "status": "HYPOTHETICAL_ONLY",
        "decision": "STOP" if any(r["decision"] == "STOP" for r in results) else "ALLOW",
        "reasons": reasons,
        "max_live_exposure_ns": max(r["max_live_exposure_ns"] for r in results),
        "scenario_count": len(accept_delay_ns_grid) * len(cancel_delay_ns_grid),
        "fill_status": "NOT_MODELED",
    }
