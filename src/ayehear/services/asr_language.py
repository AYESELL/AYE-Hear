from __future__ import annotations

from dataclasses import dataclass

from ayehear.i18n import resolve_language
from ayehear.models.runtime import ModelSettings


@dataclass(frozen=True)
class AsrResolution:
    requested_language: str
    asr_language: str
    asr_model_name: str


def resolve_asr_language_and_model(
    requested_language: str | None,
    model_settings: ModelSettings,
) -> AsrResolution:
    """Resolve ASR language and model from selected meeting/protocol language.

    Fallback chain for model lookup:
    1) requested language mapping
    2) German mapping (de)
    3) configured default whisper_model
    """
    normalized_language = resolve_language(requested_language)

    language_map = _normalize_language_model_map(model_settings.whisper_model_by_language)
    fallback_default = model_settings.whisper_model

    resolved_model = (
        language_map.get(normalized_language)
        or language_map.get("de")
        or fallback_default
    )

    return AsrResolution(
        requested_language=(requested_language or "").strip(),
        asr_language=normalized_language,
        asr_model_name=resolved_model,
    )


def _normalize_language_model_map(language_map: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_language, model_name in language_map.items():
        model = (model_name or "").strip()
        if not model:
            continue
        normalized[resolve_language(raw_language)] = model
    return normalized
