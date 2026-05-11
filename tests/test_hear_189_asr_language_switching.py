from __future__ import annotations

import sys
from unittest.mock import patch

from ayehear.models.runtime import ModelSettings, RuntimeConfig
from ayehear.services.asr_language import resolve_asr_language_and_model


def test_resolver_de_and_de_de_use_de_language_and_de_model() -> None:
    models = ModelSettings(
        whisper_model="default-model",
        whisper_model_by_language={"de": "de-model", "en": "en-model"},
    )

    direct = resolve_asr_language_and_model("de", models)
    variant = resolve_asr_language_and_model("de-DE", models)

    assert direct.asr_language == "de"
    assert direct.asr_model_name == "de-model"
    assert variant.asr_language == "de"
    assert variant.asr_model_name == "de-model"


def test_resolver_en_and_en_us_use_en_mapping_when_available() -> None:
    models = ModelSettings(
        whisper_model="default-model",
        whisper_model_by_language={"de": "de-model", "en": "en-model"},
    )

    direct = resolve_asr_language_and_model("en", models)
    variant = resolve_asr_language_and_model("en-US", models)

    assert direct.asr_language == "en"
    assert direct.asr_model_name == "en-model"
    assert variant.asr_language == "en"
    assert variant.asr_model_name == "en-model"


def test_resolver_en_falls_back_to_de_mapping_when_en_mapping_missing() -> None:
    models = ModelSettings(
        whisper_model="default-model",
        whisper_model_by_language={"de": "de-model"},
    )

    resolved = resolve_asr_language_and_model("en", models)

    assert resolved.asr_language == "en"
    assert resolved.asr_model_name == "de-model"


def test_resolver_en_falls_back_to_default_model_when_no_language_mapping_exists() -> None:
    models = ModelSettings(
        whisper_model="default-model",
        whisper_model_by_language={},
    )

    resolved = resolve_asr_language_and_model("en-US", models)

    assert resolved.asr_language == "en"
    assert resolved.asr_model_name == "default-model"


def test_resolver_unknown_language_falls_back_to_de() -> None:
    models = ModelSettings(
        whisper_model="default-model",
        whisper_model_by_language={"de": "de-model"},
    )

    resolved = resolve_asr_language_and_model("fr-FR", models)

    assert resolved.asr_language == "de"
    assert resolved.asr_model_name == "de-model"


def _make_window(qapp, protocol_language: str, language_map: dict[str, str]):
    from ayehear.app.window import MainWindow

    cfg = RuntimeConfig(
        protocol={"language": protocol_language, "supported_languages": ["de", "en"]},
        models={
            "whisper_model": "default-model",
            "whisper_profile": "balanced",
            "whisper_model_by_language": language_map,
        },
    )

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=cfg)
    return win


def test_mainwindow_initializes_transcription_service_with_en_when_meeting_language_en(qapp) -> None:
    win = _make_window(
        qapp=qapp,
        protocol_language="en-US",
        language_map={"de": "de-model", "en": "en-model"},
    )

    assert win._transcription_service.language == "en"
    assert win._transcription_service.model_name == "en-model"

    win.deleteLater()
    qapp.processEvents()


def test_mainwindow_updates_asr_language_on_prestart_language_switch(qapp) -> None:
    win = _make_window(
        qapp=qapp,
        protocol_language="de",
        language_map={"de": "de-model", "en": "en-model"},
    )
    assert win._transcription_service.language == "de"

    idx_en = win._protocol_language.findData("en")
    assert idx_en >= 0
    win._protocol_language.setCurrentIndex(idx_en)
    qapp.processEvents()

    assert win._transcription_service.language == "en"
    assert win._transcription_service.model_name == "en-model"

    win.deleteLater()
    qapp.processEvents()


def test_mainwindow_meeting_lock_prevents_language_switch_during_active_meeting(qapp) -> None:
    win = _make_window(
        qapp=qapp,
        protocol_language="en",
        language_map={"de": "de-model", "en": "en-model"},
    )

    win._meeting_title.setText("ASR Lock Meeting")
    with patch.object(win, "_start_audio_pipeline", return_value="OK"):
        win._start_meeting()

    assert win._protocol_language.isEnabled() is False
    assert win._transcription_service.language == "en"
    assert win._transcription_service.model_name == "en-model"

    idx_de = win._protocol_language.findData("de")
    assert idx_de >= 0
    win._protocol_language.setCurrentIndex(idx_de)
    qapp.processEvents()

    assert win._transcription_service.language == "en"
    assert win._transcription_service.model_name == "en-model"
    assert win.runtime_config.protocol.language == "en"

    win.deleteLater()
    qapp.processEvents()
