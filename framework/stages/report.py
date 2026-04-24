#!/usr/bin/env python3
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database


class ReportGenerator:
    def __init__(self, db: Database):
        self.db = db

    def generate(self, date: str):
        conn = self.db.get_conn()
        try:
            # Get early-burst projects
            projects = conn.execute('''
                SELECT p.*, e.overall_score, e.star_velocity_score,
                       e.activity_index_score, e.novelty_score
                FROM projects p
                JOIN early_burst_signals e ON p.id = e.project_id
                WHERE e.is_early_burst = 1
                AND date(e.calculated_at) = ?
                ORDER BY e.overall_score DESC
            ''', (date,)).fetchall()

            # Get top opportunities
            opportunities = conn.execute('''
                SELECT o.*, p.name as project_name, p.url as project_url
                FROM opportunities o
                JOIN projects p ON o.project_id = p.id
                WHERE o.impact_potential = 'high'
                AND date(o.source_analysis_date) = ?
                ORDER BY o.source_analysis_date DESC
                LIMIT 20
            ''', (date,)).fetchall()

            # Get summary stats
            total_projects = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE date(first_seen_at) <= ?",
                (date,)
            ).fetchone()[0]

            total_analyzed = conn.execute(
                "SELECT COUNT(*) FROM analyses WHERE date(analyzed_at) = ?",
                (date,)
            ).fetchone()[0]

            # Generate markdown
            lines = [
                f"# AI Project Opportunities Report - {date}",
                "",
                "## Summary",
                "",
                f"- **Total projects tracked:** {total_projects}",
                f"- **Early-burst projects detected:** {len(projects)}",
                f"- **Projects analyzed today:** {total_analyzed}",
                f"- **High-impact opportunities identified:** {len(opportunities)}",
                "",
                "---",
                "",
                f"## Early-Burst Projects ({len(projects)})",
                ""
            ]

            for i, p in enumerate(projects, 1):
                tech = p['tech_layer'] or 'TBD'
                app = p['application'] or 'TBD'

                lines.extend([
                    f"### {i}. {p['name']}",
                    "",
                    f"**Score:** {p['overall_score']:.2f} (Velocity: {p['star_velocity_score']:.2f}, Activity: {p['activity_index_score']:.2f}, Novelty: {p['novelty_score']:.2f})",
                    "",
                    f"**Classification:** {tech} / {app}",
                    "",
                    f"**Stars:** {p['stars']} | **Language:** {p['language'] or 'N/A'}",
                    "",
                    f"**URL:** {p['url']}",
                    "",
                    f"**Description:** {p['description'] or 'No description'}",
                    "",
                    "---",
                    ""
                ])

            if opportunities:
                lines.extend([
                    "## Top Extension Opportunities",
                    ""
                ])

                for opp in opportunities:
                    lines.extend([
                        f"### {opp['title']}",
                        "",
                        f"**Project:** [{opp['project_name']}]({opp['project_url']})",
                        "",
                        f"**Type:** {opp['opportunity_type']} | **Impact:** {opp['impact_potential']} | **Difficulty:** {opp['difficulty']} | **Time Horizon:** {opp['time_horizon']}",
                        "",
                        f"**Description:** {opp['description']}",
                        "",
                        f"**Key Insight:** {opp['key_insight'] or 'N/A'}",
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True)
    args = parser.parse_args()

    db = Database()
    generator = ReportGenerator(db)
    generator.generate(args.date)


if __name__ == '__main__':
    main()
