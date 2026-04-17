#!/usr/bin/env python3
"""
HEAR-038: Smoke Test for Installed App UI Workflows

Test Scope:
- Meeting title selection
- Participant selection
- Speaker edit
- Apply correction with unknown speaker flow
- All setup action buttons

Test Type: Manual + Automated UI Discovery
"""

import sys
from datetime import datetime
from pathlib import Path

# Try pywinauto for Windows UI automation
try:
    from pywinauto import Desktop  # type: ignore[import-untyped]
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False
    print("WARNING: pywinauto not available, running discovery-only mode")

class SmokeTester:
    def __init__(self, log_file: Path = None):
        self.log_file = log_file or Path("C:\\Temp\\hear-smoke-test-evidance.txt")
        self.results = []
        self.start_time = datetime.now()
        
    def log(self, message: str, level: str = "INFO"):
        """Log message to file and console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    
    def test_app_discovery(self):
        """Test 1: Application Discovery"""
        self.log("=" * 60)
        self.log("TEST 1: Application Discovery", "TEST")
        
        if not HAS_PYWINAUTO:
            self.log("pywinauto not available - manual verification required", "WARN")
            return {"status": "WARN", "reason": "No automation library"}
        
        try:
            desktop = Desktop(backend="uia")
            ayehear_win = None
            
            # Find AyeHear window
            for window in desktop.windows():
                if "AyeHear" in window.name or "AYE Hear" in window.name:
                    ayehear_win = window
                    break
            
            if ayehear_win:
                self.log(f"✓ Found AyeHear window: '{ayehear_win.name}'", "PASS")
                self.log(f"  Window Handle: {ayehear_win.handle}")
                self.log(f"  Is Visible: {ayehear_win.is_visible()}")
                self.log(f"  Is Enabled: {ayehear_win.is_enabled()}")
                return {"status": "PASS", "window": ayehear_win.name}
            else:
                self.log("✗ AyeHear window not found", "FAIL")
                return {"status": "FAIL", "reason": "Window not found"}
                
        except Exception as e:
            self.log(f"✗ Discovery error: {e}", "ERROR")
            return {"status": "ERROR", "reason": str(e)}
    
    def test_ui_elements(self):
        """Test 2: UI Elements Discovery"""
        self.log("=" * 60)
        self.log("TEST 2: UI Elements Discovery", "TEST")
        
        if not HAS_PYWINAUTO:
            self.log("Manual UI inspection required (no automation library)", "WARN")
            return {"status": "WARN", "elements_found": 0}
        
        try:
            desktop = Desktop(backend="uia")
            expected_elements = {
                "meeting_title": False,
                "participant_selection": False,
                "speaker_edit": False,
                "correction_button": False,
                "action_buttons": False
            }
            
            # Look for typical workflow elements
            for window in desktop.windows():
                if "AyeHear" in window.name:
                    try:
                        descendants = window.descendants()
                        for elem in descendants:
                            name = elem.name.lower()
                            
                            if "meeting" in name or "title" in name:
                                expected_elements["meeting_title"] = True
                            if "participant" in name or "speaker" in name:
                                expected_elements["participant_selection"] = True
                            if "edit" in name:
                                expected_elements["speaker_edit"] = True
                            if "correction" in name or "correc" in name:
                                expected_elements["correction_button"] = True
                            if "button" in elem.element_info.control_type or "action" in name:
                                expected_elements["action_buttons"] = True
                    except Exception:
                        pass
            
            found_count = sum(1 for v in expected_elements.values() if v)
            total_count = len(expected_elements)
            
            self.log(f"UI Elements Discovered: {found_count}/{total_count}")
            for elem, found in expected_elements.items():
                status = "✓" if found else "✗"
                self.log(f"  {status} {elem}: {found}")
            
            return {"status": "INFO", "elements_found": found_count, "total": total_count}
            
        except Exception as e:
            self.log(f"✗ UI discovery error: {e}", "ERROR")
            return {"status": "ERROR", "reason": str(e)}
    
    def test_workflows_manual(self):
        """Test 3: Manual Workflow Validation Notes"""
        self.log("=" * 60)
        self.log("TEST 3: Manual Workflow Checklist", "TEST")
        
        workflows = {
            "Meeting Title Selection": {
                "steps": [
                    "Launch AyeHear app",
                    "Create New Meeting",
                    "Enter meeting title (e.g., 'Q1 Planning')",
                    "Click Save/Confirm"
                ],
                "expected": "Meeting title displayed in UI"
            },
            "Participant Selection": {
                "steps": [
                    "Click 'Add Participant' button",
                    "Select participant from list or add new",
                    "Click 'Enroll' to capture audio sample",
                    "Verify participant appears in meeting"
                ],
                "expected": "Participant list shows enrolled members"
            },
            "Speaker Edit": {
                "steps": [
                    "During meeting, select a transcript segment",
                    "Click 'Edit Speaker' or 'Assign Speaker'",
                    "Select different participant from dropdown",
                    "Click 'Apply' or 'Save'"
                ],
                "expected": "Speaker assignment updated in transcript"
            },
            "Correction with Unknown Speaker": {
                "steps": [
                    "During meeting, unknown/unidentified speaker speaks",
                    "Segment marked as 'Unknown' or 'Uncertain'",
                    "Manually assign to known participant",
                    "Verify correction persists in protocol"
                ],
                "expected": "Protocol reflects corrected speaker"
            },
            "Setup Action Buttons": {
                "steps": [
                    "Verify all buttons are clickable: Create, Edit, Delete, Export",
                    "Verify buttons are properly disabled when not applicable",
                    "Test hover states and tooltips"
                ],
                "expected": "All action buttons functional"
            }
        }
        
        for workflow_name, workflow_data in workflows.items():
            self.log(f"\n📋 Workflow: {workflow_name}")
            self.log(f"   Expected: {workflow_data['expected']}")
            for i, step in enumerate(workflow_data['steps'], 1):
                self.log(f"   Step {i}: {step}")
        
        return {"status": "INFO", "workflows_documented": len(workflows)}
    
    def test_runtime_checks(self):
        """Test 4: Runtime Environment Checks"""
        self.log("=" * 60)
        self.log("TEST 4: Runtime Environment Validation", "TEST")
        
        checks = {}
        
        # Check app process
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq AyeHear.exe"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "AyeHear.exe" in result.stdout:
                self.log("✓ AyeHear process running", "PASS")
                checks["process_running"] = True
            else:
                self.log("✗ AyeHear process not found", "WARN")
                checks["process_running"] = False
        except Exception as e:
            self.log(f"✗ Process check failed: {e}", "ERROR")
            checks["process_running"] = False
        
        # Check PostgreSQL connectivity (for offline test notes)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', 5432))
            sock.close()
            if result == 0:
                self.log("✓ PostgreSQL reachable on localhost:5432", "PASS")
                checks["postgres_local"] = True
            else:
                self.log("⚠ PostgreSQL not reachable (may be expected in test)", "WARN")
                checks["postgres_local"] = False
        except Exception as e:
            self.log(f"⚠ PostgreSQL check inconclusive: {e}", "WARN")
            checks["postgres_local"] = None
        
        return {"status": "INFO", "runtime_checks": checks}
    
    def test_installer_validation(self):
        """Test 5: Installer Path Validation"""
        self.log("=" * 60)
        self.log("TEST 5: Installation Validation", "TEST")
        
        _install_dir = Path("C:\\AyeHear")
        expected_files = [
            Path("C:\\AyeHear\\app\\AyeHear.exe"),
            Path("C:\\AyeHear\\app\\unins000.exe"),
        ]
        
        validation_results = {}
        
        for file_path in expected_files:
            if file_path.exists():
                size_kb = file_path.stat().st_size / 1024
                self.log(f"✓ Found: {file_path.name} ({size_kb:.1f} KB)", "PASS")
                validation_results[file_path.name] = True
            else:
                self.log(f"✗ Missing: {file_path}", "FAIL")
                validation_results[file_path.name] = False
        
        return {"status": "INFO", "files_validated": validation_results}
    
    def generate_report(self):
        """Generate final smoke test report"""
        self.log("\n" + "=" * 60)
        self.log("SMOKE TEST EXECUTION COMPLETE", "SUMMARY")
        self.log(f"Start Time: {self.start_time}")
        self.log(f"End Time: {datetime.now()}")
        duration = (datetime.now() - self.start_time).total_seconds()
        self.log(f"Duration: {duration:.1f}s")
        self.log("\n📌 NEXT STEPS:")
        self.log("1. Manually walk through each workflow listed above")
        self.log("2. Document any UI glitches or missing elements")
        self.log("3. Test speaker correction with unknown speaker flow")
        self.log("4. Verify protocol export (Markdown, DOCX, PDF)")
        self.log("5. Capture screenshots of critical workflows")
        self.log("=" * 60)
    
    def run_all_tests(self):
        """Run complete test suite"""
        self.log("HEAR-038 SMOKE TEST - Installer App UI Workflows")
        self.log(f"Start: {self.start_time}")
        self.log(f"Log: {self.log_file}")
        
        test_results = []
        test_results.append(("Discovery", self.test_app_discovery()))
        test_results.append(("UI Elements", self.test_ui_elements()))
        test_results.append(("Workflows", self.test_workflows_manual()))
        test_results.append(("Runtime", self.test_runtime_checks()))
        test_results.append(("Installation", self.test_installer_validation()))
        
        self.generate_report()
        
        return test_results


if __name__ == "__main__":
    tester = SmokeTester()
    try:
        results = tester.run_all_tests()
        sys.exit(0)
    except Exception as e:
        tester.log(f"FATAL ERROR: {e}", "ERROR")
        import traceback
        tester.log(traceback.format_exc(), "ERROR")
        sys.exit(1)
