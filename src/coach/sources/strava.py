"""Strava adapter.

Returns the shape audit.audit() expects:

    {"ftp": int,
     "window": [iso_date, iso_date],
     "rides": [{"id","name","date","kind","moving","elapsed",
                "time":[s...], "watts":[w...],
                "provenance": "within_ride"|"race"|"maximal_test"}]}

Provenance defaults to "within_ride" and MUST stay that way unless the rider
explicitly tags a session. See registry v0.2 section 3.3 -- letting a submaximal
best masquerade as a measurement produces confidently wrong diagnoses.

  * classify kind by sport_type: VirtualRide -> indoor, Ride -> outdoor.
  * do NOT trust the activity name for anything but display (section 3.5).
  * Zwift virtual terrain distorts distance and elevation; power and time are
    the only trustworthy fields on virtual rides.
"""

def fetch_window(client, athlete_id, start, end, ftp):
    raise NotImplementedError(
        "Wire to your Strava client. data/fixtures/ has a real 28-day example "
        "to develop against.")
