#!/usr/bin/env python3
import os
import sys
import argparse
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database


def _escape_md(text) -> str:
    if text is None:
        return ''
    text = str(text).replace('\\', '\\\\').replace('|', '\\|')
    text = text.replace('[', '\\[').replace(']', '\\]')
    text = text.replace('*', '\\*').replace('_', '\\_')
    text = text.replace('`', '\\`').replace('<', '\\<').replace('>', '\\>')
    text = text.replace('(', '\\(').replace(')', '\\)')
    text = text.replace('\r', ' ').replace('\t', ' ').replace('\n', ' ')
    return text


class ReportGenerator:
    def __init__(self, db: Database):
        self.db = db

    def generate(self, date: str):
        conn = self.db.get_conn()
        try:
            # Get early-burst projects (latest record per project today, then filter is_early_burst)
            projects = conn.execute('''
                SELECT p.*, e.overall_score, e.star_velocity_score,
                       e.activity_index_score, e.community_buzz_score, e.novelty_score
                FROM projects p
                JOIN (
                    SELECT project_id, overall_score, star_velocity_score,
                           activity_index_score, community_buzz_score, novelty_score, is_early_burst,
                           ROW_NUMBER() OVER (
                               PARTITION BY project_id ORDER BY calculated_at DESC
                           ) as rn
                    FROM early_burst_signals
                ) e ON p.id = e.project_id AND e.rn = 1 AND e.is_early_burst = 1
                ORDER BY CAST(e.overall_score AS REAL) DESC
            ''').fetchall()

            # Get summary stats
            total_projects = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE date(first_seen_at) <= ? OR first_seen_at IS NULL OR first_seen_at = ''",
                (date,)
            ).fetchone()[0]

            total_early_burst = conn.execute("""
                SELECT COUNT(DISTINCT project_id) FROM (
                    SELECT project_id, is_early_burst,
                           ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) as rn
                    FROM early_burst_signals
                ) WHERE rn = 1 AND is_early_burst = 1
            """).fetchone()[0]

            total_analyzed = conn.execute(
                "SELECT COUNT(DISTINCT project_id) FROM analyses WHERE date(analyzed_at) = ?",
                (date,)
            ).fetchone()[0]

            open_opportunities = conn.execute(
                "SELECT COUNT(*) FROM opportunities WHERE status = 'open'"
            ).fetchone()[0]

            # Validation metrics
            try:
                total_evaluated = int(conn.execute(
                    "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome IN ('true_positive', 'false_positive')"
                ).fetchone()[0] or 0)
            except (ValueError, TypeError):
                total_evaluated = 0
            try:
                tp_count = int(conn.execute(
                    "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'true_positive'"
                ).fetchone()[0] or 0)
            except (ValueError, TypeError):
                tp_count = 0
            try:
                fp_count = int(conn.execute(
                    "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'false_positive'"
                ).fetchone()[0] or 0)
            except (ValueError, TypeError):
                fp_count = 0
            try:
                fn_count = int(conn.execute(
                    "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'false_negative'"
                ).fetchone()[0] or 0)
            except (ValueError, TypeError):
                fn_count = 0
            try:
                tn_count = int(conn.execute(
                    "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'true_negative'"
                ).fetchone()[0] or 0)
            except (ValueError, TypeError):
                tn_count = 0

            # Tech stack distribution (latest analysis per project only)
            tech_distribution = conn.execute('''
                SELECT tech_layer, COUNT(*) as count
                FROM (
                    SELECT tech_layer,
                           ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY analyzed_at DESC) as rn
                    FROM analyses
                    WHERE tech_layer IS NOT NULL AND tech_layer != ''
                )
                WHERE rn = 1
                GROUP BY tech_layer
                ORDER BY count DESC
            ''').fetchall()

            # Top opportunities sorted by impact_potential and overall_score.
            # Join each opportunity to the analysis that GENERATED it
            # (analyzed_at = source_analysis_date) so its score is the one it
            # earned — not whatever the project's latest analysis scored.
            # Exclude heuristic/template analyses (they produce no real opportunities;
            # legacy v1.0 rows are pre-tagging template output).
            top_opportunities = conn.execute('''
                SELECT o.*, p.name as project_name, p.url as project_url, a.overall_score
                FROM opportunities o
                JOIN projects p ON o.project_id = p.id
                LEFT JOIN analyses a
                    ON a.project_id = o.project_id
                    AND a.analyzed_at = o.source_analysis_date
                WHERE o.status = 'open'
                  AND COALESCE(a.analyzer_version, '') NOT IN ('heuristic-v1', 'v1.0')
                ORDER BY
                    CASE o.impact_potential
                        WHEN 'high' THEN 3
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END DESC,
                    COALESCE(a.overall_score, 0) DESC
                LIMIT 20
            ''').fetchall()

            # Generate markdown
            lines = [
                f"# AI Project Opportunities Report - {date}",
                "",
                "## Global Statistics",
                "",
                f"- **Total projects tracked:** {total_projects}",
                f"- **Early-burst projects detected (all time):** {total_early_burst}",
                f"- **Projects analyzed today:** {total_analyzed}",
                f"- **Open opportunities:** {open_opportunities}",
                "",
                "## Validation Metrics",
                "",
            ]

            if total_evaluated > 0 or (fn_count + tn_count) > 0:
                if total_evaluated > 0:
                    precision = tp_count / total_evaluated
                    try:
                        avg_tp = float(conn.execute('''
                            SELECT AVG(growth_rate_actual) FROM prediction_outcomes
                            WHERE outcome = 'true_positive'
                        ''').fetchone()[0] or 0)
                    except (ValueError, TypeError):
                        avg_tp = 0.0
                    try:
                        avg_fp = float(conn.execute('''
                            SELECT AVG(growth_rate_actual) FROM prediction_outcomes
                            WHERE outcome = 'false_positive'
                        ''').fetchone()[0] or 0)
                    except (ValueError, TypeError):
                        avg_fp = 0.0
                    try:
                        avg_pred_tp = float(conn.execute('''
                            SELECT AVG(growth_rate_predicted) FROM prediction_outcomes
                            WHERE outcome = 'true_positive'
                        ''').fetchone()[0] or 0)
                    except (ValueError, TypeError):
                        avg_pred_tp = 0.0
                    try:
                        avg_pred_fp = float(conn.execute('''
                            SELECT AVG(growth_rate_predicted) FROM prediction_outcomes
                            WHERE outcome = 'false_positive'
                        ''').fetchone()[0] or 0)
                    except (ValueError, TypeError):
                        avg_pred_fp = 0.0
                    lines.append(f"- **Predictions evaluated:** {total_evaluated} (TP: {tp_count}, FP: {fp_count})")
                    lines.append(f"- **Precision (7d+ horizon):** {precision:.1%}")
                    lines.append(f"- **Avg actual growth — TP:** {avg_tp:.1f} stars/day, FP: {avg_fp:.1f} stars/day")
                    lines.append(f"- **Avg predicted growth — TP:** {avg_pred_tp:.1f} stars/day, FP: {avg_pred_fp:.1f} stars/day")
                lines.append(f"- **Missed bursts (FN):** {fn_count} | **Correctly passed (TN):** {tn_count}")
                tp_trending = int(conn.execute('''
                    SELECT COUNT(*) FROM prediction_outcomes po
                    JOIN projects p ON po.project_id = p.id
                    WHERE po.outcome = 'true_positive'
                      AND COALESCE(po.source_at_pred, p.source) = 'trending'
                ''').fetchone()[0] or 0)
                if tp_trending + fn_count > 0:
                    recall = tp_trending / (tp_trending + fn_count)
                    lines.append(f"- **Recall (trending-source):** {recall:.1%}")

                # Score bucket calibration table
                buckets = conn.execute('''
                    SELECT
                        CASE
                            WHEN overall_score_at_prediction >= 0.8 THEN '0.8+'
                            WHEN overall_score_at_prediction >= 0.7 THEN '0.7-0.8'
                            WHEN overall_score_at_prediction >= 0.65 THEN '0.65-0.7'
                            ELSE '<0.65'
                        END as bucket,
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome = 'true_positive' THEN 1 ELSE 0 END) as tp_count
                    FROM prediction_outcomes
                    WHERE outcome IN ('true_positive', 'false_positive')
                    GROUP BY bucket
                    ORDER BY MIN(overall_score_at_prediction) DESC
                ''').fetchall()

                if buckets:
                    lines.extend(["", "### Score Bucket Calibration", "", "| Bucket | Evaluated | Precision |", "|--------|-----------|-----------|"])
                    for b in buckets:
                        try:
                            b_total = int(b['total']) if b['total'] is not None else 0
                        except (ValueError, TypeError):
                            b_total = 0
                        try:
                            b_tp = int(b['tp_count']) if b['tp_count'] is not None else 0
                        except (ValueError, TypeError):
                            b_tp = 0
                        b_prec = b_tp / b_total if b_total > 0 else 0
                        lines.append(f"| {b['bucket']} | {b_total} | {b_prec:.1%} |")
            else:
                lines.append("_No predictions have matured enough for evaluation._")

            lines.extend([
                "",
                "---",
                "",
                "## Tech Stack Distribution",
                ""
            ])

            if tech_distribution:
                lines.extend(["| Tech Layer | Count |", "|------------|-------|"])
                for row in tech_distribution:
                    lines.append(f"| {_escape_md(row['tech_layer'])} | {row['count']} |")
                lines.append("")
            else:
                lines.extend(["_No tech layer data available._", ""])

            lines.extend([
                "---",
                "",
                f"## Top Opportunities",
                ""
            ])

            if top_opportunities:
                lines.extend([
                    "| # | Project | Opportunity | Type | Impact | Score | Difficulty | Horizon |",
                    "|---|---------|-------------|------|--------|-------|------------|---------|"
                ])
                for i, opp in enumerate(top_opportunities, 1):
                    score = opp['overall_score'] if opp['overall_score'] is not None else 'N/A'
                    proj_name = _escape_md(opp['project_name']) or 'Unnamed'
                    raw_url = opp['project_url'] or ''
                    safe_url = _escape_md(quote(raw_url, safe='/:?#[]@!$&\'*+,;=')) if raw_url else 'N/A'
                    raw_title = _escape_md(opp['title']) or 'Untitled'
                    opp_title = raw_title if len(raw_title) <= 80 else raw_title[:77] + '...'
                    opp_type = _escape_md(opp['opportunity_type']) or 'unknown'
                    impact = _escape_md(opp['impact_potential']) or 'N/A'
                    difficulty = _escape_md(opp['difficulty']) or 'N/A'
                    horizon = _escape_md(opp['time_horizon']) or 'N/A'
                    lines.append(
                        f"| {i} | [{proj_name}]({safe_url}) | {opp_title} | "
                        f"{opp_type} | {impact} | {score} | "
                        f"{difficulty} | {horizon} |"
                    )
                lines.append("")
            else:
                lines.extend(["_No open opportunities found._", ""])

            lines.extend([
                "---",
                "",
                f"## Early-Burst Projects ({len(projects)})",
                ""
            ])

            for i, p in enumerate(projects, 1):
                tech = _escape_md(p['tech_layer']) or 'TBD'
                app = _escape_md(p['application']) or 'TBD'
                proj_name = _escape_md(p['name']) or 'Unnamed'
                proj_url = _escape_md(p['url']) or 'N/A'
                raw_desc = _escape_md(p['description']) or 'No description'
                proj_desc = raw_desc if len(raw_desc) <= 200 else raw_desc[:197] + '...'
                lang = _escape_md(p['language']) or 'N/A'

                lines.extend([
                    f"### {i}. {proj_name}",
                    "",
                    f"**Score:** {float(p['overall_score'] or 0):.2f} (Velocity: {float(p['star_velocity_score'] or 0):.2f}, Activity: {float(p['activity_index_score'] or 0):.2f}, Buzz: {float(p['community_buzz_score'] or 0):.2f}, Novelty: {float(p['novelty_score'] or 0):.2f})",
                    "",
                    f"**Classification:** {tech} / {app}",
                    "",
                    f"**Stars:** {p['stars'] or 0} | **Language:** {lang}",
                    "",
                    f"**URL:** {proj_url}",
                    "",
                    f"**Description:** {proj_desc}",
                    "",
                    "---",
                    ""
                ])


            # Write report
            report_path = os.path.join(
                os.path.dirname(self.db.db_path),
                'reports',
                f'{date}.md'
            )

            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            print(f"Report generated: {report_path}")

        finally:
            conn.close()


import re

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True)
    args = parser.parse_args()

    if not re.match(r'^\d{4}-\d{2}-\d{2}$', args.date):
        print("ERROR: date must be in YYYY-MM-DD format")
        sys.exit(1)

    db = Database()
    generator = ReportGenerator(db)
    generator.generate(args.date)


if __name__ == '__main__':
    main()
