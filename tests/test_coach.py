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


def test_critical_flag_outranks_warnings_when_both_present():
    """Regression: insert(0) ordering let a warn-level adherence flag sit
    above the critical one when both stated and planned hours were given."""
    a = audit(FIXTURE, FTP, stated_weekly_hours=9, planned_weekly_hours=9)
    assert a["flags"][0]["id"] == "volume_collapse"
    assert a["flags"][0]["severity"] == "critical"
    severities = [f["severity"] for f in a["flags"]]
    rank = {"critical": 0, "warn": 1, "info": 2}
    assert severities == sorted(severities, key=lambda s: rank[s])
