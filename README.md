# PDF-EPUBOR

Convertisseur PDF → EPUB3 pour Linux Debian, avec interface graphique PyQt6.

Transforme n'importe quel PDF textuel en EPUB3 lisible sur liseuse ou application
de lecture, avec détection automatique de la structure (chapitres, titres, listes,
encadrés, index, annexes) et prévisualisation intégrée.

---

## Fonctionnalités

- Extraction texte et images via PyMuPDF (fitz)
- Conversion automatique des images CMYK → RGB (visibilité sur toutes liseuses)
- Détection et gestion de la mise en page multi-colonnes (sidebar Eyrolles)
- Suppression automatique des en-têtes et pieds de page répétitifs
- Listes à puces, blocs de code monospace, encadrés `<aside>`
- Annexes et index extraits en chapitres EPUB distincts
- Table des matières EPUB3 générée depuis les signets PDF ou la typographie
- Interface PyQt6 avec prévisualisation QWebEngineView

---

## Prérequis

- Python 3.10+
- Linux Debian / Ubuntu (testé sur Debian 13)
- Dépendances Python : `PyQt6`, `PyMuPDF`, `ebooklib`, `Pillow`

---

## Installation

```bash
pip install -r requirements.txt --break-system-packages
```

Ou via les paquets système Debian pour PyQt6 :

```bash
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine
pip install PyMuPDF ebooklib Pillow --break-system-packages
```

---

## Usage

```bash
python main.py
```

1. Cliquer **Ouvrir PDF** et sélectionner un fichier
2. Ajuster les paramètres (seuils header/footer, mode sidebar…)
3. Cliquer **Convertir** — l'EPUB est généré dans le même dossier
4. La prévisualisation s'affiche automatiquement dans le panneau droit

---

## Structure du projet

```
pdf-epubor/
├── main.py                  # Point d'entrée — QApplication
├── ui/
│   ├── main_window.py       # Fenêtre principale (QSplitter)
│   ├── config_panel.py      # Panneau de configuration
│   ├── preview_panel.py     # Prévisualisation QWebEngineView
│   └── log_panel.py         # Journal + barre de progression
├── core/
│   ├── pdf_extractor.py     # Extraction PDF via PyMuPDF
│   ├── cleaner.py           # Nettoyage et structuration
│   └── epub_builder.py      # Construction EPUB3 via ebooklib
└── requirements.txt
```

---

## Licence

MIT
