"""Readiness engine.

Maps health metrics to a training-readiness state per registry v0.2 section 5.
Designed against what a Fitbit Air actually reports through the Google Health
API -- no weight, no ECG.

  * worst signal wins
  * decisions gate on TRENDS, never single readings
  * never substitute a HARDER session on amber or red
  * missing data is missing, not zero
"""

GREEN, AMBER, RED = "green", "amber", "red"
_ORDER = {GREEN: 0, AMBER: 1, RED: 2}


def _band(value, green, amber):
    def inside(v, rng):
        lo, hi = rng
        return (lo is None or v >= lo) and (hi is None or v <= hi)
    if inside(value, green):
        return GREEN
    if inside(value, amber):
        return AMBER
    return RED


SIGNALS = {
    "resting_hr_delta_bpm": lambda v: _band(v, (None, 3), (4, 7)),
    "hrv_pct_below_baseline": lambda v: _band(v, (None, 0.0), (0.05, 0.10)),
    "resp_rate_delta": lambda v: _band(v, (None, 1), (1, 2)),
    "sleep_hours": lambda v: _band(v, (7, None), (5.5, 7)),
    "subjective_1_10": lambda v: _band(v, (7, None), (4, 6)),
}


def assess(signals, history=None):
    """signals: dict of the keys above. Missing keys are skipped, not zeroed."""
    history = history or {}
    per_signal, state = {}, GREEN
    missing = []

    for key, fn in SIGNALS.items():
        if key not in signals or signals[key] is None:
            missing.append(key)
            continue
        s = fn(signals[key])
        per_signal[key] = s
        if _ORDER[s] > _ORDER[state]:
            state = s

    notes, escalations = [], []

    if per_signal.get("resp_rate_delta") == RED and \
       per_signal.get("resting_hr_delta_bpm") == RED:
        state = RED
        escalations.append("illness_protocol_no_training")
        notes.append("Elevated respiratory rate and resting HR together suggest "
                     "illness. Rest. If you have symptoms, see a clinician "
                     "rather than modifying the session.")

    if history.get("consecutive_red_days", 0) >= 2:
        escalations.append("insert_recovery_week")
        notes.append("Two consecutive red days -- insert a recovery week and "
                     "defer any block.")

    if history.get("hrv_declining_days", 0) >= 10:
        escalations.append("insert_recovery_week")
        notes.append("HRV trending down for 10+ days.")

    if missing:
        notes.append(
            "No data for: " + ", ".join(missing) + ". Fitbit syncs only when "
            "the Fitbit app has run -- treat this as unknown, not as good.")

    if not per_signal:
        state = "unknown"
        notes.append("No readiness signals available. Falling back to the "
                     "planned session; ask the rider how they feel.")

    return {
        "state": state,
        "per_signal": per_signal,
        "missing": missing,
        "escalations": escalations,
        "notes": notes,
    }


ACTIONS = {
    GREEN: "prescribe_as_planned",
    AMBER: "reduce_volume_30pct_or_substitute_endurance_z2",
    RED: "substitute_recovery_spin_or_rest",
    "unknown": "prescribe_as_planned_with_caveat",
}
