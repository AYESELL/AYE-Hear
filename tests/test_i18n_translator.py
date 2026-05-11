from __future__ import annotations

import logging

from ayehear.i18n import Translator, resolve_language


def test_default_language_is_de() -> None:
    translator = Translator()
    assert translator.language == "de"


def test_en_resolution() -> None:
    translator = Translator("en")
    assert translator.language == "en"


def test_language_normalization_de_and_en_regions() -> None:
    assert resolve_language("de-DE") == "de"
    assert resolve_language("en-US") == "en"


def test_unknown_language_falls_back_to_de() -> None:
    translator = Translator("xx")
    assert translator.language == "de"


def test_missing_key_uses_fallback_chain_and_logs_warning(caplog) -> None:
    translator = Translator("en")
    caplog.set_level(logging.WARNING)

    value = translator.tr("ui.unknown.key")

    assert value == "ui.unknown.key"
    assert "Missing i18n key 'ui.unknown.key'" in caplog.text


def test_placeholders_format_with_kwargs() -> None:
    translator = Translator("de")
    value = translator.tr("ui.generic.greeting", name="Sascha")
    assert value == "Hallo Sascha"
