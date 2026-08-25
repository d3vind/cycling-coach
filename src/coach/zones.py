"""Zone model and session classification.

Implements registry v0.2 sections 3.1 (pedalling time) and 3.5 (classify from
power, never from platform labels).
"""

from collections import defaultdict

ZONES = {
    "recovery": (0.00, 0.55),
    "endurance": (0.56, 0.75),
    "tempo": (0.76, 0.87),
    "sweetspot": (0.88, 0.94),
    "threshold": (0.94, 1.05),
    "vo2max": (1.06, 1.28),
    "anaerobic": (1.29, 99.0),
}

LOW_MAX = 0.76
HIGH_MIN = 1.05
MAX_GAP_S = 120


def deltas(times):
    """Time weight per sample, capped so pauses do not distort."""
    out = []
    for i, t in enumerate(times):
        if i == 0:
            d = times[1] - times[0] if len(times) > 1 else 1
        else:
            d = t - times[i - 1]
        out.append(min(d, MAX_GAP_S))
    return out


def occupancy(watts, times, ftp, exclude_zeros=True):
    """Time in each zone.

    v0.2 3.1: distribution is computed over PEDALLING time. Zero-watt
    coasting is returned separately, never counted as low intensity.
    """
    occ = defaultdict(float)
    tri = {"low": 0.0, "moderate": 0.0, "high": 0.0}
    coasting = 0.0

    for w, d in zip(watts, deltas(times)):
        if exclude_zeros and w == 0:
            coasting += d
            continue
        frac = w / ftp
        for name, (lo, hi) in ZONES.items():
            if lo <= frac < hi:
                occ[name] += d
                break
        if frac < LOW_MAX:
            tri["low"] += d
        elif frac < HIGH_MIN:
            tri["moderate"] += d
        else:
            tri["high"] += d

    return dict(occ), tri, coasting


def best_effort(watts, times, window_s):
    """Best time-weighted rolling average over window_s.

    On downsampled streams this is a FLOOR, not a maximal test. Callers must
    tag the result provenance accordingly (see registry v0.2 3.3).
    """
    best = 0.0
    n = len(times)
    for i in range(n):
        acc_t, acc_w = 0.0, 0.0
        for j in range(i, n):
            d = min(times[j] - times[j - 1], MAX_GAP_S) if j > i else 1
            acc_t += d
            acc_w += watts[j] * d
            if acc_t >= window_s:
                best = max(best, acc_w / acc_t)
                break
        if times[-1] - times[i] < window_s:
            break
    return best


def contiguous_seconds(watts, times, lo_pct, hi_pct, ftp):
    """Longest contiguous run with power inside [lo_pct, hi_pct] of FTP."""
    best = cur = 0.0
    for w, d in zip(watts, deltas(times)):
        if lo_pct <= w / ftp < hi_pct:
            cur += d
            best = max(best, cur)
        else:
            cur = 0.0
    return best


def classify(ride, ftp):
    """Classify a session from measured power.

    v0.2 3.5: never trust the file name or the source platform's category.
    The original label is preserved as display metadata only.
    """
    watts, times = ride["watts"], ride["time"]
    occ, tri, coasting = occupancy(watts, times, ftp)
    total = sum(tri.values()) or 1.0

    high_s = tri["high"]
    mod_share = tri["moderate"] / total
    b5 = best_effort(watts, times, 300)
    thr_s = contiguous_seconds(watts, times, 0.94, 1.05, ftp)

    if high_s >= 300 and b5 / ftp >= 1.06:
        label = "vo2max_supra"
    elif high_s >= 120:
        label = "threshold_plus"
    elif mod_share >= 0.30 and thr_s >= 300:
        label = "threshold"
    elif mod_share >= 0.30:
        label = "sweetspot_tempo"
    elif mod_share >= 0.12:
        label = "endurance_with_efforts"
    else:
        label = "endurance_easy"

    return label, {
        "platform_label": ride.get("name", ""),
        "duration_min": round(ride["moving"] / 60, 1),
        "pedalling_s": round(total),
        "coasting_s": round(coasting),
        "seconds_above_105": round(high_s),
        "moderate_share": round(mod_share, 3),
        "best_5min_w": round(b5),
        "best_5min_pct_ftp": round(b5 / ftp, 3),
        "longest_threshold_block_s": round(thr_s),
    }
