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
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    raw = yaml.safe_load(f)
            except FileNotFoundError:
                raise RuntimeError(f"Config file not found: {self.config_path}")
            except yaml.YAMLError as e:
                raise RuntimeError(f"Invalid YAML in config file {self.config_path}: {e}")
            if raw is None:
                raise RuntimeError(f"Config file is empty: {self.config_path}")
            self._config = raw
        return self._config

    def _require_key(self, key: str):
        val = self.load().get(key)
        if val is None:
            raise RuntimeError(f"Missing required config key: '{key}'")
        return val

    def get_category(self) -> CategoryConfig:
        cat = self._require_key('category')
        return CategoryConfig(**cat)

    def get_dimensions(self) -> DimensionsConfig:
        dims = self._require_key('dimensions')
        return DimensionsConfig(
            tech_layer=dims.get('tech_layer', []),
            application=dims.get('application', [])
        )

    def get_early_burst_config(self) -> EarlyBurstConfig:
        eb = self._require_key('early_burst')
        return EarlyBurstConfig(**eb)

    def get_github_topics(self) -> List[str]:
        return self.load().get('sources', {}).get('github', {}).get('topics', [])

    def get_star_range(self) -> tuple:
        return tuple(self.load().get('sources', {}).get('github', {}).get('star_range', [50, 50000]))

    def get_ecosystems(self) -> List[str]:
        return self.load().get('sources', {}).get('ecosystems', [])

    def get_filters(self) -> Dict:
        return self.load().get('filters', {})

    def get_scheduling_config(self) -> Dict:
        return self.load().get('scheduling', {})

    def get_resilience_config(self) -> Dict:
        return self.load().get('resilience', {})
