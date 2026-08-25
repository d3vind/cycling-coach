"""Google Health API adapter (Fitbit data).

Returns the shape readiness.assess() expects:

    {"resting_hr_delta_bpm": float,   # vs 30-day baseline
     "hrv_pct_below_baseline": float, # 7-day trend vs 30-day baseline
     "sleep_hours": float,
     "resp_rate_delta": float,
     "subjective_1_10": int|None}

Scopes required:
    .activity_and_fitness.readonly
    .health_metrics_and_measurements.readonly
    .sleep.readonly

Constraints that shape this module (docs/google-health.md has the full list):
  * exercise and sleep page at 25 records, not 10000. Budget for pagination.
  * rollup range caps: 14 days for heart-rate, active-minutes, total-calories,
    calories-in-heart-rate-zone; 90 days for everything else.
  * Fitbit Air reports no weight and no body fat (Aria scales only) and no ECG.
    W/kg therefore needs manual entry or a separate scale integration.
  * devices sync only via the Fitbit mobile app, roughly every 15 minutes while
    it is running. This morning's HRV may simply not exist yet. Return None for
    missing signals -- never zero, never a stale value silently reused.
  * use dailyRollUp for date-bucketed data; it handles DST and travel correctly.
  * some types support true zeros; absent != zero, and conflating them corrupts
    the 30-day baselines everything else depends on.
  * webhooks exist for HRV, resting HR, sleep and exercise. Prefer them to polling.
  * back off exponentially on 429 and 504. Never retry a large failed payload
    immediately.
"""

BASELINE_WINDOW_DAYS = 30
TREND_WINDOW_DAYS = 7


def fetch_readiness(client, user_id, on_date):
    raise NotImplementedError(
        "Wire to the Google Health API. Compute deltas against a "
        f"{BASELINE_WINDOW_DAYS}-day baseline and trends over "
        f"{TREND_WINDOW_DAYS} days -- never decide on a single reading.")
