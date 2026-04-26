# Design: Acceleration Scoring, Validation Loop, and Product Differentiation

## Background

The framework has three critical weaknesses that undermine user trust and retention:

1. **Star velocity is a lagging absolute metric** — it tells you how many stars were gained, not whether growth is *accelerating*. Two projects with the same weekly gain can have completely different trajectories (one plateauing, one exploding).
2. **No validation loop** — we mark projects as "early-burst" but never check if they actually burst. The scoring weights (0.35/0.25/0.25/0.15) are arbitrary and untested.
3. **No differentiation from ChatGPT** — the LLM analysis receives the same metadata any user could paste into a chat interface. There is no structural advantage.

This plan addresses all three without adding external data sources.

---

## 1. Acceleration-Aware Star Velocity

### Problem

Current `calculate_star_velocity` compares current stars to 7d/30d ago. It captures **volume** but misses **acceleration**.

| Week | Stars | Weekly Gain | Current Score |
|------|-------|-------------|---------------|
| W-3  | 100   | —           | —             |
| W-2  | 120   | +20         | —             |
| W-1  | 150   | +30         | —             |
| Now  | 200   | +50         | High          |

Both Project A (gaining 50/wk consistently) and Project B (20→30→50 accelerating) get the same score. But B is the real early-burst signal.

### Solution: Growth Acceleration Score

Calculate three weekly deltas and their ratio:

```
delta_w1 = current - stars_7d_ago      # most recent week
delta_w2 = stars_7d_ago - stars_14d_ago
delta_w3 = stars_14d_ago - stars_21d_ago
```

**Acceleration ratio** = `delta_w1 / max(delta_w2, 1)`

- ratio >= 2.0: growth is doubling week-over-week → strong early-burst
- ratio 1.0-2.0: steady growth → moderate signal
- ratio < 1.0: decelerating → weak signal even if absolute gain is high

**Combined velocity score** = `0.6 * volume_score + 0.4 * acceleration_score`

This weights absolute growth slightly higher (you still need *some* mass) but acceleration provides the discriminative signal.

### Data Requirement

Requires 14-21 days of star history samples. The existing `star_history` table already supports this. We just need to read more history points in `_calculate_and_store_burst_score`.

---

## 2. Validation Loop

### Problem

The framework emits predictions but never measures their accuracy. Users have no reason to trust the "early-burst" label.

### Solution: Track Prediction Outcomes

**New table: `prediction_outcomes`**

```sql
CREATE TABLE prediction_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    predicted_at TEXT,           -- when we first marked is_early_burst=1
    stars_at_prediction INTEGER,
    overall_score_at_prediction REAL,
    checked_at TEXT,             -- last validation run
    stars_now INTEGER,
    growth_rate_actual REAL,     -- (stars_now - stars_at_prediction) / days
    outcome TEXT                 -- 'true_positive' | 'false_positive' | 'pending'
);
```

**Validation logic (new script `validate.py`):**

1. Find all projects where `is_early_burst=1` for the first time in the last N days
2. Record `stars_at_prediction` and `overall_score_at_prediction`
3. Re-fetch current star count via GitHub API (or use latest sample)
4. Calculate actual growth rate over the prediction window
5. Classify outcome:
   - **true_positive**: actual growth rate >= predicted trajectory
   - **false_positive**: actual growth rate < predicted trajectory (or flat/negative)
   - **pending**: not enough time elapsed (minimum 7 days)

**Report integration:**

Add a "Validation Metrics" section to the daily report:
- Precision (TP / (TP + FP)) for predictions made 7+ days ago
- Average actual growth rate of TP vs FP projects
- Calibration chart: predicted score buckets vs actual outcomes

**Feedback into scoring:**

Run a weekly `reweight.py` script that:
1. Loads prediction_outcomes
2. Fits a simple logistic regression or correlation between `overall_score` components and `outcome`
3. Suggests weight adjustments (or directly updates config weights)

This closes the loop: predict → validate → learn → adjust.

---

## 3. Differentiation from "Just Use ChatGPT"

### Problem

The current LLM prompt contains only static metadata (name, description, stars, topics). A user can copy-paste the same into ChatGPT and get a similar answer.

### Solution: Feed LLM Structural Data Humans Cannot Easily Generate

**Three categories of proprietary signal:**

#### A. Temporal Trajectory (Star History Curve)

Instead of just "Stars: 200", provide the full sampled history:

```json
{
  "star_history": [
    {"date": "2026-04-01", "stars": 50},
    {"date": "2026-04-08", "stars": 80},
    {"date": "2026-04-15", "stars": 130},
    {"date": "2026-04-22", "stars": 200}
  ],
  "weekly_growth_rates": [0.60, 0.625, 0.538],
  "acceleration_trend": "decelerating slightly but still strong"
}
```

This lets the LLM reason about *trajectory*, not just *state*.

#### B. Peer Comparison (Relative Positioning)

Find 3-5 projects in the same tech_layer/application with similar age and star count. Provide:

```json
{
  "peer_comparison": {
    "this_project": {"stars": 200, "age_months": 3, "weekly_gain": 50},
    "peer_1": {"name": "xyz", "stars": 180, "age_months": 4, "weekly_gain": 20},
    "peer_2": {"name": "abc", "stars": 350, "age_months": 2, "weekly_gain": 80},
    "percentile_in_peer_group": 75
  }
}
```

This gives the LLM relative context: "Is this project overperforming or underperforming vs. direct competitors?"

#### C. Inflection Point Detection

Analyze the star history for structural breaks:
- When did growth rate change significantly?
- Was there a specific commit or release around that time?
- Is the project currently in an "upward inflection", "plateau", or "decline" phase?

This is computed via simple slope-change detection on the star history, then fed to the LLM as a signal.

#### D. Updated Prompt Template

The prompt should include:
1. Static metadata (as before)
2. **Temporal trajectory** (star history + growth rates + acceleration)
3. **Peer comparison** (relative positioning)
4. **Inflection point analysis** (phase detection)
5. **Explicit instruction**: "Use the trajectory and peer data to identify non-obvious opportunities that would not be visible from the README alone."

---

## Implementation Priority

| Priority | Feature | Files to Touch | Effort |
|----------|---------|---------------|--------|
| P0 | Acceleration scoring in `scoring_engine.py` | scoring_engine.py, discover.py | Low |
| P0 | Validation table + script | db.py, validate.py | Medium |
| P1 | Trajectory data in LLM prompt | analyze.py, db.py | Medium |
| P1 | Peer comparison query | analyze.py, db.py | Medium |
| P2 | Inflection point detection | analyze.py | Low |
| P2 | Report validation metrics | report.py | Low |
| P2 | Weight reweighting script | reweight.py | Medium |

---

## Success Metrics

After implementation:
- **Precision** of early-burst predictions (7-day horizon) should be measurable and > 60%
- **User retention**: the differentiation features provide concrete value that manual ChatGPT usage cannot replicate
- **Calibration**: predicted score buckets should correlate monotonically with actual outcomes
