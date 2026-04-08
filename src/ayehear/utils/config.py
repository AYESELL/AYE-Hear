from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ayehear.models.runtime import RuntimeConfig


def load_runtime_config(path: Path) -> RuntimeConfig:
    if not path.exists():
        return RuntimeConfig()

    with path.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle) or {}
    return RuntimeConfig.model_validate(data)
