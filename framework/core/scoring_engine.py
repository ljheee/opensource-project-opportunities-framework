from datetime import datetime, timezone
from typing import Optional, Dict, Any
from framework.core.config_loader import EarlyBurstConfig


class ScoringEngine:
    def __init__(self, config: EarlyBurstConfig):
        self.config = config

    def calculate_star_velocity(self, current: int, past_7d: Optional[int],
                                past_30d: Optional[int]) -> float:
        if past_7d is None or past_7d == 0 or current <= past_7d:
            return 0.5

        weekly_growth = (current - past_7d) / past_7d
        daily_absolute = (current - past_7d) / 7

        threshold = self.config.metrics['star_velocity']['thresholds']
        target_weekly = threshold['weekly_growth_rate']
        target_daily = threshold['daily_absolute']

        weekly_score = min(weekly_growth / target_weekly, 1.5)
        daily_score = min(daily_absolute / target_daily, 1.5)

        return min((weekly_score * 0.7 + daily_score * 0.3), 1.0)

    def calculate_activity_index(self, open_issues: int,
                                  commit_frequency: float,
                                  pr_merge_rate: Optional[float] = None) -> float:
        threshold = self.config.metrics['activity_index']['thresholds']
        score = 0.0

        if commit_frequency >= threshold['commit_frequency']:
            score += 0.4
        elif commit_frequency >= threshold['commit_frequency'] * 0.5:
            score += 0.2
        else:
            score += 0.1

        if pr_merge_rate is not None:
            if pr_merge_rate >= threshold['pr_merge_rate']:
                score += 0.3
            elif pr_merge_rate >= threshold['pr_merge_rate'] * 0.5:
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
            months_old = (datetime.now(timezone.utc) - first_commit).days / 30
        except:
            return 0.5

        threshold = self.config.metrics['novelty_signal']['thresholds']
        max_months = threshold['first_commit_within_months'] * 2

        age_score = max(0, 1.0 - (months_old / max_months))

        contrib_threshold = threshold['unique_contributors_weekly']
        contrib_score = min(unique_contributors_weekly / contrib_threshold, 1.0) if contrib_threshold > 0 else 0

        return min(age_score * 0.6 + contrib_score * 0.4, 1.0)

    def calculate_overall(self, star_velocity: float, activity: float,
                          buzz: float, novelty: float) -> Dict[str, Any]:
        weights = self.config.metrics

        overall = (
            star_velocity * weights['star_velocity']['weight'] +
            activity * weights['activity_index']['weight'] +
            buzz * weights['community_buzz']['weight'] +
            novelty * weights['novelty_signal']['weight']
        )

        return {
            'star_velocity_score': star_velocity,
            'activity_index_score': activity,
            'community_buzz_score': buzz,
            'novelty_score': novelty,
            'overall_score': overall,
            'is_early_burst': overall >= self.config.min_score
        }
