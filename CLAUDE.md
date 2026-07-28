# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **config-driven framework** for discovering early-stage, fast-growing open-source projects in a specific category (currently AI) and identifying extension opportunities. It discovers projects from GitHub topics, ecosystem organizations, and trending pages; filters and classifies them; scores them for early-burst signals; optionally performs LLM-based deep analysis; and generates Markdown reports.

The framework is intentionally category-agnostic: behavior is driven by `config.yaml`, not code.

## Common Commands

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GITHUB_TOKEN
```

### Run the Full Pipeline

- Incremental (daily): `./run.sh`
- Bulk backfill: `./run_bulk.sh [BATCH_SIZE]` (default 20)

Both scripts pull remote changes, initialize the DB, run crash recovery, execute the relevant stages, and commit/push `data/framework.db` and `data/reports/*.md`.

### Run Individual Stages

```bash
python framework/stages/init_db.py
python framework/stages/discover.py [--dry-run]
python framework/stages/filter.py [--dry-run]
python framework/stages/schedule.py --mode incremental|bulk [--batch-size N]
python framework/stages/analyze.py --date YYYY-MM-DD [--use-llm] --max-tasks N
python framework/stages/report.py --date YYYY-MM-DD
python framework/stages/validate.py [--metrics-only] [--min-days 7]
python framework/stages/reweight.py --dry-run|--apply
```

### Crash Recovery

Both entry scripts run this automatically, but it can be invoked manually:

```bash
PYTHONPATH=. python -c "from framework.core.db import Database; db = Database(); db.repair_analyzing_status(); db.repair_orphan_records()"
```

### SQLite WAL Checkpoint

Before committing the DB to git (also done by the entry scripts):

```bash
sqlite3 data/framework.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

### Notes on Testing and Linting

There is currently no test suite, linter, or type checker configured. Validation is done by running the stages directly.

## High-Level Architecture

### Configuration-Driven Design

`config.yaml` is the single source of truth for the framework. It defines:

- `category`: the domain being tracked (name, display name, version).
- `dimensions`: `tech_layer` and `application` taxonomies used to classify projects.
- `sources`: GitHub topics, ecosystem organizations, and trending languages/periods to discover.
- `early_burst`: scoring weights and thresholds for the early-burst detector.
- `filters`: skip patterns, category keywords, and tech-layer classification rules.
- `scheduling`: batch sizes and daily limits for bulk vs. incremental analysis.
- `resilience`: retry settings for GitHub API and LLM analysis.

To adapt the framework to another category, replace the values in `config.yaml`; the code is designed to remain unchanged.

### Six-Stage Pipeline

```
init_db.py  ->  discover.py  ->  filter.py  ->  schedule.py  ->  analyze.py  ->  report.py
                                                         ^
                                               validate.py / reweight.py (closed loop)
```

1. **init_db.py**: Creates and migrates SQLite tables, and runs crash recovery (`repair_analyzing_status`, `repair_orphan_records`).
2. **discover.py**: Fetches repositories from three sources:
   - GitHub topic search (`topic:X language:Y stars:min..max`).
   - Ecosystem organization repos (`/orgs/{org}/repos`).
   - GitHub Trending HTML parsing.
   It upserts projects, samples star counts, and computes early-burst signals.
3. **filter.py**: Heuristic semantic filter that classifies `discovered` projects into `tech_layer`/`application` and marks them as `scheduled` or `filtered_skip`.
4. **schedule.py**: Creates analysis tasks of type `bulk` or `incremental`, prioritizing by early-burst score.
5. **analyze.py**: Picks pending tasks, optionally calls an LLM CLI tool via `framework/prompts/ai_analyze.md`, and stores `analyses` and `opportunities`. Falls back to a heuristic analyzer when LLM is unavailable.
6. **report.py**: Generates a daily Markdown report in `data/reports/YYYY-MM-DD.md` with global stats, tech-stack distribution, top opportunities, and early-burst project listings.

**validate.py** and **reweight.py** form a closed-loop improvement path:

- `validate.py` records predictions when projects first become early-burst, then after `min_days` compares predicted vs. actual star growth to label outcomes `true_positive` or `false_positive`.
- `reweight.py` analyzes these outcomes and proposes/adjusts the weights and `min_score` in `config.yaml`.

### Data Model

SQLite database at `data/framework.db` with WAL mode enabled. Key tables:

- `projects`: discovered repositories and their status (`discovered` → `scheduled` → `analyzing` → `active`, or `filtered_skip`).
- `star_history`: daily star-count samples used for velocity and trajectory.
- `early_burst_signals`: component scores (`star_velocity`, `activity_index`, `community_buzz`, `novelty`) and `overall_score`.
- `tasks`: analysis task queue (`pending` → `running` → `done`/`failed`).
- `analyses`: structured LLM output with `overall_score CHECK(overall_score BETWEEN 1 AND 10)`.
- `opportunities`: concrete extension opportunities tied to a project.
- `prediction_outcomes`: validation records for the closed-loop scoring feedback.

### Scoring Engine

`framework/core/scoring_engine.py` implements the early-burst model:

```
overall_score = weighted_sum(star_velocity, activity_index, community_buzz, novelty)
```

- Star velocity supports acceleration-aware scoring when 14-day (and optionally 21-day) star history is available.
- Activity index combines commit recency, PR merge rate, and open issues.
- Novelty is derived from repository age and contributor signals.
- A project is considered an early-burst when `overall_score >= early_burst.min_score`.

### LLM Integration

When `USE_LLM=true` and `CLI_TOOL` is set in the environment, `analyze.py` calls an external CLI tool:

- `claude` / `gemini` / `aider`: prompt passed via `-p` argument.
- Cursor agent (`agent`/`cursor-agent`): prompt passed via stdin.

Without LLM, a heuristic analyzer produces rule-based analyses.

### Discovery Sources and Anchors

The framework discovers projects through:

1. **GitHub Topics**: broad, tag-based search.
2. **Ecosystem Organizations**: repos from known organizations (e.g., `huggingface`, `pytorch`).
3. **GitHub Trending**: HTML-parsed trending pages for configured languages and periods.
4. **Anchor Discovery** (design reserved in `docs/superpowers/specs/anchor.md`): reverse discovery by searching for new projects that mention known concepts/projects/standards in their name or description.

Anchors are intended as search reference points, not targets. They are categorized into protocol/standard layer, well-known project layer, and application scenario layer, with different maintenance cadences.

### Stability and Concurrency

- SQLite uses WAL mode, `busy_timeout=5000`, and `synchronous=NORMAL`.
- `run.sh` and `run_bulk.sh` use a shared `flock` lock file on Linux; on macOS they warn and continue without locking. Do not run both scripts concurrently.
- Entry scripts include crash recovery and a 3-retry git push loop.
- `discover.py` implements GitHub API rate-limit handling (2s between search requests, 0.5s between others, exponential backoff on retries).

## Environment Variables

Defined in `.env`:

- `GITHUB_TOKEN` (required): GitHub personal access token used by `discover.py`.
- `USE_LLM` (optional): set `true` to enable LLM analysis.
- `CLI_TOOL` (optional): external CLI tool for LLM calls; defaults to `claude`.

## GitHub Actions

`.github/workflows/discover.yml` runs the full pipeline daily at 01:00 UTC and can be triggered manually in `incremental` or `bulk` mode. It commits and pushes `data/` after each run.
