"""Fenêtre principale de PDF-EPUBOR"""

import os
import tempfile
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QToolBar, QFileDialog, QMessageBox,
    QStatusBar, QLabel, QProgressBar
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
