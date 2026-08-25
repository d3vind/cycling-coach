# Cycling Training Methods Registry

**Version:** 0.2
**Last updated:** 2026-08-25
**Purpose:** The canonical, evidence-graded knowledge base that the interval-generation engine reasons over. This document is the *why*; `methods.json` is the *what* the generator consumes.

---

## 0. How to maintain this

This is a living document. The discipline that keeps it useful:

1. **Nothing enters without a grade and a source.** If it came from a coaching blog, it's grade C or D and labelled as such. Coaching wisdom is allowed — it just isn't allowed to masquerade as evidence.
2. **Effect sizes, not adjectives.** "Improves FTP" is useless to a generator. "+8.4% 40-min power over 12 weeks (n=30, trained cyclists ~3.3 W/kg)" is actionable.
3. **Every method declares prerequisites and contraindications.** A generator that can't refuse to prescribe something is dangerous in a public app.
4. **Contested findings stay contested.** Do not resolve a genuine scientific disagreement by picking the answer you like. Record both, give the practical default, flag the uncertainty in the entry.
5. **Bump the version and log the change.** See §8.
6. **Never let a derived number acquire the authority of a measured one.** A figure computed from a submaximal effort is a floor, not a measurement. Once it enters a summary it will get quoted as fact. Carry provenance with every number or the engine will confidently diagnose the wrong limiter — see §3.3, which exists because exactly that happened during development.

### Evidence grading scale

| Grade | Meaning |
|---|---|
| **A** | Multiple peer-reviewed RCTs or a systematic review in trained cyclists/endurance athletes. Effect replicated across labs. |
| **B** | At least one good peer-reviewed trial in a relevant population, or strong consistent observational/field data. Not yet replicated broadly. |
| **C** | Mechanistically plausible, widely used by credible coaches, but thin or conflicting direct evidence. |
| **D** | Practice-based convention. Include only if useful and harmless; never present to users as science. |

---

## 1. Method entries

Each entry is the human-readable record. Machine parameters live in `methods.json` under the same `id`.

---

### `endurance_z2` — Low-intensity endurance
**Category:** aerobic base · **Grade:** A

**Prescription:** Continuous riding at 56–75% FTP, 60–300 min. No surges. Should be conversational.

**Why it's in here:** The foundation every distribution model rests on. Low-intensity volume drives mitochondrial density, capillarisation, fat oxidation, and — critically — the *fatigue resistance* that determines power output late in a race. It is also what allows high-intensity sessions to be genuinely high-intensity.

**Evidence:** The 2024 systematic review by Nøst, Aune & van den Tillaar (*Sports* 12(12):326, DOI 10.3390/sports12120326) found distributions of roughly 75–80% low-intensity / 15–20% high-intensity most beneficial for VO2max and work economy. Seiler's body of work on intensity distribution is the underlying literature.

**Prerequisites:** None. Safe entry point for any user.

**Contraindications:** None, but duration must scale to the user's current longest ride — do not jump a user from 90 min to 4 h.

**Engine selection logic:** Default fill for any unallocated session. Should constitute 70–80% of prescribed *time* in most plans.

---

### `vo2_short_short_30_15` — Rønnestad 30/15 short intervals
**Category:** VO2max · **Grade:** A · **⭐ Highest evidence-to-effort ratio in the registry**

**Prescription:** 3 sets × 13 reps of (30 s at power-at-VO2max ≈ 118–128% FTP / 15 s at ~55–60% FTP). 3 min easy between sets. ~60 min total with warm-up/cool-down.

**Evidence:** Rønnestad, Hansen, Vegge, Tønnessen & Slettaløkken, *Scandinavian Journal of Medicine & Science in Sports* 2015; 25(2):143–151 (DOI 10.1111/sms.12165). Effort-matched design in trained/well-trained cyclists (VO2max ~66 mL/kg/min, ~3.4–3.7 W/kg — note how closely this matches a typical committed amateur). Over 10 weeks with 2 HIT sessions/week: **VO2max +8.7%, peak power +8.5%, 40-min all-out power +12%.** The effort-matched comparison group doing 4×5 min gained only ~+2.6% VO2max and +4% 40-min power.

**Why this matters for the generator:** Same perceived effort, roughly triple the adaptation. If a user has one hard session to spend, this is usually it.

**Prerequisites:** Established aerobic base (≥6 weeks consistent riding); a known FTP or equivalent anchor; ERG-capable trainer strongly preferred (the 30 s blocks are hard to pace outdoors).

**Contraindications:** Do not prescribe on a red readiness day. Do not prescribe more than 2–3×/week outside a deliberate, time-boxed block. Not appropriate as a user's first-ever structured session.

**Engine selection logic:** Primary VO2max stimulus. Alternate with `vo2_short_short_40_20` for variety without changing the physiological target.

---

### `vo2_short_short_40_20` — 40/20 variant
**Category:** VO2max · **Grade:** B

**Prescription:** 3 sets × 8 reps of (40 s at ~118–125% FTP / 20 s easy). 3–4 min between sets.

**Evidence:** Same mechanistic family as 30/15 and widely used, but the specific 40/20 protocol has less direct effort-matched trial data than 30/15. Treat as a well-supported variant rather than an independently proven protocol.

**Prerequisites / contraindications:** As `vo2_short_short_30_15`.

**Engine selection logic:** Rotate with 30/15 to manage monotony. Slightly higher accumulated time-at-intensity per rep — useful as a progression.

---

### `vo2_long_intervals` — Classic 4×5 / 5×5 min VO2max
**Category:** VO2max · **Grade:** A (effective) / B (relative to short-short)

**Prescription:** 4–5 reps × 4–5 min at 105–120% FTP, equal or near-equal recovery.

**Evidence:** Effective in absolute terms and used as the VO2max arm in Almquist et al. 2022 (below). But directly inferior to short intervals when effort is matched (Rønnestad 2015, above).

**Prerequisites:** Same as short-short, plus higher pacing skill — users routinely blow up on rep 1.

**Engine selection logic:** Use when the user explicitly prefers longer efforts, when specificity to sustained climbing matters, or as variety within a VO2 phase. Do not present as equivalent to short-short for pure VO2 adaptation.

---

### `threshold_2x20` — Threshold / FTP intervals
**Category:** threshold · **Grade:** B

**Prescription:** 2×20 min at 94–105% FTP, 5–10 min easy between. Progressions: 3×15 → 2×20 → 2×25 → 3×20.

**Evidence:** Long-standing and effective for raising power at threshold; Almquist 2022 included moderate/threshold work in its successful 12-week protocol. Weaker independent effect-size data than the VO2max short-interval literature.

**Prerequisites:** Base established; FTP anchor set within the last ~8 weeks.

**Contraindications:** Accumulating these *alongside* frequent moderate-hard riding is the classic "gray zone" trap — see §3.

**Engine selection logic:** Second quality session of the week. Increase share during a specificity/peak phase.

---

### `sweetspot_intervals` — Sweet spot
**Category:** sub-threshold · **Grade:** B

**Prescription:** 3×15 or 4×12 min at 84–94% FTP, 4–5 min easy between.

**Evidence:** Best stimulus-per-hour available to a time-crunched rider; the 84–94% band derives from Coggan's zone work. Included in the successful Almquist 2022 protocol.

**Important caveat the generator must encode:** Sweet spot raises the floor but does not raise the ceiling. A plan built *only* on sweet spot reliably plateaus, because maximal aerobic power is never challenged. Widely-quoted "sweet spot gains you 15–25 W" figures come from coaching blogs, not trials — do not surface them as evidence.

**Prerequisites:** Base established.

**Contraindications:** Should not exceed ~2 sessions/week, and should not be the *only* intensity in a block longer than ~6 weeks.

**Engine selection logic:** Workhorse for users with <7 h/week. Always pair with at least one true VO2max session per week.

---

### `over_unders` — Over-under intervals
**Category:** threshold · **Grade:** C

**Prescription:** 3×9–12 min alternating 2 min at 95–100% FTP / 1 min at 105–110% FTP.

**Evidence:** Mechanistically sound (lactate shuttling / clearance under repeated supra-threshold load) and coach-standard, but limited direct trial evidence for superiority over steady threshold work.

**Prerequisites:** Comfortable completing `threshold_2x20`.

**Engine selection logic:** Race-specificity phase, especially for riders facing surging group racing or rolling terrain.

---

### `durability_long_ride` — Long ride with late-ride efforts
**Category:** fatigue resistance · **Grade:** B

**Prescription:** 2.5–5 h at Z2, with 2–4 × 8–15 min at tempo/sweet spot placed in the **final third** of the ride, after ≥25 kJ/kg of work.

**Evidence:** Muriel et al., *International Journal of Sports Physiology and Performance* 2022; 17(1):22–30 (DOI 10.1123/ijspp.2021-0082) found WorldTour and ProTeam riders had comparable maximal power "when fatigue is not considered," but WorldTour riders produced greater power as accumulated work rose from 0 to 35 kJ/kg. A companion field study (Muriel et al., *IJSPP* 2023; 18(1):99; n=12 pros) quantified the decay: 40-min TT power fell from 386 W fresh to 375 W after ~4 h / 40 kJ/kg.

**Why the generator must not skip this:** Races are decided on power *late*. A plan that optimises fresh FTP and ignores durability optimises the wrong number. This is also the quality most often lost when a rider moves to short indoor sessions.

**Prerequisites:** Current longest ride within ~30% of target duration. Fuelling plan in place (see §4).

**Contraindications:** Indoor 60-min-capped users cannot execute this — flag the gap explicitly rather than silently substituting.

**Engine selection logic:** Weekly weekend anchor whenever schedule and daylight allow.

---

### `block_periodization_vo2` — Front-loaded VO2 block
**Category:** periodization structure · **Grade:** C (genuinely contested)
**⚠️ Contested — do not present as settled.**

**Prescription:** Week 1: 5 VO2max sessions Mon–Fri, easy weekend. Weeks 2–4: 1 VO2 + 2 sub-threshold + Z2 maintenance. Recovery week follows.

**Evidence — positive:** Rønnestad, Ellefsen, Nygaard et al., *Scand J Med Sci Sports* 2014; 24(2):327–335 (DOI 10.1111/sms.12016): block periodization gave VO2max +8.8% vs +3.7% traditional, 40-min power +8.2%. Also Rønnestad, Hansen & Ellefsen, *Scand J Med Sci Sports* 2014; 24(1):34–42 (DOI 10.1111/j.1600-0838.2012.01485.x): VO2max +4.6%, Wmax +2.1% in block group, no change in traditional.

**Evidence — null:** Almquist et al., *Frontiers in Physiology* 2022; 13:837634 (DOI 10.3389/fphys.2022.837634) — larger and pre-registered — found **no difference** between block and traditional periodization over 12 weeks.

**Practical default:** Offer as an option for users who want variety or respond well to concentrated load. Do not make it the default, and do not claim superiority in user-facing copy.

**Prerequisites:** ≥12 weeks consistent training history; good recovery metrics; not available to first-season users.

**Contraindications:** Any amber/red readiness state during week 1 should abort the block, not just the session.

---

### `strength_maximal` — Heavy resistance training
**Category:** supporting · **Grade:** B

**Prescription:** 2×/week, 30–40 min. Squat, deadlift, single-leg press, calf, core. 3–4 sets × 4–8 reps, heavy.

**Evidence:** Consistent evidence for improved cycling economy and time-to-exhaustion in trained cyclists over 8–12 week interventions; effect on a *fresh* FTP test is small. Best framed as durability and economy, not FTP.

**Engine selection logic:** Schedule on the same day as a hard ride (protects easy days). Prioritise in off-season/winter phases.

---

### `taper` — Pre-event taper
**Category:** periodization structure · **Grade:** A

**Prescription:** 5–10 days. Reduce volume 30–50% (up to ~40% in race week) while **maintaining intensity** via short openers. Day before: ~30 min with 3×1 min at race pace.

**Evidence:** Taper literature consistently shows ~2–3% performance gain with only ~1–3% fitness loss when volume is cut and intensity preserved.

**Engine selection logic:** Auto-trigger when a user has flagged an A-priority event. Must override the normal weekly template.

---

### `recovery_spin` — Active recovery
**Category:** recovery · **Grade:** C

**Prescription:** 30–45 min below 55% FTP. Genuinely easy.

**Evidence:** Evidence for active vs passive recovery is mixed. Main practical value is habit maintenance and blood flow without adding load.

**Engine selection logic:** Amber readiness substitution; day after a hard block.

---

## 2. Distribution models

| Model | Shape | Best fit | Grade |
|---|---|---|---|
| **Polarized** | ~80% Z1–2, ~0–5% threshold, ~15–20% high | High-volume users (≥12 h/wk) | A |
| **Pyramidal** | ~75% low, ~15% moderate, ~10% high | Most time-crunched users (6–10 h/wk) | A |
| **Threshold/sweet-spot heavy** | Large moderate-hard middle | Very time-limited (<5 h/wk), short blocks only | B |
| **"Gray zone"** | Unintentional moderate-hard majority | ❌ Never prescribe — see §3 | — |

**Engine rule:** Below ~10 h/week, default to **pyramidal**. Pure polarized requires an easy-volume budget most users don't have; forcing it on 8 h/week produces too little total stimulus.

---

## 3. The gray-zone failure mode

The single most common pattern in self-coached riders, and the one the generator exists to prevent:

> Structured indoor sessions sit at sweet spot/threshold. Outdoor "endurance" rides drift into tempo because riding easy feels unproductive. Net result: a large majority of weekly time in the moderate-hard middle. High fatigue cost, low adaptive return, and no stimulus above threshold — so the ceiling never rises and FTP plateaus.

**Detection heuristics the engine should run on ingested ride data:**
- % of **pedalling** time in the moderate band exceeding ~35% → flag. See §3.1 — this must not be computed on elapsed time.
- Best 5-min power < ~110% of FTP → the VO2 ceiling is sitting on the threshold floor; prescribe VO2 work, not more sweet spot. (Trained riders normally sit at 115–125%.) Subject to the provenance rule in §3.3.
- Nominal "easy" rides with normalized power > 80% FTP → the user's easy isn't easy.
- **Run the distribution check per-context, not just in aggregate** (§3.2).

---

### 3.1 Pedalling time, not elapsed time

**The bug this replaces:** v0.1 computed intensity distribution over elapsed time, which counts zero-watt coasting as low-intensity training. Outdoors that is a large bucket — in the first real-world validation run, 3.6 h of a 20 h window was freewheeling. The same rider's moderate share read **29.4% on elapsed time and 35.8% on pedalling time**: passing on one basis and flagging on the other.

**Rules:**
1. Compute all intensity-distribution percentages over samples where `watts > 0`.
2. Report coasting time separately as its own quantity. It's a useful terrain/traffic signal, not training intensity.
3. Never compare an indoor rider's distribution to an outdoor rider's without this normalisation. Indoor trainers produce almost no zeros, so under elapsed-time maths outdoor riders will systematically appear better-distributed than they are.

---

### 3.2 Distribution must be checked per-context

Aggregate distribution hides the failure it's meant to catch. Validation case:

| Context | Low | Moderate | High |
|---|---|---|---|
| Indoor (structured) | 44% | **48%** | 8% |
| Outdoor | 58% | 31% | 11% |
| Aggregate | 54% | 36% | 10% |

The aggregate looks borderline. The indoor block alone is nearly half moderate — a textbook gray-zone pattern — and outdoor volume is masking it. **Segment by indoor/outdoor and by structured/unstructured before flagging.**

---

### 3.3 Anchor and power-curve provenance

**The bug this replaces:** the engine treated a within-ride 5-minute best from a long endurance ride as the rider's 5-minute maximal power, concluded the power curve was compressed, and recommended a VO2max intervention. A maximal-effort check on recent data showed 122.5% of FTP — entirely normal, no compression, wrong diagnosis. The real limiter was volume adherence (§3.4), which nothing in v0.1 measured.

**Rules the engine must enforce:**
1. Tag every power-curve point with provenance: `maximal_test`, `race`, `interval_session`, or `within_ride`.
2. **`within_ride` values are lower bounds only.** They may never trigger a limiter diagnosis on their own.
3. Diagnosing a compressed power curve requires a `maximal_test` or `race` data point less than ~8 weeks old. If none exists, the engine's output is "insufficient data — prescribe a 5-min max test," not a training recommendation.
4. Cross-check the FTP anchor: best 20-min × 0.95 should land within ~5% of the stated FTP. If it doesn't, flag the anchor before prescribing percentages of it. **This check is itself provenance-gated** — a within-ride 20-min best is a floor, so a low implied FTP is not evidence the anchor is wrong. Emit an info-level `ftp_anchor_unverified` in that case, and reserve the warn-level `ftp_anchor_suspect` for `maximal_test` or `race` data.
5. Sanity-check interval targets against the rider's known maximal power. A prescription at or above best 5-min power for reps longer than ~90 s is either undoable or evidence the anchor is wrong. Flag, don't serve.

---

### 3.4 Volume adherence — check this first

**The most predictive signal in the validation case, and absent from v0.1 entirely.** A rider reporting 9 h/week availability was completing a mean of 3.74 h/week across four consecutive weeks — 42% of stated capacity. The platform's own model projected an FTP *decline*, correctly.

**Rule: the engine evaluates adherence before it evaluates structure.** No interval-selection change competes with a 2× volume gap, and recommending one while ignoring the gap is malpractice dressed as precision.

- Completed vs. planned hours, 4-week rolling → flag below ~80%.
- Completed vs. *stated available* hours → flag below ~70%. This catches the plan being wrong, not just the rider being inconsistent.
- Sustained adherence below ~60% → stop optimising the plan and ask why. Illness, life load, or an unrealistic template. All three need a conversation, not a new workout.

---

### 3.5 Platform labels are not physiological categories

Every ingested source names things differently and none map cleanly onto the underlying stimulus. TrainerRoad files "long suprathreshold" under a VO2max heading; Zwift names rides after routes; Strava inherits whatever the recorder sent. In the validation set, a session named `Zwift - Cardinal` was pure threshold work (242–253 W blocks, **zero** seconds above 105% FTP) despite sitting in a block labelled VO2.

**Rule: classify sessions from duration × %FTP measured in the file. Never from the name, and never from the source platform's category.** Retain the original label as metadata for display only.

Reference boundaries for the classifier:

| Class | Signature |
|---|---|
| Endurance (easy) | <12% of pedalling time in moderate band, no sustained supra |
| Endurance with efforts | 12–30% moderate |
| Sweet spot / tempo | ≥30% moderate, no sustained threshold block |
| Threshold | ≥30% moderate with ≥5 min contiguous at 94–105% |
| Threshold+ | ≥2 min above 105% |
| VO2max / suprathreshold | ≥5 min above 105% **and** best 5-min ≥106% FTP |

---

## 4. Progression, retesting, and expectations

**Expected FTP trajectory** (anchor: Almquist 2022, whose subjects at ~3.3–3.4 W/kg on ~7.5–8 h/week are an excellent proxy for the target user — the paper reports 5-min and 40-min TT power increases of 8.9 ± 8.9% and 8.4 ± 9.0%, Wmax +6 ± 7%, power at 4 mmol/L +10 ± 12%, with GE and VO2peak unaltered):

| Horizon | Expected change | Note |
|---|---|---|
| 4 weeks | ~0% measurable | Adaptation lags. **The engine must set this expectation or users quit.** |
| 8 weeks | +3–5% | First reliable signal |
| 12 weeks | ~+8% | Matches Almquist / Rønnestad |
| 24 weeks | +10–12% | Consistency-dependent, non-linear |

Note the ±8–9% standard deviations. Individual response varies enormously — surface ranges, never point predictions.

**Retest cadence:** every 4–6 weeks, at phase boundaries. More frequent testing measures noise, since FTP change takes 6–8 weeks to manifest.

**Recovery weeks:** every 3–4 weeks, or triggered by readiness (§5).

---

## 5. Readiness engine — health metrics → workout modification

Inputs available from the Google Health API (see §6 for what each device actually supports).

| Signal | Green | Amber | Red |
|---|---|---|---|
| Resting HR vs 30-day baseline | ≤ +3 bpm | +4–7 bpm | ≥ +8 bpm, or ≥ +5 sustained 3+ days |
| HRV trend (7-day vs 30-day) | ≥ baseline | 5–10% below | >10% below, or 10–14 day decline |
| Sleep (last night / 3-night avg) | ≥7 h | 5.5–7 h | <5.5 h, or <6 h avg over 3 nights |
| Respiratory rate vs baseline | ≤ +1 | +1–2 | >+2 (illness signal) |
| Subjective (1–10) | ≥7 | 4–6 | ≤3 |

**Action rules:**
- **Green:** prescribe as planned.
- **Amber:** hold the session type, cut volume ~30% (e.g. 3 sets → 2), or substitute `endurance_z2`. Never substitute a *harder* session.
- **Red:** substitute `recovery_spin` or full rest. Two consecutive red days → insert a recovery week and defer the block.
- **Any red on respiratory rate + elevated RHR together:** treat as probable illness. Recommend rest and, if symptomatic, seeing a clinician. Do not prescribe training.

**Missing data is not good data.** When no signals are available the engine returns `unknown`, not green. Fitbit syncs only when its app has run, so this morning's HRV may simply not exist yet — see §6 gotcha 4.

**Design warning:** HRV is noisy and heavily confounded by alcohol, late meals, sleep timing, and measurement inconsistency. Gate decisions on *trends* (7-day rolling), never single readings, or the app will yo-yo users for no physiological reason. Evidence for HRV-guided training is promising but not settled — grade B at best.

---

## 6. Google Health API integration notes

The Fitbit Web API is being replaced; the current path is the **Google Health API** (REST or gRPC, Google OAuth). There's a [migration guide](https://developers.google.com/health/migration) for existing Fitbit Web API developers.

### Scopes needed
- `.activity_and_fitness.readonly` — exercise, VO2max, active minutes, distance, steps
- `.health_metrics_and_measurements.readonly` — heart rate, HRV, resting HR, SpO2, respiratory rate, skin temp
- `.sleep.readonly` — sleep sessions

### Fitbit Air coverage — what you actually get

✅ **Supported:** heart rate, heart-rate variability, daily HRV, daily resting heart rate, daily VO2 max, VO2 max, run VO2 max, daily respiratory rate, respiratory rate sleep summary, daily oxygen saturation, oxygen saturation, daily sleep temperature derivations, sleep, exercise, active minutes, active zone minutes, steps, distance, sedentary period, total calories, nutrition log.

❌ **Not supported on Fitbit Air:**
- **Weight** — Aria/Aria 2/Aria Air scales only. *This is a real product problem: W/kg is central to cycling and you cannot get body mass from the band.* Plan for manual entry or a scale integration.
- **Body fat** — same, Aria scales only.
- **ECG** — Charge 5/6, Pixel Watch, Sense/Sense 2 only.

### Gotchas that will bite you

1. **Page size of 25 for `exercise` and `sleep`.** Most data types cap at 10,000 per page — these two cap at **25**. A 10-year sleep backfill returns 25 sessions on page one. Budget for heavy pagination.
2. **Rollup range limits:** 14 days max for `heart-rate`, `active-minutes`, `total-calories`, `calories-in-heart-rate-zone`; 90 days for everything else. Chunk historical aggregation queries accordingly.
3. **Distances are in millimeters** (including `elevationGainMillimeters`). Convert at the boundary, once.
4. **No direct device access.** Fitbit devices sync only to the Fitbit mobile app; your app reads what's already synced. Data appears ~every 15 min when the app is open and in Bluetooth range. **Your readiness engine cannot assume this morning's HRV is available when the user opens your app.** Design for stale/missing data.
5. **True zeros.** Some types distinguish an actual zero from missing data. Don't treat absent as zero — it will corrupt trend baselines.
6. **Use `dailyRollUp`** for anything date-bucketed; it handles DST and travel time-zone stitching correctly.
7. **Phased sync:** hot-load 7–14 days for the UI, cold-load history in a background queue. Exponential backoff on 429 and 504 — never retry large failed payloads immediately.
8. **Webhooks** are supported for HRV, resting HR, sleep, exercise, and others — use them instead of polling.

### Worth grabbing
The [API Parity Tool](https://developers.google.com/health/migration/parity-tool) publishes a context file designed to be fed directly to an LLM or dropped into an `Agents.md`. Given you're building an AI-driven product, that's close to free integration accuracy.

---

## 7. Guardrails for a public-facing app

You're moving from "AI plans my training" to "AI plans strangers' training," and that changes the risk profile materially. Non-negotiables:

1. **Screen before prescribing.** Age, training history, known cardiac conditions, current injuries, pregnancy. A user with no base must not be able to receive `vo2_short_short_30_15` on day one — the prerequisites in §1 exist to be enforced in code, not just documented.
2. **Hard caps the LLM cannot exceed.** Max sessions/week, max weekly TSS ramp (~5–8%/week), max consecutive hard days, mandatory recovery week cadence. Generative models will happily produce a 25-hour week if the prompt drifts. Validate generated output against a rules layer *after* generation.
3. **Anchor requirement.** No intensity prescription without a valid FTP/threshold anchor set within ~8 weeks. Percentages of a wrong FTP are actively harmful.
4. **Medical disclaimer + escalation paths.** Chest pain, syncope, unexplained severe fatigue, or persistent elevated RHR with symptoms → route to "see a doctor," never to a modified workout.
5. **Don't let readiness metrics become a stick.** Consumer HRV/sleep scores drive real anxiety and, in some users, compulsive exercise or under-fuelling. Frame outputs as suggestions, avoid streak mechanics on hard training, and never gamify weight.
6. **Fuelling guidance is a safety feature, not a nice-to-have.** Prescribing repeated hard sessions without carbohydrate guidance is how you produce under-fuelled, injured users. Baseline: 60–90 g carbs/h for hard or long sessions (a ~2:1 glucose:fructose mix is needed to exceed ~60 g/h, per Jeukendrup, *Sports Medicine* 2014), 30–60 g/h for shorter sub-threshold work; ~1.8 g/kg/day protein (Witard et al., *Sports Medicine* 2025, DOI 10.1007/s40279-025-02203-8).
7. **Never prescribe weight loss.** Especially not to hit a W/kg target. This is the single highest-liability feature in a cycling app and the easiest to get wrong.

---

## 8. Research backlog / open questions

- [ ] Female-specific training response and menstrual-cycle periodization — the cited literature is overwhelmingly male. **This is a coverage gap, not a settled area.** Do not extrapolate.
- [ ] Masters (50+) recovery ratios and high-intensity tolerance.
- [ ] Does HRV-guided prescription actually beat fixed periodization? Current evidence is promising, not conclusive.
- [ ] Heat acclimation as a cheap aerobic stimulus — plausible, worth grading.
- [ ] Indoor vs outdoor FTP offset (commonly 5–10% lower indoors) — needs a defensible source before the engine auto-adjusts.
- [ ] Validation of Fitbit-derived VO2max against lab values in trained cyclists — likely poor; probably should not feed the engine directly.
- [ ] Durability metrics: which of kJ/kg-adjusted power decay vs. simple late-ride power is more actionable?
- [ ] **The §3 thresholds are still conventions, not findings.** 35% moderate, 110% 5-min ratio, 80% easy-ride drift — all were picked from coaching convention and have now been tested against exactly one athlete. They need calibration across a real user population before shipping as defaults.
- [ ] Coasting share as a standalone metric — plausibly a useful terrain/group-riding signal, currently discarded.
- [ ] Sensor dropout is currently collapsed into coasting. Null and zero are different states; `coasting_hours` silently absorbs both.
- [ ] The anchor cross-check in §3.3 is one-sided — a within-ride 20-min best *above* stated FTP emits nothing, though a floor exceeding the anchor is real evidence the anchor is low.
- [ ] Does the classifier in §3.5 hold up against Zwift racing, where power is ragged and supra bursts are frequent but unstructured? Likely over-classifies races as VO2max sessions.
- [ ] Downsampled streams overstate short-duration bests. The v0.2 validation fixture read 312 W / 122% FTP for best 5-min; the same window at full resolution read 295 W / 116%. Any power-curve threshold calibrated on downsampled data is optimistic.

---

## 9. Changelog

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-08-25 | Initial registry. 13 methods, distribution models, gray-zone detection, readiness rules, Google Health API integration notes, public-app guardrails. |
| 0.2 | 2026-08-25 | First real-data validation run (n=1, 14 rides, 28 days). Four corrections, all found by running v0.1 against actual power files rather than by reasoning about it: **§3.1** intensity distribution must use pedalling time, not elapsed — coasting zeros were inflating the low bucket and masking gray-zone patterns outdoors. **§3.2** distribution must be segmented indoor/outdoor; aggregate hid a 48%-moderate indoor block. **§3.3** power-curve provenance — v0.1 let a submaximal within-ride best drive a limiter diagnosis, producing a confidently wrong VO2max recommendation; `within_ride` values are now lower bounds that cannot trigger a diagnosis alone, and anchor cross-checking is mandatory. **§3.4** volume adherence added as a first-order check ahead of structure; it was the actual limiter in the validation case and v0.1 did not measure it at all. **§3.5** session classification from measured duration × %FTP, never from platform labels. Also added maintenance rule 6 on data provenance. |
| 0.2.1 | 2026-08-25 | Live-data run against the Strava adapter. The §3.3 anchor cross-check was found to be ungated: it fired on a within-ride 20-min best, asserting a 255 W anchor was 11% high when the underlying number was a floor, not a measurement. Same class of error the section exists to prevent, in the section itself. Now split into warn-level `ftp_anchor_suspect` (requires `maximal_test` or `race`) and info-level `ftp_anchor_unverified` (within-ride, does not drive a recommendation). |
