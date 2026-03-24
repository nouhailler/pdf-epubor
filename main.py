#!/usr/bin/env python3
"""PDF-EPUBOR — Convertisseur PDF vers EPUB3"""

import sys
import os

# Supprime l'avertissement Qt "cached device pixel ratio value was stale"
# (bug interne QtWebEngine/HiDPI sous Linux, sans impact fonctionnel)
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PDF-EPUBOR")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PDF-EPUBOR")

    # Style moderne
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
