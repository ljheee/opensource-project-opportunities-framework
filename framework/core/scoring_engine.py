from datetime import datetime, timezone
from typing import Optional, Dict, Any
from framework.core.config_loader import EarlyBurstConfig


class ScoringEngine:
    def __init__(self, config: EarlyBurstConfig):
        self.config = config

    def _thresholds(self, metric_name: str) -> Dict:
        metrics = getattr(self.config, 'metrics', {})
        return metrics.get(metric_name, {}).get('thresholds', {})

    def _weight(self, metric_name: str) -> float:
        metrics = getattr(self.config, 'metrics', {})
        return metrics.get(metric_name, {}).get('weight', 0.25)

    def calculate_star_velocity(self, current: int, past_7d: Optional[int],
                                past_30d: Optional[int]) -> float:
        threshold = self._thresholds('star_velocity')
        target_weekly = max(threshold.get('weekly_growth_rate', 0.15), 0.0001)
        target_daily = max(threshold.get('daily_absolute', 10), 0.0001)

        # Primary: 7-day velocity
        if past_7d is not None and past_7d > 0 and current > past_7d:
            weekly_growth = (current - past_7d) / past_7d
            daily_absolute = (current - past_7d) / 7
            weekly_score = min(weekly_growth / target_weekly, 1.5)
            daily_score = min(daily_absolute / target_daily, 1.5)
            return min((weekly_score * 0.7 + daily_score * 0.3), 1.0)

        # Fallback: 30-day velocity (normalize weekly growth by 4.3 weeks)
        if past_30d is not None and past_30d > 0 and current > past_30d:
            weekly_growth = ((current - past_30d) / past_30d) / 4.3
            daily_absolute = (current - past_30d) / 30
            weekly_score = min(weekly_growth / target_weekly, 1.5)
            daily_score = min(daily_absolute / target_daily, 1.5)
            return min((weekly_score * 0.7 + daily_score * 0.3), 1.0)

        return 0.5

    def calculate_activity_index(self, open_issues: int,
                                  commit_frequency: float,
                                  pr_merge_rate: Optional[float] = None) -> float:
        threshold = self._thresholds('activity_index')
        commit_freq_thresh = threshold.get('commit_frequency', 3)
        pr_merge_thresh = threshold.get('pr_merge_rate', 0.3)
        score = 0.0

        if commit_frequency >= commit_freq_thresh:
            score += 0.4
        elif commit_frequency >= commit_freq_thresh * 0.5:
            score += 0.2
        else:
            score += 0.1

        if pr_merge_rate is not None:
            if pr_merge_rate >= pr_merge_thresh:
                score += 0.3
            elif pr_merge_rate >= pr_merge_thresh * 0.5:
                score += 0.15
        else:
            score += 0.15

        if open_issues >= 10:
            score += 0.3
        elif open_issues >= 3:
            score += 0.2
        elif open_issues > 0:
            score += 0.1

        return min(score, 1.0)

    def calculate_novelty(self, first_commit_at: Optional[str],
                          unique_contributors_weekly: int = 0) -> float:
        if first_commit_at is None:
            return 0.5

        try:
            first_commit = datetime.fromisoformat(first_commit_at.replace('Z', '+00:00'))
            if first_commit.tzinfo is None:
                first_commit = first_commit.replace(tzinfo=timezone.utc)
            months_old = (datetime.now(timezone.utc) - first_commit).days / 30
        except (ValueError, TypeError):
            return 0.5

        threshold = self._thresholds('novelty_signal')
        max_months = threshold.get('first_commit_within_months', 6) * 2

        age_score = max(0, 1.0 - (months_old / max_months)) if max_months > 0 else 0.5

        contrib_threshold = threshold.get('unique_contributors_weekly', 2)
        contrib_score = min(unique_contributors_weekly / contrib_threshold, 1.0) if contrib_threshold > 0 else 0

        return min(age_score * 0.6 + contrib_score * 0.4, 1.0)

    def default_buzz_score(self) -> float:
        """Return default community buzz score when data is unavailable."""
        return self._thresholds('community_buzz').get('default_score', 0.3)

    def calculate_overall(self, star_velocity: float, activity: float,
                          buzz: float, novelty: float) -> Dict[str, Any]:
        overall = (
            star_velocity * self._weight('star_velocity') +
            activity * self._weight('activity_index') +
            buzz * self._weight('community_buzz') +
            novelty * self._weight('novelty_signal')
        )

        return {
            'star_velocity_score': star_velocity,
            'activity_index_score': activity,
            'community_buzz_score': buzz,
            'novelty_score': novelty,
            'overall_score': overall,
            'is_early_burst': overall >= getattr(self.config, 'min_score', 0.65)
        }
