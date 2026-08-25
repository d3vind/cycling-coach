#!/usr/bin/env python3
"""Daily training brief.

    python scripts/daily_brief.py [--fixture PATH] [--refresh] [--readiness KEY=VAL ...]

Runs the audit over the recent window, assesses readiness, and prints one
suggested session with its reasoning. --refresh fetches a live window from
Strava (STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN in the environment) and falls
back to the committed fixture when credentials are absent or the fetch fails.
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coach.audit import audit                    # noqa: E402
from coach.readiness import assess               # noqa: E402
from coach.recommend import recommend            # noqa: E402
from coach.registry import Registry              # noqa: E402
from coach.sources import strava                 # noqa: E402

RULE = "=" * 72
WINDOW_DAYS = 28
PRIVATE_WINDOW = ROOT / "data" / "private" / "window_28d.json"


def _parse_kv(pairs):
    out = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = None
    return out


def _refresh_window(rider):
    """Fetch a live window into data/private/. Returns it, or None to signal
    the caller to fall back to the committed fixture (reason on stderr)."""
    try:
        client = strava.StravaClient.from_env()
    except strava.MissingCredentials as e:
        print(f"[refresh] {e}; using fixture", file=sys.stderr)
        return None
    end = date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    try:
        window = strava.fetch_window(client, rider.get("strava_athlete_id"),
                                     start, end, rider.get("ftp"))
    except Exception as e:  # the brief must still print on any fetch failure
        print(f"[refresh] fetch failed ({e}); using fixture", file=sys.stderr)
        return None
    if not window["rides"]:
        print("[refresh] no rides with power in the window; using fixture",
              file=sys.stderr)
        return None
    PRIVATE_WINDOW.parent.mkdir(parents=True, exist_ok=True)
    PRIVATE_WINDOW.write_text(json.dumps(window))
    print(f"[refresh] wrote {len(window['rides'])} rides to {PRIVATE_WINDOW}",
          file=sys.stderr)
    return window


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default=str(ROOT / "data" / "fixtures" / "window_28d.json"))
    ap.add_argument("--profile", default=str(ROOT / "data" / "rider.json"))
    ap.add_argument("--refresh", action="store_true",
                    help="fetch a live window from Strava into data/private/ "
                         "(falls back to --fixture without credentials)")
    ap.add_argument("--readiness", action="append")
    ap.add_argument("--goal", default="raise_ftp")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    rider = json.loads(Path(args.profile).read_text())
    window = _refresh_window(rider) if args.refresh else None
    if window is None:
        window = json.loads(Path(args.fixture).read_text())
    ftp = rider.get("ftp", window.get("ftp"))

    a = audit(window, ftp,
              stated_weekly_hours=rider.get("stated_weekly_hours"),
              planned_weekly_hours=rider.get("planned_weekly_hours"))

    rider.setdefault("best_5min_w", a["power_curve"]["best_5min_w"])

    r = assess(_parse_kv(args.readiness))
    rec = recommend(a, r, rider, goal=args.goal, registry=Registry())

    if args.json:
        print(json.dumps({"audit": a, "readiness": r, "recommendation": rec},
                         indent=2, default=float))
        return

    d, pc, ad = a["distribution"], a["power_curve"], a["adherence"]

    print(RULE)
    print(f"DAILY BRIEF   FTP {ftp} W   readiness: {r['state'].upper()}")
    print(RULE)

    print(f"\nRECENT LOAD  ({ad['mean_hours']:.1f} h/wk mean", end="")
    if "vs_stated" in ad:
        print(f", {ad['vs_stated']:.0%} of stated available)", end="")
    else:
        print(")", end="")
    print(f"\n  distribution (pedalling time): "
          f"{d['low']:.0%} low / {d['moderate']:.0%} mod / {d['high']:.0%} high")
    for seg, s in d["by_segment"].items():
        print(f"    {seg:<9} {s['low']:.0%} / {s['moderate']:.0%} / {s['high']:.0%}")
    print(f"  coasting excluded: {d['coasting_hours']:.1f} h")
    print(f"  best 5-min {pc['best_5min_w']:.0f} W ({pc['best_5min_pct_ftp']:.0%} FTP)"
          f"  [{pc['best_5min_provenance']}]")
    print(f"  best 20-min {pc['best_20min_w']:.0f} W -> implies FTP "
          f"{pc['implied_ftp_from_20min']:.0f} W ({pc['anchor_error_pct']:+.0%})")

    if a["flags"]:
        print("\nFLAGS")
        for f in a["flags"]:
            tag = {"critical": "!!", "warn": " !", "info": "  "}[f["severity"]]
            print(f"  {tag} {f['id']}")
            print(f"     {f['detail']}")

    s = rec["session"]
    print(f"\nTODAY  ->  {s['method'] or 'REST'}")
    if s.get("detail"):
        for line in _wrap(s["detail"], 66):
            print(f"     {line}")

    if rec["reasoning"]:
        print("\nWHY")
        for line in rec["reasoning"]:
            for w in _wrap(line, 66):
                print(f"  {w}")

    if rec["warnings"]:
        print("\nNOTES")
        for line in rec["warnings"]:
            wrapped = _wrap(line, 66)
            for i, w in enumerate(wrapped):
                print(f"  - {w}" if i == 0 else f"    {w}")

    print("\n" + RULE)
    print("Suggestion, not instruction. Not medical advice.")


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


if __name__ == "__main__":
    main()
