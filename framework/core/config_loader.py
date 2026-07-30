from dataclasses import dataclass, fields, field
from typing import List, Dict, Optional, Any
import yaml
import os


@dataclass
class CategoryConfig:
    name: str = 'ai'
    display_name: str = 'AI Projects'
    version: str = '1.0'


@dataclass
class DimensionsConfig:
    tech_layer: List[Dict]
    application: List[Dict]


@dataclass
class EarlyBurstConfig:
    enabled: bool = True
    min_score: float = 0.65
    metrics: Dict[str, Any] = field(default_factory=dict)


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
            if not isinstance(raw, dict):
                raise RuntimeError(f"Config file must contain a mapping (dict), got {type(raw).__name__}: {self.config_path}")
            self._config = raw
        return self._config

    def _require_key(self, key: str):
        cfg = self.load()
        if key not in cfg:
            raise RuntimeError(f"Missing required config key: '{key}'")
        return cfg[key]

    def get_category(self) -> CategoryConfig:
        cat = self._require_key('category') or {}
        valid_keys = {f.name for f in fields(CategoryConfig)}
        return CategoryConfig(**{k: v for k, v in cat.items() if k in valid_keys})

    def get_dimensions(self) -> DimensionsConfig:
        dims = self._require_key('dimensions') or {}
        return DimensionsConfig(
            tech_layer=dims.get('tech_layer', []),
            application=dims.get('application', [])
        )

    def get_early_burst_config(self) -> EarlyBurstConfig:
        eb = self._require_key('early_burst') or {}
        valid_keys = {f.name for f in fields(EarlyBurstConfig)}
        filtered = {k: v for k, v in eb.items() if k in valid_keys}
        # Type safety: enabled / min_score may come from YAML as strings
        if 'enabled' in filtered:
            v = filtered['enabled']
            if isinstance(v, str):
                filtered['enabled'] = v.lower() in ('true', '1', 'yes', 'on')
            else:
                filtered['enabled'] = bool(v)
        if 'min_score' in filtered:
            try:
                filtered['min_score'] = float(filtered['min_score'])
            except (ValueError, TypeError):
                filtered['min_score'] = 0.65
        # Guard against malformed metrics value
        if not isinstance(filtered.get('metrics'), dict):
            filtered['metrics'] = {}
        return EarlyBurstConfig(**filtered)

    def get_github_topics(self) -> List[str]:
        topics = ((self.load().get('sources') or {}).get('github') or {}).get('topics', [])
        return topics if isinstance(topics, list) else []

    def get_star_range(self) -> tuple:
        raw = ((self.load().get('sources') or {}).get('github') or {}).get('star_range', [50, 50000])
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return (50, 50000)
        try:
            min_val = int(raw[0])
            max_val = int(raw[1])
        except (ValueError, TypeError):
            return (50, 50000)
        if min_val < 0 or max_val < 0 or min_val > max_val:
            return (50, 50000)
        return (min_val, max_val)

    def get_created_within_days(self) -> int:
        raw = ((self.load().get('sources') or {}).get('github') or {}).get('created_within_days', 730)
        try:
            val = int(raw)
        except (ValueError, TypeError):
            return 730
        return val if val > 0 else 730

    def get_event_rate_max_per_day(self) -> int:
        raw = ((self.load().get('sources') or {}).get('github') or {}).get('event_rate_max_per_day', 50)
        try:
            val = int(raw)
        except (ValueError, TypeError):
            return 50
        return val if val > 0 else 50

    def get_structure_max_per_day(self) -> int:
        raw = ((self.load().get('sources') or {}).get('github') or {}).get('structure_max_per_day', 50)
        try:
            val = int(raw)
        except (ValueError, TypeError):
            return 50
        return val if val > 0 else 50

    def get_ecosystems(self) -> List[str]:
        ecosystems = (self.load().get('sources') or {}).get('ecosystems', [])
        return ecosystems if isinstance(ecosystems, list) else []

    def get_filters(self) -> Dict:
        val = self.load().get('filters')
        return val if isinstance(val, dict) else {}

    def get_scheduling_config(self) -> Dict:
        val = self.load().get('scheduling')
        return val if isinstance(val, dict) else {}

    def get_resilience_config(self) -> Dict:
        val = self.load().get('resilience')
        return val if isinstance(val, dict) else {}
