#!/usr/bin/env python3
"""
Stage 4: Deep Analysis of AI Projects
Analyzes scheduled/early-burst projects and identifies extension opportunities.
"""
import os
import sys
import json
import argparse
import re
import shlex
import shutil
import subprocess
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.core.scheduler import Scheduler


VALID_OPPORTUNITY_TYPES = {'product', 'tech', 'market', 'integration', 'business_model'}
VALID_IMPACT_LEVELS = {'high', 'medium', 'low'}
VALID_DIFFICULTY_LEVELS = {'high', 'medium', 'low'}
VALID_TIME_HORIZONS = {'short', 'medium', 'long'}

_GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
_README_HEADERS = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
if _GITHUB_TOKEN:
    _README_HEADERS['Authorization'] = f'Bearer {_GITHUB_TOKEN}'

_README_MAX_CHARS = 10000
_DATA_URI_RE = re.compile(r'!\[[^\]]*\]\(\s*data:[^)]*\)', re.IGNORECASE)
_IMG_TAG_RE = re.compile(r'<(img|picture|source)[^>]*>.*?</\1>|<(img|source)[^>]*/?>', re.IGNORECASE | re.DOTALL)
_BADGE_RE = re.compile(r'\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)')


def _sanitize_readme(text: str) -> str:
    """Strip base64 data URIs, img/picture tags, and badge links before truncation."""
    text = _DATA_URI_RE.sub('', text)
    text = _IMG_TAG_RE.sub('', text)
    text = _BADGE_RE.sub('', text)
    return text[:_README_MAX_CHARS]


def _fetch_readme(project_id: str) -> str:
    """Fetch and sanitize a repo's README. Returns '' on any failure."""
    try:
        r = requests.get(
            f"https://api.github.com/repos/{project_id}/readme",
            headers=_README_HEADERS, timeout=30
        )
        if r.status_code != 200:
            print(f"  README fetch failed for {project_id}: HTTP {r.status_code}")
            return ''
        import base64
        raw = base64.b64decode(r.json().get('content') or '')
        return _sanitize_readme(raw.decode('utf-8', errors='replace'))
    except Exception as e:
        print(f"  README fetch error for {project_id}: {e}")
        return ''


def _is_whole_word(text: str, pattern: str) -> bool:
    """Check if pattern appears as a whole word in text."""
    if not text or not pattern:
        return False
    for match in re.finditer(re.escape(pattern), text, re.IGNORECASE):
        start, end = match.span()
        left_ok = start == 0 or not text[start - 1].isalnum()
        right_ok = end == len(text) or not text[end].isalnum()
        if left_ok and right_ok:
            return True
    return False


def _calculate_peer_percentile(project_stars: int, peers: List[Dict]) -> Tuple[float, int, int]:
    """Calculate star count percentile within peer group.

    Returns (percentile, peers_below, total_peers).
    """
    if not peers:
        return 0.0, 0, 0
    try:
        ps = int(project_stars) if project_stars is not None else 0
    except (ValueError, TypeError):
        ps = 0
    peer_stars = []
    for p in peers:
        try:
            s = int(p.get('stars')) if p.get('stars') is not None else 0
        except (ValueError, TypeError):
            s = 0
        peer_stars.append(s)
    total = len(peer_stars)
    below = sum(1 for s in peer_stars if ps > s)
    # If tied with highest, treat as 100th percentile
    if peer_stars and ps >= max(peer_stars):
        return 100.0, below, total
    percentile = (below / total) * 100 if total > 0 else 0.0
    return percentile, below, total


def _detect_inflection(star_history: List[Dict]) -> Optional[Dict]:
    """Detect growth phase from star history trajectory.

    Returns None if insufficient data, otherwise dict with:
    - phase: accelerating | stable_growth | decelerating | decline
    - slope_recent: stars/day in recent period
    - slope_prior: stars/day in prior period
    - ratio: slope_recent / slope_prior
    """
    if len(star_history) < 3:
        return None

    # Sort ascending by date
    sorted_hist = sorted(star_history, key=lambda x: x.get('sampled_at', ''))

    # Split into two halves: prior (first half) and recent (second half)
    mid_idx = len(sorted_hist) // 2
    prior = sorted_hist[:mid_idx + 1]  # include midpoint
    recent = sorted_hist[mid_idx:]

    if len(prior) < 2 or len(recent) < 2:
        return None

    earliest = prior[0]
    mid = prior[-1]
    latest = recent[-1]

    def days_between(a, b):
        try:
            da = datetime.fromisoformat(a['sampled_at'].replace('Z', '+00:00'))
            db = datetime.fromisoformat(b['sampled_at'].replace('Z', '+00:00'))
            if da.tzinfo is None:
                da = da.replace(tzinfo=timezone.utc)
            if db.tzinfo is None:
                db = db.replace(tzinfo=timezone.utc)
            return max((db - da).total_seconds() / 86400, 1.0)
        except (ValueError, TypeError, KeyError):
            return 1.0

    days_prior = days_between(earliest, mid)
    days_recent = days_between(mid, latest)

    try:
        stars_earliest = int(earliest.get('stars', 0) or 0)
    except (ValueError, TypeError):
        stars_earliest = 0
    try:
        stars_mid = int(mid.get('stars', 0) or 0)
    except (ValueError, TypeError):
        stars_mid = 0
    try:
        stars_latest = int(latest.get('stars', 0) or 0)
    except (ValueError, TypeError):
        stars_latest = 0

    slope_prior = (stars_mid - stars_earliest) / days_prior
    slope_recent = (stars_latest - stars_mid) / days_recent

    if slope_recent < 0:
        phase = 'decline'
        ratio = None
    elif slope_prior <= 0:
        # Prior was flat/declining, any positive recent is recovery/growth
        phase = 'accelerating' if slope_recent > 0 else 'decline'
        ratio = None  # ratio is meaningless when prior <= 0
    else:
        # Guard against near-zero slope_prior causing extreme ratios;
        # cap ratio at 100 so tiny prior slopes don't distort classification.
        safe_slope_prior = max(slope_prior, 0.0001)
        ratio = round(min(slope_recent / safe_slope_prior, 100.0), 2)
        if ratio >= 1.5:
            phase = 'accelerating'
        elif ratio >= 0.8:
            phase = 'stable_growth'
        elif ratio >= 0.5:
            phase = 'decelerating'
        else:
            phase = 'decline'

    return {
        'phase': phase,
        'slope_recent': round(slope_recent, 1),
        'slope_prior': round(slope_prior, 1),
        'ratio': ratio
    }


def get_project_data(db: Database, project_id: str, conn=None) -> Optional[Dict]:
    """Get project and burst signal data."""
    should_close = conn is None
    conn = conn or db.get_conn()
    try:
        proj = conn.execute(
            "SELECT * FROM projects WHERE id=?",
            (project_id,)
        ).fetchone()

        if not proj:
            return None

        proj_dict = dict(proj)

        # Get latest burst signals
        signals = conn.execute(
            """SELECT * FROM early_burst_signals
               WHERE project_id=? ORDER BY calculated_at DESC LIMIT 1""",
            (project_id,)
        ).fetchone()

        if signals:
            proj_dict['burst_signals'] = dict(signals)

        # Get star history for trajectory analysis
        cursor = conn.execute('''
            SELECT sampled_at, stars FROM star_history
            WHERE project_id = ?
            AND sampled_at >= date('now', '-30 days')
            ORDER BY sampled_at ASC
        ''', (project_id,))
        proj_dict['star_history'] = [dict(row) for row in cursor.fetchall()]

        # Get peer projects for competitive context
        proj_dict['peers'] = db.get_peer_projects(
            project_id,
            proj_dict.get('tech_layer'),
            proj_dict.get('application'),
            limit=5,
            conn=conn
        )

        proj_dict['readme'] = _fetch_readme(project_id)

        # Calculate peer percentile
        proj_dict['peer_percentile'] = _calculate_peer_percentile(
            proj_dict.get('stars', 0) or 0,
            proj_dict.get('peers', [])
        )

        # Detect inflection point from star history
        proj_dict['inflection'] = _detect_inflection(
            proj_dict.get('star_history', [])
        )

        return proj_dict
    finally:
        if should_close:
            conn.close()


def get_pending_analysis_tasks(db: Database, date: str, limit: int = 10) -> List[Dict]:
    """Get pending tasks for LLM analysis."""
    conn = db.get_conn()
    try:
        cursor = conn.execute(
            """SELECT * FROM tasks
               WHERE task_date=? AND status='pending'
               AND task_type IN ('bulk', 'incremental')
               ORDER BY priority_score DESC
               LIMIT ?""",
            (date, limit)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def validate_opportunity(opp: Dict) -> Tuple[bool, str]:
    """Validate opportunity structure and values."""
    required_fields = ['opportunity_type', 'title', 'description']
    for field in required_fields:
        if field not in opp or not opp[field]:
            return False, f"Missing required field: {field}"

    opp_type = opp.get('opportunity_type', '')
    if opp_type not in VALID_OPPORTUNITY_TYPES:
        return False, f"Invalid opportunity_type: {opp_type}"

    impact = opp.get('impact_potential', 'medium')
    if impact not in VALID_IMPACT_LEVELS:
        opp['impact_potential'] = 'medium'

    difficulty = opp.get('difficulty', 'medium')
    if difficulty not in VALID_DIFFICULTY_LEVELS:
        opp['difficulty'] = 'medium'

    time_horizon = opp.get('time_horizon', 'medium')
    if time_horizon not in VALID_TIME_HORIZONS:
        opp['time_horizon'] = 'medium'

    return True, ""


def store_analysis_and_opportunities(db: Database, project_id: str, analysis: Dict, conn=None,
                                     analyzer_version: str = 'llm-v1') -> int:
    """Store analysis results and opportunities atomically."""
    should_close = conn is None
    conn = conn or db.get_conn()
    opportunities_stored = 0

    try:
        now = datetime.now(timezone.utc).isoformat()

        # Store analysis
        conn.execute("""
            INSERT INTO analyses (
                project_id, analyzed_at, tech_layer, application,
                problem_solved, innovation_summary, differentiation,
                market_timing, ecosystem_position, commercialization_path,
                overall_score, analyzer_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, now,
            analysis.get('tech_layer') or '',
            analysis.get('application') or '',
            analysis.get('problem_solved') or '',
            analysis.get('innovation_summary') or '',
            analysis.get('differentiation') or '',
            analysis.get('market_timing') or '',
            analysis.get('ecosystem_position') or '',
            analysis.get('commercialization_path') or '',
            analysis.get('overall_score', 5),
            analyzer_version
        ))

        # Store opportunities
        opportunities = analysis.get('opportunities', [])
        for opp in opportunities:
            if opp is None or not isinstance(opp, dict):
                print(f"    Warning: Skipping non-dict opportunity: {opp}")
                continue
            valid, error = validate_opportunity(opp)
            if not valid:
                print(f"    Warning: Invalid opportunity - {error}")
                continue

            # Deduplicate by (project_id, title): update existing, insert new
            existing = conn.execute(
                "SELECT id FROM opportunities WHERE project_id = ? AND title = ?",
                (project_id, opp.get('title', ''))
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE opportunities SET
                        source_analysis_date = ?,
                        description = ?,
                        impact_potential = ?,
                        difficulty = ?,
                        time_horizon = ?,
                        key_insight = ?,
                        evidence = ?,
                        last_seen_at = ?,
                        status = 'open'
                    WHERE id = ?
                """, (
                    now,
                    opp.get('description', ''),
                    opp.get('impact_potential', 'medium'),
                    opp.get('difficulty', 'medium'),
                    opp.get('time_horizon', 'medium'),
                    opp.get('key_insight', ''),
                    json.dumps(opp.get('evidence') or []),
                    now,
                    existing['id']
                ))
            else:
                conn.execute("""
                    INSERT INTO opportunities (
                        project_id, source_analysis_date, opportunity_type,
                        title, description, impact_potential, difficulty,
                        time_horizon, key_insight, evidence, first_seen_at,
                        last_seen_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """, (
                    project_id, now,
                    opp.get('opportunity_type', ''),
                    opp.get('title', ''),
                    opp.get('description', ''),
                    opp.get('impact_potential', 'medium'),
                    opp.get('difficulty', 'medium'),
                    opp.get('time_horizon', 'medium'),
                    opp.get('key_insight', ''),
                    json.dumps(opp.get('evidence') or []),
                    now, now
                ))
            opportunities_stored += 1

        if should_close:
            conn.commit()
        return opportunities_stored

    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def extract_json_from_text(text: str) -> Optional[Dict]:
    """Extract JSON object from text, handling various formats."""
    if not isinstance(text, str):
        return None

    # Try to find JSON block with braces, respecting string boundaries
    stack = []
    start = -1
    in_string = False
    escape = False

    for i, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == '{':
            if not stack:
                start = i
            stack.append('{')
        elif char == '}':
            if stack:
                stack.pop()
                if not stack and start >= 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        continue

    # Fallback: try to find JSON between markdown code blocks
    code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Last resort: try parsing entire text
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def validate_analysis_output(analysis: Dict) -> Tuple[bool, str, Dict]:
    """Validate that LLM output has required structure.

    Returns (is_valid, error_message, cleaned_analysis).  The returned
    dictionary is a shallow copy with overall_score clamped and
    opportunities guaranteed to be a list.
    """
    if not isinstance(analysis, dict):
        return False, "Analysis is not a dictionary", {}

    cleaned = dict(analysis)

    # Check required fields
    required_fields = ['tech_layer', 'application', 'problem_solved',
                       'innovation_summary', 'differentiation', 'market_timing',
                       'ecosystem_position', 'commercialization_path']
    for field in required_fields:
        if field not in cleaned:
            return False, f"Missing required field: {field}", cleaned

    # Validate overall_score is numeric and clamp to [1, 10]
    score = cleaned.get('overall_score')
    if not isinstance(score, (int, float)):
        try:
            score = float(score) if score else 5
        except (ValueError, TypeError):
            score = 5
    try:
        if score != score:  # NaN check
            score = 5
        score = int(score)
    except (ValueError, OverflowError):
        score = 5
    cleaned['overall_score'] = min(10, max(1, score))

    # Ensure opportunities is a list
    opportunities = cleaned.get('opportunities')
    if not isinstance(opportunities, list):
        cleaned['opportunities'] = []

    return True, "", cleaned


def _format_prompt(template: str, values: Dict[str, str]) -> str:
    """Replace only known placeholders, leaving all other braces untouched."""
    if not values:
        return template
    # Sort keys by length descending so longer keys match before shorter prefixes
    sorted_keys = sorted(values.keys(), key=len, reverse=True)
    pattern = re.compile(r'\{(' + '|'.join(re.escape(k) for k in sorted_keys) + r')\}')
    return pattern.sub(lambda m: str(values.get(m.group(1), m.group(0))), template)


def generate_analysis_with_llm(project: Dict, cli_tool: str,
                                resilience_config: Optional[Dict] = None) -> Optional[Dict]:
    """Generate analysis using LLM via CLI tool."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'prompts', 'ai_analyze.md'
    )
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        print(f"  Prompt file not found: {prompt_path}")
        return None

    topics = project.get('topics')
    if isinstance(topics, list):
        topics = json.dumps(topics)

    # Format star history trajectory for the prompt
    star_history = project.get('star_history', [])
    if star_history and len(star_history) >= 2:
        traj_lines = ["| Date | Stars | Weekly Gain |"]
        traj_lines.append("|------|-------|-------------|")
        prev_stars = None
        for entry in star_history:
            sampled = entry.get('sampled_at') or 'N/A'
            date_str = str(sampled)[:10]
            try:
                stars = int(entry.get('stars', 0) or 0)
            except (ValueError, TypeError):
                stars = 0
            if prev_stars is not None and prev_stars > 0:
                gain = stars - prev_stars
                pct = f"{gain:+d} ({gain/prev_stars*100:+.1f}%)"
            else:
                pct = "—"
            traj_lines.append(f"| {date_str} | {stars} | {pct} |")
            prev_stars = stars
        star_trajectory = "\n".join(traj_lines)
    else:
        star_trajectory = "_No star history data available._"

    # Format peer comparison for competitive context
    peers = project.get('peers', [])
    percentile, below, total = project.get('peer_percentile', (0.0, 0, 0))
    if peers:
        peer_lines = ["| Project | Stars | URL |"]
        peer_lines.append("|---------|-------|-----|")
        for peer in peers:
            peer_name = peer.get('name') or 'Unknown'
            peer_stars = peer.get('stars') or 0
            peer_url = peer.get('url') or 'N/A'
            peer_lines.append(f"| {peer_name} | {peer_stars} | {peer_url} |")
        peer_lines.append("")
        peer_lines.append(
            f"Percentile in peer group: {percentile:.0f}% (above {below} of {total} peers)"
        )
        peer_comparison = "\n".join(peer_lines)
    else:
        peer_comparison = "_No peer projects found in this category._"

    # Format inflection point analysis
    inflection = project.get('inflection')
    if inflection:
        phase = inflection['phase']
        slope_r = inflection['slope_recent']
        slope_p = inflection['slope_prior']
        ratio = inflection['ratio']

        phase_desc = {
            'accelerating': 'Growth rate has accelerated significantly.',
            'stable_growth': 'Growth is steady and consistent.',
            'decelerating': 'Growth rate is slowing down.',
            'decline': 'Star growth has stalled or reversed.'
        }.get(phase, '')

        ratio_str = f"{ratio}x" if ratio is not None else "N/A (prior slope <= 0)"
        inflection_lines = [
            f"- Phase: {phase}",
            f"- Recent slope: {slope_r} stars/day",
            f"- Prior slope: {slope_p} stars/day",
            f"- Ratio (recent/prior): {ratio_str}",
            f"- Assessment: {phase_desc}"
        ]
        inflection_analysis = "\n".join(inflection_lines)
    else:
        inflection_analysis = "_Insufficient star history data for inflection analysis._"

    prompt = _format_prompt(prompt_template, {
        'name': project.get('name') or 'Unknown',
        'url': project.get('url') or 'N/A',
        'description': project.get('description') or 'N/A',
        'language': project.get('language') or 'N/A',
        'stars': project.get('stars') or 0,
        'topics': topics or '[]',
        'overall_score': (project.get('burst_signals') or {}).get('overall_score') if (project.get('burst_signals') or {}).get('overall_score') is not None else 'N/A',
        'star_velocity': (project.get('burst_signals') or {}).get('star_velocity_score') if (project.get('burst_signals') or {}).get('star_velocity_score') is not None else 'N/A',
        'activity_index': (project.get('burst_signals') or {}).get('activity_index_score') if (project.get('burst_signals') or {}).get('activity_index_score') is not None else 'N/A',
        'novelty': (project.get('burst_signals') or {}).get('novelty_score') if (project.get('burst_signals') or {}).get('novelty_score') is not None else 'N/A',
        'star_trajectory': star_trajectory,
        'peer_comparison': peer_comparison,
        'inflection_analysis': inflection_analysis,
        'readme_excerpt': project.get('readme') or '_README unavailable._',
    })

    try:
        # Handle CLI_TOOL that may contain spaces (e.g., "claude --dangerously-skip-permissions")
        cli_parts = shlex.split(cli_tool)
        if not cli_parts:
            print("  CLI tool is empty")
            return None
        cmd = cli_parts[0]
        extra_args = cli_parts[1:] if len(cli_parts) > 1 else []

        # Check if command exists
        if not shutil.which(cmd):
            print(f"  CLI tool not found: {cmd}")
            return None

        # Detect cursor/agent mode: prompt via stdin; claude mode: prompt via -p arg
        is_agent = os.path.basename(cmd) in ('agent', 'cursor-agent')

        # Avoid duplicate -p when CLI_TOOL already contains it.
        # Remove both the flag and its following argument value.
        if not is_agent:
            deduped = []
            skip_next = False
            for arg in extra_args:
                if skip_next:
                    skip_next = False
                    continue
                if arg == '-p':
                    skip_next = True
                    continue
                deduped.append(arg)
            extra_args = deduped

        cfg = resilience_config if isinstance(resilience_config, dict) else {}
        try:
            max_retries = int(cfg.get('max_retries', 2))
        except (ValueError, TypeError):
            max_retries = 2
        if max_retries < 1:
            max_retries = 1
        try:
            timeout = int(cfg.get('timeout_seconds', 300))
        except (ValueError, TypeError):
            timeout = 300
        if timeout < 1:
            timeout = 300
        for attempt in range(1, max_retries + 1):
            try:
                if is_agent:
                    result = subprocess.run(
                        [cmd] + extra_args,
                        input=prompt,
                        capture_output=True, text=True, timeout=timeout, shell=False
                    )
                else:
                    result = subprocess.run(
                        [cmd] + extra_args + ['-p', prompt],
                        capture_output=True, text=True, timeout=timeout, shell=False
                    )

                if result.returncode != 0:
                    print(f"  LLM error (attempt {attempt}/{max_retries}): {result.stderr}")
                    if attempt < max_retries:
                        continue
                    return None

                analysis = extract_json_from_text(result.stdout)
                if analysis is None:
                    print(f"  Could not parse LLM response (attempt {attempt}/{max_retries})")
                    if attempt < max_retries:
                        continue
                    return None

                # Validate output structure
                valid, error, analysis = validate_analysis_output(analysis)
                if not valid:
                    print(f"  Invalid LLM output (attempt {attempt}/{max_retries}): {error}")
                    if attempt < max_retries:
                        continue
                    return None

                return analysis

            except (subprocess.SubprocessError, OSError) as e:
                print(f"  Error calling LLM (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    continue
                return None

    except (OSError, ValueError) as e:
        print(f"  Error calling LLM: {e}")
        return None


def generate_heuristic_analysis(project: Dict) -> Dict:
    """Generate a basic heuristic analysis when LLM is unavailable."""
    description = (project.get('description') or '').lower()
    topics = project.get('topics', '[]') or '[]'
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except (json.JSONDecodeError, TypeError):
            topics = []
    if not topics:
        topics = []
    topics_str = ' '.join(str(t) for t in topics).lower()

    # Determine tech layer (whole-word match to avoid false positives)
    tech_layer = 'ai_application'
    if any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['model', 'llm', 'gpt', 'foundation', 'bert']):
        if any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['inference', 'serving', 'deployment']):
            tech_layer = 'inference_engine'
        else:
            tech_layer = 'foundation_model'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['training', 'fine-tune', 'distributed']):
        tech_layer = 'training_framework'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['inference', 'serving', 'deployment']):
        tech_layer = 'inference_engine'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['tool', 'sdk', 'library', 'framework']):
        tech_layer = 'ai_toolchain'

    # Determine application
    application = 'multimodal'
    if any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['code', 'coding', 'programming', 'developer']):
        application = 'code_generation'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['image', 'diffusion', 'stable-diffusion', 'vision']):
        application = 'image_generation'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['agent', 'autonomous', 'bot']):
        application = 'agent'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['data', 'annotation', 'label', 'dataset']):
        application = 'data_annotation'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(description, kw) for kw in ['eval', 'benchmark', 'safety', 'test']):
        application = 'model_evaluation'

    # Heuristic path provides classification only. Subjective narrative fields
    # stay empty and no opportunities are fabricated (LLM path owns those).

    return {
        'tech_layer': tech_layer,
        'application': application,
        'problem_solved': '',
        'innovation_summary': '',
        'differentiation': '',
        'market_timing': '',
        'ecosystem_position': 'application_layer' if tech_layer == 'ai_application' else ('base_layer' if tech_layer in ('foundation_model', 'training_framework') else 'middleware'),
        'commercialization_path': '',
        'overall_score': min(10, max(1, 5 + int(float(((project.get('burst_signals') or {}).get('overall_score') or 0)) * 5))),
        'opportunities': []
    }


def run_analysis(db: Database, scheduler: Scheduler, date: str,
                 use_llm: bool = False, cli_tool: str = None, max_tasks: int = 10,
                 resilience_config: Optional[Dict] = None):
    """Run the analysis stage."""
    print("=== Stage 4: Deep Analysis ===")

    tasks = get_pending_analysis_tasks(db, date, max_tasks)
    if not tasks:
        print("No pending tasks to analyze.")
        return 0

    print(f"Found {len(tasks)} tasks to analyze")

    analyzed = 0
    total_opportunities = 0

    for task in tasks:
        project_id = task['project_id']
        print(f"\nAnalyzing: {project_id}")

        conn = db.get_conn()
        previous_status = 'scheduled'
        committed = False
        try:
            # Save previous status for recovery on failure
            prev_status_row = conn.execute(
                "SELECT status FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            previous_status = (prev_status_row['status'] or 'scheduled') if prev_status_row else 'scheduled'

            # Mark task as running and project as analyzing (same transaction)
            scheduler.mark_task_running(task['id'], conn=conn)
            conn.execute("UPDATE projects SET status='analyzing' WHERE id=?", (project_id,))
            conn.commit()

            # Get project data
            project = get_project_data(db, project_id, conn=conn)
            if not project:
                print(f"  Project not found: {project_id}")
                scheduler.mark_task_failed(task['id'], 'project_not_found', conn=conn)
                conn.execute("UPDATE projects SET status=? WHERE id=?", (previous_status, project_id))
                conn.commit()
                continue

            # Generate analysis
            if use_llm and cli_tool:
                analysis = generate_analysis_with_llm(project, cli_tool, resilience_config)
                analyzer_version = 'llm-v1'
            else:
                analysis = None
                analyzer_version = 'llm-v1'

            if not analysis:
                print(f"  Using heuristic analysis (LLM unavailable)")
                analysis = generate_heuristic_analysis(project)
                analyzer_version = 'heuristic-v1'

            # Store analysis and opportunities atomically (shared conn)
            opportunities_count = store_analysis_and_opportunities(
                db, project_id, analysis, conn=conn, analyzer_version=analyzer_version
            )

            # Mark task complete and project as active (same transaction)
            scheduler.mark_task_done(task['id'], opportunities_count, conn=conn)
            conn.execute("UPDATE projects SET status='active' WHERE id=?", (project_id,))
            conn.commit()
            committed = True

            analyzed += 1
            total_opportunities += opportunities_count

            print(f"  Analyzed: {opportunities_count} opportunities found")

        except Exception as e:
            print(f"  Error analyzing {project_id}: {e}")
            if committed:
                print(f"  Warning: Exception after commit; task already marked done")
            else:
                try:
                    conn.rollback()
                    scheduler.mark_task_failed(task['id'], str(e)[:100], conn=conn)
                    conn.execute("UPDATE projects SET status=? WHERE id=?", (previous_status, project_id))
                    conn.commit()
                except Exception as status_err:
                    print(f"  Warning: Could not reset project status: {status_err}")
        finally:
            conn.close()

    print(f"\nAnalyzed {analyzed} projects, found {total_opportunities} opportunities")
    return analyzed


def main():
    parser = argparse.ArgumentParser(description="Deep analysis of AI projects")
    parser.add_argument('--date', help="Analysis date (YYYY-MM-DD)")
    parser.add_argument('--use-llm', action='store_true',
                        help="Use LLM for analysis (requires CLI_TOOL env)")
    parser.add_argument('--max-tasks', type=int, default=10,
                        help="Maximum tasks to process")
    args = parser.parse_args()

    if args.max_tasks <= 0:
        print("ERROR: max-tasks must be a positive integer")
        sys.exit(1)

    # Get CLI tool from environment (only if --use-llm is specified)
    cli_tool = os.environ.get('CLI_TOOL', 'claude') if args.use_llm else None

    # Get date
    if args.date:
        date = args.date
    else:
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    db = Database()
    scheduler = Scheduler(db.db_path, {})

    config = ConfigLoader()
    resilience_cfg = config.get_resilience_config().get('llm_analysis', {})

    run_analysis(db, scheduler, date,
                 use_llm=args.use_llm,
                 cli_tool=cli_tool,
                 max_tasks=args.max_tasks,
                 resilience_config=resilience_cfg)


if __name__ == '__main__':
    main()
