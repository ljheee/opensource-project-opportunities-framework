#!/usr/bin/env python3
"""
Stage 3: Semantic Filtering for AI Projects
Classifies discovered projects using heuristics and updates their status.
"""
import os
import sys
import json
import sqlite3
import argparse
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database
from framework.core.config_loader import ConfigLoader

_FILTER_CFG = None


def _get_filter_cfg() -> dict:
    global _FILTER_CFG
    if _FILTER_CFG is None:
        _FILTER_CFG = ConfigLoader().get_filters()
    return _FILTER_CFG


def get_discovered_projects(db: Database, limit: int = 50) -> list:
    """Get projects awaiting semantic filtering."""
    conn = db.get_conn()
    try:
        cursor = conn.execute(
            "SELECT * FROM projects WHERE status='discovered' ORDER BY first_seen_at ASC, id ASC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_project_status(db: Database, project_id: str, status: str,
                          tech_layer: str = None, application: str = None,
                          filter_reason: str = None):
    """Update project classification and status."""
    conn = db.get_conn()
    try:
        if status == 'scheduled':
            conn.execute("""
                UPDATE projects
                SET status='scheduled', tech_layer=?, application=?, filter_reason=?
                WHERE id=?
            """, (tech_layer, application, filter_reason or 'valid_ai_project', project_id))
        else:
            conn.execute("""
                UPDATE projects
                SET status='filtered_skip', tech_layer=NULL, application=NULL, filter_reason=?
                WHERE id=?
            """, (filter_reason, project_id))
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def classify_project_heuristic(project: dict) -> tuple:
    """
    Heuristic classification based on project metadata.
    Returns: (should_keep, tech_layer, application, reason)
    """
    name = (project.get('name') or '').lower()
    desc = (project.get('description') or '').lower()
    topics = project.get('topics', '[]') or '[]'
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except (json.JSONDecodeError, TypeError):
            topics = []
    if not topics:
        topics = []
    topics_str = ' '.join(str(t) for t in topics).lower()

    cfg = _get_filter_cfg()

    def _is_whole_word(text: str, pattern: str) -> bool:
        """Check if pattern appears as a whole word in text."""
        if not text or not pattern:
            return False
        pattern = str(pattern)
        for match in re.finditer(re.escape(pattern), text, re.IGNORECASE):
            start, end = match.span()
            left_ok = start == 0 or not text[start - 1].isalnum()
            right_ok = end == len(text) or not text[end].isalnum()
            if left_ok and right_ok:
                return True
        return False

    # Skip patterns from config
    skip_patterns = cfg.get('skip_patterns', [])
    if not isinstance(skip_patterns, list):
        skip_patterns = []
    for pattern in skip_patterns:
        pattern = str(pattern) if pattern is not None else ''
        if not pattern:
            continue
        if _is_whole_word(name, pattern) or _is_whole_word(desc, pattern):
            return False, None, None, f'skip_pattern:{pattern}'

    # Check for AI focus via topics and description
    cat_kw = cfg.get('category_keywords', {})
    if not isinstance(cat_kw, dict):
        cat_kw = {}
    ai_keywords = cat_kw.get('ai', [])
    if not isinstance(ai_keywords, list):
        ai_keywords = []
    has_ai_focus = any(
        _is_whole_word(topics_str, str(kw)) or _is_whole_word(desc, str(kw))
        for kw in ai_keywords if kw is not None
    )

    if not has_ai_focus:
        return False, None, None, 'no_ai_focus'

    # Tech layer classification from config rules
    tech_layer_rules = cfg.get('tech_layer_rules', {})
    if not isinstance(tech_layer_rules, dict):
        tech_layer_rules = {}
    tech_layer = 'ai_application'  # default
    for layer, keywords in tech_layer_rules.items():
        if not isinstance(keywords, list):
            continue
        if any(_is_whole_word(topics_str, str(kw)) or _is_whole_word(desc, str(kw)) for kw in keywords if kw is not None):
            if layer == 'foundation_model':
                if any(_is_whole_word(topics_str, kw) or _is_whole_word(desc, kw) for kw in ['inference', 'serving', 'deployment']):
                    tech_layer = 'inference_engine'
                else:
                    tech_layer = 'foundation_model'
            else:
                tech_layer = layer
            break

    # Application classification (whole-word to avoid substring false positives)
    application = 'multimodal'  # default
    if any(_is_whole_word(topics_str, kw) or _is_whole_word(desc, kw)
           for kw in ['code', 'coding', 'programming', 'developer']):
        application = 'code_generation'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(desc, kw)
             for kw in ['image', 'diffusion', 'stable-diffusion', 'vision']):
        application = 'image_generation'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(desc, kw)
             for kw in ['agent', 'autonomous', 'bot']):
        application = 'agent'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(desc, kw)
             for kw in ['data', 'annotation', 'label', 'dataset']):
        application = 'data_annotation'
    elif any(_is_whole_word(topics_str, kw) or _is_whole_word(desc, kw)
             for kw in ['eval', 'benchmark', 'safety', 'test']):
        application = 'model_evaluation'

    return True, tech_layer, application, 'valid_ai_project'


def run_filter(db: Database, dry_run: bool = False, limit: int = 50):
    """Run the semantic filtering stage."""
    print("=== Stage 3: Semantic Filtering ===")

    projects = get_discovered_projects(db, limit=limit)
    if not projects:
        print("No projects to filter.")
        return 0

    print(f"Found {len(projects)} projects to classify")

    if dry_run:
        print("\nDry run - showing classifications:")
        for proj in projects:
            keep, tech, app, reason = classify_project_heuristic(proj)
            action = "KEEP" if keep else "SKIP"
            print(f"  {action}: {proj['id']} -> {tech}/{app} ({reason})")
        return len(projects)

    # Classify each project
    processed = 0
    kept = 0
    skipped = 0

    for proj in projects:
        try:
            keep, tech_layer, application, reason = classify_project_heuristic(proj)

            if keep:
                update_project_status(db, proj['id'], 'scheduled',
                                      tech_layer, application, reason)
                kept += 1
            else:
                update_project_status(db, proj['id'], 'filtered_skip',
                                      filter_reason=reason)
                skipped += 1

            processed += 1
        except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
            print(f"  Error processing {proj['id']}: {e}")
            try:
                update_project_status(db, proj['id'], 'filtered_skip',
                                      filter_reason=f'filter_error:{e}')
            except Exception as mark_err:
                print(f"  Warning: Could not mark {proj['id']} as failed: {mark_err}")

    print(f"\nProcessed {processed} projects: {kept} kept, {skipped} skipped")
    return processed


def main():
    parser = argparse.ArgumentParser(description="Semantic filtering for AI projects")
    parser.add_argument('--dry-run', action='store_true',
                        help="Don't write to database")
    parser.add_argument('--limit', type=int, default=50,
                        help="Max projects to classify per invocation")
    args = parser.parse_args()

    if args.limit <= 0:
        print("ERROR: limit must be a positive integer")
        sys.exit(1)

    db = Database()
    run_filter(db, dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
