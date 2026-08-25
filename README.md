# cycling-coach

An evidence-graded training engine for cyclists. It reads power files, works out
what stimulus is actually missing, and suggests one session for today.

The design premise is that a generative model should not be trusted to prescribe
training. It will happily produce a 25-hour week, or five VO2max days for someone
six weeks off the couch, if the prompt drifts. So the decision layer here is
deterministic and the rules are enforced in code. A language model may later
phrase the output or vary the workout, but only inside these bounds.

## Status

Early. The analysis layer works and is tested. sources/strava.py is
implemented (OAuth2 refresh-token flow, credentials from the environment);
sources/google_health.py remains a documented interface. The fixture in
data/fixtures/ is a real 28-day window to develop against without
credentials.

Every threshold in the registry has been validated against exactly one athlete.
They are conventions, not findings. Do not ship them as defaults without
calibrating against a real population.

## Quick start

    python3 -m venv .venv && source .venv/bin/activate
    pip install pytest
    python3 -m pytest tests/ -q

    python3 scripts/daily_brief.py \
      --readiness sleep_hours=7.5 \
      --readiness resting_hr_delta_bpm=2 \
      --readiness subjective_1_10=8

Add --refresh to fetch a live 28-day window from Strava into data/private/
(gitignored). It needs STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET and
STRAVA_REFRESH_TOKEN in the environment, and falls back to the committed
fixture when they are absent or the fetch fails.

Output:

    DAILY BRIEF   FTP 255 W   readiness: GREEN

    RECENT LOAD  (3.7 h/wk mean, 42% of stated available)
      distribution (pedalling time): 54% low / 36% mod / 10% high
        indoor    44% / 48% / 8%
        outdoor   58% / 31% / 11%
      best 5-min 312 W (122% FTP)  [within_ride]

    FLAGS
      !! volume_collapse
         completing 3.7 h/wk against 9 h stated available (42%).
       ! gray_zone_segment_indoor
         indoor sessions are 48% moderate -- masked by the aggregate

    TODAY  ->  endurance_z2
         142-191 W, 60-120 min

## Layout

    docs/TRAINING_METHODS_REGISTRY.md   the knowledge base -- evidence, grades, sources
    data/methods.json                   machine layer the engine consumes
    src/coach/zones.py                  zone model, session classification
    src/coach/audit.py                  distribution, detectors, power curve, adherence
    src/coach/readiness.py              health signals -> green/amber/red
    src/coach/registry.py               eligibility + the post-generation rules layer
    src/coach/recommend.py              daily decision
    src/coach/sources/                  Strava adapter; Google Health interface
    scripts/daily_brief.py              CLI

methods.json and the registry markdown share IDs. The split is deliberate: the
prose carries nuance (contested findings, effect sizes, contraindications) that
JSON cannot, and the JSON carries only what a generator needs to build a session.

## Four things this gets right that most training tools don't

**Distribution is computed over pedalling time, not elapsed time.** Counting
zero-watt coasting as low intensity inflates the easy bucket outdoors and hides
gray-zone patterns. The validation athlete read 29.4% moderate on elapsed time
and 35.8% on pedalling time -- passing on one basis, flagging on the other.

**Distribution is checked per segment.** The same athlete's aggregate looked
borderline while his indoor block alone was 48% moderate. Outdoor volume masked
it. Aggregate hides the exact failure the detector exists to catch.

**Power-curve points carry provenance.** A 5-minute best pulled from inside a
long endurance ride is a floor, not a measurement. Earlier versions let one drive
a limiter diagnosis and produced a confident, wrong recommendation. Now
within_ride values cannot trigger a diagnosis alone; the engine says "go do a
5-min max test" instead of guessing.

**Volume adherence is evaluated before structure.** No interval-selection change
competes with a 2x volume gap. If someone is completing 42% of their stated
hours, the answer is not a different workout.

## Safety posture

This is a training tool, not a medical device. Specifics:

- Prerequisites and contraindications are enforced in registry.eligible(), not
  merely documented. A rider with no base cannot receive VO2max intervals.
- registry.validate_plan() runs **after** generation. Prompting is not a control.
- No intensity prescription without an FTP anchor set within 8 weeks.
  Percentages of a wrong anchor are actively harmful.
- Interval targets are sanity-checked against known maximal power. A prescription
  at or above best 5-min power for reps over 90 s is rejected.
- Missing health data returns unknown, never a green light. Fitbit syncs only
  when its app has run; this morning's HRV may simply not exist.
- Weight loss prescription and W/kg targets are in the registry's forbid list.
- Readiness output is framed as suggestion. Consumer HRV and sleep scores drive
  real anxiety and, in some users, compulsive exercise. No streak mechanics on
  hard training.

Escalation paths (chest pain, syncope, persistent elevated resting HR with
symptoms) route to "see a clinician," never to a modified workout.

## Data

data/fixtures/window_28d.json contains real ride data -- power streams, dates,
ride names -- published with the athlete's consent.

## License

MIT. The training methods registry cites peer-reviewed work throughout; the
citations are in docs/TRAINING_METHODS_REGISTRY.md and the papers are not mine.
