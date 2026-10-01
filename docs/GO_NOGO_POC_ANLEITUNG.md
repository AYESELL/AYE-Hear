---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-09-30
category: governance
task: HEAR-197
---

# POC-Aufnahme S1: Anleitung für Sascha

Dauer insgesamt etwa 20 Minuten. Es wird eine einzige Aufnahme von 4 bis 6 Minuten gemacht, nur Sascha spricht. HEAR läuft dabei mit, damit dieselbe Sprache einmal live durch HEAR geht und einmal als Datei vorliegt.

## 1. Vorbereiten (5 min)

1. Ordner `D:\AYE\hear-eval\` anlegen. Hier liegt alles; nichts davon kommt ins Repository.
2. Ruhiger Raum wie im Alltag, keine weiteren Personen, kein Radio oder Fernseher.
3. **Netzwerk trennen** (WLAN aus bzw. Netzwerkkabel ab), bevor HEAR startet. Erst nach dem Export wieder verbinden. So ist belegt, dass HEAR offline gearbeitet hat.
4. Windows-App **Audiorekorder** öffnen. Unter Einstellungen als Mikrofon **Amazon USB Streaming Mic** wählen und als Format **WAV** (falls angeboten, sonst Standard lassen).
5. In Windows prüfen, dass dasselbe Mikrofon als Standard-Eingabegerät gesetzt ist. HEAR nutzt immer das Standardgerät.
6. **AYE Hear 0.7.1** starten. Neues Meeting „POC-S1“, intern, Teilnehmer: Sascha. Sprecher-Anmeldung (8 Sekunden) wie gewohnt durchführen.
7. Kurztest: Rekorder 10 s aufnehmen, während HEAR läuft. Kommen beide Pegel an, passt es. Startet HEAR nicht oder zeigt einen Datenbankfehler, trotzdem weitermachen und nur die Datei aufnehmen. Das ist dann selbst ein Befund.

## 2. Aufnehmen (6 min)

1. Im Rekorder die Aufnahme starten, danach in HEAR das Meeting starten, dann 3 Sekunden warten.
2. Anhand der Stichpunkte unten **frei sprechen, nicht ablesen**, als würdest du einem Kollegen die Ergebnisse einer Besprechung berichten. Versprecher und „äh“ sind in Ordnung. Ziel sind 4 bis 6 Minuten.
3. In HEAR das Meeting beenden, danach die Aufnahme im Rekorder stoppen.
4. Die Datei als `D:\AYE\hear-eval\S1.wav` speichern (oder `S1.m4a`, falls kein WAV angeboten wird).
5. In HEAR Protokoll und Transkript exportieren. Die Dateien aus `D:\AYE\AyeHear\exports\` nach `D:\AYE\hear-eval\` kopieren.

## 3. Stichpunkte (Vorlage, frei vortragen)

Thema: Kurzbesprechung zur Einführung eines neuen Ticketsystems. Die Namen sind erfunden; bitte keine echten Personen oder Kunden verwenden.

- Anlass: Das alte Ticketsystem läuft Ende Januar aus. Heute ging es um Nachfolger und Zeitplan.
- **Entscheidung 1:** Wir nehmen „HelpFlow“ statt „DeskOne“, weil es eine offene API und eine Anbindung an die Task-CLI hat.
- **Entscheidung 2:** Start am 1. Dezember mit dem Support-Team, die anderen Teams folgen im Januar.
- **Entscheidung 3:** Budget höchstens 4.800 Euro im ersten Jahr, inklusive Schulung.
- **Aufgabe:** Anna Berger holt bis 15. Oktober ein verbindliches Angebot ein.
- **Aufgabe:** Tom Keller testet bis Kalenderwoche 44 die Datenmigration mit 200 Alt-Tickets.
- **Aufgabe:** Sascha plant zwei Schulungstermine à 90 Minuten.
- **Aufgabe:** Lea Schmitt klärt mit dem Datenschutz, ob die Cloud-Option abgeschaltet werden kann.
- **Offener Punkt:** Ob die SLA-Auswertung in AYE Know einfließen soll, ist noch nicht entschieden.
- **Risiko:** Wenn die Migration länger als zwei Wochen dauert, verschiebt sich der Start.

## 4. Soll-Liste (2 min, direkt nach der Aufnahme)

Die Stichpunkte oben in eine Textdatei `D:\AYE\hear-eval\S1-soll.txt` kopieren und nur anpassen, was du tatsächlich anders gesagt oder weggelassen hast. Das ist der Maßstab für die Zusammenfassung.

## 5. Danach

Kurze Nachricht an die Projektleitung, dass Aufnahme und Soll-Liste vorliegen. Später folgen zwei kurze Schritte:

- **Referenz:** Du bekommst ein Vor-Transkript, in dem die unsicheren Stellen markiert sind. Du hörst die Aufnahme einmal durch und korrigierst dabei (15 bis 20 min).
- **Bewertung:** Du bewertest zwei bis drei Zusammenfassungen mit „brauchbar ja/nein“ und misst dabei mit der Stoppuhr, wie lange die Nacharbeit dauert (10 bis 15 min).

Auch für die späteren Messläufe wird das Netzwerk getrennt. Die Ollama-Desktop-App baut sonst im Hintergrund Verbindungen ins Internet auf (vermutlich Update-Prüfung); siehe Bericht, Abschnitt 2.9.
