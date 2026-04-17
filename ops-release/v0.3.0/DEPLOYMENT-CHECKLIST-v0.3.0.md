# AYE Hear v0.3.0 — Deployment Checklist

**Target:** Operations engineer installing on a fresh Windows 10/11 machine
**Installer:** `AyeHear-Setup-0.3.0.exe`
**ADR refs:** ADR-0001 (offline-first), ADR-0006 (PostgreSQL), ADR-0009 (encryption at rest)

---

## Pre-Flight Checklist

### 1. Hardware Requirements

- [ ] Windows 10 21H2+ or Windows 11 (64-bit)
- [ ] Minimum 8 GB RAM (16 GB recommended for Whisper inference)
- [ ] Minimum 2 GB free disk space on `C:\` (installer: 341 MB, bundle: ~645 MB uncompressed)
- [ ] Microphone connected and listed in Windows Sound Settings
- [ ] Administrator account available (installer requires elevation)

### 2. Encryption at Rest (ADR-0009)

- [ ] **BitLocker enabled** on the target drive before installation
  - Verify: `manage-bde -status C:` → `Protection Status: Protection On`
  - If BitLocker is not available (e.g., Windows Home): document waiver per HEAR-055 process
    and obtain AYEHEAR_SECURITY sign-off before proceeding
- [ ] Volume encryption method: AES-256 (preferred) or AES-128 (acceptable)

### 3. Network / Connectivity

- [ ] **No internet required** — application is fully offline (ADR-0001)
- [ ] Local loopback (`127.0.0.1`) must not be firewalled
  - PostgreSQL binds to `127.0.0.1:5432` only
  - Ollama (optional LLM) binds to `127.0.0.1:11434` only

### 4. PostgreSQL Pre-check

- [ ] If PostgreSQL 16 is already installed: verify no port conflict on `5432`
  - `netstat -ano | findstr :5432`
  - If occupied: note the PID and check if it is a conflicting service
- [ ] If no PostgreSQL installed: installer will set it up automatically

### 5. Existing Installation

- [ ] If upgrading from v0.2.0 or earlier:
  - Uninstall previous version via "Add or Remove Programs" → "AYE Hear"
  - Verify `C:\AyeHear\app\` is removed before re-running installer
  - Database data in `C:\AyeHear\data\` is preserved by default
  - Back up `C:\AyeHear\data\` before uninstall if in doubt

---

## Installation Steps

1. Right-click `AyeHear-Setup-0.3.0.exe` → **Run as administrator**
2. Windows SmartScreen warning (unsigned): click **"More info"** → **"Run anyway"**
3. Follow the Inno Setup wizard:
   - Accept default install path `C:\AyeHear\app\`
   - Accept PostgreSQL runtime installation if prompted
4. Wait for PostgreSQL setup script to complete (progress shown in console window)
5. Installation completes — click **Finish**

---

## Post-Flight Validation

### Immediate (within 5 minutes)

- [ ] Desktop shortcut "AYE Hear" exists → double-click → application opens
- [ ] Title bar shows "AYE Hear" (no version crash dialog)
- [ ] Log file created: `C:\AyeHear\logs\ayehear.log`
  - Open with Notepad — first line should contain `AYE Hear logging initialised`
  - Confirms logging module is working

### Database Health

- [ ] PostgreSQL service running:
  `Get-Service -Name "postgresql*" | Select-Object Name, Status`
  → Status: `Running`
- [ ] Application connects to database (check log for `DatabaseBootstrap` — no `ERROR` lines)

### ASR (Transcription)

- [ ] In the app: navigate to Meeting Setup, start a test meeting
- [ ] Speak into the microphone — transcript panel should show text within ~5 seconds
- [ ] If "Transkription nicht verfügbar" warning appears: check `ayehear.log` for
  `asr_diagnostic=not_installed` or `model_load_error`
  - Model should be bundled at `C:\AyeHear\app\_internal\models\whisper\base\model.bin`

### Microphone Level Meter

- [ ] MicLevelWidget shows `Active` state (green) when speaking
- [ ] MicLevelWidget shows `No Signal` warning after 3 seconds of silence

---

## Rollback Procedure

If the installation fails or the application does not start:

1. **Uninstall**: "Add or Remove Programs" → "AYE Hear" → Uninstall
2. **Collect logs**: Copy `C:\AyeHear\logs\ayehear.log` before uninstalling
3. **Report**: Open issue against HEAR project with log attachment + Windows version
4. **Rollback**: Re-install v0.2.0 installer if available
   - v0.2.0 artifact: `dist/AyeHear-Setup-0.2.0.exe` (94.6 MB, does not include bundled Whisper)

---

## Contact

- **Operations questions:** AYEHEAR_DEVOPS
- **Security waiver (BitLocker):** AYEHEAR_SECURITY
- **Architecture questions:** AYEHEAR_ARCHITECT
- **Issue tracker:** GitHub → AYESELL/AYE-Hear → Issues
