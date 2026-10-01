---
name: auftrag-vorlage
description: Auftragsvorlage der Projektleitung an eine Rolle mit Pflichtfeldern Phase und Nicht-Ziele
---

<!-- Verwaltet durch platform-tools/tools/claude-kit. Änderungen in der Vorlage vornehmen und install.py erneut ausführen. -->

# Auftragsvorlage (Projektleitung an eine Rolle)

Jeder Auftrag an eine Rolle enthält alle Felder. Fehlt Phase oder Nicht-Ziele, fragt die Rolle zurück, statt zu raten. Keine Mit-Erledigen-Klausel: Was nicht unter Ziel oder Akzeptanzkriterien steht, ist nicht Teil des Auftrags; Neues meldet die Rolle als Vorschlag im Übergabebericht.

```
Task: <ID> – <Titel>
Rolle: <Fachrolle>

**Phase:** Konzept | Code | Härtung   (genau eine)
**Ziel:** <ein Satz>
**Akzeptanzkriterien:** <nummerierte, prüfbare Kriterien; Reviews prüfen nur dagegen>; stehend in jedem Auftrag: Risiko Produktion/Daten/Secrets (Skill arbeitsblock 2a) – ein solcher Befund ist ein zulässiges „blockiert aktuelles Ziel: ja“, auch außerhalb von Phase; nach der Korrekturrunde Eskalation
**Nicht-Ziele:** <was ausdrücklich nicht getan wird, mindestens eine Zeile>
**Blockschnitt:** <Auftrag in Blöcke geschnitten, die in ein Turn-Limit passen; nach jedem Block Zwischen-Commit auf dem Task-Branch>
**Git-Rahmen:** Task-Branch <typ>/<ID>-<kurzname>; Worktree ja/nein; Basis <Trunk-SHA>; Commit/Push freigegeben ja/nein
**Gate:** <Konzept-Gate des PO nötig? ja (Architekturrelevanz oder Konzept und Code im Block) / nein>; bei Code nach Konzept: Freigabe von Sascha (Datum, Wortlaut) steht im Task
**Vorgaben:** Task am Ende auf REVIEW setzen, nicht Complete-Task; kein -SkipReview/-Force; keine Hook-Overrides (SKIP_*, --no-verify, git push --force; Start-Task -Force ausgenommen) ohne Freigabe von Sascha im Task
**Ergebnisse der Vorrollen:** <knapp, mit Quelle>
**Rückgabe:** Übergabebericht nach task-execution Abschnitt 8; Befunde im Befundformat (Abschnitt 5d)
```

Prüfrollen (Review) bekommen zusätzlich: Diff bzw. Artefakt, die Akzeptanzkriterien der umsetzenden Runde und – bei Re-Review – die bisherigen blockierenden Auflagen. Sie prüfen nur den Diff der Korrekturrunde und nur diese Auflagen.
