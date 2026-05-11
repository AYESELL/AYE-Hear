from __future__ import annotations

from typing import Final

DEFAULT_LANGUAGE: Final[str] = "de"
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("de", "en")

CATALOG: Final[dict[str, dict[str, str]]] = {
    "de": {
        "ui.app.workspace_title": "AYE Hear Arbeitsbereich",
        "ui.setup.protocol_language_label": "Protokollsprache",
        "ui.language.option.de": "Deutsch",
        "ui.language.option.en": "Englisch",
        "ui.speaker.edit.title": "Sprecher bearbeiten",
        "ui.speaker.remove.title": "Sprecher entfernen",
        "ui.speaker.select_required": "Bitte einen Sprecher auswählen.",
        "ui.generic.greeting": "Hallo {name}",
    },
    "en": {
        "ui.app.workspace_title": "AYE Hear Workspace",
        "ui.setup.protocol_language_label": "Protocol Language",
        "ui.language.option.de": "German",
        "ui.language.option.en": "English",
        "ui.speaker.edit.title": "Edit Speaker",
        "ui.speaker.remove.title": "Remove Speaker",
        "ui.speaker.select_required": "Please select a speaker.",
        "ui.generic.greeting": "Hello {name}",
    },
}

# Hardcoded emergency fallback strings to guarantee non-crashing lookups.
HARDCODED_FALLBACKS: Final[dict[str, str]] = {
    "ui.app.workspace_title": "AYE Hear Workspace",
    "ui.setup.protocol_language_label": "Protocol Language",
    "ui.language.option.de": "German",
    "ui.language.option.en": "English",
    "ui.speaker.edit.title": "Edit Speaker",
    "ui.speaker.remove.title": "Remove Speaker",
    "ui.speaker.select_required": "Please select a speaker.",
    "ui.generic.greeting": "Hello {name}",
}
