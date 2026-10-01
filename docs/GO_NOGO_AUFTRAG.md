---
owner: AYEHEAR_LEAD
status: active
updated: 2026-09-30
category: governance
---

# Auftrag an den Architekten AYE HEAR: Go/No-Go-Bewertung

Quelle: Auftrag von Sascha (Product Owner), 2026-09-30, unverändert übernommen.

## Ziel

Eine belastbare Entscheidungsgrundlage für Sascha (Product Owner): AYE HEAR weiterentwickeln, auf fertige Bausteine umbauen oder einstellen. Keine Code-Änderungen in diesem Auftrag. Nur Bestandsaufnahme, Messung, Vergleich und Empfehlung. Zeitrahmen: ein Arbeitsblock.

## Ausgangslage

HEAR ist eine Windows-Desktop-App für lokale, offline-first Meeting-Dokumentation: WASAPI-Aufnahme, Faster-Whisper, lokale Sprecher-Embeddings mit Enrollment, Protokoll-Extraktion über Ollama, PostgreSQL, Export als MD, DOCX oder PDF. Maßgeblich sind docs/PRODUCT_FOUNDATION.md und docs/adr/.
In den Prototypen lag die Erkennungsgenauigkeit bei etwa 80 bis 90 %. Das war zu wenig für brauchbare Protokolle.
Das Produkt muss nicht zwingend verkauft werden. Eigennutzung durch AYE ist ein legitimes Ziel. Der Aufwand soll aber in keinem Verhältnis zu einer fertigen, kostenlosen Lösung stehen.

## 1. Bestandsaufnahme

Für jede Stufe (Aufnahme, Transkription, Sprechertrennung und -zuordnung, Korrektur, Protokoll-Extraktion, Export) festhalten:

- Status (fertig, teilweise, nicht umgesetzt)
- Was nachweislich funktioniert (mit Beleg: Test, Messung, Beispiel)
- Was nicht funktioniert oder instabil ist
- Welche Modelle und Versionen im Einsatz sind

## 2. Messung mit echten Daten

Mit mindestens drei eigenen deutschen Aufnahmen (2, 4 und 6 oder mehr Sprecher, davon eine mit schlechter Akustik oder Zwischenrufen), jeweils 15 bis 30 Minuten:

- Wortfehlerrate (WER) gegen eine manuell korrigierte Referenz
- Sprecherzuordnung: Anteil richtig zugeordneter Redeanteile (DER, falls messbar)
- Laufzeit im Verhältnis zur Aufnahmedauer auf Saschas Hardware (mit und ohne GPU)
- Nacharbeitszeit bis zum brauchbaren Protokoll pro Stunde Meeting

## 3. Alternativen für einzelne Bausteine prüfen und mit denselben Aufnahmen messen

- Transkription: aktuelles Whisper-Modell in der größten lauffähigen Variante (large-v3 bzw. large-v3-turbo) mit sauberer Konfiguration (Sprache fest auf Deutsch, VAD, Beam Search). Außerdem prüfen, ob neuere offene Modelle mit Deutsch-Unterstützung bessere Werte liefern, z. B. NVIDIA Canary oder Mistral Voxtral. Verfügbarkeit, Lizenz und Deutsch-Qualität selbst verifizieren.
- Sprechertrennung: NVIDIA Nemotron 3 Diarization (bis 8 Sprecher, ca. 100 Mio. Parameter, OpenMDW-Lizenz, nur Hauptmodell, nicht „-preview“, siehe Wissensdatenbank KB-0042) gegen die aktuelle Lösung und gegen pyannote. Prüfen, ob es ohne NVIDIA-GPU lauffähig ist.
- Protokoll: aktuelles lokales Modell über Ollama. Prüfen, ob die Qualität des Protokolls eher an der Transkription oder am Sprachmodell scheitert.

## 4. Marktvergleich: Gibt es das schon kostenlos und lokal?

Mindestens diese Werkzeuge mit denselben Aufnahmen testen und bewerten: aTrain (Uni Graz) und noScribe. Zusätzlich ein Open-Source-Werkzeug für lokale Meeting-Protokolle mit Ollama recherchieren und testen, falls vorhanden. Für jedes festhalten: Transkriptionsqualität, Sprechertrennung, Protokollfunktion, Bedienbarkeit, Lizenz, Datenfluss (wirklich offline?), Pflegezustand.

## 5. Bewertung

- Was kann HEAR, das die kostenlosen Werkzeuge nicht können? Mögliche Kandidaten: Sprecher-Enrollment mit Namen, strukturierte Protokolle (Entscheidungen, Aufgaben, Risiken), Live-Aufnahme, Einbindung in AYE-Systeme (Wissensdatenbank, Task-CLI). Ist dieser Unterschied den Aufwand wert?
- Aufwandsschätzung bis zur Eigennutzungsreife, getrennt nach „mit bestehender Architektur“ und „mit fertigen Bausteinen“.

## 6. Empfehlung in drei Optionen

- **Go:** HEAR weiterbauen, mit konkretem Plan, welche Bausteine getauscht werden.
- **Umbau:** Fertiges Werkzeug (z. B. aTrain oder noScribe) für Transkription und Sprechertrennung nutzen, HEAR schrumpft auf den Protokoll-Baustein, der deren Ausgabe mit lokalem Sprachmodell zu einem strukturierten Protokoll verarbeitet.
- **No-Go:** Einstellen, Code und Erkenntnisse archivieren, Eigenbedarf mit fertigem Werkzeug decken.

## Vorschlag für die Go-Kriterien (Sascha entscheidet final)

- WER auf deutschen Meeting-Aufnahmen höchstens 10 %
- Sprecherzuordnung mindestens 90 % bei 2 bis 6 Sprechern
- Nacharbeit höchstens 15 Minuten pro Stunde Meeting
- Klarer Mehrwert gegenüber aTrain und noScribe, der den Aufwand rechtfertigt

Werden die Qualitätskriterien auch mit den besten verfügbaren Bausteinen nicht erreicht, ist das ein No-Go, unabhängig vom Mehrwert.

## Ausgabe

Ein Bericht unter docs/ (z. B. docs/GO_NOGO_2026-10.md): Bestandstabelle, Messergebnisse als Tabelle (HEAR, Alternativen, Marktwerkzeuge), Bewertung, klare Empfehlung mit Begründung und Aufwand. Bei Go oder Umbau einen ADR-Entwurf beilegen. Stoppen und Sascha fragen, bevor Modelle heruntergeladen werden, die Lizenzbedingungen mit Einschränkungen haben.
