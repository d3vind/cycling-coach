"""Training audit.

Runs the registry v0.2 detectors over a window of rides and returns structured
findings. Pure functions over plain dicts -- no data-source dependency, so the
fetch layer can be swapped freely.
"""

from collections import defaultdict
from datetime import date

from .zones import classify, occupancy, best_effort


def _iso_week(datestr):
    y, m, d = map(int, datestr.split("-"))
    return date(y, m, d).isocalendar()[1]


def audit(window, ftp, stated_weekly_hours=None, planned_weekly_hours=None):
    """Analyse a list of rides.

    window: dict with 'rides' (list) and optional 'window' (date pair).
    Each ride needs: date, name, kind ('indoor'|'outdoor'), moving, time[], watts[].
    """
    rides = window["rides"]

    agg_occ = defaultdict(float)
    agg_tri = {"low": 0.0, "moderate": 0.0, "high": 0.0}
    coasting_total = 0.0
    by_kind = {}
    weekly = defaultdict(float)
    sessions = []
    curve = []

    for r in rides:
        label, ev = classify(r, ftp)
        occ, tri, coast = occupancy(r["watts"], r["time"], ftp)

        for k, v in occ.items():
            agg_occ[k] += v
        for k in agg_tri:
            agg_tri[k] += tri[k]
        coasting_total += coast

        kind = r.get("kind", "unknown")
        seg = by_kind.setdefault(kind, {"low": 0.0, "moderate": 0.0, "high": 0.0})
        for k in seg:
            seg[k] += tri[k]

        weekly[_iso_week(r["date"])] += r["moving"] / 3600.0

        b5 = best_effort(r["watts"], r["time"], 300)
        b20 = best_effort(r["watts"], r["time"], 1200)
        curve.append({
            "date": r["date"], "name": r["name"],
            "best_5min": b5, "best_20min": b20,
            "provenance": r.get("provenance", "within_ride"),
        })

        sessions.append({"date": r["date"], "class": label, **ev})

    total = sum(agg_tri.values()) or 1.0

    distribution = {
        "basis": "pedalling_time",
        "low": agg_tri["low"] / total,
        "moderate": agg_tri["moderate"] / total,
        "high": agg_tri["high"] / total,
        "pedalling_hours": total / 3600.0,
        "coasting_hours": coasting_total / 3600.0,
        "by_segment": {
            k: {z: v[z] / (sum(v.values()) or 1.0) for z in v}
            for k, v in by_kind.items()
        },
        "zone_hours": {k: v / 3600.0 for k, v in agg_occ.items()},
    }

    best5 = max(curve, key=lambda c: c["best_5min"])
    best20 = max(curve, key=lambda c: c["best_20min"])
    qualifying = [c for c in curve if c["provenance"] in ("maximal_test", "race")]

    power_curve = {
        "best_5min_w": best5["best_5min"],
        "best_5min_pct_ftp": best5["best_5min"] / ftp,
        "best_5min_source": best5["name"],
        "best_5min_provenance": best5["provenance"],
        "best_20min_w": best20["best_20min"],
        "best_20min_pct_ftp": best20["best_20min"] / ftp,
        "best_20min_source": best20["name"],
        "best_20min_provenance": best20["provenance"],
        "ceiling_gap_w": best5["best_5min"] - best20["best_20min"],
        "has_qualifying_maximal_data": bool(qualifying),
    }

    implied = best20["best_20min"] * 0.95
    power_curve["implied_ftp_from_20min"] = implied
    power_curve["anchor_error_pct"] = (implied - ftp) / ftp

    flags = []

    if distribution["moderate"] > 0.35:
        flags.append({
            "id": "gray_zone_moderate_share", "severity": "warn",
            "detail": f"{distribution['moderate']:.1%} of pedalling time in the "
                      f"moderate band (limit 35%)",
        })

    for seg, dist in distribution["by_segment"].items():
        if dist["moderate"] > 0.35:
            flags.append({
                "id": f"gray_zone_segment_{seg}", "severity": "warn",
                "detail": f"{seg} sessions are {dist['moderate']:.0%} moderate -- "
                          f"masked by the aggregate",
            })

    if power_curve["best_5min_pct_ftp"] < 1.10:
        if qualifying:
            flags.append({
                "id": "compressed_power_curve", "severity": "warn",
                "detail": f"best 5-min is {power_curve['best_5min_pct_ftp']:.0%} "
                          f"of FTP (trained 115-125%) -- prescribe VO2 work",
            })
        else:
            flags.append({
                "id": "insufficient_maximal_data", "severity": "info",
                "detail": "5-min power looks low but all data is within-ride "
                          "(a floor, not a measurement). Prescribe a 5-min max "
                          "test before diagnosing the ceiling.",
            })

    # v0.2 3.3 applies to the anchor cross-check too: a within-ride 20-min
    # best is a floor, so it can leave the anchor unconfirmed but never
    # assert it is wrong. Only a maximal effort can do that.
    if best20["provenance"] in ("maximal_test", "race"):
        if abs(power_curve["anchor_error_pct"]) > 0.05:
            flags.append({
                "id": "ftp_anchor_suspect", "severity": "warn",
                "detail": f"20-min x 0.95 implies {implied:.0f} W vs stated {ftp} W "
                          f"({power_curve['anchor_error_pct']:+.1%})",
            })
    elif power_curve["anchor_error_pct"] < -0.05:
        flags.append({
            "id": "ftp_anchor_unverified", "severity": "info",
            "detail": f"best 20-min in the window is within-ride (a floor): "
                      f"x 0.95 implies {implied:.0f} W vs stated {ftp} W "
                      f"({power_curve['anchor_error_pct']:+.1%}). Not evidence "
                      f"the anchor is wrong -- it just has not been confirmed "
                      f"by a maximal effort.",
        })

    drift = []
    for r in rides:
        label, _ = classify(r, ftp)
        if not label.startswith("endurance"):
            continue
        from .zones import deltas
        d = deltas(r["time"])
        ap = sum(w * dd for w, dd in zip(r["watts"], d)) / sum(d)
        drift.append({"date": r["date"], "name": r["name"],
                      "avg_w": round(ap), "pct_ftp": ap / ftp})
    if any(x["pct_ftp"] > 0.80 for x in drift):
        flags.append({"id": "easy_rides_not_easy", "severity": "warn",
                      "detail": "endurance rides averaging above 80% FTP"})

    weeks = sorted(weekly)
    mean_h = sum(weekly.values()) / len(weeks) if weeks else 0.0
    adherence = {"weekly_hours": {w: weekly[w] for w in weeks},
                 "mean_hours": mean_h}

    if stated_weekly_hours:
        ratio = mean_h / stated_weekly_hours
        adherence["vs_stated"] = ratio
        if ratio < 0.60:
            flags.insert(0, {
                "id": "volume_collapse", "severity": "critical",
                "detail": f"completing {mean_h:.1f} h/wk against {stated_weekly_hours} h "
                          f"stated available ({ratio:.0%}). Stop optimising the plan -- "
                          f"find out why before changing sessions.",
            })
        elif ratio < 0.70:
            flags.insert(0, {
                "id": "volume_gap", "severity": "warn",
                "detail": f"completing {ratio:.0%} of stated available hours",
            })

    if planned_weekly_hours:
        ratio = mean_h / planned_weekly_hours
        adherence["vs_planned"] = ratio
        if ratio < 0.80:
            flags.insert(0, {"id": "plan_adherence_low", "severity": "warn",
                             "detail": f"completing {ratio:.0%} of planned hours"})

    # Rank by severity. Do not rely on insertion order -- v0.2 3.4 requires
    # adherence collapse to surface above everything else.
    _rank = {"critical": 0, "warn": 1, "info": 2}
    flags.sort(key=lambda f: _rank[f["severity"]])

    return {
        "ftp": ftp,
        "sessions": sessions,
        "distribution": distribution,
        "power_curve": power_curve,
        "easy_ride_drift": drift,
        "adherence": adherence,
        "flags": flags,
    }
