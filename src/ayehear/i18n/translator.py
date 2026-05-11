from __future__ import annotations

import logging
from typing import Any

from ayehear.i18n.catalog import CATALOG, DEFAULT_LANGUAGE, HARDCODED_FALLBACKS, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

_LANGUAGE_ALIASES: dict[str, str] = {
    "de": "de",
    "de-de": "de",
    "deutsch": "de",
    "ger": "de",
    "german": "de",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "english": "en",
}


def resolve_language(language: str | None) -> str:
    if not language:
        return DEFAULT_LANGUAGE

    normalized = language.strip().lower().replace("_", "-")
    return _LANGUAGE_ALIASES.get(normalized, DEFAULT_LANGUAGE)


class Translator:
    def __init__(self, language: str | None = None) -> None:
        self._language = resolve_language(language)

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str | None) -> None:
        self._language = resolve_language(language)

    def tr(self, key: str, **kwargs: Any) -> str:
        resolved = self._lookup(key)
        if kwargs:
            try:
                return resolved.format(**kwargs)
            except Exception as exc:
                logger.warning("i18n formatting failed for key '%s': %s", key, exc)
                return resolved
        return resolved

    def _lookup(self, key: str) -> str:
        configured = CATALOG.get(self._language, {})
        if key in configured:
            return configured[key]

        logger.warning("Missing i18n key '%s' for language '%s'. Falling back to '%s'.", key, self._language, DEFAULT_LANGUAGE)
        fallback_de = CATALOG.get(DEFAULT_LANGUAGE, {})
        if key in fallback_de:
            return fallback_de[key]

        logger.warning("Missing i18n key '%s' in fallback language '%s'. Using hardcoded fallback.", key, DEFAULT_LANGUAGE)
        return HARDCODED_FALLBACKS.get(key, key)
