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
import re
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
                time.sleep(max(0, 2 - elapsed))
        else:
            elapsed = time.time() - _last_request_time
            if elapsed < 0.5:
                time.sleep(max(0, 0.5 - elapsed))

        max_retries = self.resilience.get('github_api', {}).get('max_retries', 3)
        retry_delay = max(self.resilience.get('github_api', {}).get('retry_delay_seconds', 60), 0)
        if max_retries < 1:
            max_retries = 1

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
                    if attempt >= max_retries - 1:
                        raise GitHubAPIError(f"Rate limited after {attempt + 1} attempts")
                    continue

                if response.status_code == 429:
                    retry_after = max(int(response.headers.get('Retry-After', 60)), 0)
                    print(f"  Too many requests. Waiting {retry_after}s...")
                    time.sleep(min(retry_after, retry_delay))
                    if attempt >= max_retries - 1:
                        raise GitHubAPIError(f"Too many requests after {attempt + 1} attempts")
                    continue

                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as e:
                    raise GitHubAPIError(f"Invalid JSON response: {e}")

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait = retry_delay * (attempt + 1)
                    print(f"  Request failed (attempt {attempt + 1}). Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise GitHubAPIError(f"Failed after {attempt + 1} attempts: {e}")

        raise GitHubAPIError("Unexpected end of retry loop")

    def _should_skip_repo(self, repo: Dict) -> tuple[bool, str]:
        """Check if repository should be skipped based on filters."""
        filters = self.config.get_filters()

        stars = repo.get('stargazers_count') or 0
        if stars < self.star_min:
            return True, f"stars_too_few:{stars}"
        if stars > self.star_max:
            return True, f"stars_too_many:{stars}"

        if repo.get('archived'):
            return True, "archived"

        # Check stale (no commits in 180 days)
        pushed = repo.get('pushed_at') or ''
        if pushed:
            try:
                pushed_dt = datetime.fromisoformat(pushed.replace('Z', '+00:00'))
                if pushed_dt.tzinfo is None:
                    pushed_dt = pushed_dt.replace(tzinfo=timezone.utc)
                stale_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
                if pushed_dt < stale_cutoff:
                    return True, f"stale_since:{pushed[:10]}"
            except (ValueError, TypeError):
                pass

        # Check skip patterns
        name = (repo.get('name') or '').lower()
        desc = (repo.get('description') or '').lower()
        for pattern in filters.get('skip_patterns', []):
            if pattern and (pattern in name or pattern in desc):
                return True, f"skip_pattern:{pattern}"

        if repo.get('fork'):
            return True, "is_fork"

        # Check required filters from config
        required = filters.get('required', {})
        if required.get('has_code') and (repo.get('size') or 0) == 0:
            return True, "empty_repo"

        return False, ""

    def _upsert_project(self, repo: Dict, source: str, signal: str, conn=None):
        """Insert or update project in database.

        Uses the provided connection if available; otherwise opens and closes
        its own.  Does NOT commit — the caller is responsible for committing
        the transaction.
        """
        should_close = conn is None
        conn = conn or self.db.get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            project_id = repo.get('full_name')
            if not project_id:
                raise ValueError("Repository missing full_name")

            # Check if project exists and get current metadata for change detection
            existing = conn.execute(
                'SELECT topics, description, status, filter_reason FROM projects WHERE id = ?', (project_id,)
            ).fetchone()

            new_topics = json.dumps(repo.get('topics') or [])
            new_desc = (repo.get('description') or '')[:500]

            if existing:
                old_topics = existing['topics'] or '[]'
                old_desc = existing['description'] or ''
                old_status = existing['status']
                old_filter_reason = existing['filter_reason']
                if old_status in ('active', 'scheduled', 'analyzing'):
                    reset_status = old_status
                    reset_filter_reason = old_filter_reason
                elif old_status == 'filtered_skip':
                    metadata_changed = old_topics != new_topics or old_desc != new_desc
                    reset_status = 'discovered' if metadata_changed else 'filtered_skip'
                    reset_filter_reason = None if metadata_changed else old_filter_reason
                else:
                    reset_status = 'discovered'
                    reset_filter_reason = None
            else:
                reset_status = 'discovered'
                reset_filter_reason = None

            # Insert or update project
            conn.execute('''
                INSERT INTO projects (
                    id, name, url, language, stars, open_issues, forks,
                    created_at, first_commit_at, last_commit_at, topics, description,
                    category, source, status, filter_reason, first_seen_at, last_fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    url = excluded.url,
                    language = excluded.language,
                    stars = excluded.stars,
                    open_issues = excluded.open_issues,
                    forks = excluded.forks,
                    last_commit_at = excluded.last_commit_at,
                    topics = excluded.topics,
                    description = excluded.description,
                    source = excluded.source,
                    filter_reason = excluded.filter_reason,
                    last_fetched_at = excluded.last_fetched_at,
                    status = CASE
                        WHEN projects.status IN ('active', 'scheduled', 'analyzing')
                            THEN projects.status
                        ELSE excluded.status
                    END
            ''', (
                project_id,
                repo.get('name'),
                repo.get('html_url'),
                repo.get('language'),
                repo.get('stargazers_count') or 0,
                repo.get('open_issues_count') or 0,
                repo.get('forks_count') or 0,
                repo.get('created_at'),
                repo.get('created_at'),
                repo.get('pushed_at'),
                new_topics,
                new_desc,
                'ai',
                source,
                reset_status,
                reset_filter_reason,
                now if not existing else None,
                now
            ))

            return project_id
        finally:
            if should_close:
                conn.close()

    def _sample_star_count(self, project_id: str, stars: int, conn=None):
        """Sample current star count for velocity tracking."""
        self.db.sample_star_count(project_id, stars, conn=conn)

    def _calculate_and_store_burst_score(self, project_id: str, conn=None):
        """Calculate early-burst score from sampled data."""
        should_close = conn is None
        conn = conn or self.db.get_conn()
        try:
            # Get current project info
            proj = conn.execute(
                'SELECT * FROM projects WHERE id = ?', (project_id,)
            ).fetchone()

            if not proj:
                return

            current_stars = proj['stars'] or 0

            # Get star history from shared conn if available, else new conn
            if should_close:
                history = self.db.get_project_star_history(project_id, days=35)
            else:
                cursor = conn.execute('''
                    SELECT * FROM star_history
                    WHERE project_id = ?
                    AND sampled_at >= date('now', '-35 days')
                    ORDER BY sampled_at DESC
                ''', (project_id,))
                history = [dict(row) for row in cursor.fetchall()]

            # Find stars from 7d and 30d ago
            stars_7d_ago = None
            stars_30d_ago = None

            now = datetime.now(timezone.utc)
            for sample in history:
                sampled_at = sample.get('sampled_at')
                if not sampled_at:
                    continue
                sample_date = datetime.fromisoformat(sampled_at).date()
                days_ago = (now.date() - sample_date).days

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
                proj['first_commit_at'] or proj['created_at'], 1
            )
            buzz_score = self.scoring.default_buzz_score()

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
            if should_close:
                conn.commit()

        finally:
            if should_close:
                conn.close()

    def discover_topics(self) -> List[Dict]:
        """Discover from GitHub topics."""
        results = []
        topics = self.config.get_github_topics()
        languages = self.config.load().get('sources', {}).get('github', {}).get('languages', [])

        print(f"Discovering from {len(topics)} topics x {len(languages)} languages...")

        for topic in topics:
            for lang in languages:
                query = f"topic:{topic} language:{lang} stars:{self.star_min}..{self.star_max}"
                url = "https://api.github.com/search/repositories"

                try:
                    data = self._github_request(url, {"q": query, "sort": "stars", "per_page": 30}, is_search=True)

                    if not isinstance(data, dict):
                        print(f"  Unexpected search response type: {type(data)}")
                        continue

                    for repo in (data.get('items') or []):
                        skip, reason = self._should_skip_repo(repo)
                        if not skip:
                            results.append({
                                'repo': repo,
                                'source': 'github_topic',
                                'signal': f"{topic}/{lang}"
                            })
                        else:
                            print(f"  Skip ({reason}): {repo.get('full_name', 'unknown')}")

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

                    if not isinstance(repos, list):
                        print(f"  Unexpected response type from {org}: {type(repos)}")
                        break

                    for repo in repos:
                        stars = repo.get('stargazers_count') or 0
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

    def discover_trending(self) -> List[Dict]:
        """Discover from GitHub Trending pages (HTML parsing)."""
        cfg = self.config.load()
        trending_cfg = cfg.get('sources', {}).get('trending', {})
        languages = trending_cfg.get('languages', [])
        periods = trending_cfg.get('periods', ['daily', 'weekly'])

        # GitHub non-repo path prefixes to filter out navigation links
        _NON_REPO_PREFIXES = {
            "features", "marketplace", "login", "logout", "settings", "explore",
            "notifications", "issues", "pulls", "sponsors", "about", "pricing",
            "enterprise", "topics", "collections", "events", "apps", "contact",
            "security", "organizations", "new", "codespaces", "copilot", "orgs", "users",
        }

        results = []
        for lang in languages:
            for period in periods:
                url = f"https://github.com/trending/{lang}?since={period}"
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    r.raise_for_status()
                    raw = re.findall(
                        r'href=[\'"]/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)[\'"]', r.text
                    )
                    seen: set[str] = set()
                    repo_names: list[str] = []
                    for full_name in raw:
                        if full_name in seen:
                            continue
                        seen.add(full_name)
                        owner = full_name.split("/")[0]
                        if owner in _NON_REPO_PREFIXES:
                            continue
                        repo_names.append(full_name)
                        if len(repo_names) >= 25:
                            break

                    if not repo_names:
                        print(
                            f"  WARN: trending {lang}/{period} parsed 0 projects, "
                            "HTML structure may have changed"
                        )
                        continue

                    for full_name in repo_names:
                        api_url = f"https://api.github.com/repos/{full_name}"
                        try:
                            repo = self._github_request(api_url)
                            if not repo:
                                continue
                            skip, reason = self._should_skip_repo(repo)
                            if not skip:
                                results.append({
                                    'repo': repo,
                                    'source': 'trending',
                                    'signal': f"{lang}/{period}",
                                })
                        except GitHubAPIError:
                            pass
                except Exception as e:
                    print(f"  trending_error {lang}/{period}: {e}")
                time.sleep(1)

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

        # Source 3: Trending
        print("Source 3: GitHub Trending...")
        trending_results = self.discover_trending()
        all_results.extend(trending_results)
        print(f"  Found: {len(trending_results)} projects")

        # Deduplicate
        seen: Set[str] = set()
        unique_results = []
        for item in all_results:
            pid = (item.get('repo') or {}).get('full_name')
            if pid and pid not in seen:
                seen.add(pid)
                unique_results.append(item)

        print(f"\nTotal unique projects: {len(unique_results)}")

        if dry_run:
            print("\nDry run - not writing to database")
            for item in unique_results[:10]:
                print(f"  {(item.get('repo') or {}).get('full_name', 'unknown')} ({item['source']})")
            return

        # Store results
        print("\nStoring projects...")
        stored_count = 0
        conn = self.db.get_conn()
        try:
            for item in unique_results:
                try:
                    project_id = self._upsert_project(
                        item['repo'], item['source'], item['signal'],
                        conn=conn
                    )
                    self._sample_star_count(
                        project_id,
                        (item.get('repo') or {}).get('stargazers_count') or 0,
                        conn=conn
                    )
                    self._calculate_and_store_burst_score(project_id, conn=conn)
                    stored_count += 1
                except Exception as e:
                    repo_name = (item.get('repo') or {}).get('full_name', 'unknown')
                    print(f"  Error storing {repo_name}: {e}")
            conn.commit()
        finally:
            conn.close()

        print(f"\nStored {stored_count} projects")

        # Sample star counts for existing active projects
        print("\nSampling star history for existing projects...")
        conn = self.db.get_conn()
        try:
            active_projects = conn.execute(
                "SELECT id, stars FROM projects WHERE status IN ('scheduled', 'active')"
            ).fetchall()

            for proj in active_projects:
                self._sample_star_count(proj['id'], proj['stars'] or 0, conn=conn)
                self._calculate_and_store_burst_score(proj['id'], conn=conn)
            conn.commit()

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
