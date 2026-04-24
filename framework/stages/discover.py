#!/usr/bin/env python3
"""
Stage 1: Discover AI projects from multiple sources.
Samples star counts to build velocity history.
"""
import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.core.scoring_engine import ScoringEngine


# GitHub API Configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
HEADERS = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'Bearer {GITHUB_TOKEN}'

# Rate limiting state
_last_request_time = 0


class GitHubAPIError(Exception):
    """GitHub API error with retry info."""
    def __init__(self, message: str, status_code: int = None, retry_after: int = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class DiscoverStage:
    """Multi-source project discovery stage."""

    def __init__(self, config: ConfigLoader, db: Database):
        self.config = config
        self.db = db
        self.scoring = ScoringEngine(config.get_early_burst_config())
        self.resilience = config.get_resilience_config()
        self.star_min, self.star_max = config.get_star_range()

    def _github_request(self, url: str, params: Optional[Dict] = None,
                       is_search: bool = False) -> Dict:
        """Make GitHub API request with rate limit handling."""
        global _last_request_time

        # Rate limiting for search API
        if is_search:
            elapsed = time.time() - _last_request_time
            if elapsed < 2:
                time.sleep(2 - elapsed)
        else:
            elapsed = time.time() - _last_request_time
            if elapsed < 0.5:
                time.sleep(0.5 - elapsed)

        max_retries = self.resilience.get('github_api', {}).get('max_retries', 3)
        retry_delay = self.resilience.get('github_api', {}).get('retry_delay_seconds', 60)

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=HEADERS,
                    params=params,
                    timeout=30
                )
                _last_request_time = time.time()

                # Handle rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    wait_time = max(reset_time - int(time.time()), 60)
                    print(f"  Rate limited. Waiting {wait_time}s...")
                    time.sleep(min(wait_time, 3600))
                    continue

                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"  Too many requests. Waiting {retry_after}s...")
                    time.sleep(min(retry_after, retry_delay))
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait = retry_delay * (attempt + 1)
                    print(f"  Request failed (attempt {attempt + 1}). Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise GitHubAPIError(f"Failed after {attempt + 1} attempts: {e}")

        return {}

    def _should_skip_repo(self, repo: Dict) -> tuple[bool, str]:
        """Check if repository should be skipped based on filters."""
        filters = self.config.get_filters()

        stars = repo.get('stargazers_count', 0)
        if stars < self.star_min:
            return True, f"stars_too_few:{stars}"
        if stars > self.star_max:
            return True, f"stars_too_many:{stars}"

        if repo.get('archived'):
            return True, "archived"

        # Check stale (no commits in 180 days)
        pushed = repo.get('pushed_at', '')
        if pushed:
            try:
                pushed_dt = datetime.fromisoformat(pushed.replace('Z', '+00:00'))
                stale_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
                if pushed_dt < stale_cutoff:
                    return True, f"stale_since:{pushed[:10]}"
            except:
                pass

        # Check skip patterns
        name = repo.get('name', '').lower()
        desc = (repo.get('description') or '').lower()
        for pattern in filters['skip_patterns']:
            if pattern in name or pattern in desc:
                return True, f"skip_pattern:{pattern}"

        if repo.get('fork'):
            return True, "is_fork"

        return False, ""

    def _upsert_project(self, repo: Dict, source: str, signal: str):
        """Insert or update project in database."""
        conn = self.db.get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            project_id = repo['full_name']

            # Check if project exists
            existing = conn.execute(
                'SELECT 1 FROM projects WHERE id = ?', (project_id,)
            ).fetchone()

            # Insert or update project
            conn.execute('''
                INSERT INTO projects (
                    id, name, url, language, stars, open_issues, forks,
                    created_at, last_commit_at, topics, description,
                    category, source, status, first_seen_at, last_fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    stars = excluded.stars,
                    open_issues = excluded.open_issues,
                    forks = excluded.forks,
                    last_commit_at = excluded.last_commit_at,
                    topics = excluded.topics,
                    description = excluded.description,
                    last_fetched_at = excluded.last_fetched_at
            ''', (
                project_id,
                repo.get('name'),
                repo.get('html_url'),
                repo.get('language'),
                repo.get('stargazers_count', 0),
                repo.get('open_issues_count', 0),
                repo.get('forks_count', 0),
                repo.get('created_at'),
                repo.get('pushed_at'),
                json.dumps(repo.get('topics', [])),
                repo.get('description', '')[:500],
                'ai',
                source,
                now if not existing else None,
                now
            ))

            conn.commit()
            return project_id
        finally:
            conn.close()

    def _sample_star_count(self, project_id: str, stars: int):
        """Sample current star count for velocity tracking."""
        self.db.sample_star_count(project_id, stars)

    def _calculate_and_store_burst_score(self, project_id: str):
        """Calculate early-burst score from sampled data."""
        conn = self.db.get_conn()
        try:
            # Get current project info
            proj = conn.execute(
                'SELECT * FROM projects WHERE id = ?', (project_id,)
            ).fetchone()

            if not proj:
                return

            # Get star history
            current_stars = proj['stars']
            history = self.db.get_project_star_history(project_id, days=35)

            # Find stars from 7d and 30d ago
            stars_7d_ago = None
            stars_30d_ago = None

            now = datetime.now(timezone.utc)
            for sample in history:
                sample_date = datetime.fromisoformat(sample['sampled_at'].replace('Z', '+00:00'))
                days_ago = (now - sample_date).days

                if 6 <= days_ago <= 8 and stars_7d_ago is None:
                    stars_7d_ago = sample['stars']
                if 28 <= days_ago <= 32 and stars_30d_ago is None:
                    stars_30d_ago = sample['stars']

            # Calculate scores
            velocity_score = self.scoring.calculate_star_velocity(
                current_stars, stars_7d_ago, stars_30d_ago
            )
            activity_score = self.scoring.calculate_activity_index(
                proj['open_issues'] or 0, 3
            )
            novelty_score = self.scoring.calculate_novelty(
                proj['created_at'], 1
            )
            buzz_score = 0.3

            result = self.scoring.calculate_overall(
                velocity_score, activity_score, buzz_score, novelty_score
            )

            # Store result
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT INTO early_burst_signals (
                    project_id, calculated_at,
                    star_velocity_score, activity_index_score,
                    community_buzz_score, novelty_score,
                    overall_score, is_early_burst, signals_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_id, now_iso,
                result['star_velocity_score'],
                result['activity_index_score'],
                result['community_buzz_score'],
                result['novelty_score'],
                result['overall_score'],
                result['is_early_burst'],
                json.dumps({
                    'stars_7d_ago': stars_7d_ago,
                    'stars_30d_ago': stars_30d_ago,
                    'current_stars': current_stars
                })
            ))
            conn.commit()

        finally:
            conn.close()

    def discover_topics(self) -> List[Dict]:
        """Discover from GitHub topics."""
        results = []
        topics = self.config.get_github_topics()
        languages = self.config.load()['sources']['github']['languages']

        print(f"Discovering from {len(topics)} topics x {len(languages)} languages...")

        for topic in topics:
            for lang in languages:
                query = f"topic:{topic} language:{lang} stars:{self.star_min}..{self.star_max}"
                url = "https://api.github.com/search/repositories"

                try:
                    data = self._github_request(url, {"q": query, "sort": "stars", "per_page": 30}, is_search=True)

                    for repo in data.get('items', []):
                        skip, reason = self._should_skip_repo(repo)
                        if not skip:
                            results.append({
                                'repo': repo,
                                'source': 'github_topic',
                                'signal': f"{topic}/{lang}"
                            })
                        else:
                            print(f"  Skip ({reason}): {repo['full_name']}")

                except GitHubAPIError as e:
                    print(f"  Error searching {topic}/{lang}: {e}")
                    continue

        return results

    def discover_ecosystems(self) -> List[Dict]:
        """Discover from ecosystem organizations."""
        results = []
        ecosystems = self.config.get_ecosystems()

        print(f"Discovering from {len(ecosystems)} ecosystems...")

        for org in ecosystems:
            page = 1
            while page <= 5:
                url = f"https://api.github.com/orgs/{org}/repos"
                params = {"per_page": 100, "page": page, "sort": "updated"}

                try:
                    repos = self._github_request(url, params)

                    if not repos:
                        break

                    for repo in repos:
                        stars = repo.get('stargazers_count', 0)
                        if stars < self.star_min or stars > self.star_max:
                            continue

                        skip, reason = self._should_skip_repo(repo)
                        if not skip:
                            results.append({
                                'repo': repo,
                                'source': 'ecosystem',
                                'signal': org
                            })

                    page += 1

                except GitHubAPIError as e:
                    print(f"  Error fetching {org}: {e}")
                    break

        return results

    def run(self, dry_run: bool = False):
        """Execute full discovery process."""
        print("=== Stage 1: Discover ===")
        print(f"Star range: {self.star_min} - {self.star_max}")
        print(f"Dry run: {dry_run}")
        print()

        all_results = []

        # Source 1: Topics
        print("Source 1: GitHub Topics...")
        all_results.extend(self.discover_topics())
        print(f"  Found: {len(all_results)} projects")

        # Source 2: Ecosystems
        print("Source 2: Ecosystem Organizations...")
        eco_results = self.discover_ecosystems()
        all_results.extend(eco_results)
        print(f"  Found: {len(eco_results)} projects")

        # Deduplicate
        seen: Set[str] = set()
        unique_results = []
        for item in all_results:
            pid = item['repo']['full_name']
            if pid not in seen:
                seen.add(pid)
                unique_results.append(item)

        print(f"\nTotal unique projects: {len(unique_results)}")

        if dry_run:
            print("\nDry run - not writing to database")
            for item in unique_results[:10]:
                print(f"  {item['repo']['full_name']} ({item['source']})")
            return

        # Store results
        print("\nStoring projects...")
        stored_count = 0
        for item in unique_results:
            try:
                project_id = self._upsert_project(item['repo'], item['source'], item['signal'])
                self._sample_star_count(project_id, item['repo']['stargazers_count'])
                self._calculate_and_store_burst_score(project_id)
                stored_count += 1
            except Exception as e:
                print(f"  Error storing {item['repo']['full_name']}: {e}")

        print(f"\nStored {stored_count} projects")

        # Sample star counts for existing active projects
        print("\nSampling star history for existing projects...")
        conn = self.db.get_conn()
        try:
            active_projects = conn.execute(
                "SELECT id, stars FROM projects WHERE status IN ('scheduled', 'active')"
            ).fetchall()

            for proj in active_projects:
                self._sample_star_count(proj['id'], proj['stars'])

            print(f"  Sampled {len(active_projects)} existing projects")
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="Discover AI projects")
    parser.add_argument('--dry-run', action='store_true', help="Don't write to database")
    args = parser.parse_args()

    config = ConfigLoader()
    db = Database()

    stage = DiscoverStage(config, db)
    stage.run(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
