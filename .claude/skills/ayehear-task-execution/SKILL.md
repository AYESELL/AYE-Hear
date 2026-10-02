---
name: ayehear-task-execution
description: Gemeinsamer Arbeitsablauf aller Rollen in AYE Hear – Task klären, Kontext gezielt laden, Architekturcheck, Task-CLI-Lebenszyklus, Nachweis vor Abschluss, Lessons, Rollen-Gedächtnis und Übergabebericht. Wird von jeder Rolle vorgeladen.
---

<!-- Verwaltet durch platform-tools/tools/claude-kit. Änderungen in der Vorlage vornehmen und install.py erneut ausführen. -->

# Gemeinsamer Taskablauf (gilt für alle Rollen)

Diese Datei ist die einzige Quelle für den gemeinsamen Ablauf. Die Rollendateien enthalten nur, was rollenspezifisch ist.

## Wo Informationen liegen

- **Aufgabe, Stand, Übergaben zwischen Rollen:** Task-CLI (Projekt `hear`): Status, Implementation Notes, Folge-Tasks
- **Entscheidungen:** ADRs unter `docs/adr/`
- **Gesamtstand für Sascha:** `docs/STATUS.md` (eine Seite)
- **Fehler und Lösungen für alle Rollen:** `docs/lessons/INDEX.md` (eine Zeile pro Lesson)
- **Eigene Erfahrungen der Rolle:** Rollen-Gedächtnis (`.claude/agent-memory/<rolle>/`)
  
- **Quality Gates / Definition of Done:** `docs/governance/QUALITY_GATES.md`, `docs/governance/DEFINITIONS_OF_DONE.md`
- **Windows Packaging / Local Testing:** `docs/quick-refs/WINDOWS_PACKAGING_RUNBOOK.md`, `docs/quick-refs/LOCAL_TESTING_QUICKREF.md`

## 1. Task klären

- Aufruf der Task-CLI immer über den Wrapper, nur einfache Anführungszeichen im Befehl:
  `pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File G:/Repo/aye-hear/.claude/tools/task.ps1 "Get-Task -Id HEAR-123"`
- Im PowerShell-Werkzeug wird `pwsh …` (verschachtelter Prozess) immer abgelehnt; dort das Skript direkt aufrufen: `G:/Repo/aye-hear/.claude/tools/task.ps1 "Get-Task -Id HEAR-123"` (Pfad genau so: Großbuchstabe Laufwerk, Schrägstriche). Im Bash-Werkzeug bleibt es beim `pwsh …`-Aufruf oben.
- Die Beschreibung und die Implementation Notes des Tasks und seiner Vorgänger sind die Übergabe der vorherigen Rolle.
- Ohne Task-ID im Auftrag: offene Tasks der eigenen Rolle abrufen und im Bericht nachfragen, statt selbst einen zu wählen oder anzulegen.
- Gehört der Task nicht zur eigenen Rolle: nicht bearbeiten, an die zuständige Rolle verweisen.

## 1a. Werkzeuge und Befehle

Erlaubnisregeln prüfen den Befehlstext genau; zusammengesetzte oder ungewöhnliche Befehle lösen Rückfragen aus. Deshalb:

1. Dateien mit Read, Grep und Glob lesen und durchsuchen, nicht mit PowerShell (`Get-Content`, `Get-ChildItem`, `Select-String`, `Get-Item`) oder `cat`/`grep` im Shell-Werkzeug. Nur die eingebauten Werkzeuge halten die `Read(...)`-Sperren (`.env`, `secrets/`) zuverlässig ein. PowerShell nur für Git, die Task-CLI und Kommandos, die kein eingebautes Werkzeug ersetzt.
2. Ein einfacher Befehl pro Schritt: keine Semikolon-Ketten, keine Pipes in Filterbefehle (`Select-String`, `Where-Object`), kein `%`/`ForEach-Object` mit Skriptblock, keine `$env:`-Variablen (auch keine `$`-Ausdrücke oder Backticks in doppelten Anführungszeichen). Den Task-Wrapper ohne Pipe und ohne `2>&1` aufrufen und die Ausgabe direkt lesen. Aufrufform je Werkzeug: Bash `pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File G:/Repo/aye-hear/.claude/tools/task.ps1 "<Befehl>"`; PowerShell `G:/Repo/aye-hear/.claude/tools/task.ps1 "<Befehl>"` direkt ohne `pwsh` (verschachteltes `pwsh` fragt dort immer nach).
3. Im Argument des Task-Wrappers nie `$`, Backtick oder Backslash vor einem Leerzeichen verwenden (umschreiben); das fragt in beiden Werkzeugen immer nach, auch mit passender Regel.
4. Im PowerShell-Werkzeug den Gesamtbefehl unter etwa 1000 Byte halten (Umlaute zählen doppelt). Lange Argumente (z. B. `-ImplementationNotes`, Beschreibungen) über das Bash-Werkzeug übergeben oder kürzen – oder besser den Text mit dem Write-Werkzeug als UTF-8-Datei ablegen (Scratchpad) und den Datei-Parameter nutzen (Punkt 5).
   Der Hook `task-call-guard` (PreToolUse) lehnt `task.ps1`-Aufrufe mit Pipe, Semikolon, `foreach`, Statuslisten, falschen Statuswerten und im PowerShell-Werkzeug über 1000 Byte schon vor dem Popup mit dieser Anleitung ab.
5. Notes werden angehängt, nie neu geschrieben: nur den neuen Eintrag (Datum, Rolle) übergeben, nie den Altinhalt mitschicken (Abschnitt 4). `Set-Task -ImplementationNotesFile <Datei>` bzw. `Complete-Task -NoteFile <Datei>` hängen den UTF-8-Dateiinhalt an die bestehenden Notes an (Leerzeile dazwischen; über 5000 Zeichen gesamt wird nichts geschrieben); Umlaute bleiben erhalten, die Datei-Parameter bleiben empfohlen. `Complete-Task -Note`/`-ImplementationNotes` hängen ebenfalls an. `Set-Task -ImplementationNotes` lehnt bei vorhandenen Notes ab; Ersetzen nur mit `-ReplaceNotes` und Freigabe. `Set-Task -Note` legt nur einen Verlaufseintrag an (bis 500 Zeichen). Gegenstück für Beschreibungen: `New-Task -DescriptionFile`.
6. Pro Schritt ein einfacher Befehl: keine Variablen, `foreach`, Skriptblöcke (`% { }`, `ForEach-Object`) und Semikolon-Ketten; keine Select-String- oder Filterketten hinter dem Wrapper.
7. Git im Arbeitsverzeichnis ausführen, nicht mit `git -C <Pfad>`; nur so entsprechen `git status`, `git log`, `git add` und `git commit` den Erlaubnisregeln. In einem Worktree (Abschnitt 5b Punkt 2) gilt dasselbe: Git ohne `-C`, der Task-Wrapper nur in der PowerShell-Form (`pwsh` im Bash-Werkzeug wird dort blockiert). Sieht der Auftrag einen Worktree vor und ist der Subagent nicht darin gebunden, stoppt er und meldet; er arbeitet nie im Hauptordner weiter. Die Isolation von Claude Code ist teilweise: Edit und Write auf den Hauptordner werden blockiert, nicht aber Shell-Schreiben dorthin (Umleitung, `Set-Content`); `git -C <Hauptordner>` fragt nur im Manual-Modus, im Auto-Modus kann der Klassifikator genehmigen. Beides unterlässt die Rolle selbst.
8. Task-Felder mit einem einfachen `Get-Task -Id …` lesen, nicht durch Filterbefehle leiten.

### Kurzreferenz Task-CLI (aus dem Quelltext `tools/task-cli/Public`)

Aufruf immer über den Wrapper (Abschnitt 1): Bash-Werkzeug mit `pwsh -NoProfile … -File`, PowerShell-Werkzeug `G:/Repo/aye-hear/.claude/tools/task.ps1 "<Befehl>"` direkt ohne `pwsh`. `Get-Help` und `Get-Command` lehnt der Wrapper ab; Parameternamen stehen nur hier. Rollen: die Rollen-IDs der Task-CLI dieses Repos in Großbuchstaben (z. B. `AYEHEAR_LEAD`), Prioritäten klein geschrieben, Status groß geschrieben.

**Klarstellung:** Die Tabelle listet alle Werte, die die Task-CLI technisch kennt, nicht was eine Rolle tun darf. Rollen setzen nie `Set-Task -Status DONE`. Ein Abschluss mit `Complete-Task` ist nur nach Abschnitt 5a zulässig, durch die Projektleitung `ayehear-lead` oder die prüfende Rolle nach dem Review; die umsetzende Rolle schließt ihren Task nie selbst. `New-Task` legt nur die Projektleitung an, außer Sascha beauftragt es einer Rolle ausdrücklich; sonst schlagen Rollen Folge-Tasks im Übergabebericht vor (Abschnitt 4, Punkt 5).

| Befehl               | Pflicht                                                                                                   | Wichtige optionale Parameter                                                                                                                                                                                                                                                                                                                                                                                                    |
| -------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `New-Task`           | `-Title` (1–200 Zeichen), `-Role` (nicht `-AssignedRole`), `-Priority` (`critical` `high` `medium` `low`) | `-CreatedByRole` (Standard: Entwicklerrolle des Repos, immer eigene Rolle setzen), `-StoryPoints` (1 2 3 5 8 13), `-Type`, `-Description` (bis 2000 Zeichen) oder `-DescriptionFile`, `-Parent`, `-QualityGateType` (`standard` `ops` `docs`), `-Sprint`, `-DryRun`                                                                                                                                                             |
| `Set-Task`           | `-Id` und mindestens ein zu änderndes Feld                                                                | `-Status` (`DRAFT` `OPEN` `IN_PROGRESS` `BLOCKED` `REVIEW` `DONE` `CANCELLED`), `-Note` (bis 500 Zeichen, angehängt), `-ImplementationNotesFile` (UTF-8-Datei, wird angehängt, bis 5000 gesamt) oder `-ImplementationNotes` (nur ohne vorhandene Notes; Ersetzen nur mit `-ReplaceNotes` und Freigabe), `-Priority`, `-Type`, `-Title`, `-Description`, `-StoryPoints`, `-AssignedToRole`, `-ChangedByRole`, `-QualityGateType` |
| `Start-Task`         | `-Id`                                                                                                     | `-ChangedByRole` (Standard: Entwicklerrolle des Repos), `-Force`, `-Note`, `-DryRun`                                                                                                                                                                                                                                                                                                                                            |
| `Complete-Task`      | `-Id`                                                                                                     | `-ChangedByRole`, `-NoteFile` (UTF-8-Datei) oder `-Note`/`-ImplementationNotes` (alle hängen an die Notes an; Ersetzen nur mit `-ReplaceNotes` und Freigabe); `-SkipReview`, `-Force` nur mit Freigabe (Abschnitt 5a)                                                                                                                                                                                                           |
| `Get-Task`           | keine                                                                                                     | `-Id`, `-Role`, `-Status`, `-Priority`, `-ParentId`, `-Limit`, `-OutputFormat` (`Table` `JSON` `CSV` `Markdown`)                                                                                                                                                                                                                                                                                                                |
| `Add-TaskDependency` | `-Id` und genau eines von `-BlockedBy`, `-Blocks`, `-RelatedTo` (jeweils Task-ID)                         | `-CreatedByRole`                                                                                                                                                                                                                                                                                                                                                                                                                |
| `New-FollowUpTask`   | `-ParentId`, `-Title` (Position 0 und 1)                                                                  | `-Role`, `-Priority` (beide vom Eltern-Task geerbt), `-Type` (`TASK` `FEATURE` `BUG`), `-Description`, `-StoryPoints`, `-CreatedByRole`                                                                                                                                                                                                                                                                                         |

- **`-Project`:** `New-Task` und `Get-Task` immer mit `-Project hear` aufrufen (der Standard ist `platform`, in anderen Repos sonst das falsche Projekt).
- **`-Type` bei `New-Task`:** gültig sind `TASK` (Standard), `FEATURE`, `BUG`; `docs`/`documentation`/`deployment` werden zu `TASK`, `development` zu `FEATURE`, `fix`/`bugfix` zu `BUG`. `EPIC` und `ADR` lehnt `New-Task` ab: erst anlegen, dann `Set-Task -Id HEAR-123 -Type EPIC` (dort gültig: `TASK` `FEATURE` `BUG` `ADR` `EPIC`).
- **Task mit langer Beschreibung** (ein einfacher Bash-Aufruf, Wrapper in doppelten, alles Innere in einfachen Anführungszeichen; `-DryRun` prüft nur und schreibt nichts, zum Anlegen weglassen):

```
pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File G:/Repo/aye-hear/.claude/tools/task.ps1 "New-Task -Title 'Kurzreferenz prüfen' -Role <ROLLE> -Priority medium -CreatedByRole <EIGENE_ROLLE> -Type FEATURE -StoryPoints 3 -Description 'Ziel: … Kontext: … Akzeptanz: …' -DryRun"
```

## 2. Kontext gezielt laden

- Immer: `docs/PRODUCT_FOUNDATION.md`.
- Dazu die rollenspezifischen Dokumente und verbindlichen ADRs aus der Rollendatei. Abschnitte wie „Mandatory First Action“ in Rollendateien heißen: vor der ersten fachlichen Änderung lesen – nicht vor jeder Antwort.
- Nur weitere Dateien, die der Task konkret nennt oder berührt. Große Dateien (Kompendien, Logs, Pläne) nie vollständig laden, sondern gezielt durchsuchen.

## 3. Architekturcheck (vor der ersten Änderung)

Liste für dich die ADRs und Contracts, die der Task berührt, und prüfe, ob der geplante Weg ihnen entspricht. Beim Bearbeiten bestimmter Pfade lädt Claude Code zusätzlich automatisch die passenden Regeln aus `.claude/rules/`. Widerspricht der Auftrag einer ADR oder fehlt eine erlaubte Operation: nicht umgehen, sondern blockieren und an die Architektur-Rolle (`ayehear-architect`) eskalieren.

## 4. Lebenszyklus in der Task-CLI

1. `Start-Task -Id HEAR-123 -ChangedByRole <ROLLE> -Force`
2. Während der Arbeit: Zwischenstände mit `Set-Task -Id HEAR-123 -Note '…'` (landet im Verlauf des Tasks, höchstens 500 Zeichen, wird angehängt).
   **Achtung:** Notes werden angehängt. Nur den neuen Eintrag mit Datum und Rolle übergeben, nie den Altinhalt mitschicken (sonst steht er doppelt). Empfohlen: neuen Eintrag als UTF-8-Datei schreiben und `Set-Task -Id HEAR-123 -ImplementationNotesFile <Datei>` bzw. `Complete-Task -Id HEAR-123 -NoteFile <Datei>` verwenden. Das Limit von 5000 Zeichen gilt gesamt; wird es überschritten, schreibt die Task-CLI nichts. `Set-Task -ImplementationNotes` lehnt bei vorhandenen Notes ab. Ersetzen nur mit `-ReplaceNotes` und Freigabe, vorher mit `Get-Task -Id HEAR-123` lesen; ältere Einträge zusammenfassen, nie stillschweigend löschen.
3. Abschluss: Ist `REVIEW` Pflicht (Abschnitt 5a, im Zweifel ja), setzt du `Set-Task -Id HEAR-123 -Status REVIEW -Note '…'` und beendest – kein `Complete-Task`. Nur wenn Abschnitt 5a den Direktabschluss erlaubt: `Complete-Task -Id HEAR-123 -ChangedByRole <ROLLE>`. Nie `-SkipReview` oder `-Force` bei `Complete-Task` (Abschnitt 5a).
4. Blockiert: `Set-Task -Id HEAR-123 -Status BLOCKED -Note '<Grund>'`.
5. Folgearbeit: im Übergabebericht als Vorschlag für einen Folge-Task formulieren (Titel, Rolle, Ziel, Bezug, **Story-Points-Vorschlag** nach Abschnitt 4a). Anlegen tut die Projektleitung (`ayehear-lead`). Selbst anlegen nur, wenn Sascha es ausdrücklich beauftragt.

Nie `Set-Task -Status DONE`.

## 4a. Story Points (Aufwandsschätzung, Pflicht bei jedem Task)

Jeder Task trägt Story Points (SP). **Zuständig ist der Ersteller des Tasks**: die Projektleitung beim Anlegen, jede andere Rolle mit einem SP-Vorschlag in ihren Folge-Task-Vorschlägen (Abschnitt 4, Punkt 5, und Übergabebericht).

- **Gültige Werte:** 1, 2, 3, 5, 8, 13 (Task-CLI `ValidateSet`). Andere Werte werden abgelehnt.
- **Faustregel (Aufwand inkl. Prüfung, nicht Zeit):** 1 = triviale Korrektur, eine Stelle · 2 = kleine, klare Änderung · 3 = überschaubar, wenige Dateien · 5 = mittel, mehrere Komponenten oder Abstimmung nötig · 8 = groß, mit Unsicherheit oder Migration · 13 = sehr groß; besser in Tasks schneiden.
- **Epics:** Ein Task über 13 SP oder mit mehreren Rollen über mehrere Arbeitsblöcke wird ein Epic (`Set-Task -Type EPIC`; `New-Task` akzeptiert nur `TASK`, `FEATURE`, `BUG`) und in Teil-Tasks zerlegt; jeder Teil-Task bekommt eigene SP.
- **Anlegen:** `New-Task … -StoryPoints <wert>` immer ausdrücklich setzen. Lässt man den Parameter weg, setzt die Task-CLI still einen Typ-Standard (TASK 2, FEATURE 5, BUG 3, ADR 3, EPIC 8), der keine Schätzung ist und nicht als solche gelten darf.
- **Nachtragen/Korrigieren:** `Set-Task -Id HEAR-123 -StoryPoints <wert>`. Fehlen SP (0/leer), verweigert `Start-Task` den Start mit dieser Meldung; dann Ersteller (Projektleitung) um Schätzung bitten oder, wenn sie im Auftrag fehlt, im Bericht nachfragen.
- Die ausführende Rolle darf eine erkennbar falsche Schätzung im Bericht anmerken (Ist-Aufwand vs. SP), ändert sie aber nicht eigenmächtig.

## 5. Nachweis vor Abschluss (blockierend)

`Complete-Task` ist nur zulässig, wenn die Implementation Notes enthalten:

- die tatsächlich ausgeführten Prüfungen mit Ergebnis, z. B. `pnpm test → 42 passed`,
- die berührten ADRs mit „eingehalten“ oder dem Verweis auf die Eskalation,
- die Pfade der erzeugten Berichte oder geänderten Dateien.

„Tests grün“ ohne Befehl und Ergebnis zählt nicht.

## 5a. Review vor Abschluss

**Ablauf:** umsetzende Rolle setzt `REVIEW` (mit den Nachweisen aus Abschnitt 5) und beendet → eine andere, geeignete Rolle prüft unabhängig → erst danach wird der Task mit dem Bericht geschlossen (Projektleitung `ayehear-lead` oder die prüfende Rolle; das Prüfergebnis mit Rolle, Datum und Befund steht in den Implementation Notes). Die umsetzende Rolle prüft und schließt ihren Task nie selbst.

**Prüfende Rolle:** Code, Contract, Skripte, Konfiguration → `ayehear-qa` · Daten, Rechte, Secrets, Lizenzen, externe Dienste → zusätzlich `ayehear-security` · Architekturfrage oder Abweichung von einer ADR → `ayehear-architect`. Anhaltspunkt ist die Review-Governance-Matrix der Task-CLI (`Get-ReviewPersona`).

**`REVIEW` ist Pflicht**, sobald eines zutrifft:

- Code, Contract, Skript, Konfiguration, Migration oder Rechte werden geändert,
- Priorität `high` oder `critical`,
- der Task ist Teil einer Kette (Folge-Tasks setzen auf sein Ergebnis auf),
- der Task ist umfangreich (mehr als eine kleine, in sich abgeschlossene Änderung).

**Direkter Abschluss** durch die Rolle ist nur zulässig, wenn keines davon zutrifft **und** der Task eine kleine Doku-Korrektur ist, den Gate-Typ `docs` hat oder eine reine Rückfrage/Klärung ohne Änderung ist. Im Zweifel `REVIEW`.

**`-SkipReview` und `-Force` bei `Complete-Task`** (umgehen Bestätigung und Review-/Checkpoint-Gates) nie auf eigene Initiative und nie ohne ausdrückliche Freigabe von Sascha. Die Freigabe (wer, wann, Grund) steht vorher in den Implementation Notes. Blockiert ein Gate den Abschluss und fehlt die Freigabe: Task auf `REVIEW` oder `BLOCKED` lassen und im Bericht melden. (`Start-Task … -Force` in Abschnitt 4 ist davon nicht betroffen.)

## 5b. Git: Stand sichern, wiederherstellbar halten (ADR-0100)

Grundsatz: Fertige Arbeit liegt als Commit auf einem Branch, der auf `origin` existiert. Uncommittete Änderungen, Stashes und nur lokale Commits sind Übergangszustände und stehen immer im Task (Git-Stand, Punkt 9).

1. **Vor der ersten Änderung:** `git fetch origin`, `git status --short`, `git stash list`. Aktiver Trunk dieses Repos: `feature/phase-1b-implementation-updates` – nicht automatisch `main`. Fehlt der Trunk auf `origin`, ist ein anderer Remote-Branch deutlich aktiver, oder liegen fremde Änderungen oder unbekannte Stashes vor: nichts davon anfassen, im Bericht melden.
2. **Branch und Worktree:** eigene Arbeit auf `<typ>/HEAR-<nr>-<kurzname>`. Basis ist `origin/feature/phase-1b-implementation-updates` (Worktree der Projektleitung) bzw. der lokale `HEAD` des Hauptordners, der der Trunk sein muss (Subagent mit `isolation: worktree` und `worktree.baseRef: "head"`). Direkt auf dem Trunk nur, wenn der Auftrag es ausdrücklich erlaubt. Arbeitet eine zweite Sitzung im selben Repo oder war das Verzeichnis beim Start nicht sauber: eigener Worktree unter `.claude/worktrees/` (Voraussetzung: `.claude/worktrees/` steht in der `.gitignore` des Repos).
   - **Start als Subagent:** von der Projektleitung mit `isolation: worktree` (Ordner `agent-<id>`, Branch `worktree-agent-<id>`).
   - **Basisprüfung, erste Aktion vor jeder Änderung:** `git log -1 --oneline`, `git branch --show-current`, `git rev-parse HEAD`. Weiter nur, wenn der Branch `worktree-agent-<id>` heißt und `git rev-parse HEAD` genau dem vollständigen Trunk-SHA aus dem Auftrag entspricht (Gleichheit, nicht nur Abstammung); sonst nichts ändern, Stopp und die drei Werte melden. Danach Git ohne `-C`.
   - **Umbenennen:** nach dem Commit, vor dem Bericht `git branch -m <typ>/HEAR-<nr>-<kurzname>` (ohne Task-Nummer im Branch kann ein Aufräumschritt den Worktree keinem Task zuordnen).
   - **Schreiben:** Dateien nur mit Edit/Write im eigenen Worktree; Shell-Befehle schreiben nie außerhalb des Worktrees (außer Scratchpad): keine Umleitung, kein `tee`, `Set-Content`, `Out-File`, `Copy-Item`, `Move-Item` mit Ziel im Hauptordner, kein `git -C` auf den Hauptordner – Claude Code blockiert das bei Subagenten nicht (im Manual-Modus fragt es bei `git -C`; im Auto-Modus kann der Klassifikator genehmigen, Shell-Schreiben in den Hauptordner bleibt immer Rollenregel). Eine Rückfrage zu `git -C` oder einem Pfad außerhalb des Worktrees heißt: Stopp, nicht bestätigen lassen. Task-CLI nur in der PowerShell-Form. `docs/STATUS.md` und `docs/BACKLOG.md` nur im Hauptordner durch die Projektleitung.
   - **Abhängigkeiten und Hooks:** Abhängigkeiten im Worktree selbst installieren, bevor Build, Typecheck, Lint, Tests oder Commit-Hooks sie brauchen (sonst greifen still die Pakete des Hauptordners); keine Junctions oder Symlinks auf den Hauptordner. Nie `--no-verify`.
   - **Aufräumen:** Entfernen nur durch die Projektleitung nach dem Merge mit `git worktree remove <pfad>` (nie per Dateimanager, `Remove-Item -Recurse` oder `--force`); vorher `git status --ignored --short` im Worktree prüfen, denn `git worktree remove` löscht ignorierte Dateien ohne Meldung. Ein sauberer, gepushter Worktree kann vor dem Merge von Claude Code entfernt werden; gemergt wird vom Branch. Der Git-Stand nennt Worktree-Ordner und Branch.
3. **Immer mit Pfaden:** `git add <pfade>`, `git stash push -m '<ID>: <grund>' -- <pfade>`, `git checkout HEAD -- <pfade>`. Nie auf das ganze Verzeichnis: `git stash` ohne Pfade, `git add -A`/`.`, `git commit -a`, `git checkout .`, `git restore .`, `git clean`, `-AutoStage`/`-AutoPush`.
4. **Stash:** lieber ein WIP-Commit auf dem Task-Branch. Eigener Stash nur kurz, mit Task-ID, vor Sitzungsende aufgelöst. Fremde oder unklare Stashes nur lesen (`git stash show -p stash@{n}`); `pop`/`apply`/`drop`/`clear` nur mit Freigabe der Projektleitung. Sichern statt löschen: `git branch rescue/stash-<datum>-<n> stash@{n}` und pushen.
5. **Aus fremdem Stash/Branch übernehmen:** nur die Differenz (`git diff stash@{n}^1 stash@{n} -- <pfad>`), nie die ganze Datei (`git show stash@{n}:<pfad>` bringt fremden Inhalt mit). Danach `git diff` Hunk für Hunk prüfen.
6. **Commit** per einfachem `git commit` mit Hooks (husky, commitlint), nie mit `--no-verify`; Entscheidung Sascha 29.09.2026. Format: Conventional Commits, Task-ID im Betreff, Body-Zeilen höchstens 100 Zeichen, am Ende die Co-Authored-By-Zeile aus der Vorgabe der Sitzung. Hooks können generierte Dateien (`docs/quick-ref`, `api`) neu erzeugen; sie erscheinen dann als Änderung und werden mit `git add <pfade>` geprüft und gegebenenfalls erneut committet. Task-Branch spätestens vor `REVIEW` pushen, sofern der Auftrag Commit/Push freigibt (Abschnitt 9).
7. **Vor jedem Push:** `git fetch origin`, dann `git log --oneline origin/<branch>..<branch>` – existiert `origin/<branch>` noch nicht (erster Push dieses Branches), stattdessen `git log --oneline origin/feature/phase-1b-implementation-updates..<branch>`. Nur pushen, wenn jeder gelistete Commit zum eigenen Task gehört oder freigegeben ist – sonst Stopp. Immer `git push origin <branch>`; kein `--all`, kein `--tags`, nie Force. Zurückgehaltene Commits liegen auf `hold/<ID>-…`, nie auf einem geteilten Branch.
8. **Statt `git reset --hard`** (gesperrt), nur wenn der lokale Branch inhaltlich gleich `origin/<b>` ist: `git diff --stat HEAD origin/<b>` (muss leer sein) → `git branch backup/<ID>-<datum>` → `git update-ref refs/heads/<b> origin/<b> <alter-sha>` → `git reset` (mixed) → `git status`; nur geprüfte Pfade mit `git checkout HEAD -- <pfade>`. Bei echten Unterschieden: Stopp.
9. **Git-Stand** vor `REVIEW` in die Implementation Notes und den Übergabebericht: `Git-Stand: <repo> · <branch> · <sha7> · gepusht ja/nein · offen: keine | <pfade/stash + grund>`. Merge in den Trunk macht die Projektleitung nach bestandenem REVIEW; `DONE` erst, wenn der Commit im gepushten Trunk liegt.

## 5c. Rückweisungsregeln

Gilt für jede Rückweisung zur Überarbeitung – im `REVIEW`-Schritt (Abschnitt 5a) ebenso wie bei jeder anderen Übergabe zwischen zwei Rollen.

1. **Konkretes Kriterium + Beleg.** Wer zurückweist, nennt explizit (a) welches dokumentierte Kriterium nicht erfüllt ist (Verweis auf die konkrete Stelle/den konkreten Prüfpunkt), (b) woran das gemessen wurde (Befehl, Zahl, Abschnitt, Quelle). Eine Rückweisung ohne beides ist nicht zulässig. Existiert für den geprüften Schritt kein dokumentiertes Kriterium, darf nicht zurückgewiesen werden – stattdessen Freigabe von Sascha einholen statt eines Freitext-Urteils.
2. **Höchstens eine Überarbeitungsschleife je Prüfschritt.** Erfüllt die Arbeit nach der ersten Überarbeitung das genannte Kriterium weiterhin nicht: keine zweite Runde mit derselben oder einer weiteren KI-Prüfinstanz. Stattdessen Eskalation an Sascha (oder `ayehear-lead` in seinem Auftrag) mit: ursprünglicher Einreichung, Rückweisungsgrund, Ergebnis der Überarbeitung, offener Lücke.
3. **Festes Feldformat statt Freitext.** Übergaben zwischen Rollen (Task-Status → `REVIEW`, Review-Ergebnis, Rückweisung) nennen: Kriterium · Befund (erfüllt/nicht erfüllt) · Beleg (Befehl/Zahl/Abschnitt) · bei „nicht erfüllt“: konkrete nächste Aktion. Frei formulierte Zusatzbegründung ist erlaubt, ersetzt aber nicht diese Pflichtfelder.
4. **Kein zweiter KI-Prüfer als Ersatz für ein fehlendes Kriterium.** Fällt ein Prüfschritt in Kategorie „kein Kriterium“ (kein Test/Build/Contract/Zahlen- oder Quellenabgleich, kein Ja/Nein-Prüfpunkt) und lässt sich kurzfristig kein hartes Kriterium nachrüsten, entscheidet ein Mensch (Sascha), nicht eine weitere Rolle.

Herkunft: Bestandsaufnahme PLAT-3302/PLAT-3304 (platform-tools, Kit-Quelle dieser Regeln).

## 5d. Scope-Disziplin für Aufträge, Befunde und Overrides

1. **Auftrag:** Er nennt **Phase** (Konzept, Code, Härtung), Akzeptanzkriterien und **Nicht-Ziele**. Fehlt etwas davon, nachfragen statt raten. Nie über Phase und Nicht-Ziele hinaus arbeiten; Neues steht als **Vorschlag im Übergabebericht**, nicht im Code.
2. **Befundformat (Reviewer):** ID · Schweregrad (hoch/mittel/niedrig) · verletztes Akzeptanzkriterium · Beleg · **blockiert aktuelles Ziel: ja/nein** · Vorschlag. „ja“ ist zulässig bei verletztem Akzeptanzkriterium oder bei konkretem Risiko für Produktion, Daten oder Secrets (stehendes Kriterium „Risiko Produktion/Daten/Secrets“, Skill `ayehear-arbeitsblock` 2a; wird immer behoben, nie ins Backlog verschoben, von der Phase ausgenommen; nach der Korrekturrunde Eskalation nach 5c.2). Geprüft wird sonst nur gegen die Akzeptanzkriterien; alles, was das Ziel nicht bricht, ist „nein“ und geht gebündelt in `docs/BACKLOG.md` (Entscheidung der Projektleitung). Ist im Bericht eine Erkenntnis angegeben (Abschnitt 8), bewertet die prüfende Rolle sie als Ja/Nein-Punkt (Kriterien und Ablage nach Abschnitt 7 erfüllt); „nein“ ist ein Hinweis ohne eigene Rückweisungsrunde.
3. **Review-Budget:** je Task eine Review-Runde plus eine Korrekturrunde. Re-Review prüft nur den Diff und nur die bisherigen blockierenden Auflagen; redaktionelle Reste ohne Re-Review (Abschnitt 5c.2, Skill `ayehear-arbeitsblock` 2a).
4. **Hook-Overrides:** `SKIP_*`, `--no-verify`, `git push --force` sowie `-Force` und `-SkipReview` bei `Complete-Task` nie ohne Freigabe von Sascha (`Start-Task -Force` aus Abschnitt 4 ist ausgenommen); die Freigabe (wer, wann, Grund) steht vor der Nutzung in den Implementation Notes.
5. **Entscheidungen:** Offene Fragen an Sascha höchstens eine echte Entscheidung je Bericht, mit Standardempfehlung; Zustimmung gilt nur bei ausdrücklicher Aussage, der Vermerk steht wörtlich in den Notes.

## 5e. Codex als optionale Zweitprüfung (nur Ergänzung)

1. **Wann sinnvoll:** bei Architektur-, Security-, Hook- und Kit-Änderungen und bei ADR-Entwürfen, wenn eine zweite, unabhängige Modellsicht Mehrwert bringt. Nie Ersatz für `ayehear-qa` oder `ayehear-security` (Abschnitt 5a), nur Ergänzung; sie ersetzt keine Freigabe.
2. **Aufruf:** über die Befehle `review` bzw. `adversarial-review` des installierten Codex-Plugins (Einrichtung und Prüfung: Skill `codex:setup`), nie über einen fest verdrahteten Plugin-Pfad. Immer im Task-Worktree (Abschnitt 5b) mit `--base <Basis-SHA des Task-Branches> --scope branch`, nicht auf dem gemeinsamen Trunk, sonst prüft Codex fremde Commits. Der Lauf dauert mehrere Minuten (`--wait`) und kostet API-Geld (eigener Schlüssel).
3. **Grenzen:** nur `review` und `adversarial-review` (lesend). `task` und `rescue` (Arbeit an Codex abgeben) nie ohne ausdrückliche Freigabe von Sascha. Keine Secrets, Kennwörter oder Zugangsdaten im Fokus-Text oder in den geprüften Dateien.
4. **Ergebnis:** als Befund nach Abschnitt 5d.2 einordnen (ID · Schweregrad · Kriterium · Beleg · blockiert ja/nein · Vorschlag); ohne verletztes Akzeptanzkriterium ist er „nein“.
5. **Gate aus:** Das Review-Gate des Plugins (Prüfung bei jedem Stopp) bleibt ausgeschaltet (Kosten und Zeit je Antwort); Codex wird nur gezielt aufgerufen, nie als Pflichtschritt eingebaut.

## 6. Bei Problemen: Lessons zuerst

Tritt ein Fehler oder ein unerwartetes Verhalten auf, zuerst in `docs/lessons/INDEX.md` nach dem Symptom suchen. Hast du ein nicht-triviales Problem gelöst, das auch andere Rollen treffen kann, ergänze dort eine Zeile (Datum, Bereich, Symptom, Ursache/Lösung, Quelle). Nur für die eigene Rolle Relevantes gehört ins Rollen-Gedächtnis.

## 7. Rollen-Gedächtnis

Halte im eigenen Gedächtnis nur dauerhafte, überprüfte Erfahrungen fest, die künftigen Aufträgen dieser Rolle helfen: Stolperfallen, bewährte Befehle, wiederkehrende Fehlerbilder, Konventionen. Kein Task-Stand (der gehört in die Task-CLI), keine Secrets, keine Rohdaten. Kurz halten; Veraltetes entfernen.

**Erkenntnis ablegen (nach Geltung):** Eine Erkenntnis aus dem Task wird nur festgehalten, wenn sie nicht aus Code, git oder CLAUDE.md ableitbar, übertragbar und kein Task-Stand ist; keine Kopie der Implementation Notes. Ablage durch die umsetzende Rolle: **Rolle** → Rollen-Gedächtnis mit Zeile in dessen `MEMORY.md`; **Projekt** → eine Zeile in `docs/lessons/INDEX.md` (Abschnitt 6); **alle Repos** → nur als Vorschlag an die Projektleitung im Übergabebericht, nie direkt ins Kit.

## 8. Übergabebericht an die Hauptsession

Jede Rolle endet mit diesem Bericht (Deutsch, knapp):

- **Task:** ID, Titel, Status in der Task-CLI
- **Kontext geladen:** welche Dokumente und ADRs
- **Ergebnis:** was erledigt wurde; bei fachlichen Aussagen Befund und Deutung trennen
- **Architektur:** berührte ADRs – eingehalten oder eskaliert
- **Geänderte Dateien**
- **Prüfungen:** Befehl → Ergebnis
- **Offene Fragen an Sascha:** jeweils mit Empfehlung
- **Rückweisung erhalten oder ausgesprochen (falls zutreffend):** Kriterium · Befund · Beleg · Aktion (Abschnitt 5c)
- **Neue Lessons:** Zeilen in `docs/lessons/INDEX.md`, falls ergänzt
- **Erkenntnis (optional):** gelernt · nicht wiederholen · Geltung (Rolle | Projekt | alle Repos) – oder „keine“; „keine“ ist ausdrücklich gültig, das Feld ist kein Pflichtfeld (Ablage nach Abschnitt 7)
- **Git-Stand:** Repo · Branch · Commit · gepusht ja/nein · offen (Abschnitt 5b)
- **Vorgeschlagene Folge-Tasks:** Titel, Rolle, Ziel, Bezug, Story Points (Vorschlag, Abschnitt 4a)
- **Nächste Rolle:** wer übernimmt, Übergabestatus; bei `REVIEW` die vorgeschlagene prüfende Rolle

## 9. Grenzen, die für alle gelten

- Offline-first: keine Übertragung von Audio-, Transkript- oder Sprecherdaten an externe/Cloud-Dienste (ADR-0001, ADR-0009).
- Datenzugriff nur über den definierten Persistence-Contract (ADR-0007), keine Ad-hoc-SQL an den kanonischen Entitäten vorbei.
- Speicherung von Sprecherprofilen und personenbezogenen Daten nur gemäß Verschlüsselungs-/Encryption-at-rest-Modell (ADR-0009).
- Änderungen an platform-tools (Auth, i18n, Billing, Task-CLI, Claude-Kit) nur über Tasks im Projekt `platform` (ADR-0040).

- `.env*`, `.credentials/`, `secrets/`, Schlüssel- und Zertifikatsdateien werden nicht gelesen.
- Kein Commit, Push oder Merge ohne ausdrücklichen Auftrag.

## 10. Zusätzliche Stopp-Regeln dieses Repos (anhalten und Sascha fragen)

Zusätzlich zu den Grenzen in Abschnitt 9: Trifft eines davon zu, nicht selbst entscheiden, sondern anhalten, den Task auf `BLOCKED` oder `REVIEW` lassen und im Übergabebericht (Abschnitt 8) unter „Offene Fragen an Sascha“ melden.

- Abweichungen von der Zwei-Zustände-Scope-Trennung (Operations-Handoff vs. Product-Complete, ADR-0010)
- Jede Änderung, die eine Cloud-Übertragung von Audio- oder Sprecherdaten einführen würde
