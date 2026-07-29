from datetime import datetime, timezone
from typing import Optional, Dict, Any
from framework.core.config_loader import EarlyBurstConfig


class ScoringEngine:
    def __init__(self, config: EarlyBurstConfig):
        self.config = config

    def _thresholds(self, metric_name: str) -> Dict:
        val = self.config.metrics.get(metric_name, {}).get('thresholds', {})
        return val if isinstance(val, dict) else {}

    def _weight(self, metric_name: str) -> float:
        val = self.config.metrics.get(metric_name, {}).get('weight', 0.25)
        try:
            w = float(val) if val is not None else 0.25
        except (ValueError, TypeError):
            return 0.25
        return max(w, 0.0)

    def _volume_score(self, current: int, past: int, days: int) -> float:
        """Raw volume score for a given lookback period."""
        if days <= 0:
            return 0.0
        threshold = self._thresholds('star_velocity')
        try:
            target_weekly = max(float(threshold.get('weekly_growth_rate', 0.15)), 0.0001)
        except (ValueError, TypeError):
            target_weekly = 0.15
        try:
            target_daily = max(float(threshold.get('daily_absolute', 10)), 0.0001)
        except (ValueError, TypeError):
            target_daily = 10

        if past > 0:
            weekly_growth = ((current - past) / past) / (days / 7)
            daily_absolute = (current - past) / days
        else:
            # 0 -> N stars: maximum velocity signal
            return 1.0

        weekly_score = min(weekly_growth / target_weekly, 1.5)
        daily_score = min(daily_absolute / target_daily, 1.5)
        return max(0.0, min((weekly_score * 0.7 + daily_score * 0.3), 1.0))

    def calculate_star_velocity(self, current: int, past_7d: Optional[int],
                                past_14d: Optional[int] = None,
                                past_21d: Optional[int] = None,
                                past_30d: Optional[int] = None) -> float:
        """
        Calculate star velocity with optional acceleration awareness.

        When past_14d (and optionally past_21d) are provided, the score
        blends absolute volume (60%) with week-over-week acceleration (40%).
        """
        # Primary: 7-day velocity (volume)
        if past_7d is not None and current > past_7d:
            volume_score = self._volume_score(current, past_7d, 7)

            # Acceleration: compare recent week to previous week
            if past_14d is not None:
                delta_w1 = current - past_7d
                delta_w2 = past_7d - past_14d

                if delta_w1 > 0 and delta_w2 > 0:
                    ratio = delta_w1 / delta_w2
                    # Map ratio to acceleration score
                    if ratio >= 2.0:
                        acceleration_score = 1.0
                    elif ratio >= 1.5:
                        acceleration_score = 0.85
                    elif ratio >= 1.0:
                        acceleration_score = 0.65
                    elif ratio >= 0.5:
                        acceleration_score = 0.4
                    else:
                        acceleration_score = 0.2
                elif delta_w1 > 0 and delta_w2 <= 0:
                    # Growth starting from flatline → high acceleration signal
                    acceleration_score = 0.9
                else:
                    acceleration_score = 0.3

                # Optional: 3-week trend confirmation
                if past_21d is not None:
                    delta_w3 = past_14d - past_21d
                    if delta_w3 > 0:
                        # If all three weeks show accelerating growth, boost
                        if delta_w1 > delta_w2 > delta_w3:
                            acceleration_score = min(acceleration_score + 0.1, 1.0)
                        # If decelerating across 3 weeks, penalize
                        elif delta_w1 < delta_w2 < delta_w3:
                            acceleration_score = max(acceleration_score - 0.15, 0.0)

                return min((volume_score * 0.6 + acceleration_score * 0.4), 1.0)

            return volume_score

        # Fallback: 30-day velocity
        if past_30d is not None and current > past_30d:
            return self._volume_score(current, past_30d, 30)

        return 0.5

    def calculate_activity_index(self, open_issues: int,
                                  commit_frequency: float,
                                  pr_merge_rate: Optional[float] = None,
                                  has_tests: Optional[bool] = None,
                                  has_ci: Optional[bool] = None) -> float:
        threshold = self._thresholds('activity_index')
        try:
            commit_freq_thresh = max(float(threshold.get('commit_frequency', 3)), 0.0)
        except (ValueError, TypeError):
            commit_freq_thresh = 3
        try:
            pr_merge_thresh = max(float(threshold.get('pr_merge_rate', 0.3)), 0.0)
        except (ValueError, TypeError):
            pr_merge_thresh = 0.3
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

        if has_tests is not None or has_ci is not None:
            if has_tests and has_ci:
                score += 0.1
            elif has_tests or has_ci:
                score += 0.05

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
        try:
            max_months = float(threshold.get('first_commit_within_months', 6)) * 2
        except (ValueError, TypeError):
            max_months = 12

        age_score = max(0, min(1.0, 1.0 - (months_old / max_months))) if max_months > 0 else 0.5

        try:
            contrib_threshold = float(threshold.get('unique_contributors_weekly', 2))
        except (ValueError, TypeError):
            contrib_threshold = 2
        contrib_score = min(unique_contributors_weekly / contrib_threshold, 1.0) if contrib_threshold > 0 else 0

        return min(age_score * 0.6 + contrib_score * 0.4, 1.0)

    def default_buzz_score(self) -> float:
        """Return default community buzz score when data is unavailable."""
        try:
            return max(float(self._thresholds('community_buzz').get('default_score', 0.3)), 0.0)
        except (ValueError, TypeError):
            return 0.3

    def calculate_buzz(self, issue_health: Optional[Dict]) -> float:
        """Real community buzz from L1 issue health. None -> default fallback."""
        if not issue_health or not isinstance(issue_health, dict):
            return self.default_buzz_score()
        t = self._thresholds('community_buzz')
        def _f(key, default):
            try:
                return max(float(t.get(key, default)), 0.0001)
            except (ValueError, TypeError):
                return default
        reaction_score = min((issue_health.get('reaction_total') or 0) / _f('reaction_total_full', 50), 1.0)
        active_score = min((issue_health.get('active_issues_30d') or 0) / _f('active_issues_full', 5), 1.0)
        comments_score = min((issue_health.get('avg_comments') or 0) / _f('avg_comments_full', 5), 1.0)
        return min(reaction_score * 0.5 + active_score * 0.3 + comments_score * 0.2, 1.0)

    def calculate_overall(self, star_velocity: float, activity: float,
                          buzz: float, novelty: float) -> Dict[str, Any]:
        raw_weights = {
            'star_velocity': self._weight('star_velocity'),
            'activity_index': self._weight('activity_index'),
            'community_buzz': self._weight('community_buzz'),
            'novelty_signal': self._weight('novelty_signal'),
        }
        total_weight = sum(raw_weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in raw_weights.items()}
        else:
            weights = {k: 0.25 for k in raw_weights}

        overall = (
            star_velocity * weights['star_velocity'] +
            activity * weights['activity_index'] +
            buzz * weights['community_buzz'] +
            novelty * weights['novelty_signal']
        )

        return {
            'star_velocity_score': star_velocity,
            'activity_index_score': activity,
            'community_buzz_score': buzz,
            'novelty_score': novelty,
            'overall_score': overall,
            'is_early_burst': overall >= self.config.min_score
        }
