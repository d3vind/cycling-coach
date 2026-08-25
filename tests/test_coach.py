"""Regression tests for the v0.2 corrections.

Each test corresponds to a bug that shipped in v0.1 and was caught only by
running against real power files. They exist so the bugs cannot return.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coach.audit import audit
from coach.readiness import assess, RED, AMBER, GREEN
from coach.recommend import recommend
from coach.registry import Registry
from coach.zones import occupancy, classify

FIXTURE = json.loads((ROOT / "data" / "fixtures" / "window_28d.json").read_text())
FTP = 255


def test_coasting_is_excluded_from_distribution():
    watts = [0, 0, 0, 200, 200]
    times = [0, 10, 20, 30, 40]
    _, tri, coasting = occupancy(watts, times, 255)
    assert coasting > 0
    assert tri["low"] == 0, "zero-watt samples must not count as low intensity"


def test_elapsed_vs_pedalling_changes_the_verdict():
    """The exact bug: 29.4% elapsed vs 35.8% pedalling -- pass vs flag."""
    a = audit(FIXTURE, FTP)
    assert a["distribution"]["basis"] == "pedalling_time"
    assert a["distribution"]["moderate"] > 0.35
    assert a["distribution"]["coasting_hours"] > 3.0


def test_segment_flag_fires_when_aggregate_would_hide_it():
    a = audit(FIXTURE, FTP)
    seg = a["distribution"]["by_segment"]
    assert seg["indoor"]["moderate"] > seg["outdoor"]["moderate"]
    assert any(f["id"] == "gray_zone_segment_indoor" for f in a["flags"])


def test_within_ride_data_cannot_trigger_compression_diagnosis():
    """The bug that produced a confidently wrong VO2max recommendation."""
    fake = json.loads(json.dumps(FIXTURE))
    for r in fake["rides"]:
        r["watts"] = [min(w, 240) for w in r["watts"]]
        r["provenance"] = "within_ride"
    a = audit(fake, FTP)
    ids = {f["id"] for f in a["flags"]}
    assert "compressed_power_curve" not in ids
    assert "insufficient_maximal_data" in ids


def test_maximal_data_does_allow_the_diagnosis():
    fake = json.loads(json.dumps(FIXTURE))
    for r in fake["rides"]:
        r["watts"] = [min(w, 240) for w in r["watts"]]
        r["provenance"] = "maximal_test"
    a = audit(fake, FTP)
    assert any(f["id"] == "compressed_power_curve" for f in a["flags"])


def test_anchor_cross_check():
    a = audit(FIXTURE, FTP)
    assert abs(a["power_curve"]["anchor_error_pct"]) < 0.05


def test_target_sanity_rejects_prescription_above_5min_power():
    """TrainerRoad 'Fishers': 6 x 2 min at 124% FTP = 316 W, against a
    measured best 5-min of 312 W."""
    reg = Registry(ROOT / "data" / "methods.json")
    reg.methods["fishers"] = {
        "id": "fishers", "name": "Fishers",
        "structure": {"type": "intervals", "reps": 6, "work_s": 120,
                      "work_pct": [1.24, 1.24], "rest_s": 240},
    }
    rider = {"ftp": 255, "best_5min_w": 312}
    ok, why = reg.check_targets("fishers", rider)
    assert ok is False
    assert "anchor" in why[0]


def test_registry_long_intervals_stay_inside_the_ceiling():
    reg = Registry(ROOT / "data" / "methods.json")
    rider = {"ftp": 255, "best_5min_w": 312}
    ok, _ = reg.check_targets("vo2_long_intervals", rider)
    assert ok is True


def test_volume_collapse_is_critical_and_ranked_first():
    a = audit(FIXTURE, FTP, stated_weekly_hours=9)
    assert a["flags"][0]["severity"] == "critical"
    assert a["flags"][0]["id"] == "volume_collapse"


def test_cardinal_is_threshold_not_vo2max():
    """Named inside a VO2 block; contains zero seconds above 105% FTP."""
    ride = next(r for r in FIXTURE["rides"] if r["name"] == "Zwift - Cardinal")
    label, ev = classify(ride, FTP)
    assert label == "threshold"
    assert ev["seconds_above_105"] == 0
    assert ev["platform_label"] == "Zwift - Cardinal"


def test_worst_signal_wins():
    r = assess({"sleep_hours": 8, "resting_hr_delta_bpm": 9})
    assert r["state"] == RED


def test_missing_data_is_not_treated_as_good():
    r = assess({})
    assert r["state"] == "unknown"
    assert r["notes"]


def test_illness_protocol():
    r = assess({"resp_rate_delta": 3, "resting_hr_delta_bpm": 9})
    assert "illness_protocol_no_training" in r["escalations"]


def test_plan_validation_catches_an_overreaching_week():
    reg = Registry(ROOT / "data" / "methods.json")
    week = [{"method": "vo2_short_short_30_15", "hard": True, "hours": 1}] * 4
    v = reg.validate_plan(week)
    assert any("hard sessions" in x for x in v)
    assert any("consecutive" in x for x in v)


def test_sweetspot_alone_is_flagged():
    reg = Registry(ROOT / "data" / "methods.json")
    week = [{"method": "sweetspot_intervals", "hard": True, "hours": 1},
            {"method": "endurance_z2", "hard": False, "hours": 2}]
    v = reg.validate_plan(week)
    assert any("ceiling" in x for x in v)


def test_red_readiness_blocks_vo2():
    reg = Registry(ROOT / "data" / "methods.json")
    rider = {"ftp": 255, "base_weeks": 20, "ftp_anchor_age_weeks": 3}
    ok, why = reg.eligible("vo2_short_short_30_15", rider, RED)
    assert ok is False


def _low_20min_window(provenance):
    """One ride: 5 min at 300 W (117% FTP, so maximal data is not 'missing'),
    then 15+ min at 150 W. Best 20-min implies ~178 W against a stated 255."""
    times = list(range(0, 1220, 10))
    watts = [300] * 30 + [150] * (len(times) - 30)
    return {"ftp": FTP, "window": ["2026-07-28", "2026-08-25"],
            "rides": [{"id": "1", "name": "ride", "date": "2026-08-20",
                       "kind": "outdoor", "moving": 1210, "elapsed": 1210,
                       "time": times, "watts": watts,
                       "provenance": provenance}]}


def test_anchor_cross_check_needs_maximal_provenance():
    """v0.2 3.3 applies to the anchor check too: a within-ride 20-min best is
    a floor, so a low implied FTP cannot assert the anchor is wrong -- it can
    only be reported as unconfirmed, at info level."""
    a = audit(_low_20min_window("within_ride"), FTP)
    flags = {f["id"]: f["severity"] for f in a["flags"]}
    assert "ftp_anchor_suspect" not in flags
    assert flags.get("ftp_anchor_unverified") == "info"


def test_anchor_cross_check_fires_on_maximal_provenance():
    a = audit(_low_20min_window("maximal_test"), FTP)
    flags = {f["id"]: f["severity"] for f in a["flags"]}
    assert flags.get("ftp_anchor_suspect") == "warn"
    assert "ftp_anchor_unverified" not in flags


def test_within_ride_floor_above_stated_ftp_is_not_flagged():
    """The gate is one-sided: within_ride only reports 'unverified' when the
    implied FTP is below stated. Above stated, suspect still requires maximal
    provenance."""
    fake = json.loads(json.dumps(FIXTURE))
    for r in fake["rides"]:
        r["watts"] = [round(w * 1.15) for w in r["watts"]]
        r["provenance"] = "within_ride"
    a = audit(fake, FTP)
    assert a["power_curve"]["anchor_error_pct"] > 0.05
    ids = {f["id"] for f in a["flags"]}
    assert "ftp_anchor_suspect" not in ids
    assert "ftp_anchor_unverified" not in ids


def test_unverified_anchor_does_not_prescribe_a_test_on_its_own():
    """Info-level ftp_anchor_unverified must not trigger ftp_test; it becomes
    a note on the session the engine would otherwise pick."""
    a = audit(_low_20min_window("within_ride"), FTP)
    assert any(f["id"] == "ftp_anchor_unverified" for f in a["flags"])
    r = assess({"sleep_hours": 8, "resting_hr_delta_bpm": 0, "subjective_1_10": 8})
    assert r["state"] == GREEN
    rider = {"ftp": FTP, "base_weeks": 20, "ftp_anchor_age_weeks": 3,
             "best_5min_w": 300}
    rec = recommend(a, r, rider, registry=Registry(ROOT / "data" / "methods.json"))
    assert rec["session"]["method"] != "ftp_test"
    assert any("unconfirmed" in w for w in rec["warnings"])


def test_suspect_anchor_still_prescribes_a_test():
    a = audit(_low_20min_window("maximal_test"), FTP)
    r = assess({"sleep_hours": 8, "resting_hr_delta_bpm": 0, "subjective_1_10": 8})
    rider = {"ftp": FTP, "base_weeks": 20, "ftp_anchor_age_weeks": 3,
             "best_5min_w": 300}
    rec = recommend(a, r, rider, registry=Registry(ROOT / "data" / "methods.json"))
    assert rec["session"]["method"] == "ftp_test"


def test_critical_flag_outranks_warnings_when_both_present():
    """Regression: insert(0) ordering let a warn-level adherence flag sit
    above the critical one when both stated and planned hours were given."""
    a = audit(FIXTURE, FTP, stated_weekly_hours=9, planned_weekly_hours=9)
    assert a["flags"][0]["id"] == "volume_collapse"
    assert a["flags"][0]["severity"] == "critical"
    severities = [f["severity"] for f in a["flags"]]
    rank = {"critical": 0, "warn": 1, "info": 2}
    assert severities == sorted(severities, key=lambda s: rank[s])
