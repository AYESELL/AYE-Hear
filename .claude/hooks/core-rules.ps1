<#
    SessionStart-Hook (AYE Hear), Matcher compact|clear (PLAT-3532, M4a): spielt nach /compact und /clear
    einen kurzen Kernblock neu ein. Reine Textausgabe: kein Task-CLI-Aufruf, kein Dateizugriff, keine Netzabfrage.
    Fehler: Der Aufruf in settings.json faengt einen Skriptfehler ab (Exit 1, Hinweis auf stderr): die Sitzung
    wird nicht blockiert, der Ausfall ist aber sichtbar. Kernblock hoechstens 150 Woerter (Test).
#>
$ErrorActionPreference = 'Stop'
Write-Output @'
Kernregeln neu eingespielt nach Kontextverlust (Marker: KIT-KERNREGELN-V1).
1. Rolle: Arbeite in der zugewiesenen Rolle (Hauptsession: ayehear-lead), keine fremde Rolle uebernehmen.
2. Phasenmodell: Konzept, Code, Haertung. Nur die Phase des Auftrags bearbeiten.
3. Review vor Abschluss: Eine andere Rolle prueft, bevor ein Task schliesst. Nie den eigenen Task abschliessen.
4. Einfache Befehle: ein Befehl pro Schritt, keine Ketten, keine Pipes.
5. Die Task-CLI ist fuehrend fuer Status, Notes und Uebergaben. Ablauf: Skill ayehear-task-execution.
6. Scope halten: Akzeptanzkriterien und Nicht-Ziele einhalten. Neues nur als Vorschlag im Bericht.
7. Overrides (SKIP_*, --no-verify, -Force, -SkipReview) gibt nur Sascha frei.
'@
exit 0
