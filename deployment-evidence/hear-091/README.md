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
