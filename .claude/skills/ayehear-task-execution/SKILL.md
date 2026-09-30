---
name: ayehear-task-execution
description: Gemeinsamer Arbeitsablauf aller Rollen in AYE Hear – Task klären, Kontext gezielt laden, Architekturcheck, Task-CLI-Lebenszyklus, Nachweis vor Abschluss, Lessons, Rollen-Gedächtnis und Übergabebericht. Wird von jeder Rolle vorgeladen.
---

<!-- Verwaltet durch platform-tools/tools/claude-kit. Änderungen in der Vorlage vornehmen und install.py erneut ausführen. -->

# Gemeinsamer Taskablauf (gilt für alle Rollen)

Diese Datei ist die einzige Quelle für den gemeinsamen Ablauf. Die Rollendateien enthalten nur, was rollenspezifisch ist.

## Wo Informationen liegen

| Was                                       | Wo                                                                          |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| Aufgabe, Stand, Übergaben zwischen Rollen | Task-CLI (Projekt `hear`): Status, Implementation Notes, Folge-Tasks |
| Entscheidungen                            | ADRs unter `docs/adr/`                                                    |
| Gesamtstand für Sascha                    | `docs/STATUS.md` (eine Seite)                                               |
| Fehler und Lösungen für alle Rollen       | `docs/lessons/INDEX.md` (eine Zeile pro Lesson)                             |
| Eigene Erfahrungen der Rolle              | Rollen-Gedächtnis (`.claude/agent-memory/<rolle>/`)                         |

| Quality Gates / Definition of Done | `docs/governance/QUALITY_GATES.md`, `docs/governance/DEFINITIONS_OF_DONE.md` |
| Windows Packaging / Local Testing | `docs/quick-refs/WINDOWS_PACKAGING_RUNBOOK.md`, `docs/quick-refs/LOCAL_TESTING_QUICKREF.md` |

## 1. Task klären

- Aufruf der Task-CLI immer über den Wrapper, nur einfache Anführungszeichen im Befehl:
  `pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File G:/Repo/aye-hear/.claude/tools/task.ps1 "Get-Task -Id HEAR-123"`
- Die Beschreibung und die Implementation Notes des Tasks und seiner Vorgänger sind die Übergabe der vorherigen Rolle.
- Ohne Task-ID im Auftrag: offene Tasks der eigenen Rolle abrufen und im Bericht nachfragen, statt selbst einen zu wählen oder anzulegen.
- Gehört der Task nicht zur eigenen Rolle: nicht bearbeiten, an die zuständige Rolle verweisen.

## 2. Kontext gezielt laden

- Immer: `docs/PRODUCT_FOUNDATION.md`.
- Dazu die rollenspezifischen Dokumente und verbindlichen ADRs aus der Rollendatei. Abschnitte wie „Mandatory First Action“ in Rollendateien heißen: vor der ersten fachlichen Änderung lesen – nicht vor jeder Antwort.
- Nur weitere Dateien, die der Task konkret nennt oder berührt. Große Dateien (Kompendien, Logs, Pläne) nie vollständig laden, sondern gezielt durchsuchen.

## 3. Architekturcheck (vor der ersten Änderung)

Liste für dich die ADRs und Contracts, die der Task berührt, und prüfe, ob der geplante Weg ihnen entspricht. Beim Bearbeiten bestimmter Pfade lädt Claude Code zusätzlich automatisch die passenden Regeln aus `.claude/rules/`. Widerspricht der Auftrag einer ADR oder fehlt eine erlaubte Operation: nicht umgehen, sondern blockieren und an die Architektur-Rolle (`ayehear-architect`) eskalieren.

## 4. Lebenszyklus in der Task-CLI

1. `Start-Task -Id HEAR-123 -ChangedByRole <ROLLE> -Force`
2. Während der Arbeit: Zwischenstände mit `Set-Task -Id HEAR-123 -Note '…'` (landet im Verlauf des Tasks, höchstens 500 Zeichen, wird angehängt).
   **Achtung:** `-ImplementationNotes` (bei `Set-Task` und `Complete-Task`) **ersetzt** das Feld vollständig (höchstens 5000 Zeichen). Vor jedem Schreiben das Feld mit `Get-Task -Id HEAR-123` lesen, den bisherigen Inhalt übernehmen und den neuen Eintrag mit Datum und Rolle anhängen; bei Platzmangel ältere Einträge zusammenfassen, nie stillschweigend löschen.
3. Abschluss: Ist `REVIEW` Pflicht (Abschnitt 5a, im Zweifel ja), setzt du `Set-Task -Id HEAR-123 -Status REVIEW -Note '…'` und beendest – kein `Complete-Task`. Nur wenn Abschnitt 5a den Direktabschluss erlaubt: `Complete-Task -Id HEAR-123 -ChangedByRole <ROLLE>`. Nie `-SkipReview` oder `-Force` bei `Complete-Task` (Abschnitt 5a).
4. Blockiert: `Set-Task -Id HEAR-123 -Status BLOCKED -Note '<Grund>'`.
5. Folgearbeit: im Übergabebericht als Vorschlag für einen Folge-Task formulieren (Titel, Rolle, Ziel, Bezug). Anlegen tut die Projektleitung (`ayehear-lead`). Selbst anlegen nur, wenn Sascha es ausdrücklich beauftragt.

Nie `Set-Task -Status DONE`. Nie `-InteractiveApms`.

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
2. **Branch:** eigene Arbeit auf `<typ>/HEAR-<nr>-<kurzname>` ab `origin/feature/phase-1b-implementation-updates`. Direkt auf dem Trunk nur, wenn der Auftrag es ausdrücklich erlaubt. Arbeitet eine zweite Sitzung im selben Repo oder war das Verzeichnis beim Start nicht sauber: eigener Worktree (`git worktree add ../<repo>-wt-<nr> -b <branch> origin/feature/phase-1b-implementation-updates`) – die Projektleitung gibt das im Auftrag vor.
3. **Immer mit Pfaden:** `git add <pfade>`, `git stash push -m '<ID>: <grund>' -- <pfade>`, `git checkout HEAD -- <pfade>`. Nie auf das ganze Verzeichnis: `git stash` ohne Pfade, `git add -A`/`.`, `git commit -a`, `git checkout .`, `git restore .`, `git clean`, `-AutoStage`/`-AutoPush`.
4. **Stash:** lieber ein WIP-Commit auf dem Task-Branch. Eigener Stash nur kurz, mit Task-ID, vor Sitzungsende aufgelöst. Fremde oder unklare Stashes nur lesen (`git stash show -p stash@{n}`); `pop`/`apply`/`drop`/`clear` nur mit Freigabe der Projektleitung. Sichern statt löschen: `git branch rescue/stash-<datum>-<n> stash@{n}` und pushen.
5. **Aus fremdem Stash/Branch übernehmen:** nur die Differenz (`git diff stash@{n}^1 stash@{n} -- <pfad>`), nie die ganze Datei (`git show stash@{n}:<pfad>` bringt fremden Inhalt mit). Danach `git diff` Hunk für Hunk prüfen.
6. **Commit** über `git commit`, Task-ID in der Nachricht. Task-Branch spätestens vor `REVIEW` pushen, sofern der Auftrag Commit/Push freigibt (Abschnitt 9).
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

## 6. Bei Problemen: Lessons zuerst

Tritt ein Fehler oder ein unerwartetes Verhalten auf, zuerst in `docs/lessons/INDEX.md` nach dem Symptom suchen. Hast du ein nicht-triviales Problem gelöst, das auch andere Rollen treffen kann, ergänze dort eine Zeile (Datum, Bereich, Symptom, Ursache/Lösung, Quelle). Nur für die eigene Rolle Relevantes gehört ins Rollen-Gedächtnis.

## 7. Rollen-Gedächtnis

Halte im eigenen Gedächtnis nur dauerhafte, überprüfte Erfahrungen fest, die künftigen Aufträgen dieser Rolle helfen: Stolperfallen, bewährte Befehle, wiederkehrende Fehlerbilder, Konventionen. Kein Task-Stand (der gehört in die Task-CLI), keine Secrets, keine Rohdaten. Kurz halten; Veraltetes entfernen.

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
- **Git-Stand:** Repo · Branch · Commit · gepusht ja/nein · offen (Abschnitt 5b)
- **Vorgeschlagene Folge-Tasks:** Titel, Rolle, Ziel, Bezug
- **Nächste Rolle:** wer übernimmt, Übergabestatus; bei `REVIEW` die vorgeschlagene prüfende Rolle

## 9. Grenzen, die für alle gelten

- Offline-first: keine Übertragung von Audio-, Transkript- oder Sprecherdaten an externe/Cloud-Dienste (ADR-0001, ADR-0009).
- Datenzugriff nur über den definierten Persistence-Contract (ADR-0007), keine Ad-hoc-SQL an den kanonischen Entitäten vorbei.
- Speicherung von Sprecherprofilen und personenbezogenen Daten nur gemäß Verschlüsselungs-/Encryption-at-rest-Modell (ADR-0009).
- Änderungen an platform-tools (Auth, i18n, Billing, Task-CLI, Claude-Kit) nur über Tasks im Projekt `platform` (ADR-0040).

- `.env*`, `.credentials/`, `secrets/`, Schlüssel- und Zertifikatsdateien werden nicht gelesen.
- Kein Commit, Push oder Merge ohne ausdrücklichen Auftrag.
