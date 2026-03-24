"""Panneau de configuration gauche"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox,
    QLabel, QLineEdit, QComboBox, QSpinBox,
    QRadioButton, QButtonGroup, QFormLayout, QPushButton,
    QHBoxLayout, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont


class ConfigPanel(QWidget):
    analyze_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(380)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area pour gérer les petites fenêtres
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(10)

        self._build_file_group()
        self._build_clean_group()
        self._build_thresholds_group()
        self._build_mode_group()
        self._build_extra_group()
        self._build_metadata_group()
        self._build_buttons()
        self._layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------ #
    #  Constructeurs de sections                                           #
    # ------------------------------------------------------------------ #

    def _build_file_group(self):
        grp = QGroupBox("Fichier source")
        fl = QFormLayout(grp)
        fl.setContentsMargins(12, 16, 12, 12)
        fl.setVerticalSpacing(8)
        fl.setHorizontalSpacing(12)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.lbl_filename = QLabel("—")
        self.lbl_filename.setWordWrap(True)
        bold = QFont()
        bold.setBold(True)
        self.lbl_filename.setFont(bold)

        self.lbl_pages = QLabel("—")
        fl.addRow("Fichier :", self.lbl_filename)
        fl.addRow("Pages :", self.lbl_pages)
        self._layout.addWidget(grp)

    def _build_clean_group(self):
        grp = QGroupBox("Nettoyage")
        vl = QVBoxLayout(grp)
        vl.setContentsMargins(12, 16, 12, 12)
        vl.setSpacing(9)

        self.chk_images       = QCheckBox("Conserver les images")
        self.chk_toc          = QCheckBox("Extraire la table des matières")
        self.chk_footers      = QCheckBox("Supprimer les pieds de page")
        self.chk_headers      = QCheckBox("Supprimer les en-têtes répétés")
        self.chk_page_numbers = QCheckBox("Supprimer les numéros de page")
        self.chk_hyphenation  = QCheckBox("Corriger les césures")

        for chk in [self.chk_images, self.chk_toc, self.chk_footers,
                    self.chk_headers, self.chk_page_numbers, self.chk_hyphenation]:
            chk.setChecked(True)
            vl.addWidget(chk)

        self._layout.addWidget(grp)

    def _build_thresholds_group(self):
        grp = QGroupBox("Réglages fins")
        fl = QFormLayout(grp)
        fl.setContentsMargins(12, 16, 12, 12)
        fl.setVerticalSpacing(10)
        fl.setHorizontalSpacing(12)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_footer_thresh = QSpinBox()
        self.spin_footer_thresh.setRange(50, 99)
        self.spin_footer_thresh.setValue(90)
        self.spin_footer_thresh.setSuffix(" %")
        self.spin_footer_thresh.setToolTip("Seuil Y au-delà duquel un texte est considéré pied de page")
        self.spin_footer_thresh.setMinimumWidth(90)

        self.spin_header_thresh = QSpinBox()
        self.spin_header_thresh.setRange(1, 50)
        self.spin_header_thresh.setValue(10)
        self.spin_header_thresh.setSuffix(" %")
        self.spin_header_thresh.setToolTip("Seuil Y en-dessous duquel un texte est considéré en-tête")
        self.spin_header_thresh.setMinimumWidth(90)

        self.spin_min_image = QSpinBox()
        self.spin_min_image.setRange(10, 500)
        self.spin_min_image.setValue(100)
        self.spin_min_image.setSuffix(" px")
        self.spin_min_image.setMinimumWidth(90)
        self.spin_min_image.setToolTip(
            "Taille minimale des deux dimensions (largeur ET hauteur).\n"
            "Les filets décoratifs (ratio > 10) et les données < 1 Ko sont\n"
            "toujours exclus, quelle que soit cette valeur."
        )

        self.spin_repeat_min = QSpinBox()
        self.spin_repeat_min.setRange(2, 20)
        self.spin_repeat_min.setValue(3)
        self.spin_repeat_min.setSuffix(" pages")
        self.spin_repeat_min.setMinimumWidth(90)

        self.spin_prelim_pages = QSpinBox()
        self.spin_prelim_pages.setRange(0, 20)
        self.spin_prelim_pages.setValue(5)
        self.spin_prelim_pages.setSuffix(" pages")
        self.spin_prelim_pages.setMinimumWidth(90)
        self.spin_prelim_pages.setToolTip(
            "Les N premières pages (couverture, faux-titre, bibliographie…)\n"
            "sont regroupées en un seul chapitre «Couverture» et ne sont\n"
            "pas soumises au découpage en chapitres."
        )

        fl.addRow("Seuil bas de page :", self.spin_footer_thresh)
        fl.addRow("Seuil haut de page :", self.spin_header_thresh)
        fl.addRow("Taille min. image :", self.spin_min_image)
        fl.addRow("Répétition min. :", self.spin_repeat_min)
        fl.addRow("Pages liminaires :", self.spin_prelim_pages)

        # ── Séparateur colonnes ───────────────────────────────────────
        from PyQt6.QtWidgets import QFrame
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        fl.addRow(sep)

        self.combo_col_mode = QComboBox()
        self.combo_col_mode.addItems(["Ignorer la sidebar", "Sidebar en annexe"])
        self.combo_col_mode.setToolTip(
            "Ignorer la sidebar : seule la colonne principale est conservée.\n"
            "Sidebar en annexe : la sidebar est ajoutée à la fin du chapitre."
        )
        self.combo_col_mode.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.spin_col_split = QSpinBox()
        self.spin_col_split.setRange(30, 70)
        self.spin_col_split.setValue(55)
        self.spin_col_split.setSuffix(" %")
        self.spin_col_split.setMinimumWidth(90)
        self.spin_col_split.setToolTip(
            "Seuil X séparant colonne principale et sidebar.\n"
            "Blocs avec x0 > seuil × largeur page → considérés sidebar."
        )

        fl.addRow("Pages multi-colonnes :", self.combo_col_mode)
        fl.addRow("Seuil de colonne :", self.spin_col_split)

        self._layout.addWidget(grp)

    def _build_mode_group(self):
        grp = QGroupBox("Mode d'export")
        vl = QVBoxLayout(grp)
        vl.setContentsMargins(12, 16, 12, 12)
        vl.setSpacing(9)

        self.radio_structured = QRadioButton("Structuré — HTML avec balises (rendu visuel)")
        self.radio_structured.setChecked(True)
        self.radio_plain = QRadioButton("Texte brut — flux continu (optimal TTS)")

        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.radio_structured, 0)
        self.mode_group.addButton(self.radio_plain, 1)

        vl.addWidget(self.radio_structured)
        vl.addWidget(self.radio_plain)
        self._layout.addWidget(grp)

    def _build_extra_group(self):
        grp = QGroupBox("Exports supplémentaires")
        vl = QVBoxLayout(grp)
        vl.setContentsMargins(12, 16, 12, 12)
        vl.setSpacing(9)

        self.chk_export_txt  = QCheckBox("Exporter aussi en .txt")
        self.chk_export_html = QCheckBox("Exporter aussi en .html")
        vl.addWidget(self.chk_export_txt)
        vl.addWidget(self.chk_export_html)
        self._layout.addWidget(grp)

    def _build_metadata_group(self):
        grp = QGroupBox("Métadonnées")
        fl = QFormLayout(grp)
        fl.setContentsMargins(12, 16, 12, 12)
        fl.setVerticalSpacing(10)
        fl.setHorizontalSpacing(12)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("Titre du document")
        self.edit_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.edit_author = QLineEdit()
        self.edit_author.setPlaceholderText("Auteur")
        self.edit_author.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.combo_lang = QComboBox()
        self.combo_lang.addItems([
            "fr-FR", "en-US", "en-GB", "de-DE", "es-ES", "it-IT",
            "pt-BR", "pt-PT", "nl-NL", "pl-PL", "ru-RU", "ja-JP", "zh-CN"
        ])
        self.combo_lang.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.edit_date = QLineEdit()
        self.edit_date.setPlaceholderText("YYYY-MM-DD")
        self.edit_date.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        fl.addRow("Titre :", self.edit_title)
        fl.addRow("Auteur :", self.edit_author)
        fl.addRow("Langue :", self.combo_lang)
        fl.addRow("Date :", self.edit_date)
        self._layout.addWidget(grp)

    def _build_buttons(self):
        hl = QHBoxLayout()
        hl.setSpacing(8)

        btn_analyze = QPushButton("🔍  Analyser")
        btn_analyze.setMinimumHeight(36)
        btn_analyze.clicked.connect(self.analyze_requested.emit)

        btn_export = QPushButton("💾  Exporter EPUB")
        btn_export.setMinimumHeight(36)
        btn_export.clicked.connect(self.export_requested.emit)

        hl.addWidget(btn_analyze)
        hl.addWidget(btn_export)
        self._layout.addLayout(hl)

    # ------------------------------------------------------------------ #
    #  API publique                                                        #
    # ------------------------------------------------------------------ #

    def set_file_info(self, filename: str, page_count: int):
        self.lbl_filename.setText(filename)
        self.lbl_pages.setText(str(page_count))

    def set_metadata(self, metadata: dict):
        self.edit_title.setText(metadata.get('title', ''))
        self.edit_author.setText(metadata.get('author', ''))
        lang = metadata.get('language', 'fr-FR')
        idx = self.combo_lang.findText(lang)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        self.edit_date.setText(metadata.get('date', ''))

    def get_config(self) -> dict:
        return {
            'keep_images':        self.chk_images.isChecked(),
            'extract_toc':        self.chk_toc.isChecked(),
            'remove_footers':     self.chk_footers.isChecked(),
            'remove_headers':     self.chk_headers.isChecked(),
            'remove_page_numbers':self.chk_page_numbers.isChecked(),
            'fix_hyphenation':    self.chk_hyphenation.isChecked(),
            'footer_threshold':   self.spin_footer_thresh.value() / 100.0,
            'header_threshold':   self.spin_header_thresh.value() / 100.0,
            'min_image_size':     self.spin_min_image.value(),
            'repeat_min':         self.spin_repeat_min.value(),
            'export_mode':        'plain' if self.radio_plain.isChecked() else 'structured',
            'export_txt':         self.chk_export_txt.isChecked(),
            'export_html':        self.chk_export_html.isChecked(),
            'column_mode':        'ignore_sidebar' if self.combo_col_mode.currentIndex() == 0
                                  else 'sidebar_annex',
            'col_split':          self.spin_col_split.value() / 100.0,
            'prelim_pages':       self.spin_prelim_pages.value(),
        }

    def get_metadata(self) -> dict:
        return {
            'title':    self.edit_title.text(),
            'author':   self.edit_author.text(),
            'language': self.combo_lang.currentText(),
            'date':     self.edit_date.text(),
        }
