#!/usr/bin/env python3
"""
LLM Top-N Re-analysis Stage
对当前 early-burst 头部项目执行证据化 LLM 分析（L2 通路）。

用途：CI 环境无 LLM CLI，只能产出 heuristic 分类；本 stage 在本地运行，
为高分项目补充带 evidence_json 的真实分析。幂等：近 7 天内已有 llm-v1
分析的项目自动跳过。

用法：
    USE_LLM=true CLI_TOOL="claude --dangerously-skip-permissions" \
        python framework/stages/llm_top.py --max 5
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.analyze import (
    get_project_data,
    generate_analysis_with_llm,
    store_analysis_and_opportunities,
)

REANALYZE_DAYS = 7


def get_llm_candidates(db: Database, limit: int) -> list:
    """Top early-burst projects without a recent llm-v1 analysis."""
    conn = db.get_conn()
    try:
        cursor = conn.execute('''
            SELECT e.project_id, e.overall_score
            FROM early_burst_signals e
            JOIN (
                SELECT project_id, MAX(calculated_at) as latest_at
                FROM early_burst_signals
                GROUP BY project_id
            ) latest ON e.project_id = latest.project_id
                     AND e.calculated_at = latest.latest_at
            WHERE e.is_early_burst = 1
              AND EXISTS (
                  -- 只重分析已完成过任务的项目：否则 CI 的 heuristic 任务仍会排期，
                  -- 更新的 heuristic-v1 行会盖过本分析的分类输出（review 中-2）
                  SELECT 1 FROM tasks t
                  WHERE t.project_id = e.project_id AND t.status = 'done'
              )
              AND NOT EXISTS (
                  SELECT 1 FROM analyses a
                  WHERE a.project_id = e.project_id
                    AND a.analyzer_version = 'llm-v1'
                    AND a.analyzed_at >= datetime('now', '-' || ? || ' days')
              )
            ORDER BY e.overall_score DESC, e.project_id ASC
            LIMIT ?
        ''', (REANALYZE_DAYS, limit))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def run(db: Database, max_projects: int, cli_tool: str) -> int:
    print("=== LLM Top-N Re-analysis ===")
    candidates = get_llm_candidates(db, max_projects)
    if not candidates:
        print("No candidates (all top projects already analyzed recently).")
        return 0
    print(f"Candidates: {len(candidates)}")

    config = ConfigLoader()
    resilience_cfg = config.get_resilience_config().get('llm_analysis', {})

    analyzed = 0
    for cand in candidates:
        project_id = cand['project_id']
        print(f"\nAnalyzing: {project_id} (burst score {cand['overall_score']:.2f})")
        conn = db.get_conn()
        try:
            project = get_project_data(db, project_id, conn=conn)
            if not project:
                print(f"  Project not found: {project_id}")
                continue
            analysis = generate_analysis_with_llm(project, cli_tool, resilience_cfg)
            if not analysis:
                print("  LLM analysis unavailable/failed, skipping")
                continue
            evidence = {
                'innovation_evidence': analysis.get('innovation_evidence') or [],
                'problem_evidence': analysis.get('problem_evidence') or [],
                'confidence': analysis.get('confidence') or 'medium',
                'cannot_determine': analysis.get('cannot_determine') or [],
                'validation': analysis.get('_evidence_meta') or {},
            }
            opportunities_count = store_analysis_and_opportunities(
                db, project_id, analysis, conn=conn,
                analyzer_version='llm-v1', evidence=evidence
            )
            conn.commit()
            analyzed += 1
            print(f"  Done: {opportunities_count} opportunities, "
                  f"confidence={evidence['confidence']}, "
                  f"stripped={evidence['validation']}")
        except Exception as e:
            conn.rollback()
            print(f"  Error analyzing {project_id}: {e}")
        finally:
            conn.close()

    print(f"\nAnalyzed {analyzed}/{len(candidates)} projects with LLM")
    return analyzed


def main():
    parser = argparse.ArgumentParser(description="LLM re-analysis of top early-burst projects")
    parser.add_argument('--max', type=int, default=5, help="Max projects to analyze")
    args = parser.parse_args()
    if args.max <= 0:
        print("ERROR: --max must be a positive integer")
        sys.exit(1)

    if os.environ.get('USE_LLM', 'false') != 'true':
        print("ERROR: set USE_LLM=true (and CLI_TOOL) to run this stage")
        sys.exit(1)
    cli_tool = os.environ.get('CLI_TOOL', 'claude')

    run(Database(), args.max, cli_tool)


if __name__ == '__main__':
    main()
