"""Registry loader and the rules layer.

Two jobs:
  1. Load methods.json and answer "is this method allowed for this rider today?"
  2. Validate any generated plan AFTER generation against hard_limits.

Job 2 exists because a generative model will cheerfully produce a 25-hour week
if the prompt drifts. Prompting is not a control. This is the control.
"""

import json
from pathlib import Path

from .readiness import GREEN, AMBER, RED

_ORDER = {RED: 0, AMBER: 1, GREEN: 2, "unknown": 2}

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "methods.json"


class Registry:
    def __init__(self, path=None):
        self.data = json.loads(Path(path or DEFAULT_PATH).read_text())
        self.methods = {m["id"]: m for m in self.data["methods"]}
        self.limits = self.data["hard_limits"]

    def eligible(self, method_id, rider, readiness_state):
        """Return (ok: bool, reasons: list[str])."""
        m = self.methods[method_id]
        reasons = []

        need = m.get("readiness_min", AMBER)
        if _ORDER[readiness_state] < _ORDER[need]:
            reasons.append(f"needs {need} readiness, rider is {readiness_state}")

        pre = m.get("prerequisites", {})
        if "min_base_weeks" in pre and rider.get("base_weeks", 0) < pre["min_base_weeks"]:
            reasons.append(f"needs {pre['min_base_weeks']}+ weeks of base")
        if pre.get("requires_ftp_anchor") and not rider.get("ftp"):
            reasons.append("no FTP anchor set")
        if "ftp_anchor_max_age_weeks" in pre:
            age = rider.get("ftp_anchor_age_weeks")
            if age is None or age > pre["ftp_anchor_max_age_weeks"]:
                reasons.append(
                    f"FTP anchor older than {pre['ftp_anchor_max_age_weeks']} weeks")
        if "min_training_history_weeks" in pre and \
                rider.get("training_history_weeks", 0) < pre["min_training_history_weeks"]:
            reasons.append("insufficient training history")
        if pre.get("fuelling_plan_confirmed") and not rider.get("fuelling_plan_confirmed"):
            reasons.append("no fuelling plan confirmed")

        for c in m.get("contraindications", []):
            if c == "red_readiness" and readiness_state == RED:
                reasons.append("contraindicated on red readiness")
            elif c == "first_season_user" and rider.get("first_season"):
                reasons.append("not available to first-season riders")
            elif c == "first_structured_session" and rider.get("first_structured_session"):
                reasons.append("not appropriate as a first structured session")
            elif c == "illness_flag" and rider.get("illness_flag"):
                reasons.append("illness flagged")
            elif c == "indoor_session_cap_under_150min" and \
                    rider.get("indoor_only") and rider.get("indoor_cap_min", 999) < 150:
                reasons.append(
                    "cannot be executed within the rider's indoor session cap -- "
                    "flag the durability gap rather than substituting silently")

        return (not reasons), reasons

    def available(self, rider, readiness_state):
        return [mid for mid in self.methods
                if self.eligible(mid, rider, readiness_state)[0]]

    def check_targets(self, method_id, rider):
        """v0.2 3.3 target sanity check.

        Reject any prescription at or above the rider's best 5-min power for
        reps longer than 90 s. Either it is undoable or the anchor is wrong.
        """
        m = self.methods[method_id]
        s = m.get("structure", {})
        ftp, b5 = rider.get("ftp"), rider.get("best_5min_w")
        if not (ftp and b5):
            return True, []

        work_s = s.get("work_s")
        if isinstance(work_s, list):
            work_s = max(work_s)
        pct = s.get("work_pct")
        if not (work_s and pct and work_s > 90):
            return True, []

        target = ftp * pct[1]
        if target >= b5:
            return False, [
                f"{method_id} targets {target:.0f} W for {work_s:.0f}s reps, at or "
                f"above best 5-min power ({b5:.0f} W). Undoable as written, or the "
                f"FTP anchor is too high."]
        return True, []

    def validate_plan(self, week):
        """week: list of {'method': id, 'hard': bool, 'hours': float}.

        Returns list of violations. Run this AFTER generation, always.
        """
        v = []
        L = self.limits

        if len(week) > L["max_sessions_per_week"]:
            v.append(f"{len(week)} sessions exceeds max {L['max_sessions_per_week']}")

        hard = [d for d in week if d.get("hard")]
        if len(hard) > L["max_hard_sessions_per_week"]:
            v.append(f"{len(hard)} hard sessions exceeds max "
                     f"{L['max_hard_sessions_per_week']}")

        run = best = 0
        for d in week:
            run = run + 1 if d.get("hard") else 0
            best = max(best, run)
        if best > L["max_consecutive_hard_days"]:
            v.append(f"{best} consecutive hard days exceeds max "
                     f"{L['max_consecutive_hard_days']}")

        counts = {}
        for d in week:
            counts[d["method"]] = counts.get(d["method"], 0) + 1
        for mid, n in counts.items():
            cap = self.methods.get(mid, {}).get("max_per_week")
            if cap and n > cap:
                v.append(f"{mid} scheduled {n}x, max {cap}")

        ids = set(counts)
        for mid in ids:
            rule = self.methods[mid].get("pairing_rule")
            if rule == "must_pair_with_vo2max_session_same_week":
                if not any(self.methods[o].get("category") == "vo2max" for o in ids):
                    v.append(f"{mid} present with no VO2max session that week -- "
                             f"raises the floor without raising the ceiling")

        return v
