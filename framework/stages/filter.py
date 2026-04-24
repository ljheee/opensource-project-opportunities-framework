#!/usr/bin/env python3
"""
Stage 3: Semantic Filtering for AI Projects
Classifies discovered projects using heuristics and updates their status.
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database


def get_discovered_projects(db: Database, limit: int = 50) -> list:
    """Get projects awaiting semantic filtering."""
    conn = db.get_conn()
    try:
        cursor = conn.execute(
            "SELECT * FROM projects WHERE status='discovered' LIMIT ?",
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
                SET status='filtered_skip', filter_reason=?
                WHERE id=?
            """, (filter_reason, project_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def classify_project_heuristic(project: dict) -> tuple:
    """
    Heuristic classification based on project metadata.
    Returns: (should_keep, tech_layer, application, reason)
    """
    name = project.get('name', '').lower()
    desc = (project.get('description') or '').lower()
    topics = project.get('topics', '[]') or '[]'
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except:
            topics = []
    if not topics:
        topics = []
    topics_str = ' '.join(topics).lower()

    # Skip patterns
    skip_patterns = ['awesome', 'tutorial', 'demo', 'examples', 'course',
                     'curated-list', 'awesome-list', 'playground']
    for pattern in skip_patterns:
        if pattern in name or pattern in desc:
            return False, None, None, f'skip_pattern:{pattern}'

    # Check for AI focus via topics and description
    ai_keywords = ['llm', 'ai', 'machine-learning', 'deep-learning', 'neural',
                   'transformer', 'gpt', 'bert', 'llama', 'model', 'inference',
                   'training', 'fine-tuning', 'embedding', 'vector', 'agent',
                   'generative', 'diffusion', 'stable-diffusion', 'openai',
                   'langchain', 'huggingface', 'pytorch', 'tensorflow']

    has_ai_focus = any(kw in topics_str or kw in desc for kw in ai_keywords)

    if not has_ai_focus:
        return False, None, None, 'no_ai_focus'

    # Tech layer classification
    tech_layer = 'ai_application'  # default
    if any(kw in topics_str or kw in desc for kw in ['foundation', 'llm', 'model', 'gpt', 'bert']):
        if 'inference' in desc or 'serving' in desc or 'deployment' in desc:
            tech_layer = 'inference_engine'
        else:
            tech_layer = 'foundation_model'
    elif any(kw in topics_str or kw in desc for kw in ['training', 'fine-tune', 'distributed']):
        tech_layer = 'training_framework'
    elif any(kw in topics_str or kw in desc for kw in ['tool', 'sdk', 'library', 'framework']):
        tech_layer = 'ai_toolchain'

    # Application classification
    application = 'multimodal'  # default
    if any(kw in topics_str or kw in desc for kw in ['code', 'coding', 'programming', 'developer']):
        application = 'code_generation'
    elif any(kw in topics_str or kw in desc for kw in ['image', 'diffusion', 'stable-diffusion', 'vision']):
        application = 'image_generation'
    elif any(kw in topics_str or kw in desc for kw in ['agent', 'autonomous', 'bot']):
        application = 'agent'
    elif any(kw in topics_str or kw in desc for kw in ['data', 'annotation', 'label', 'dataset']):
        application = 'data_annotation'
    elif any(kw in topics_str or kw in desc for kw in ['eval', 'benchmark', 'safety', 'test']):
        application = 'model_evaluation'

    return True, tech_layer, application, 'valid_ai_project'


def run_filter(db: Database, dry_run: bool = False):
    """Run the semantic filtering stage."""
    print("=== Stage 3: Semantic Filtering ===")

    projects = get_discovered_projects(db)
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
        except Exception as e:
            print(f"  Error processing {proj['id']}: {e}")

    print(f"\nProcessed {processed} projects: {kept} kept, {skipped} skipped")
    return processed


def main():
    parser = argparse.ArgumentParser(description="Semantic filtering for AI projects")
    parser.add_argument('--dry-run', action='store_true',
                        help="Don't write to database")
    args = parser.parse_args()

    db = Database()
    run_filter(db, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
