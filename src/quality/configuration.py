"""Read approved Q1 settings without installing defaults or writing configs."""
from __future__ import annotations

import yaml

from src.paths import CONFIGS


def load_settings(section: str) -> tuple[int, dict]:
    path = CONFIGS / 'q1.yaml'
    if not path.is_file():
        raise ValueError('configs/q1.yaml is absent; M1 configuration approval remains required')
    document = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or not isinstance(document.get(section), dict):
        raise ValueError(f'configs/q1.yaml must contain a {section} mapping')
    shared = yaml.safe_load((CONFIGS / 'default.yaml').read_text(encoding='utf-8'))
    seed = shared['seed']
    if not isinstance(seed, int) or seed < 0:
        raise ValueError('project seed must be a nonnegative integer')
    return seed, document[section]


def require_settings(settings: dict, keys) -> None:
    missing = set(keys) - set(settings)
    if missing:
        raise ValueError('Q1 settings missing: ' + ', '.join(sorted(missing)))
