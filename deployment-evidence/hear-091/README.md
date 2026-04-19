# HEAR-091 Installed E2E Evidence Bundle

## Purpose
Collect all artifacts from one fresh non-default packaged install run to close HEAR-091 AC1/AC2/AC5 gaps.

## Installer Baseline
- Installer: AyeHear-Setup-0.4.0.exe
- Expected SHA256: 8AFED4E807EC82CC33EB48B302150D8700C24E599154826C032DEAC6F91CA48D

## Required Artifacts
1. screenshot-install-path.png
- Installer wizard showing a non-default install path (example: D:\AyeHearCustom\app)

2. screenshot-install-success.png
- Successful completion page

3. screenshot-readiness-startup.png
- App startup with full System Readiness box visible

4. screenshot-readiness-after-start.png
- Readiness after meeting start attempt

5. screenshot-enrollment.png
- Enrollment flow visible with status

6. screenshot-transcription-attribution.png
- Running transcription + attribution indicators

7. screenshot-protocol-draft.png
- Protocol draft panel (not empty/static)

8. screenshot-export-success.png
- Export action completed + target path visible

9. runtime-log-excerpts.txt
- Relevant runtime log snippets with timestamps for bootstrap, readiness states, export

10. exported-artifacts-list.txt
- Paths and filenames of generated exports from installed run

## Notes Template
- Install path used:
- Runtime root observed:
- Aggregate readiness state at startup:
- Aggregate readiness state during meeting:
- Blocking/degraded reasons shown:
- Final QA decision proposal (GO or NO-GO):

---

## HEAR-111 Evidence Index (2026-04-19)

Evidence folder: `deployment-evidence/hear-091/2026-04-19-hear-111/`

1. `01-app-running-20260419-141809.png`
- Installed app running from installed runtime.

2. `02-runtime-log-tail.txt`
- Runtime log tail containing installed-flow events and bootstrap traces.

3. `03-netstat-ayehear.txt`
- Loopback-only runtime DB connection evidence.

4. `04-install-root-tree.txt`
- Install-root tree for installed package under `D:\AYE\AyeHear`.

5. `05-export-list.txt`
- Export artifacts list (protocol + transcript outputs).

6. `06-post-evidence-20260419-141826.png`
- Post-run screenshot after evidence capture.

7. `07-install-root-explorer.png`
- Explorer view of install root.

8. `08-runtime-folder-explorer.png`
- Explorer view of runtime folder (includes `pg.dsn`).

9. `09-logs-folder-explorer.png`
- Explorer view of logs folder.

10. `10-exports-folder-explorer.png`
- Explorer view of exports folder with generated artifacts.

11. `11-runtime-log-current-run.txt`
- Filtered current-run startup log excerpt (`2026-04-19 14:17*`).

### HEAR-111 AC Mapping Result
- AC1: PASS
- AC2: PASS
- AC3: PASS
- AC4: PASS
- AC5: PASS

### QA Decision for HEAR-111
- Task-level decision: GO (HEAR-111 scope complete)
- Product-complete claim: still governed by release reconciliation task (HEAR-112)
