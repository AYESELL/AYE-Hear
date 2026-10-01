---
owner: AYEHEAR_LEAD
status: active
updated: 2026-09-25
category: governance
---

# Lessons Learned – AYE Hear

Rollenübergreifende Fehler und ihre Lösung. **Eine Zeile pro Lesson**, Details stehen im verlinkten Bericht. Bei einem Problem zuerst hier nach dem Symptom suchen.

Pflege: Jede Rolle ergänzt eine Zeile, wenn sie ein nicht-triviales Problem gelöst hat, das auch andere Rollen treffen kann. Rollenspezifisches gehört ins eigene Rollen-Gedächtnis. Die Dokumentationsrolle räumt bei Bedarf auf.

| Datum | Bereich | Symptom | Ursache / Lösung | Quelle |
| ----- | ------- | ------- | ---------------- | ------ |
| 2026-09-30 | Tests | `pytest` über alle Tests läuft ohne Ende bzw. bricht mit „Fatal Python error: Aborted“ ab | Modaler `QInputDialog.getItem` (Export-Profil, `window.py` `_do_export_protocol`) blockiert `test_hear_075`/`test_hear_085`. Hänger mit `-o faulthandler_timeout=180` lokalisieren; bis zur Korrektur beide Dateien per `--ignore` ausnehmen und das im Nachweis nennen | HEAR-197, `docs/GO_NOGO_2026-10.md` 1.4 |
