---
status: accepted
context_date: 2026-04-17
decision_owner: AYEHEAR_ARCHITECT
related_tasks: HEAR-097
related_adrs: ADR-0002, ADR-0013
brand_source: AYE Brand Style Guide v1.0 (AYE Digital UG, 2026)
---

# ADR-0014: AYE Desktop Design System & Brand Alignment

## Context

The current AYE Hear UI was built for functional correctness during V1 development. The
visual design is:
- Light-grey default Windows theme with no brand identity
- Inline `setStyleSheet()` calls scattered across 4 source files with raw hex literals
- Colour inconsistency: `#1a7a1a` (green status), `#1a4a7a` (blue accent),
  `#888` / `#555` (grey variants) — none aligned to the AYE colour palette
- No typography alignment to brand typeface
- No dark theme, no token system, no global QSS

The AYE Brand Style Guide (v1.0, 2026) defines a precise premium brand identity:
dark-first, metallic bronze accents, rounded sans-serif typeface. The desktop product
must reflect this brand language to be credible with the target audience
(Mittelstand CEOs and technical leaders).

## Decision

**Implement a token-based AYE Design System for the PySide6 desktop application.**

The design system consists of:
1. A `DesignTokens` class (single source of truth for all colours, typography, spacing)
2. A global QSS stylesheet generated from those tokens
3. Elimination of all inline `setStyleSheet()` calls in widget classes

## Brand Token Specification

Derived from AYE Brand Style Guide v1.0:

### Colour Tokens

```python
class AYEColors:
    # Backgrounds
    BG_PRIMARY   = "#0E0E11"   # Near Black — primary window/panel background
    BG_SECONDARY = "#17181D"   # Graphite — cards, secondary panels, input fields

    # Text
    TEXT_PRIMARY  = "#F2F2F2"  # Soft White — all body text on dark background
    TEXT_MUTED    = "#9e938c"  # Bronze Light — secondary/muted text, placeholders
    TEXT_DISABLED = "#555558"  # Custom — disabled controls (not in guide, derived)

    # Accent — Metallic Bronze gradient
    ACCENT_MID   = "#857c69"   # Bronze Mid — primary UI accents, borders, active states
    ACCENT_DARK  = "#6b6453"   # Bronze Dark — gradient start, depth/shadow accents
    ACCENT_LIGHT = "#9e938c"   # Bronze Light — gradient end, highlights

    # Semantic — mapped to brand palette (no bright greens/neons)
    STATUS_OK      = "#857c69"   # Bronze Mid — replaces #1a7a1a green (not brand)
    STATUS_WARN    = "#9e7b4e"   # Platinum Bronze — warning/attention
    STATUS_ERROR   = "#8B3A3A"   # Muted red — error states (restrained, not neon)
    STATUS_INACTIVE = "#555558"  # Disabled/inactive

    # Borders
    BORDER_SUBTLE = "#2a2b31"   # Slightly lighter than BG_SECONDARY
    BORDER_ACCENT = "#857c69"   # Bronze Mid — active/focused borders
```

### Typography Tokens

```python
class AYETypography:
    # Per Brand Style Guide §5:
    # Primary: iCiel VAG Rounded Next (licensed, not embeddable without licence)
    # Desktop substitute: "VAG Rounded" → "Arial Rounded MT" → "Arial, sans-serif"
    # Note: Varela Round is web-only (Google Fonts). Desktop Qt uses system fonts.

    FONT_FAMILY_STACK = "VAG Rounded, Arial Rounded MT, Arial, sans-serif"

    # Sizes (pt → px mapping for Qt: ~1pt = 1.33px at 96dpi)
    SIZE_H1   = 22   # px — H1 headline (28pt reduced for compact desktop)
    SIZE_H2   = 16   # px — H2 section title
    SIZE_BODY = 11   # px — body text (10–12pt range from guide)
    SIZE_LABEL = 10  # px — callout / label
    SIZE_SMALL =  9  # px — metadata, timestamps

    WEIGHT_BOLD   = "bold"
    WEIGHT_MEDIUM = "600"
    WEIGHT_NORMAL = "normal"

    LINE_HEIGHT_BODY = 1.5   # generous whitespace per guide §7.1
```

### Spacing Tokens

```python
class AYESpacing:
    XS  =  4   # px
    SM  =  8   # px
    MD  = 16   # px
    LG  = 24   # px
    XL  = 32   # px
    XXL = 48   # px
```

## Global QSS Architecture

A single `theme.py` module generates the application-level QSS from tokens.
No widget class may call `setStyleSheet()` directly — all theming is applied
at application level via `QApplication.setStyleSheet()` at startup.

```python
# src/ayehear/app/theme.py
from ayehear.app.design_tokens import AYEColors as C, AYETypography as T, AYESpacing as S

def build_stylesheet() -> str:
    return f"""
    QMainWindow, QDialog {{
        background-color: {C.BG_PRIMARY};
        color: {C.TEXT_PRIMARY};
        font-family: {T.FONT_FAMILY_STACK};
        font-size: {T.SIZE_BODY}px;
    }}

    QGroupBox {{
        background-color: {C.BG_SECONDARY};
        border: 1px solid {C.BORDER_SUBTLE};
        border-radius: 4px;
        margin-top: {S.LG}px;
        padding: {S.MD}px;
        font-size: {T.SIZE_LABEL}px;
        font-weight: {T.WEIGHT_MEDIUM};
        color: {C.ACCENT_MID};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {S.SM}px;
        color: {C.ACCENT_MID};
        font-size: {T.SIZE_LABEL}px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    QPushButton {{
        background-color: {C.BG_SECONDARY};
        color: {C.TEXT_PRIMARY};
        border: 1px solid {C.ACCENT_MID};
        border-radius: 3px;
        padding: {S.SM}px {S.MD}px;
        font-size: {T.SIZE_BODY}px;
        font-weight: {T.WEIGHT_MEDIUM};
    }}

    QPushButton:hover {{
        background-color: {C.ACCENT_DARK};
        border-color: {C.ACCENT_LIGHT};
    }}

    QPushButton:pressed {{
        background-color: {C.ACCENT_MID};
    }}

    QPushButton:disabled {{
        color: {C.TEXT_DISABLED};
        border-color: {C.BORDER_SUBTLE};
    }}

    QComboBox, QLineEdit, QTextEdit, QListWidget {{
        background-color: {C.BG_SECONDARY};
        color: {C.TEXT_PRIMARY};
        border: 1px solid {C.BORDER_SUBTLE};
        border-radius: 3px;
        padding: {S.XS}px {S.SM}px;
        selection-background-color: {C.ACCENT_DARK};
    }}

    QComboBox:focus, QLineEdit:focus {{
        border-color: {C.ACCENT_MID};
    }}

    QLabel {{
        color: {C.TEXT_PRIMARY};
        background: transparent;
    }}

    QProgressBar {{
        background-color: {C.BG_SECONDARY};
        border: 1px solid {C.BORDER_SUBTLE};
        border-radius: 2px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {C.ACCENT_MID};
    }}

    QScrollBar:vertical {{
        background: {C.BG_SECONDARY};
        width: 8px;
    }}

    QScrollBar::handle:vertical {{
        background: {C.ACCENT_DARK};
        border-radius: 4px;
        min-height: 20px;
    }}
    """
```

## Migration Path

| Current (V1) | Target (V2) |
|---|---|
| `setStyleSheet("color: #1a7a1a")` in widget | `STATUS_OK` token via global QSS |
| `setStyleSheet("color: #888")` | `TEXT_MUTED` token |
| `setStyleSheet("color: #1a4a7a")` | `ACCENT_MID` token |
| Light Windows default background | `BG_PRIMARY = #0E0E11` dark theme |
| `header.setStyleSheet("font-size: 24px; font-weight: 700;")` | H1 token in global QSS |

All inline `setStyleSheet()` calls are **prohibited** after V2 migration except for
dynamic state-dependent colour changes (e.g. mic level bar), which must use named tokens:

```python
# ✅ Allowed for dynamic state in V2
from ayehear.app.design_tokens import AYEColors as C
self._level_bar.setStyleSheet(
    f"QProgressBar::chunk {{ background-color: {C.ACCENT_MID}; }}"
)
# ❌ Not allowed
self._level_bar.setStyleSheet("QProgressBar::chunk { background-color: #857c69; }")
```

## Window Header — Brand Identity

The main window header changes from generic text to branded treatment:

- Background: `BG_PRIMARY` (#0E0E11)
- Title: "AYE Hear" — `TEXT_PRIMARY`, `SIZE_H1`, `WEIGHT_BOLD`, font family `FONT_FAMILY_STACK`
- Subtitle: "Meeting Intelligence" — `TEXT_MUTED`, `SIZE_LABEL`
- Separator: 1px `ACCENT_MID` horizontal rule below header (per Brand Guide §9.2)
- AYE logo placement: top-right of header (SVG asset, metallic gradient version)

## What the Brand Guide Explicitly Prohibits (apply to desktop)

Per Brand Style Guide §4.2 and §8:

| Prohibited | Replacement in AYE Hear |
|---|---|
| Bright greens / neons (current `#1a7a1a`) | `STATUS_OK = ACCENT_MID (#857c69)` |
| Electric blue (current `#1a4a7a`) | `ACCENT_MID (#857c69)` or `ACCENT_DARK` |
| Generic startup-style colors | Full bronze palette |
| Playful icons / cartoons | Minimal Unicode symbols or thin-stroke SVG icons |
| Light / white backgrounds | `BG_PRIMARY` (#0E0E11) throughout |
| Helvetica / Calibri | `VAG Rounded → Arial Rounded MT → Arial` |

## Assets Required from AYE Brand (not yet in repo)

The following assets must be provided and added to `assets/brand/`:

| Asset | Format | Spec |
|---|---|---|
| AYE Logo (primary) | SVG | Metallic gradient, for dark backgrounds |
| AYE Logo (simplified) | SVG | Monochrome flat (for system tray / small contexts) |
| iCiel VAG Rounded Next | OTF/TTF | Licensed; bundle only with valid Qt desktop licence |

Until the licensed font is bundled, the approved fallback chain applies:
`VAG Rounded → Arial Rounded MT → Arial, sans-serif`

## ADR Boundary with ADR-0013

ADR-0013 owns i18n (string translation).
ADR-0014 owns visual styling.
Both are independent and can be implemented in parallel, but **ADR-0013 must not
be blocked by ADR-0014 and vice versa**. String wrapping and visual refactor
touch different parts of each widget class.

## Implementation Checklist for AYEHEAR_DEVELOPER (HEAR-0XX)

- [ ] `src/ayehear/app/design_tokens.py` created with `AYEColors`, `AYETypography`, `AYESpacing`
- [ ] `src/ayehear/app/theme.py` created with `build_stylesheet()` function
- [ ] `QApplication.setStyleSheet(build_stylesheet())` called in `app.py` at startup
- [ ] All inline `setStyleSheet()` calls removed from `window.py`, `enrollment_dialog.py`,
      `system_readiness.py`, `mic_level_widget.py`
- [ ] Dynamic state colours reference named tokens (not hex literals)
- [ ] Header redesigned: dark background, AYE brand typography, bronze separator line
- [ ] AYE logo SVG assets placed in `assets/brand/` and loaded in header widget
- [ ] PyInstaller spec includes `assets/brand/` in data files
- [ ] Visual regression screenshots captured in QA evidence document

## Consequences

**Positive:**
- Single point of change for all brand colours — one token change propagates everywhere
- Eliminates the current colour chaos across 4 files
- AYE Hear visually matches the brand identity expected by Mittelstand decision-makers
- Dark theme reduces eye strain in long meeting sessions
- Scales cleanly to V2.x additions (any new widget inherits theme automatically)

**Negative:**
- Full removal of inline styles is a significant but mechanical refactor across ~300 lines
- Font licensing for desktop deployment must be resolved with AYE brand team before
  bundling iCiel VAG Rounded Next
- Dark theme requires QA verification on all Windows display scaling settings (100%, 125%, 150%)
