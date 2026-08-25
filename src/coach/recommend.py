"""Daily recommendation.

Combines: recent training audit + today's readiness + rider profile + goal
        -> one suggested session, with the reasoning made explicit.

Deliberately NOT a language model. This is the deterministic layer that decides
WHAT stimulus is needed; a generative layer may later phrase it, vary the
workout, or build the ERG file, but it does so inside these bounds.
"""

from .readiness import GREEN, AMBER, RED, ACTIONS
from .registry import Registry


def _blocking_flags(audit_result):
    return [f for f in audit_result["flags"] if f["severity"] == "critical"]


def recommend(audit_result, readiness, rider, goal="raise_ftp", registry=None):
    reg = registry or Registry()
    state = readiness["state"]
    ftp = rider["ftp"]

    rec = {
        "readiness": state,
        "action": ACTIONS[state],
        "reasoning": [],
        "warnings": [],
        "session": None,
    }

    critical = _blocking_flags(audit_result)
    if critical:
        for f in critical:
            rec["warnings"].append(f["detail"])
        rec["reasoning"].append(
            "Volume adherence is the binding constraint. Changing session type "
            "cannot compensate for a volume gap this size, so today's job is "
            "simply to ride the hours.")

    if state == RED:
        rec["session"] = {"method": "recovery_spin", "detail": "30-45 min under "
                          f"{int(ftp * 0.55)} W, or full rest"}
        rec["reasoning"].append("Red readiness. Nothing is gained today.")
        for n in readiness["notes"]:
            rec["warnings"].append(n)
        return rec

    if "illness_protocol_no_training" in readiness["escalations"]:
        rec["session"] = {"method": None, "detail": "Rest. See a clinician if symptomatic."}
        return rec

    dist = audit_result["distribution"]
    pc = audit_result["power_curve"]
    flag_ids = {f["id"] for f in audit_result["flags"]}

    want = None

    if "insufficient_maximal_data" in flag_ids:
        want = "test"
        rec["reasoning"].append(
            "No maximal-effort data in the window, so the power curve cannot be "
            "read. A 5-min max test is worth more right now than another guess "
            "at the right interval.")
    elif "ftp_anchor_suspect" in flag_ids:
        want = "test"
        rec["reasoning"].append(
            f"20-min power implies ~{pc['implied_ftp_from_20min']:.0f} W against a "
            f"stated {ftp} W. Percentages of a wrong anchor are worse than useless.")
    elif "compressed_power_curve" in flag_ids:
        want = "vo2max"
        rec["reasoning"].append(
            f"Best 5-min sits at {pc['best_5min_pct_ftp']:.0%} of FTP against a "
            f"trained norm of 115-125%. The ceiling is the limiter.")
    elif any(fid.startswith("gray_zone") for fid in flag_ids):
        want = "endurance"
        rec["reasoning"].append(
            f"{dist['moderate']:.0%} of pedalling time is in the moderate band. "
            f"More easy volume, not more intensity.")
    elif dist["high"] < 0.08 and goal == "raise_ftp":
        want = "vo2max"
        rec["reasoning"].append(
            f"Only {dist['high']:.0%} of time above threshold. The ceiling is "
            f"not being challenged.")
    else:
        want = "endurance"
        rec["reasoning"].append("Distribution is reasonable. Bank aerobic volume.")

    if want == "test":
        rec["session"] = {
            "method": "ftp_test",
            "detail": "20 min warmup, then 5 min all-out from fresh legs. Tag the "
                      "result as maximal_test so the engine can trust it.",
        }
        return rec

    # ftp_anchor_unverified is info-level by design: an unconfirmed anchor is
    # a note on the session, never a reason to prescribe a test on its own
    # (v0.2 3.3 -- within-ride bests cannot assert the anchor is wrong).
    if "ftp_anchor_unverified" in flag_ids:
        rec["warnings"].append(
            "FTP anchor is unconfirmed in this window (no maximal 20-min "
            "effort). Percent targets below assume it is right; a formal test "
            "would firm it up.")

    prefer = {
        "vo2max": ["vo2_short_short_30_15", "vo2_short_short_40_20", "vo2_long_intervals"],
        "threshold": ["threshold_2x20", "over_unders"],
        "endurance": ["endurance_z2"],
    }[want]

    for mid in prefer:
        ok, why = reg.eligible(mid, rider, state)
        if not ok:
            rec["warnings"].append(f"{mid} skipped: {'; '.join(why)}")
            continue
        ok_t, why_t = reg.check_targets(mid, rider)
        if not ok_t:
            rec["warnings"].extend(why_t)
            continue
        rec["session"] = {"method": mid, "detail": _describe(reg, mid, ftp, state)}
        break

    if rec["session"] is None:
        rec["session"] = {"method": "endurance_z2",
                          "detail": f"{int(ftp*0.56)}-{int(ftp*0.75)} W, 60-120 min"}
        rec["reasoning"].append("Nothing harder is currently permitted -- "
                                "falling back to endurance.")

    if state == AMBER:
        rec["warnings"].append(
            "Amber readiness: hold the session type but cut volume ~30% "
            "(e.g. 3 sets to 2). Never substitute something harder.")

    for n in readiness["notes"]:
        rec["warnings"].append(n)

    return rec


def _describe(reg, method_id, ftp, state):
    m = reg.methods[method_id]
    s = m.get("structure", {})
    t = s.get("type")

    if t == "continuous":
        z = reg.data["zone_model"]["zones"][s["zone"]]
        lo, hi = s["duration_min"]
        return (f"{int(ftp*z['lo_pct'])}-{int(ftp*z['hi_pct'])} W, {lo}-{min(hi,120)} min")

    if t == "intervals" and "sets" in s:
        w = s["work_pct"]
        return (f"{s['sets']} x {s['reps_per_set']} x ({s['work_s']}s at "
                f"{int(ftp*w[0])}-{int(ftp*w[1])} W / {s['rest_s']}s easy), "
                f"{s['between_sets_s']//60} min between sets. "
                f"Run in resistance mode and self-select -- do not trust ERG at a "
                f"percentage of an unverified anchor.")

    if t == "intervals":
        w = s["work_pct"]
        reps = s.get("reps") or s.get("reps_per_set")
        return (f"{reps} x {s['work_s']//60} min at "
                f"{int(ftp*w[0])}-{int(ftp*w[1])} W")

    return m["name"]
