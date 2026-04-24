from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import yaml
import os


@dataclass
class CategoryConfig:
    name: str
    display_name: str
    version: str


@dataclass
class DimensionsConfig:
    tech_layer: List[Dict]
    application: List[Dict]


@dataclass
class EarlyBurstConfig:
    enabled: bool
    min_score: float
    metrics: Dict[str, Any]


class ConfigLoader:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(base_dir, 'config.yaml')
        self.config_path = config_path
        self._config = None

    def load(self) -> Dict[str, Any]:
        if self._config is None:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        return self._config

    def get_category(self) -> CategoryConfig:
        cat = self.load()['category']
        return CategoryConfig(**cat)

    def get_dimensions(self) -> DimensionsConfig:
        dims = self.load()['dimensions']
        return DimensionsConfig(
            tech_layer=dims['tech_layer'],
            application=dims['application']
        )

    def get_early_burst_config(self) -> EarlyBurstConfig:
        eb = self.load()['early_burst']
        return EarlyBurstConfig(**eb)

    def get_github_topics(self) -> List[str]:
        return self.load()['sources']['github']['topics']

    def get_star_range(self) -> tuple:
        return tuple(self.load()['sources']['github']['star_range'])

    def get_ecosystems(self) -> List[str]:
        return self.load()['sources']['ecosystems']

    def get_filters(self) -> Dict:
        return self.load()['filters']

    def get_scheduling_config(self) -> Dict:
        return self.load()['scheduling']

    def get_resilience_config(self) -> Dict:
        return self.load().get('resilience', {})
