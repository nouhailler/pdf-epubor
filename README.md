<div align="center">

# 📖 PDF-EPUBOR

**Convertisseur PDF → EPUB3 avec interface graphique PyQt6**

*Transforme n'importe quel PDF textuel en EPUB3 lisible sur liseuse,*
*avec détection automatique de la structure et prévisualisation intégrée.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.4%2B-41CD52?logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.23%2B-blue)](https://pymupdf.readthedocs.io/)
[![Licence MIT](https://img.shields.io/badge/Licence-MIT-yellow)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-brightgreen)](https://github.com/nouhailler/pdf-epubor/releases)

</div>

---

## ✨ Fonctionnalités

| Fonctionnalité | Détail |
|---|---|
| 🖼️ **Images CMYK → RGB** | Conversion automatique, indispensable pour les liseuses |
| 🗂️ **Table des matières** | Générée depuis les signets PDF ou la typographie |
| 📐 **Mise en page multi-colonnes** | Gestion des livres à deux colonnes avec sidebar (gauche / droite) |
| 🧹 **Nettoyage automatique** | Suppression des en-têtes et pieds de page répétitifs |
| 📋 **Listes & code** | Listes à puces, blocs `<pre>`, encadrés `<aside>` |
| 📑 **Structure avancée** | Annexes et index extraits en chapitres EPUB distincts |
| 👁️ **Prévisualisation** | Rendu live via QWebEngineView avant export |
| 📦 **Traitement par lots** | Conversion de plusieurs PDF en une seule opération |

---

## 📸 Aperçu

> Interface principale avec panneau de configuration (gauche) et prévisualisation EPUB (droite).

---

## 🛠️ Prérequis

- 🐧 **Linux Debian / Ubuntu** (testé sur Debian 13)
- 🐍 **Python 3.10+**
- Dépendances : `PyQt6` · `PyMuPDF` · `ebooklib` · `Pillow`

---

## 🚀 Installation

**Option 1 — pip (tous systèmes)**

```bash
git clone https://github.com/nouhailler/pdf-epubor.git
cd pdf-epubor
pip install -r requirements.txt --break-system-packages
```

**Option 2 — paquets système Debian + pip**

```bash
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine
pip install PyMuPDF ebooklib Pillow --break-system-packages
```

---

## ▶️ Lancement

```bash
python main.py
```

### Utilisation pas à pas

1. 📂 Cliquer **Ouvrir PDF** (`Ctrl+O`) et sélectionner un fichier
2. ⚙️ Ajuster les paramètres (seuils header/footer, mode sidebar…)
3. 🔍 Cliquer **Analyser** pour prévisualiser le résultat
4. 💾 Cliquer **Exporter EPUB** (`Ctrl+S`) pour sauvegarder le fichier final

> 💡 Appuyez sur **F1** dans l'application pour afficher le guide d'utilisation complet.

---

## ⌨️ Raccourcis clavier

| Raccourci | Action |
|---|---|
| `Ctrl+O` | Ouvrir un PDF |
| `Ctrl+S` | Exporter en EPUB |
| `F1` | Guide d'utilisation |

---

## 🗃️ Structure du projet

```
pdf-epubor/
├── 🚀 main.py                  # Point d'entrée — QApplication
├── 🖥️  ui/
│   ├── main_window.py          # Fenêtre principale (QSplitter)
│   ├── config_panel.py         # Panneau de configuration
│   ├── preview_panel.py        # Prévisualisation QWebEngineView
│   └── log_panel.py            # Journal + barre de progression
├── ⚙️  core/
│   ├── pdf_extractor.py        # Extraction PDF via PyMuPDF
│   ├── cleaner.py              # Nettoyage et structuration
│   └── epub_builder.py         # Construction EPUB3 via ebooklib
└── 📄 requirements.txt
```

---

## 📦 Dépendances

| Package | Version minimale | Rôle |
|---|---|---|
| `PyQt6` | 6.4.0 | Interface graphique |
| `PyQt6-WebEngine` | 6.4.0 | Prévisualisation EPUB |
| `PyMuPDF` | 1.23.0 | Extraction PDF |
| `ebooklib` | 0.18 | Construction EPUB3 |
| `Pillow` | 10.0.0 | Traitement d'images |

---

## 📄 Licence

Distribué sous licence **MIT** — libre d'utilisation, de modification et de distribution.
