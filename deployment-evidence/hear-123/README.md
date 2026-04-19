# HEAR-123 Installed E2E Evidence Bundle

## Task
HEAR-123 - Installed-package E2E evidence for next quality-first candidate (`0.5.4`).

## Evidence Folder
- `deployment-evidence/hear-123/2026-04-19-hear-123/`

## Artifact Index
1. `01-install-root-app-tree.txt`
- Installed app root tree under `D:\AYE\AyeHear\app`.

2. `02-installed-version.txt`
- Installed runtime version (`0.5.4`).

3. `03-export-list.txt`
- Exported protocol/transcript artifact list from installed runtime.

4. `04-runtime-log-tail.txt`
- Runtime log tail including persistence/protocol errors from the run.

5. `05-runtime-log-current-run.txt`
- Timestamp-filtered runtime log excerpt (`2026-04-19 16:4*`).

6. `06-netstat-local-services.txt`
- Local-loopback network evidence for DB (`127.0.0.1:5433`) and model host (`127.0.0.1:11434`).

7. `07-trace-store.json`
- Persisted traceability store for the meeting run.

8. `08-review-store.json`
- Persisted review queue store for the meeting run.

9. `09-ayehear-exe-sha256.txt`
- SHA256 of installed `AyeHear.exe`.

10. `10-installer-sha256.txt`
- SHA256 of `dist/AyeHear-Setup-0.5.4.exe`.

## QA Outcome
- Task-level gate: NO-GO (see [docs/HEAR-123-qa-evidence.md](docs/HEAR-123-qa-evidence.md))
- Primary blocker: installed-runtime persistence instability (`meeting_id` FK violations during transcription segment persistence).