"""Strava adapter.

Returns the shape audit.audit() expects:

    {"ftp": int,
     "window": [iso_date, iso_date],
     "rides": [{"id","name","date","kind","moving","elapsed",
                "time":[s...], "watts":[w...],
                "provenance": "within_ride"|"race"|"maximal_test"}]}

Provenance defaults to "within_ride" and MUST stay that way unless the rider
explicitly tags a session. See registry v0.2 section 3.3 -- letting a submaximal
best masquerade as a measurement produces confidently wrong diagnoses. The only
promotion path is the explicit provenance_tags argument to fetch_window();
nothing is ever inferred from the activity name, the workout_type field, or
from how hard the ride looks.

  * classify kind by sport_type: VirtualRide -> indoor, Ride -> outdoor.
  * do NOT trust the activity name for anything but display (section 3.5).
  * Zwift virtual terrain distorts distance and elevation; power and time are
    the only trustworthy fields on virtual rides.

Auth is the Strava v3 OAuth2 refresh-token flow. Credentials come from the
environment: STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN.
Access tokens (and any rotated refresh token) are held in memory only and are
never written to disk.

Rate limits: 100 requests / 15 min, 1000 / day. The activity list costs one
request per 200 activities and streams cost one request per ride, so a 28-day
window is roughly 15-20 requests. 429 responses are retried with exponential
backoff; an exhausted daily budget raises immediately instead of spinning.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger(__name__)

TOKEN_URL = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"
ENV_VARS = ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REFRESH_TOKEN")

SPORT_KIND = {"Ride": "outdoor", "VirtualRide": "indoor"}
PROVENANCES = ("within_ride", "race", "maximal_test")
PER_PAGE = 200
DEFAULT_LIMITS = (100, 1000)


class StravaError(Exception):
    """Any failure talking to the Strava API."""


class MissingCredentials(StravaError):
    """Required credentials are absent."""


class NotFound(StravaError):
    """The requested resource does not exist (HTTP 404)."""


class RateLimitExceeded(StravaError):
    """Rate limited and retrying cannot help right now."""


def _urllib_transport(method, url, headers, body):
    """Default HTTP transport. Returns (status, headers_dict, body_bytes)."""
    headers = {"User-Agent": "cycling-coach/0.2", **headers}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()


def _pair(value):
    """Parse an 'a,b' rate-limit header into (int, int), or None."""
    try:
        a, b = str(value).split(",")[:2]
        return int(a.strip()), int(b.strip())
    except (TypeError, ValueError):
        return None


class StravaClient:
    """Authenticated GET client for the Strava v3 API.

    transport, sleep and clock are injectable so tests never touch the
    network or the wall clock. Tokens live in memory only.
    """

    def __init__(self, client_id, client_secret, refresh_token,
                 transport=None, sleep=time.sleep, clock=time.time,
                 max_retries=5):
        if not (client_id and client_secret and refresh_token):
            raise MissingCredentials(
                "client_id, client_secret and refresh_token are all required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._transport = transport or _urllib_transport
        self._sleep = sleep
        self._clock = clock
        self.max_retries = max_retries
        self._access_token = None
        self._expires_at = 0
        self._limits = DEFAULT_LIMITS
        self._usage = None

    @classmethod
    def from_env(cls, environ=None, **kwargs):
        env = os.environ if environ is None else environ
        missing = [n for n in ENV_VARS if not env.get(n)]
        if missing:
            raise MissingCredentials(
                "set " + ", ".join(missing) + " in the environment "
                "(from your Strava API application settings)")
        return cls(env["STRAVA_CLIENT_ID"], env["STRAVA_CLIENT_SECRET"],
                   env["STRAVA_REFRESH_TOKEN"], **kwargs)

    def get(self, path, params=None):
        """GET an API path, refreshing auth and backing off on 429."""
        url = API_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        reauthed = False
        for attempt in range(self.max_retries + 1):
            status, headers, raw = self._transport(
                "GET", url, {"Authorization": "Bearer " + self._token()}, None)
            self._note_usage(headers)
            if 200 <= status < 300:
                return json.loads(raw) if raw else None
            if status == 401 and not reauthed:
                # Access token revoked or expired server-side: one forced
                # refresh, then a second 401 is a real error.
                reauthed = True
                self._access_token = None
                continue
            if status == 429:
                self._check_daily_budget()
                if attempt < self.max_retries:
                    delay = min(900, 2 * 2 ** attempt)
                    log.info("rate limited; backing off %ss", delay)
                    self._sleep(delay)
                    continue
                raise RateLimitExceeded(
                    f"still rate limited after {self.max_retries} retries; "
                    "the 15-minute window resets on the quarter hour")
            if status == 404:
                raise NotFound(f"GET {path} -> 404")
            raise StravaError(f"GET {path} -> HTTP {status}: {raw[:200]!r}")
        raise StravaError(f"GET {path}: retries exhausted")

    def _token(self):
        if not self._access_token or self._clock() >= self._expires_at - 60:
            self._refresh_access_token()
        return self._access_token

    def _refresh_access_token(self):
        body = urllib.parse.urlencode({
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }).encode()
        status, _, raw = self._transport(
            "POST", TOKEN_URL,
            {"Content-Type": "application/x-www-form-urlencoded"}, body)
        if status != 200:
            raise StravaError(f"token refresh failed: HTTP {status}: {raw[:200]!r}")
        tok = json.loads(raw)
        self._access_token = tok["access_token"]
        self._expires_at = tok.get("expires_at") or self._clock() + tok.get("expires_in", 21600)
        # Strava may rotate the refresh token. Keep the newest in memory;
        # never persist it (see .gitignore).
        self._refresh_token = tok.get("refresh_token", self._refresh_token)

    def _note_usage(self, headers):
        h = {str(k).lower(): v for k, v in (headers or {}).items()}
        self._limits = _pair(h.get("x-ratelimit-limit")) or self._limits
        self._usage = _pair(h.get("x-ratelimit-usage")) or self._usage

    def _check_daily_budget(self):
        if self._usage and self._usage[1] >= self._limits[1]:
            raise RateLimitExceeded(
                f"daily request budget exhausted "
                f"({self._usage[1]}/{self._limits[1]}); resets at midnight UTC")


def _as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _epoch_utc(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def fetch_window(client, athlete_id, start, end, ftp, provenance_tags=None):
    """Fetch the [start, end] window of rides with measured power.

    client: StravaClient (or anything with .get(path, params)).
    athlete_id: if not None, verified against the authenticated athlete --
        auditing the wrong account's training must fail loudly, never
        silently. None skips the check (one request cheaper).
    start, end: dates (date, datetime or 'YYYY-MM-DD'), inclusive.
    provenance_tags: {activity_id: "race"|"maximal_test"} for sessions the
        rider has EXPLICITLY tagged. This is the only promotion path
        (registry v0.2 section 3.3); an unknown value raises ValueError.

    Skips, rather than failing the whole window on: non-cycling sport types,
    manual entries, estimated power (device_watts false), and activities
    whose streams carry no watts.
    """
    tags = {}
    for k, v in (provenance_tags or {}).items():
        if v not in PROVENANCES:
            raise ValueError(
                f"provenance for activity {k} must be one of {PROVENANCES}, got {v!r}")
        tags[str(k)] = v

    start_d, end_d = _as_date(start), _as_date(end)

    if athlete_id is not None:
        me = client.get("/athlete") or {}
        if str(me.get("id")) != str(athlete_id):
            raise StravaError(
                f"authenticated athlete {me.get('id')} != requested {athlete_id}; "
                "check whose refresh token is in the environment")
    base = {"after": _epoch_utc(start_d),
            "before": _epoch_utc(end_d + timedelta(days=1)),
            "per_page": PER_PAGE}
    activities = []
    page = 1
    while True:
        batch = client.get("/athlete/activities", {**base, "page": page}) or []
        activities.extend(batch)
        if len(batch) < PER_PAGE:
            break
        page += 1

    rides = []
    for a in activities:
        kind = SPORT_KIND.get(a.get("sport_type") or a.get("type"))
        if kind is None:
            continue
        if a.get("manual"):
            # Manual entries have no streams.
            continue
        if not a.get("device_watts"):
            # Estimated watts are modelled, not measured. Letting them into
            # the power curve is the same failure mode as trusting a
            # within-ride best as a maximal test.
            log.info("skipping %s: no measured power", a.get("id"))
            continue
        try:
            streams = client.get(f"/activities/{a['id']}/streams",
                                 {"keys": "time,watts", "key_by_type": "true"})
        except NotFound:
            log.info("skipping %s: no streams", a.get("id"))
            continue
        time_s = ((streams or {}).get("time") or {}).get("data") or []
        watts = ((streams or {}).get("watts") or {}).get("data") or []
        if not time_s or not watts:
            log.info("skipping %s: empty watts stream", a.get("id"))
            continue
        n = min(len(time_s), len(watts))
        rides.append({
            "id": str(a["id"]),
            "name": a.get("name", ""),  # display metadata ONLY (v0.2 3.5)
            "date": str(a.get("start_date_local") or a.get("start_date", ""))[:10],
            "kind": kind,
            "moving": a.get("moving_time", 0),
            "elapsed": a.get("elapsed_time", 0),
            "time": time_s[:n],
            # None marks recording dropouts; as 0 they land in coasting,
            # excluded from the distribution (v0.2 3.1), not in "low".
            "watts": [0 if w is None else w for w in watts[:n]],
            "provenance": tags.get(str(a["id"]), "within_ride"),
        })

    rides.sort(key=lambda r: r["date"], reverse=True)
    return {
        "ftp": ftp,
        "window": [start_d.isoformat(), end_d.isoformat()],
        "note": (f"Fetched from the Strava v3 API, window ending {end_d.isoformat()}. "
                 "Provenance is within_ride unless the rider explicitly tagged "
                 "the session (registry v0.2 section 3.3)."),
        "rides": rides,
    }
