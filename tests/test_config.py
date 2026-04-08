from pathlib import Path

from ayehear.models.runtime import RuntimeConfig
from ayehear.utils.config import load_runtime_config


def test_load_runtime_config_from_repository_file() -> None:
    config = load_runtime_config(Path("config/default.yaml"))
    assert isinstance(config, RuntimeConfig)
    assert config.audio.sample_rate_hz == 16000
    assert config.protocol.minimum_confidence == 0.65
