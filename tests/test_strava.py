"""Strava adapter tests. All responses are scripted -- nothing touches the
live API. The two assertions the registry cares most about: provenance is
"within_ride" on every returned ride unless explicitly tagged (v0.2 3.3),
and kind comes from sport_type, never from the activity name (v0.2 3.5).
"""

import importlib.util
import json
import os
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coach.audit import audit
from coach.sources import strava

TOKEN_PATH = "/oauth/token"
ACT_PATH = "/api/v3/athlete/activities"
ATHLETE_PATH = "/api/v3/athlete"


class FakeTransport:
    """Scripted HTTP double keyed by URL path. Responses queue per path; the
    last response repeats so a single entry can serve any number of calls."""

    def __init__(self):
        self.routes = {}
        self.requests = []

    def add(self, path, *responses):
        self.routes.setdefault(path, []).extend(responses)

    def __call__(self, method, url, headers, body):
        self.requests.append((method, url, headers, body))
        queue = self.routes.get(urllib.parse.urlsplit(url).path)
        assert queue, f"unexpected request: {method} {url}"
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def paths(self):
        return [urllib.parse.urlsplit(u).path for _, u, _, _ in self.requests]


def _resp(payload, status=200, usage="1,10", limit="100,1000"):
    headers = {"X-RateLimit-Limit": limit, "X-RateLimit-Usage": usage,
               "Content-Type": "application/json"}
    return (status, headers, json.dumps(payload).encode())


def token_resp(access_token="at-1"):
    return _resp({"access_token": access_token, "expires_at": 9_999_999_999,
                  "refresh_token": "rt-rotated"})


def act(aid, sport="Ride", name="Morning Ride", day="2026-08-20", **over):
    a = {"id": aid, "name": name, "sport_type": sport,
         "start_date_local": f"{day}T09:00:00Z",
         "start_date": f"{day}T07:00:00Z",
         "moving_time": 3600, "elapsed_time": 3720,
         "device_watts": True, "manual": False, "workout_type": None}
    a.update(over)
    return a


def stream_resp(time=None, watts=None):
    if time is None:
        time = list(range(0, 300, 30))
    if watts is None:
        watts = [0, 150, 160, 155, 240, 235, 150, 0, 145, 150]
    return _resp({"time": {"data": time}, "watts": {"data": watts},
                  "distance": {"data": [i * 10 for i in range(len(time))]}})


def make_client(transport, sleeps=None, **kw):
    return strava.StravaClient(
        "cid", "csec", "rtok", transport=transport,
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
        clock=lambda: 1_000_000.0, **kw)


def two_ride_transport():
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp([act(101, "Ride", name="Coffee spin", day="2026-08-19"),
                           act(202, "VirtualRide", name="Zwift - Cardinal",
                               day="2026-08-20")]))
    t.add("/api/v3/activities/101/streams", stream_resp())
    t.add("/api/v3/activities/202/streams", stream_resp())
    return t


def fetch(t, athlete_id=None, tags=None, **client_kw):
    return strava.fetch_window(make_client(t, **client_kw), athlete_id,
                               "2026-07-28", "2026-08-25", 255,
                               provenance_tags=tags)


# ---------------------------------------------------------------- provenance

def test_provenance_is_within_ride_on_every_ride():
    w = fetch(two_ride_transport())
    assert len(w["rides"]) == 2
    assert all(r["provenance"] == "within_ride" for r in w["rides"])


def test_name_and_workout_type_never_promote_provenance():
    """An activity shouting RACE / MAX TEST in its name, with a workout_type
    set, is still within_ride. Names are display metadata only."""
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp([act(7, "VirtualRide",
                               name="RACE DAY - 5 min MAX TEST!!",
                               workout_type=11)]))
    t.add("/api/v3/activities/7/streams", stream_resp())
    r = fetch(t)["rides"][0]
    assert r["provenance"] == "within_ride"
    assert r["kind"] == "indoor"
    assert r["name"] == "RACE DAY - 5 min MAX TEST!!"


def test_explicit_tag_is_the_only_promotion_path():
    w = fetch(two_ride_transport(), tags={"202": "maximal_test", 101: "race"})
    by_id = {r["id"]: r["provenance"] for r in w["rides"]}
    assert by_id == {"202": "maximal_test", "101": "race"}


def test_unknown_provenance_tag_raises():
    with pytest.raises(ValueError):
        fetch(two_ride_transport(), tags={"101": "sufferfest"})


# ------------------------------------------------------------ classification

def test_virtualride_is_indoor_and_ride_is_outdoor():
    w = fetch(two_ride_transport())
    kinds = {r["id"]: r["kind"] for r in w["rides"]}
    assert kinds == {"101": "outdoor", "202": "indoor"}
    assert w["ftp"] == 255
    assert w["window"] == ["2026-07-28", "2026-08-25"]


def test_non_cycling_sport_types_are_ignored_without_stream_fetches():
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp([act(1, "Run"), act(2, "WeightTraining"),
                           act(3, "Walk"), act(4, "Ride")]))
    t.add("/api/v3/activities/4/streams", stream_resp())
    w = fetch(t)
    assert [r["id"] for r in w["rides"]] == ["4"]
    assert not any("/activities/1/" in p or "/activities/2/" in p
                   or "/activities/3/" in p for p in t.paths())


def test_rides_without_power_are_skipped_not_fatal():
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp([
        act(1, device_watts=False),          # estimated power
        act(2, manual=True),                 # manual entry, no streams
        act(3),                              # streams present but no watts
        act(4),                              # streams 404
        act(5, day="2026-08-21"),            # good
    ]))
    t.add("/api/v3/activities/3/streams",
          _resp({"time": {"data": [0, 10, 20]},
                 "distance": {"data": [0, 50, 100]}}))
    t.add("/api/v3/activities/4/streams", _resp({"message": "Not Found"}, status=404))
    t.add("/api/v3/activities/5/streams", stream_resp())
    w = fetch(t)
    assert [r["id"] for r in w["rides"]] == ["5"]
    # no stream requests were spent on activities skippable from the summary
    assert not any("/activities/1/" in p or "/activities/2/" in p
                   for p in t.paths())


def test_null_watts_become_zero_and_streams_align():
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp([act(9)]))
    t.add("/api/v3/activities/9/streams",
          stream_resp(time=[0, 10, 20, 30, 40], watts=[200, None, 210, None]))
    r = fetch(t)["rides"][0]
    assert r["watts"] == [200, 0, 210, 0]
    assert r["time"] == [0, 10, 20, 30]


# ------------------------------------------------------------------- OAuth2

def test_refresh_token_flow_and_bearer_header():
    t = two_ride_transport()
    fetch(t)
    token_posts = [r for r in t.requests
                   if urllib.parse.urlsplit(r[1]).path == TOKEN_PATH]
    assert len(token_posts) == 1, "one refresh serves the whole window"
    method, _, _, body = token_posts[0]
    assert method == "POST"
    fields = urllib.parse.parse_qs(body.decode())
    assert fields["grant_type"] == ["refresh_token"]
    assert fields["refresh_token"] == ["rtok"]
    assert fields["client_id"] == ["cid"]
    assert fields["client_secret"] == ["csec"]
    assert urllib.parse.urlsplit(t.requests[0][1]).path == TOKEN_PATH
    gets = [r for r in t.requests if r[0] == "GET"]
    assert gets
    assert all(r[2]["Authorization"] == "Bearer at-1" for r in gets)


def test_401_refreshes_once_and_retries():
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp("at-1"), token_resp("at-2"))
    t.add(ACT_PATH, _resp({"message": "unauthorized"}, status=401), _resp([]))
    w = fetch(t)
    assert w["rides"] == []
    token_posts = [p for p in t.paths() if p == TOKEN_PATH]
    assert len(token_posts) == 2
    last_get = [r for r in t.requests if r[0] == "GET"][-1]
    assert last_get[2]["Authorization"] == "Bearer at-2"


def test_persistent_401_is_an_error_not_a_loop():
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp({"message": "unauthorized"}, status=401))
    with pytest.raises(strava.StravaError) as e:
        make_client(t).get("/athlete/activities")
    assert "401" in str(e.value)


def test_missing_credentials_raise_with_variable_names():
    with pytest.raises(strava.MissingCredentials) as e:
        strava.StravaClient.from_env(environ={})
    for name in strava.ENV_VARS:
        assert name in str(e.value)
    with pytest.raises(strava.MissingCredentials):
        strava.StravaClient.from_env(environ={"STRAVA_CLIENT_ID": "x"})
    with pytest.raises(strava.MissingCredentials):
        strava.StravaClient("", "secret", "token")


def test_athlete_id_mismatch_fails_loudly():
    t = two_ride_transport()
    t.add(ATHLETE_PATH, _resp({"id": 99}))
    with pytest.raises(strava.StravaError, match="athlete"):
        fetch(t, athlete_id=42)

    t2 = two_ride_transport()
    t2.add(ATHLETE_PATH, _resp({"id": 99}))
    assert len(fetch(t2, athlete_id="99")["rides"]) == 2


# --------------------------------------------------------------- rate limits

def test_429_backs_off_exponentially_then_succeeds():
    sleeps = []
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp({}, status=429, usage="100,50"),
          _resp({}, status=429, usage="100,51"), _resp([]))
    assert make_client(t, sleeps=sleeps).get("/athlete/activities") == []
    assert sleeps == [2, 4]


def test_429_exhausted_retries_raise():
    sleeps = []
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp({}, status=429, usage="100,50"))
    with pytest.raises(strava.RateLimitExceeded):
        make_client(t, sleeps=sleeps, max_retries=3).get("/athlete/activities")
    assert sleeps == [2, 4, 8]


def test_exhausted_daily_budget_raises_without_sleeping():
    sleeps = []
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp({}, status=429, usage="100,1000"))
    with pytest.raises(strava.RateLimitExceeded, match="daily"):
        make_client(t, sleeps=sleeps).get("/athlete/activities")
    assert sleeps == []


# ------------------------------------------------------- window and plumbing

def test_pagination_and_date_bounds():
    page1 = [act(9000 + i, "Run") for i in range(199)] + \
            [act(1, "Ride", day="2026-08-10")]
    page2 = [act(2, "VirtualRide", day="2026-08-12")]
    t = FakeTransport()
    t.add(TOKEN_PATH, token_resp())
    t.add(ACT_PATH, _resp(page1), _resp(page2))
    t.add("/api/v3/activities/1/streams", stream_resp())
    t.add("/api/v3/activities/2/streams", stream_resp())
    w = fetch(t)

    assert [r["date"] for r in w["rides"]] == ["2026-08-12", "2026-08-10"]

    list_queries = [urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
                    for _, u, _, _ in t.requests
                    if urllib.parse.urlsplit(u).path == ACT_PATH]
    assert [q["page"][0] for q in list_queries] == ["1", "2"]
    q = list_queries[0]
    after = int(datetime(2026, 7, 28, tzinfo=timezone.utc).timestamp())
    before = int(datetime(2026, 8, 26, tzinfo=timezone.utc).timestamp())
    assert int(q["after"][0]) == after
    assert int(q["before"][0]) == before


def test_fetched_window_feeds_audit():
    a = audit(fetch(two_ride_transport()), 255)
    assert a["distribution"]["basis"] == "pedalling_time"
    assert set(a["distribution"]["by_segment"]) == {"indoor", "outdoor"}
    assert a["power_curve"]["best_5min_provenance"] == "within_ride"


# ---------------------------------------------------------------------- CLI

def _load_daily_brief():
    spec = importlib.util.spec_from_file_location(
        "daily_brief_under_test", ROOT / "scripts" / "daily_brief.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_daily_brief_refresh_falls_back_without_credentials():
    env = {k: v for k, v in os.environ.items() if not k.startswith("STRAVA_")}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "daily_brief.py"), "--refresh"],
        capture_output=True, text=True, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "DAILY BRIEF" in proc.stdout
    assert "using fixture" in proc.stderr


def test_daily_brief_refresh_writes_private_window(tmp_path, monkeypatch, capsys):
    db = _load_daily_brief()
    fixture = json.loads((ROOT / "data" / "fixtures" / "window_28d.json").read_text())

    class StubClient:
        @classmethod
        def from_env(cls, **kw):
            return cls()

    monkeypatch.setattr(db.strava, "StravaClient", StubClient)
    monkeypatch.setattr(db.strava, "fetch_window",
                        lambda client, athlete_id, start, end, ftp, **kw: fixture)
    monkeypatch.setattr(db, "PRIVATE_WINDOW", tmp_path / "window_28d.json")
    monkeypatch.setattr(sys, "argv", ["daily_brief.py", "--refresh"])
    db.main()
    written = json.loads((tmp_path / "window_28d.json").read_text())
    assert len(written["rides"]) == len(fixture["rides"])
    assert "DAILY BRIEF" in capsys.readouterr().out


def test_daily_brief_refresh_falls_back_on_empty_window(monkeypatch, capsys):
    db = _load_daily_brief()

    class StubClient:
        @classmethod
        def from_env(cls, **kw):
            return cls()

    monkeypatch.setattr(db.strava, "StravaClient", StubClient)
    monkeypatch.setattr(db.strava, "fetch_window",
                        lambda *a, **kw: {"ftp": 255, "window": [], "rides": []})
    assert db._refresh_window({"ftp": 255}) is None
    assert "no rides" in capsys.readouterr().err
