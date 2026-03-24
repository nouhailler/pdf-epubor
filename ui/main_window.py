"""Fenêtre principale de PDF-EPUBOR"""

import os
import tempfile
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QToolBar, QFileDialog, QMessageBox,
    QStatusBar, QLabel, QProgressBar,
    QDialog, QTextBrowser, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QIcon, QKeySequence

from ui.config_panel import ConfigPanel
from ui.preview_panel import PreviewPanel
from ui.log_panel import LogPanel
from core.pdf_extractor import PDFExtractor
from core.cleaner import Cleaner
from core.epub_builder import EPUBBuilder
from core.exporter import Exporter


_HELP_HTML = """
<html><body style="font-family: sans-serif; font-size: 13px; color: #1a1a1a; margin: 10px;">

<h2 style="color:#2c5282; border-bottom:2px solid #2c5282; padding-bottom:4px;">
  PDF-EPUBOR — Guide d'utilisation
</h2>

<h3 style="color:#2c5282;">1. Ouvrir un PDF</h3>
<p>Cliquez sur <b>📂 Ouvrir PDF</b> (ou <b>Ctrl+O</b>) pour sélectionner un fichier PDF.</p>
<ul>
  <li>Les métadonnées (titre, auteur) sont détectées automatiquement et pré-remplies.</li>
  <li>Un avertissement s'affiche si le PDF est <b>protégé DRM</b> (non convertible)
      ou s'il s'agit d'un <b>scan sans texte</b> (pas d'OCR en V1).</li>
</ul>

<h3 style="color:#2c5282;">2. Paramètres de configuration</h3>
<p>Le panneau gauche expose les réglages de la conversion :</p>
<ul>
  <li><b>Titre / Auteur / Langue</b> — métadonnées inscrites dans l'EPUB.</li>
  <li><b>Seuil en-tête</b> — pourcentage de hauteur de page en dessous duquel
      un bloc est considéré comme un en-tête répétitif (défaut : 8 %).</li>
  <li><b>Seuil pied de page</b> — même principe depuis le bas (défaut : 93 %).</li>
  <li><b>Mode sidebar</b> — pour les livres à deux colonnes :
    <ul>
      <li><i>Ignorer la sidebar</i> — supprime la colonne de droite (recommandé TTS).</li>
      <li><i>Sidebar en annexe</i> — place la colonne de droite en encadré
          <code>&lt;aside&gt;</code> à la fin du chapitre.</li>
    </ul>
  </li>
  <li><b>Seuil colonne</b> — position X (en % de la largeur) séparant les deux
      colonnes (défaut : 55 %).</li>
  <li><b>Mode export</b> — <i>Structuré</i> génère des titres/paragraphes/listes ;
      <i>Texte brut</i> produit un flux continu (optimal pour les synthèses vocales).</li>
  <li><b>Export TXT / HTML</b> — génère en plus un fichier texte brut ou HTML
      dans le même dossier que l'EPUB.</li>
</ul>

<h3 style="color:#2c5282;">3. Analyser et prévisualiser</h3>
<p>Cliquez sur <b>🔍 Analyser</b> pour lancer une conversion vers un fichier
temporaire et afficher le résultat dans le panneau de prévisualisation.</p>
<p>Utilisez ceci pour tester vos réglages avant l'export final.</p>

<h3 style="color:#2c5282;">4. Exporter en EPUB3</h3>
<p>Cliquez sur <b>💾 Exporter EPUB</b> (ou <b>Ctrl+S</b>) pour choisir
l'emplacement de sauvegarde et lancer la conversion complète.</p>
<p>La progression s'affiche dans la barre du journal (bas de fenêtre).
Les étapes sont :</p>
<ol>
  <li>Extraction du texte et des images (PyMuPDF)</li>
  <li>Nettoyage — suppression en-têtes, pieds de page, numéros de page</li>
  <li>Construction de l'EPUB3 — chapitres, CSS, table des matières</li>
</ol>

<h3 style="color:#2c5282;">5. Traitement par lots</h3>
<p>Cliquez sur <b>📋 Traitement par lots</b> pour sélectionner plusieurs PDF
et les convertir en séquence. Chaque EPUB est créé dans le même dossier
que son PDF source, avec le même nom de base.</p>

<h3 style="color:#2c5282;">6. Ce que l'application détecte automatiquement</h3>
<ul>
  <li><b>Table des matières</b> — depuis les signets PDF natifs ; sinon détection
      typographique par taille de police.</li>
  <li><b>Titres de chapitres</b> — blocs ≥ 30 pt = H1, ≥ 14 pt gras = H2.</li>
  <li><b>Listes à puces</b> — polices Puces/Symbol/Wingdings détectées
      et converties en <code>&lt;ul&gt;&lt;li&gt;</code>.</li>
  <li><b>Blocs de code</b> — polices monospace (Courier, Consolas…) encapsulés
      dans <code>&lt;pre&gt;</code>.</li>
  <li><b>Encadrés</b> — labels d'encadrés (À RETENIR, CONSEIL, ATTENTION…)
      convertis en <code>&lt;aside class="note"&gt;</code>.</li>
  <li><b>Images CMYK</b> — converties en RGB automatiquement (indispensable
      pour les livres d'imprimerie sous liseuse).</li>
  <li><b>Annexes et index</b> — détectés et séparés en chapitres EPUB distincts.</li>
</ul>

<h3 style="color:#2c5282;">7. Raccourcis clavier</h3>
<table style="border-collapse:collapse; width:100%;">
  <tr style="background:#edf2f7;">
    <td style="padding:4px 10px;"><b>Ctrl+O</b></td>
    <td style="padding:4px 10px;">Ouvrir un PDF</td>
  </tr>
  <tr>
    <td style="padding:4px 10px;"><b>Ctrl+S</b></td>
    <td style="padding:4px 10px;">Exporter en EPUB</td>
  </tr>
  <tr style="background:#edf2f7;">
    <td style="padding:4px 10px;"><b>F1</b></td>
    <td style="padding:4px 10px;">Afficher ce guide</td>
  </tr>
</table>

<br/>
<p style="color:#718096; font-size:11px;">
  PDF-EPUBOR v1.0.0 — Python / PyQt6 / PyMuPDF / ebooklib
</p>
</body></html>
"""


class HelpDialog(QDialog):
    """Fenêtre d'aide modale avec le guide d'utilisation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aide — Guide d'utilisation")
        self.resize(680, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_HELP_HTML)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)


class ConversionThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(str)  # path to output
    error = pyqtSignal(str)
    stats = pyqtSignal(dict)

    def __init__(self, pdf_path, output_path, config, metadata):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_path = output_path
        self.config = config
        self.metadata = metadata

    def run(self):
        try:
            extractor = PDFExtractor(self.pdf_path, self.log.emit)
            self.log.emit(f"Ouverture de : {os.path.basename(self.pdf_path)}")
            self.progress.emit(5)

            raw_data = extractor.extract(self.config)
            self.progress.emit(40)
            self.log.emit(f"Extraction terminée : {len(raw_data['pages'])} pages")

            cleaner = Cleaner(self.config, self.log.emit)
            cleaned_data = cleaner.clean(raw_data)
            self.progress.emit(65)

            stats = cleaner.get_stats()
            self.stats.emit(stats)
            self.log.emit(f"Nettoyage : {stats['headers_removed']} en-têtes, "
                         f"{stats['footers_removed']} pieds de page, "
                         f"{stats['page_numbers_removed']} numéros supprimés")

            builder = EPUBBuilder(self.config, self.metadata, self.log.emit)
            builder.build(cleaned_data, self.output_path)
            self.progress.emit(90)

            # Exports supplémentaires
            if self.config.get('export_txt') or self.config.get('export_html'):
                exporter = Exporter(self.log.emit)
                base = os.path.splitext(self.output_path)[0]
                if self.config.get('export_txt'):
                    exporter.to_txt(cleaned_data, base + '.txt')
                if self.config.get('export_html'):
                    exporter.to_html(cleaned_data, base + '.html')

            self.progress.emit(100)
            self.finished.emit(self.output_path)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pdf_path = None
        self.raw_data = None
        self.conversion_thread = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("PDF-EPUBOR — Convertisseur PDF vers EPUB3")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self._create_toolbar()
        self._create_menu()

        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Splitter horizontal (gauche + centre)
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.config_panel = ConfigPanel()
        self.preview_panel = PreviewPanel()

        h_splitter.addWidget(self.config_panel)
        h_splitter.addWidget(self.preview_panel)
        h_splitter.setSizes([480, 720])   # ratio 40/60
        h_splitter.setCollapsible(0, False)
        h_splitter.setCollapsible(1, False)
        h_splitter.setStretchFactor(0, 2)
        h_splitter.setStretchFactor(1, 3)

        # Splitter vertical (haut + log)
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(h_splitter)

        self.log_panel = LogPanel()
        v_splitter.addWidget(self.log_panel)
        v_splitter.setSizes([560, 180])
        v_splitter.setCollapsible(1, False)

        main_layout.addWidget(v_splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Prêt")
        self.status_bar.addWidget(self.status_label)

        # Connexions signaux
        self.config_panel.analyze_requested.connect(self._analyze)
        self.config_panel.export_requested.connect(self._export_epub)

    def _create_toolbar(self):
        toolbar = QToolBar("Barre d'outils principale")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet("QToolBar { spacing: 6px; padding: 4px 6px; }"
                              "QToolButton { padding: 4px 10px; }")
        self.addToolBar(toolbar)

        act_open = QAction("📂 Ouvrir PDF", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.setStatusTip("Ouvrir un fichier PDF")
        act_open.triggered.connect(self._open_file)
        toolbar.addAction(act_open)

        toolbar.addSeparator()

        act_analyze = QAction("🔍 Analyser", self)
        act_analyze.setStatusTip("Analyser et prévisualiser")
        act_analyze.triggered.connect(self._analyze)
        toolbar.addAction(act_analyze)

        toolbar.addSeparator()

        act_export = QAction("💾 Exporter EPUB", self)
        act_export.setShortcut(QKeySequence.StandardKey.Save)
        act_export.setStatusTip("Exporter en EPUB3")
        act_export.triggered.connect(self._export_epub)
        toolbar.addAction(act_export)

        toolbar.addSeparator()

        act_batch = QAction("📋 Traitement par lots", self)
        act_batch.setStatusTip("Ajouter plusieurs PDF")
        act_batch.triggered.connect(self._batch_add)
        toolbar.addAction(act_batch)

    def _create_menu(self):
        menu_bar = self.menuBar()

        help_menu = menu_bar.addMenu("&Aide")

        act_guide = QAction("📖 Guide d'utilisation", self)
        act_guide.setShortcut(QKeySequence.StandardKey.HelpContents)  # F1
        act_guide.setStatusTip("Afficher le guide d'utilisation")
        act_guide.triggered.connect(self._show_help)
        help_menu.addAction(act_guide)

        help_menu.addSeparator()

        act_about = QAction("ℹ️ À propos", self)
        act_about.setStatusTip("Informations sur PDF-EPUBOR")
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _show_help(self):
        dlg = HelpDialog(self)
        dlg.exec()

    def _show_about(self):
        QMessageBox.about(
            self,
            "À propos de PDF-EPUBOR",
            "<b>PDF-EPUBOR v1.0.0</b><br/><br/>"
            "Convertisseur PDF → EPUB3 pour Linux Debian.<br/><br/>"
            "<b>Dépendances :</b><br/>"
            "PyQt6 · PyMuPDF · ebooklib · Pillow<br/><br/>"
            "Appuyez sur <b>F1</b> pour ouvrir le guide complet.",
        )

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un fichier PDF",
            os.path.expanduser("~"),
            "Fichiers PDF (*.pdf)"
        )
        if not path:
            return

        self.pdf_path = path
        self.raw_data = None

        # Extraction immédiate pour détection DRM/scan
        try:
            extractor = PDFExtractor(path, self.log_panel.append_log)
            info = extractor.get_info()

            if info.get('is_drm_protected'):
                QMessageBox.critical(self, "PDF protégé",
                    "Ce PDF est protégé par DRM et ne peut pas être converti.\n"
                    "Veuillez utiliser une version non protégée.")
                self.pdf_path = None
                return

            if info.get('is_scan'):
                QMessageBox.warning(self, "PDF scanné",
                    "Ce PDF semble être un scan sans couche texte.\n"
                    "L'OCR n'est pas supporté en V1 — le résultat sera vide ou incomplet.")

            # Pré-remplir métadonnées
            self.config_panel.set_metadata(info.get('metadata', {}))
            self.config_panel.set_file_info(
                os.path.basename(path), info.get('page_count', 0)
            )
            self.log_panel.append_log(
                f"PDF ouvert : {os.path.basename(path)} "
                f"({info.get('page_count', 0)} pages)"
            )
            self.status_label.setText(
                f"{os.path.basename(path)} — {info.get('page_count', 0)} pages"
            )

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le PDF :\n{e}")
            self.pdf_path = None

    def _analyze(self):
        if not self.pdf_path:
            QMessageBox.information(self, "Aucun fichier", "Ouvrez d'abord un fichier PDF.")
            return

        self.log_panel.append_log("--- Analyse en cours ---")
        config = self.config_panel.get_config()
        metadata = self.config_panel.get_metadata()

        tmp = tempfile.NamedTemporaryFile(suffix='.epub', delete=False)
        tmp_path = tmp.name
        tmp.close()

        self.log_panel.set_progress(0)
        self._run_conversion(self.pdf_path, tmp_path, config, metadata,
                             on_finish=self.preview_panel.load_epub)

    def _export_epub(self):
        if not self.pdf_path:
            QMessageBox.information(self, "Aucun fichier", "Ouvrez d'abord un fichier PDF.")
            return

        default_name = os.path.splitext(os.path.basename(self.pdf_path))[0] + '.epub'
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer l'EPUB",
            os.path.join(os.path.expanduser("~"), default_name),
            "Fichiers EPUB (*.epub)"
        )
        if not out_path:
            return

        config = self.config_panel.get_config()
        metadata = self.config_panel.get_metadata()
        self.log_panel.set_progress(0)
        self._run_conversion(self.pdf_path, out_path, config, metadata,
                             on_finish=lambda p: QMessageBox.information(
                                 self, "Export réussi",
                                 f"EPUB exporté avec succès :\n{p}"
                             ))

    def _run_conversion(self, pdf_path, output_path, config, metadata, on_finish=None):
        if self.conversion_thread and self.conversion_thread.isRunning():
            QMessageBox.warning(self, "En cours", "Une conversion est déjà en cours.")
            return

        self.conversion_thread = ConversionThread(pdf_path, output_path, config, metadata)
        self.conversion_thread.progress.connect(self.log_panel.set_progress)
        self.conversion_thread.log.connect(self.log_panel.append_log)
        self.conversion_thread.error.connect(
            lambda e: QMessageBox.critical(self, "Erreur de conversion", e)
        )
        if on_finish:
            self.conversion_thread.finished.connect(on_finish)
        self.conversion_thread.finished.connect(
            lambda _: self.status_label.setText("Conversion terminée")
        )
        self.conversion_thread.start()

    def _batch_add(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Sélectionner des fichiers PDF",
            os.path.expanduser("~"),
            "Fichiers PDF (*.pdf)"
        )
        if not paths:
            return
        self.log_panel.start_batch(paths)
        self._run_batch(paths)

    def _run_batch(self, paths):
        config = self.config_panel.get_config()
        metadata = self.config_panel.get_metadata()
        self.log_panel.append_log(f"Traitement par lots : {len(paths)} fichiers")

        def process_next(index):
            if index >= len(paths):
                self.log_panel.append_log("Traitement par lots terminé.")
                return
            path = paths[index]
            out_path = os.path.splitext(path)[0] + '.epub'
            self.log_panel.append_log(f"[{index+1}/{len(paths)}] {os.path.basename(path)}")

            thread = ConversionThread(path, out_path, config, metadata)
            thread.progress.connect(self.log_panel.set_progress)
            thread.log.connect(self.log_panel.append_log)
            thread.finished.connect(lambda _: process_next(index + 1))
            thread.error.connect(lambda e: (
                self.log_panel.append_log(f"ERREUR [{os.path.basename(path)}]: {e}"),
                process_next(index + 1)
            ))
            thread.start()
            # Keep reference
            if not hasattr(self, '_batch_threads'):
                self._batch_threads = []
            self._batch_threads.append(thread)

        process_next(0)
