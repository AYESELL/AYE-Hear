---
owner: AYEHEAR_DEVELOPER
status: draft
updated: 2026-04-08
---

# Development Setup Quick Reference

## Prerequisites

- **Windows 10/11** (dev or test machine)
- **Python 3.11+** (download from python.org; add to PATH)
- **Git** (GitHub CLI or Git Bash)
- **Visual Studio Build Tools** (for some dependencies)

---

## Setup (First Time)

```powershell
# 1. Clone repository
git clone https://github.com/AYESELL/AYE-Hear.git
cd AYE-Hear

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify setup
python -c "import ayehear; print('✅ Imports OK')"
```

---

## Running Locally

```powershell
# Activate venv (if not already active)
.\.venv\Scripts\Activate.ps1

# Start dev server/UI
python -m ayehear.app

# Run tests
pytest tests/ -v --cov=src

# Run linting
pylint src/ayehear
ruff check src/

# Run type check
mypy src/ayehear
```

---

## Task-CLI Quick Start

```powershell
# Load Task-CLI
Import-Module G:\Repo\platform-tools\tools\task-cli\task-cli.psd1 -Force

# Get your tasks
Get-Task -Role AYEHEAR_DEVELOPER -Status OPEN

# Start a task
Start-Task -Id HEAR-001 -Force

# Complete a task
Complete-Task -Id HEAR-001
```

---

**Owner:** AYEHEAR_DEVELOPER
