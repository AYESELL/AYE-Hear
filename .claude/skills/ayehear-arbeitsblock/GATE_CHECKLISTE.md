---
name: gate-checkliste
description: Gate-Checkliste der Projektleitung bei Task-Abschluss und Zwischen-Review
---

<!-- Verwaltet durch platform-tools/tools/claude-kit. Änderungen in der Vorlage vornehmen und install.py erneut ausführen. -->

# Gate-Checkliste (Projektleitung)

Läuft bei jedem Task-Abschluss vor `Complete-Task` und einmal als Zwischen-Review nach der Hälfte der Go-live-Gate-Tasks. Jede Zeile: ja/nein mit Beleg. Ein „ja“ bei 1, 3 oder 4 ohne Freigabe von Sascha ist ein Stopp-Grund.

## Sprintstart

- Zielsatz (ein Satz): …
- Go-live-Gate-Liste (höchstens 10 Tasks): …
- Alles andere steht mit Auslöser in `docs/BACKLOG.md`: ja/nein
- Zwischen-Review geplant nach Task Nr. …

## Prüfpunkte je Task

| #   | Prüfpunkt                                                                                                                                                                    | Beleg                                |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 1   | Neue Tasks seit Sprintstart außerhalb der Go-live-Gate-Liste?                                                                                                                | `Get-Task` (Sprint) gegen Gate-Liste |
| 2   | Review-Runden dieses Tasks (Budget: eine Review-Runde plus eine Korrekturrunde)?                                                                                             | Zahl aus den Implementation Notes    |
| 3   | Hook-Overrides (`SKIP_*`, `--no-verify`, `git push --force`, `Complete-Task -Force`/`-SkipReview`; `Start-Task -Force` zählt nicht) verwendet? Freigabe und Vermerk im Task? | Notes, `git log`, Hook-Protokoll     |
| 4   | Scope-Abweichung: geänderte Dateien außerhalb des Auftrags oder Berührung eines Nicht-Ziels?                                                                                 | `git diff --stat` gegen den Auftrag  |
| 5   | Zeilenwachstum der Artefakte (Code, Contract) je Runde                                                                                                                       | `git diff --numstat` je Runde        |
| 6   | Zurückgestellte Befunde gebündelt in `docs/BACKLOG.md`, je mit Auslöser? Kein Befund direkt als Task?                                                                        | `docs/BACKLOG.md`, Task-Liste        |
| 7   | Konzept-Gate und PO-Entscheidungen wörtlich in den Notes (wer, wann, Wortlaut)?                                                                                              | Notes                                |

Kennzahlen je Task: Review-Runden und Zeilenwachstum (Punkt 5). Auffällig: mehr als eine Korrekturrunde, oder eine Korrekturrunde, die ein Artefakt um mehr als 25 % oder mehr als 150 Zeilen wachsen lässt. Auffälligkeiten stehen im Abschlussbericht, nicht als Einzelfrage an Sascha.

## Ergebnis

Abschluss zulässig: ja/nein · Abweichungen mit Grund: … · Entscheidung für Sascha (höchstens eine, mit Standardempfehlung): …
