"""Panneau de prévisualisation central"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTreeWidget, QTreeWidgetItem, QSplitter,
    QGroupBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QFont

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None


_PLACEHOLDER_HTML = """
<html><body style="margin:0;background:#f5f5f5;">
<div style="display:flex;align-items:center;justify-content:center;
            height:100vh;font-family:sans-serif;color:#888;">
  <div style="text-align:center;">
    <div style="font-size:48px;margin-bottom:16px;">📄</div>
    <p style="font-size:16px;margin:0;">Ouvrez un PDF puis cliquez sur<br>
    <strong>Analyser</strong> pour prévisualiser le contenu.</p>
  </div>
</div></body></html>
"""


class PreviewPanel(QWidget):
    chapter_selected = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._chapters = []
        self._zoom_factor = 1.0
        self._current_epub_path = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Barre de contrôles ──────────────────────────────────────────
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        lbl = QLabel("Prévisualisation EPUB")
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        lbl.setFont(f)
        ctrl_bar.addWidget(lbl)
        ctrl_bar.addStretch()

        btn_zoom_out = QPushButton("  −  ")
        btn_zoom_out.setToolTip("Zoom arrière")
        btn_zoom_out.setFixedHeight(28)
        btn_zoom_out.clicked.connect(self._zoom_out)

        btn_zoom_in = QPushButton("  +  ")
        btn_zoom_in.setToolTip("Zoom avant")
        btn_zoom_in.setFixedHeight(28)
        btn_zoom_in.clicked.connect(self._zoom_in)

        btn_refresh = QPushButton("↻  Rafraîchir")
        btn_refresh.setFixedHeight(28)
        btn_refresh.clicked.connect(self._refresh)

        ctrl_bar.addWidget(QLabel("Zoom :"))
        ctrl_bar.addWidget(btn_zoom_out)
        ctrl_bar.addWidget(btn_zoom_in)
        ctrl_bar.addSpacing(8)
        ctrl_bar.addWidget(btn_refresh)
        root.addLayout(ctrl_bar)

        # ── Splitter : TOC | Vue web ────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # TOC dans un QGroupBox
        toc_box = QGroupBox("Table des matières")
        toc_box.setMinimumWidth(160)
        toc_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        toc_vl = QVBoxLayout(toc_box)
        toc_vl.setContentsMargins(6, 12, 6, 6)
        toc_vl.setSpacing(0)

        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderHidden(True)
        self.toc_tree.setIndentation(12)
        self.toc_tree.itemClicked.connect(self._on_toc_clicked)
        toc_vl.addWidget(self.toc_tree)

        splitter.addWidget(toc_box)

        # Vue web dans un QGroupBox
        view_box = QGroupBox("Contenu")
        view_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        view_vl = QVBoxLayout(view_box)
        view_vl.setContentsMargins(4, 12, 4, 4)
        view_vl.setSpacing(0)

        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setHtml(_PLACEHOLDER_HTML)
        else:
            from PyQt6.QtWidgets import QTextEdit
            self.web_view = QTextEdit()
            self.web_view.setReadOnly(True)
            self.web_view.setHtml(
                "<p style='color:#888;margin:40px;font-family:sans-serif;'>"
                "WebEngine non disponible — affichage texte uniquement.</p>"
            )

        view_vl.addWidget(self.web_view)
        splitter.addWidget(view_box)

        # Ratio TOC 25% / Vue 75%
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([220, 660])

        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------ #
    #  Chargement EPUB                                                     #
    # ------------------------------------------------------------------ #

    def load_epub(self, epub_path: str):
        """Charge un EPUB et affiche le premier chapitre."""
        import zipfile
        self._current_epub_path = epub_path
        self._chapters = []
        self.toc_tree.clear()

        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                names = zf.namelist()
                html_files = sorted(
                    n for n in names
                    if n.endswith(('.html', '.xhtml')) and 'nav' not in n.lower()
                )
                self._chapters = html_files

                for i, name in enumerate(html_files):
                    title = os.path.splitext(os.path.basename(name))[0]
                    # Rendre le titre plus lisible : "chapter_001" → "Chapitre 1"
                    if title.startswith('chapter_'):
                        try:
                            n = int(title.split('_')[1])
                            title = f"Chapitre {n}"
                        except (IndexError, ValueError):
                            pass
                    item = QTreeWidgetItem([title])
                    item.setData(0, Qt.ItemDataRole.UserRole, i)
                    self.toc_tree.addTopLevelItem(item)

                if html_files:
                    self.toc_tree.setCurrentItem(self.toc_tree.topLevelItem(0))
                    self._show_chapter(epub_path, html_files[0], zf)

        except Exception as e:
            msg = f"<p style='color:red;font-family:sans-serif;margin:20px;'>Erreur : {e}</p>"
            if HAS_WEBENGINE:
                self.web_view.setHtml(msg)
            else:
                self.web_view.setHtml(msg)

    def _show_chapter(self, epub_path, chapter_name, zf=None):
        import zipfile
        try:
            if zf is None:
                with zipfile.ZipFile(epub_path, 'r') as z:
                    content = z.read(chapter_name).decode('utf-8', errors='replace')
            else:
                content = zf.read(chapter_name).decode('utf-8', errors='replace')

            if HAS_WEBENGINE:
                self.web_view.setHtml(content, QUrl.fromLocalFile(epub_path))
            else:
                self.web_view.setHtml(content)
        except Exception:
            pass

    def _on_toc_clicked(self, item, _column):
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None and self._current_epub_path and idx < len(self._chapters):
            self._show_chapter(self._current_epub_path, self._chapters[idx])

    # ------------------------------------------------------------------ #
    #  Zoom & Rafraîchir                                                   #
    # ------------------------------------------------------------------ #

    def _zoom_in(self):
        if HAS_WEBENGINE:
            self._zoom_factor = min(self._zoom_factor + 0.15, 3.0)
            self.web_view.setZoomFactor(self._zoom_factor)

    def _zoom_out(self):
        if HAS_WEBENGINE:
            self._zoom_factor = max(self._zoom_factor - 0.15, 0.4)
            self.web_view.setZoomFactor(self._zoom_factor)

    def _refresh(self):
        if self._current_epub_path:
            self.load_epub(self._current_epub_path)
