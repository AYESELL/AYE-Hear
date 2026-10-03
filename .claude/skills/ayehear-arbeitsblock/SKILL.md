---
name: ayehear-arbeitsblock
description: Ablauf eines Arbeitsblocks (Sprint) der Projektleitung in AYE Hear – Planung, Ausführung über Fachrollen, Qualitätsstufen, Folge-Tasks, Stopp-Regeln und Abschlussbericht. Verwenden, wenn ein Arbeitsblock geplant, fortgesetzt oder abgeschlossen wird.
---

<!-- Verwaltet durch platform-tools/tools/claude-kit. Änderungen in der Vorlage vornehmen und install.py erneut ausführen. -->

# Arbeitsblock (Sprint) der Projektleitung

Ein Arbeitsblock ist eine Gruppe von 3 bis 8 Tasks mit einem gemeinsamen Ziel. Es gibt keine separaten Sprint-Dokumente: Ziel und Stand stehen in `docs/STATUS.md`, die Tasks in der Task-CLI (Sprint-Feld `sprint-<nummer>`, falls vom Service unterstützt; sonst Titelpräfix `[AB-<nummer>]`).

## 1. Planung (vor dem Start von Sascha freigeben lassen)

1. `docs/STATUS.md` und offene/blockierte Tasks im Projekt `hear` lesen.
2. Zielsatz: Ziel des Blocks in einem Satz formulieren. **Go-live-Gate-Liste:** höchstens 10 Tasks, die das Ziel erreichen; alles andere sofort in `docs/BACKLOG.md` mit Auslöser, nicht als Task.
3. Tasks auswählen oder anlegen: je Task Rolle, Ziel, Akzeptanzkriterien, Abhängigkeiten und **Story Points** (Schätzung der Projektleitung als Ersteller, Werte 1, 2, 3, 5, 8, 13, Skala siehe Skill `ayehear-task-execution`, Abschnitt 4a; Tasks über 13 SP zerlegen bzw. als Epic führen). Die Summe der SP gehört in die Plantabelle für Sascha. Prüf- und Dokumentationsschritte als eigene Tasks einplanen.
4. Grenzen festlegen: Kostenlimits, maximale Zahl an Versuchen, was ausdrücklich nicht Teil des Blocks ist (Nicht-Ziele). Sprintgrenze: nach der Freigabe kommen keine neuen Tasks in den Block, außer ein Gate-Task bricht (dann Sascha fragen). **Zwischen-Review** nach der Hälfte der Gate-Tasks mit `GATE_CHECKLISTE.md` (Abschnitt 2c).
5. Plan Sascha vorlegen (kurze Tabelle) und auf Freigabe warten. Enthält der Block Konzept und Code zum selben Thema, gilt das Phasen-Gate (Abschnitt 2b).

## 2. Ausführung (pro Task)

1. Rolle mit Auftrag aufrufen, nach `AUFTRAG_VORLAGE.md` (liegt neben diesem Skill): **Phase** (Konzept, Code oder Härtung), Ziel, Akzeptanzkriterien, **Nicht-Ziele**, relevante Ergebnisse der Vorrollen, erwartete Rückgabe. Keine Mit-Erledigen-Klausel. **Ein Subagenten-Lauf = ein Task** (PO-Entscheidung E-56): jeder Auftrag nennt genau eine Task-ID, die Rolle bearbeitet nur diese; mehrere Tasks sind mehrere Läufe (nacheinander oder parallel), sonst lässt sich der KI-Verbrauch keinem Task zuordnen. Aufträge an Subagenten in Blöcke schneiden, die ins Turn-Limit passen, mit Zwischen-Commit je Block. Bei Pflicht-REVIEW (Skill `ayehear-task-execution`, Abschnitt 5a) gibst du vor: „Task am Ende auf REVIEW setzen, nicht Complete-Task; kein -SkipReview/-Force.“ Bei Tasks, die Dateien ändern, nennt der Auftrag den Git-Rahmen: Task-Branch (Name), Worktree ja/nein (Voraussetzung: `.claude/worktrees/` steht in der `.gitignore`); bei ja: Subagent mit `isolation: worktree` beauftragen. Vorher prüfen: `worktree.baseRef: "head"` ist gesetzt und `HEAD` des Hauptordners ist der Trunk; den vollständigen Trunk-SHA (`git rev-parse HEAD` im Hauptordner, nachdem `git branch --show-current` dort den Trunk zeigt) in den Auftrag schreiben, dazu die Basisprüfung und den Ziel-Branchnamen. Eigene Arbeit der Projektleitung: nach `git fetch origin` Worktree mit `git worktree add .claude/worktrees/<nr>-<kurzname> -b <branch> origin/feature/phase-1b-implementation-updates` anlegen (Basis ausdrücklich `origin/feature/phase-1b-implementation-updates`) und selbst mit `EnterWorktree` betreten; den Hauptordner nie auf einen Task-Branch umstellen. Rückfall: Sitzung direkt im Worktree starten (ADR-0100 D10.9). Vor dem Merge `git status --short` im Hauptordner gegen den Stand bei Beauftragung prüfen (Shell-Schreiblücke, bis der Schutz-Hook ausgerollt ist); nicht umbenannte `worktree-agent-*`-Branches selbst umbenennen. Commit und Push des Task-Branches freigegeben.
2. Übergabebericht prüfen: Task-Status in der Task-CLI gesetzt? Prüfnachweis mit Befehl und Ergebnis vorhanden? Berührte ADRs genannt?
3. Qualitätsstufe auslösen:
   - Code oder Contract geändert → `ayehear-qa`
   - Daten, Rechte, Secrets, Lizenzen, externe Dienste berührt → zusätzlich `ayehear-security`
   - Architekturfrage offen oder Abweichung von einer ADR → `ayehear-architect`
   - Neue Nachweise oder Entscheidungen → am Blockende `ayehear-architect`
4. Befunde aus Reviews (QA, Security, Architektur) sortieren – siehe Abschnitt 2a; Abschluss nach Abschnitt 2c prüfen.
5. Task schließen: Ein Task mit Pflicht-REVIEW bleibt auf `REVIEW`, bis die unabhängige Prüfung in den Implementation Notes dokumentiert ist; erst dann schließt du ihn mit dem Bericht (`Complete-Task`). `-SkipReview`/`-Force` nur mit ausdrücklicher Freigabe von Sascha, vermerkt in den Notes. Vor `Complete-Task` bei dateiändernden Tasks: Task-Branch nach bestandenem REVIEW mit `--no-ff` in den Trunk mergen, Push nach Prüfung laut Skill Abschnitt 5b Punkt 7, `git branch -r --contains <sha>` zeigt `origin/feature/phase-1b-implementation-updates`, Task-Branch und Worktree entfernen. Worktree: Entfernen nur durch die Projektleitung nach dem Merge mit `git worktree remove <pfad>` (nie per Dateimanager, `Remove-Item -Recurse` oder `--force`); vorher `git status --ignored --short` im Worktree prüfen, denn `git worktree remove` löscht ignorierte Dateien ohne Meldung. Ein sauberer, gepushter Worktree kann vor dem Merge von Claude Code entfernt werden; gemergt wird vom Branch. Brachte der Merge neue oder geänderte Abhängigkeiten, diese im Haupt-Checkout nachinstallieren, sonst laufen Hooks und Tests dort gegen veraltete Pakete. Git-Stand in den Notes nachtragen.
6. Vorgeschlagene Folge-Tasks der Rollen prüfen und anlegen (Review-Befunde nie direkt, nur über `docs/BACKLOG.md`, Abschnitt 2a; `New-Task -Project hear … -StoryPoints <1|2|3|5|8|13> -CreatedByRole AYEHEAR_LEAD` (SP-Vorschlag der Rolle prüfen; ohne Angabe würde die Task-CLI nur einen Typ-Standard setzen), Beschreibung beginnt mit „Angelegt durch Projektleitung“, Bezug auf den auslösenden Task).
7. Fehlschlag: zweiter Versuch nur mit gezielt geändertem Auftrag. Nach dem zweiten Fehlschlag Stopp.

## 2a. Scope-Regel für Befunde

Reviews finden fast immer etwas. Damit ein Task nicht endlos wächst:

- **Review-Budget:** je Task höchstens eine Review-Runde plus eine Korrekturrunde. Reviewer prüfen nur gegen die Akzeptanzkriterien des Auftrags; Neues ist ein Vorschlag, kein Befund.
- **Befundformat:** ID · Schweregrad (hoch/mittel/niedrig) · verletztes Akzeptanzkriterium · Beleg · **blockiert aktuelles Ziel: ja/nein** · Vorschlag. „ja“ ist nur zulässig bei verletztem Akzeptanzkriterium oder bei konkretem **Risiko für Produktion, Daten oder Secrets** (stehendes Kriterium jedes Auftrags); sonst unzulässig (Skill `ayehear-task-execution`, Abschnitt 5c und 5d).
- **Blockierend** ist nur, was ohne Behebung das Ziel oder ein Akzeptanzkriterium bricht oder ein konkretes Risiko für Produktion, Daten oder Secrets bedeutet. Nur das geht in die Korrekturrunde zurück. Ein Risiko-Befund wird immer behoben und nie ins Backlog verschoben; er ist von der Phase ausgenommen. Bleibt er nach der Korrekturrunde offen, gilt Skill `ayehear-task-execution` 5c.2: Eskalation an Sascha, der Task wird ohne Behebung nicht geschlossen.
- **Re-Review** prüft nur den Diff der Korrekturrunde und nur die bisherigen blockierenden Auflagen, kein neues Voll-Review. Redaktionelle Reste (Wortlaut, Tippfehler, Format) werden ohne Re-Review behoben.
- **Alles andere** (Härtungen, Verbesserungen, Tests, Doku-Feinschliff, Altlasten) kommt gebündelt in `docs/BACKLOG.md`: Befund, Quelle, Einschätzung, **Auslöser** (wann es relevant wird). Nie direkt als Task; die Projektleitung legt aus einem Backlog-Eintrag erst einen Task an, wenn der Auslöser eintritt oder Sascha es will.
- Sascha bekommt Backlog-Punkte gesammelt im Abschlussbericht. Weitet sich ein Task aus (neue Themen, zweite Korrekturrunde nötig), ist das ein Stopp-Grund: melden und Scope bestätigen lassen.

## 2b. Gates und Entscheidungen

- **Konzept-Gate:** Code startet erst nach ausdrücklicher Freigabe des Konzepts durch Sascha, wenn der Task Architekturrelevanz hat (ADR, Contract, Datenmodell, Sicherheitsgrenze) oder der Block Konzept und Code zum selben Thema enthält (Phasen-Gate). Eigenständige Hook- und Skript-Tasks ohne Konzept-Task im Block sind nicht gegated.
- **Entscheidungsbudget:** je Halt höchstens eine echte Entscheidung an Sascha, mit Standardempfehlung. Härtungsdetails entscheidet die Projektleitung nach Abschnitt 2a.
- **PO-Annahme** gilt nur bei ausdrücklicher Aussage von Sascha; Schweigen oder eine Antwort auf anderes ist keine Zustimmung. Die Implementation Notes tragen den Entscheidungsvermerk wörtlich (wer, wann, Wortlaut).

## 2c. Prüfpunkt bei Task-Abschluss

Vor `Complete-Task` und beim Zwischen-Review `GATE_CHECKLISTE.md` (liegt neben diesem Skill) durchgehen: neue Tasks seit Sprintstart, Review-Runden je Task, Zeilenwachstum der Artefakte, Scope-Abweichungen, Hook-Overrides. Overrides (`SKIP_*`, `--no-verify`, `git push --force`, `Complete-Task -Force`/`-SkipReview`; nicht `Start-Task -Force`) nur mit Freigabe von Sascha und Vermerk im Task vor der Nutzung; sonst bleibt der Task auf `REVIEW` oder `BLOCKED`. Auffälligkeiten stehen im Abschlussbericht.

## 3. Arbeit für andere Repositories

Braucht der Block etwas aus einem anderen Repository (z. B. eine Änderung an Task-CLI oder Plattform-Services), legst du dort einen Task an – im Projekt des anderen Repos mit der fachlich zuständigen Rolle (für die Plattform `-Project platform -Role PLATFORM_<ROLLE>`). Du rufst keine Rollen anderer Repositories auf und änderst dort keine Dateien. Der Task ist die Übergabe; den Stand prüfst du über die Task-CLI.

## 4. Stopp-Regeln – anhalten und Sascha fragen

- Scope-, Strategie- oder Prioritätsänderung
- Kosten über dem Blocklimit oder ein Lauf gegen externe Dienste ohne festgelegte Grenzen
- NO-GO eines Gates (QA, Security, Architektur)
- Ein Abschluss würde `-SkipReview`/`-Force` erfordern (Gate blockiert): Freigabe von Sascha einholen, nie selbst umgehen
- Ein Hook-Override (`SKIP_*`, `--no-verify`) wäre nötig, oder die Checkliste (Abschnitt 2c) zeigt eine Scope-Abweichung
- Fehlende Operation oder Regel bzw. nötige neue oder geänderte ADR, die Sascha betrifft
- Zwei gescheiterte Versuche am selben Task
- Widersprüchliche Aussagen zweier Rollen, die sich nicht aus Quellen klären lassen

- Abweichungen von der Zwei-Zustände-Scope-Trennung (Operations-Handoff vs. Product-Complete, ADR-0010)
- Jede Änderung, die eine Cloud-Übertragung von Audio- oder Sprecherdaten einführen würde

Entscheidungsvorlage: Situation in zwei Sätzen · Optionen (2–3) mit Folgen · Empfehlung · was bis zur Entscheidung ruht.

## 5. Abschluss des Blocks

1. Alle Tasks des Blocks sind `DONE` (bei Pflicht-REVIEW erst nach dokumentierter Prüfung), `REVIEW` mit benannter prüfender Rolle oder begründet `BLOCKED`.
   1a. Git-Abgleich je berührtem Repo: `git status --short` sauber, `git stash list` ohne neue Einträge des Blocks, keine ungepushten Commits (`git log origin/feature/phase-1b-implementation-updates..feature/phase-1b-implementation-updates` leer). Abweichungen stehen mit Grund im Abschlussbericht.
2. `ayehear-architect` zieht Berichte, Index und Lessons nach.
3. `docs/STATUS.md` aktualisieren: Stand, nächste Schritte, offene Entscheidungen.
4. Abschlussbericht an Sascha: Ziel erreicht ja/teilweise/nein · erledigte Tasks · offene Punkte · Backlog-Einträge mit Auslöser (Abschnitt 2a) zur Priorisierung · Kennzahlen je Task (Review-Runden, Zeilenwachstum) und Auffälligkeiten der Gate-Checkliste · neue Lessons · Vorschlag für den nächsten Block.
