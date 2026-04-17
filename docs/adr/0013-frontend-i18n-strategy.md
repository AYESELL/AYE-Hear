---
status: accepted
context_date: 2026-04-17
decision_owner: AYEHEAR_ARCHITECT
related_tasks: HEAR-097
related_adrs: ADR-0002, ADR-0012
---

# ADR-0013: Frontend Internationalisation (i18n) Strategy

## Context

All UI strings in AYE Hear are currently hardcoded in Python source files, mixed
between German and English depending on the developer. There is no Qt i18n infrastructure
(no `tr()` wrapping, no `.ts` files, no Qt Linguist workflow).

The AYE Brand Style Guide targets German-speaking Mittelstand as the primary audience,
with EN and FR as secondary markets. ADR-0012 introduced per-meeting protocol language
selection. A parallel and independent requirement exists for **application UI language**:
users should be able to run the entire AYE Hear interface in German, English, or French —
independent of the protocol output language.

Two strategies were considered:

1. **Python-level i18n (gettext / Babel)** — Uses `.po` / `.mo` files, standard on POSIX
   but requires a separate extraction and compilation step outside Qt.
2. **Qt Linguist i18n (QCoreApplication.translate / `tr()` + `.ts` / `.qm`)** — Native Qt
   mechanism, deeply integrated with PySide6, supports dynamic language switching at
   runtime without restart.

## Decision

**Qt Linguist i18n with PySide6** is adopted as the V2 i18n strategy.

**Rationale:**
- `tr()` is the idiomatic PySide6 string marker; tooling (`lupdate`, `lrelease`) already
  exists in Qt and requires no additional dependencies.
- Qt i18n supports **runtime language switching** via `QCoreApplication.installTranslator()`
  — no application restart needed.
- `.qm` compiled files ship inside the PyInstaller bundle cleanly.
- gettext would require a parallel ecosystem next to Qt and duplicates string management.

## Scope

**V2 scope (in):**
- All visible UI strings wrapped in `self.tr()` or `QCoreApplication.translate()`
- Three translation catalogues: `ayehear_de.ts`, `ayehear_en.ts`, `ayehear_fr.ts`
- Language selector in **application Settings panel** (global, persists across sessions)
- German (`de`) remains the application default at first launch
- Dynamic switching: language change applies without restarting

**V2 scope (out / deferred):**
- Right-to-left language support (e.g. Arabic, Hebrew) — layout changes required
- Per-meeting UI language override — consistent with ADR-0012 (per-meeting is
  protocol language only; UI language is a user-level persistent setting)
- Automatic locale detection at first launch — deferred to V2.1

## Architecture Contract

### String wrapping

```python
# window.py, enrollment_dialog.py, system_readiness.py, mic_level_widget.py
# ❌ V1 (hardcoded)
QLabel("Meeting Setup")

# ✅ V2 (translatable)
QLabel(self.tr("meeting_setup_title"))     # key-based
# OR
QLabel(self.tr("Meeting Setup"))           # source-string-based (simpler for small team)
```

Source-string-based keys are used in V2 (simpler, no separate key registry).
German source strings are the canonical form since German is the primary market.

### Translation file structure

```
src/ayehear/i18n/
├── ayehear_de.ts      # German (source language — auto-generated baseline)
├── ayehear_en.ts      # English
├── ayehear_fr.ts      # French
└── ayehear_de.qm      # compiled (git-ignored, built by lrelease in CI)
    ayehear_en.qm
    ayehear_fr.qm
```

### Language persistence

Language preference stored in `RuntimeConfig` under a new `ui_language: str = "de"` field,
persisted to `config/user.yaml` (user-level override, separate from `default.yaml`).

```python
class AppSettings(BaseModel):
    name: str = "AYE Hear"
    environment: str = "development"
    autosave_interval_seconds: int = 30
    ui_language: str = "de"          # NEW — persisted user preference
```

### Runtime switcher

```python
# services/i18n_service.py (new)
class I18nService:
    def set_language(self, lang_code: str) -> None:
        """Install translator and trigger UI retranslation."""
        translator = QTranslator()
        qm_path = resource_path(f"i18n/ayehear_{lang_code}.qm")
        translator.load(qm_path)
        QCoreApplication.installTranslator(translator)
        # Emit signal to all windows for retranslateUi()
```

### Build pipeline

`Build-WindowsPackage.ps1` gains a pre-build step:
```powershell
# Compile .ts → .qm before PyInstaller
& lrelease src/ayehear/i18n/ayehear_de.ts -qm src/ayehear/i18n/ayehear_de.qm
& lrelease src/ayehear/i18n/ayehear_en.ts -qm src/ayehear/i18n/ayehear_en.qm
& lrelease src/ayehear/i18n/ayehear_fr.ts -qm src/ayehear/i18n/ayehear_fr.qm
```

## Implementation Checklist for AYEHEAR_DEVELOPER (HEAR-0XX)

- [ ] `AppSettings.ui_language: str = "de"` added to `runtime.py`
- [ ] `src/ayehear/i18n/` directory created with baseline `.ts` files
- [ ] All string literals in `window.py`, `enrollment_dialog.py`,
      `system_readiness.py`, `mic_level_widget.py` wrapped in `self.tr()`
- [ ] `I18nService` implemented with `set_language()` and translator install
- [ ] Language selector `QComboBox` in Settings panel (Deutsch / English / Français)
- [ ] Language choice persists to `config/user.yaml`
- [ ] `Build-WindowsPackage.ps1` compiles `.ts` → `.qm` before PyInstaller
- [ ] `.qm` files included in PyInstaller `--add-data` spec
- [ ] Tests: language switch applies without restart; German strings present in `.ts`

## Consequences

**Positive:**
- AYE Hear can serve DE, EN, and FR markets with same binary
- No application restart needed for language switch
- Qt tooling is already available in the dev environment (part of PySide6)

**Negative:**
- All existing string literals must be wrapped — significant but mechanical refactor
- Translator must be maintained as new strings are added (process discipline required)
- `.ts` files must be kept in sync with source; `lupdate` run required before each release
