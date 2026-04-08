from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ayehear.app.window import MainWindow
from ayehear.utils.config import load_runtime_config


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AYE Hear")
    app.setOrganizationName("AYESELL")

    config_path = Path("config/default.yaml")
    runtime_config = load_runtime_config(config_path)

    window = MainWindow(runtime_config=runtime_config)
    window.show()
    return app.exec()
