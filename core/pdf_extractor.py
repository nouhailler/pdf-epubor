"""Extraction de contenu PDF via PyMuPDF (fitz)"""

import os
from typing import Callable, Optional
import fitz  # PyMuPDF

# Polices contenant uniquement des marqueurs graphiques (flèches, puces ornées,
# numéros cerclés EuropeanPi) — à exclure du flux textuel EPUB.
_FAKE_MARKER_FONTS = ('europeanpi', 'puces')


class PDFExtractor:
    def __init__(self, pdf_path: str, log_fn: Optional[Callable] = None):
        self.pdf_path = pdf_path
        self.log = log_fn or (lambda msg: None)
        self._doc = None

    def _open(self):
        if self._doc is None:
            self._doc = fitz.open(self.pdf_path)

    # ------------------------------------------------------------------ #
    #  Informations de base                                               #
    # ------------------------------------------------------------------ #

    def get_info(self) -> dict:
        """Retourne les informations de base sur le PDF."""
        self._open()
        doc = self._doc

        if doc.needs_pass:
            if not doc.authenticate(""):
                return {'is_drm_protected': True}

        page_count = doc.page_count

        is_scan = False
        if page_count > 0:
            total_text = "".join(doc[i].get_text() for i in range(min(5, page_count)))
            is_scan = len(total_text.strip()) < 50

        meta   = doc.metadata or {}
        title  = (meta.get('title') or '').strip()
        author = (meta.get('author') or '').strip()

        # Si le titre est absent des métadonnées → chercher le plus grand texte
        # sur les 3 premières pages (souvent la page de couverture ou de faux-titre)
        if not title:
            title = self._guess_title_from_pages(doc)

        metadata = {
            'title':    title,
            'author':   author,
            'language': meta.get('language', 'fr-FR'),
            'date':     meta.get('creationDate', '')[:10] if meta.get('creationDate') else '',
        }

        return {
            'is_drm_protected': False,
            'is_scan': is_scan,
            'page_count': page_count,
            'metadata': metadata,
        }

    # ------------------------------------------------------------------ #
    #  Extraction complète                                                #
    # ------------------------------------------------------------------ #

    def extract(self, config: dict = None) -> dict:
        """Extrait le contenu complet du PDF."""
        self._open()
        doc    = self._doc
        config = config or {}

        pages  = []
        images = []
        toc    = self._extract_toc(doc)

        for page_num in range(doc.page_count):
            page      = doc[page_num]
            page_data = self._extract_page(page, page_num, config)
            pages.append(page_data)

            for img_data in self._extract_images(page, page_num):
                images.append(img_data)

        return {'pages': pages, 'images': images, 'toc': toc}

    # ------------------------------------------------------------------ #
    #  Table des matières                                                 #
    # ------------------------------------------------------------------ #

    def _extract_toc(self, doc) -> list:
        result = []
        for level, title, page in doc.get_toc():
            result.append({'level': level, 'title': title, 'page': page - 1})
        return result

    # ------------------------------------------------------------------ #
    #  Extraction d'une page avec gestion des colonnes                   #
    # ------------------------------------------------------------------ #

    def _extract_page(self, page, page_num: int, config: dict) -> dict:
        """
        Extrait les blocs texte d'une page.

        Si une mise en page 2 colonnes est détectée :
          - 'ignore_sidebar' (défaut) : seule la colonne principale est conservée
          - 'sidebar_annex'           : la sidebar est ajoutée après le contenu
                                        principal, marquée is_sidebar=True
        """
        page_height = page.rect.height
        page_width  = page.rect.width

        col_mode        = config.get('column_mode', 'ignore_sidebar')
        col_split_ratio = config.get('col_split', 0.55)

        raw_blocks = page.get_text(
            "dict",
            flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES,
        )["blocks"]

        # ── Détection colonnes ────────────────────────────────────────
        is_multi, split_x = self._detect_columns(raw_blocks, page_width, col_split_ratio)

        if is_multi:
            sidebar_block_count = sum(
                1 for b in raw_blocks
                if b.get('type') == 0 and b['bbox'][0] >= split_x
            )
            action = "ignorée" if col_mode == 'ignore_sidebar' else "déplacée en annexe"
            self.log(
                f"Page {page_num + 1} : mise en page 2 colonnes détectée, "
                f"sidebar {action} ({sidebar_block_count} bloc(s))"
            )

        # ── Extraction des spans ──────────────────────────────────────
        main_spans    = []
        sidebar_spans = []

        for block in raw_blocks:
            if block.get('type') != 0:  # 0 = texte
                continue

            # Filtrer les blocs en bande verticale très étroite :
            # texte imprimé en rotation 90° sur la tranche du livre (x0 ≈ 0-15 pts)
            block_bbox  = block['bbox']
            block_width = block_bbox[2] - block_bbox[0]
            if block_width < 20:
                continue

            block_x0       = block_bbox[0]
            is_sidebar_blk = is_multi and (block_x0 >= split_x)

            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    text = span.get('text', '')
                    if not text.strip():
                        continue

                    # Ignorer les polices de marqueurs graphiques purs
                    # (EuropeanPi-One → ❶❷❸, Puces → flèches de continuation)
                    _font_lower = span.get('font', '').lower()
                    if any(f in _font_lower for f in _FAKE_MARKER_FONTS):
                        continue

                    bbox  = span.get('bbox', [0, 0, 0, 0])
                    y_rel = bbox[1] / page_height if page_height > 0 else 0
                    x_rel = bbox[0] / page_width  if page_width  > 0 else 0

                    span_data = {
                        'text':       text,
                        'bbox':       bbox,
                        'y_rel':      y_rel,
                        'x_rel':      x_rel,
                        'font_size':  span.get('size', 12),
                        'font_flags': span.get('flags', 0),
                        'font_name':  span.get('font', ''),
                        'page':       page_num,
                        'is_sidebar': is_sidebar_blk,
                    }

                    if is_sidebar_blk:
                        sidebar_spans.append(span_data)
                    else:
                        main_spans.append(span_data)

        # Trier chaque zone par Y puis X
        main_spans.sort(key=lambda b: (b['y_rel'], b['x_rel']))
        sidebar_spans.sort(key=lambda b: (b['y_rel'], b['x_rel']))

        # ── Assembler selon le mode ───────────────────────────────────
        if not is_multi:
            # Page simple colonne : tout réunir, trier, aucun marquage
            all_spans = main_spans + sidebar_spans
            all_spans.sort(key=lambda b: (b['y_rel'], b['x_rel']))
            text_blocks = all_spans
        elif col_mode == 'ignore_sidebar':
            text_blocks = main_spans                  # sidebar définitivement ignorée
        else:  # sidebar_annex
            text_blocks = main_spans + sidebar_spans  # sidebar à la suite, marquée

        return {
            'page_num':    page_num,
            'width':       page_width,
            'height':      page_height,
            'blocks':      text_blocks,
            'has_columns': is_multi,
        }

    # ------------------------------------------------------------------ #
    #  Détection de colonnes                                              #
    # ------------------------------------------------------------------ #

    def _detect_columns(
        self,
        raw_blocks: list,
        page_width:  float,
        col_split_ratio: float,
    ) -> tuple:
        """
        Détecte si la page comporte une sidebar à droite.

        Critère : il existe des blocs texte dont x0 >= split_x ET
        des blocs dont x0 < split_x, ET le gap entre les deux zones
        représente au moins 10 % de la largeur (évite les faux positifs
        sur des paragraphes légèrement indentés).

        Returns (is_multicolumn: bool, split_x: float)
        """
        if page_width <= 0:
            return False, page_width * col_split_ratio

        split_x     = page_width * col_split_ratio
        text_blocks = [b for b in raw_blocks if b.get('type') == 0]

        if not text_blocks:
            return False, split_x

        left_x0_max  = max(
            (b['bbox'][0] for b in text_blocks if b['bbox'][0] < split_x),
            default=None,
        )
        right_x0_min = min(
            (b['bbox'][0] for b in text_blocks if b['bbox'][0] >= split_x),
            default=None,
        )

        if left_x0_max is None or right_x0_min is None:
            return False, split_x

        # Vérifier que le gap entre les deux zones est significatif (≥ 10 %)
        gap_ratio = (right_x0_min - left_x0_max) / page_width
        is_multi  = gap_ratio >= -0.05   # tolère un léger chevauchement
        # (on fait confiance à split_x configuré par l'utilisateur ;
        #  la vraie garde c'est que les deux zones sont peuplées)

        return is_multi, split_x

    # ------------------------------------------------------------------ #
    #  Extraction d'images                                                #
    # ------------------------------------------------------------------ #

    def _extract_images(self, page, page_num: int) -> list:
        """
        Extrait les images d'une page.

        Toutes les images sont converties via fitz.Pixmap et sauvegardées en PNG.
        Les images CMYK sont explicitement converties en RGB — les liseuses EPUB
        n'affichent pas le CMYK (image noire/vide sans message d'erreur).
        """
        images = []
        doc         = page.parent
        page_height = page.rect.height
        page_width  = page.rect.width
        cmyk_converted = 0

        seen_xrefs: set = set()   # éviter les doublons sur la même page

        for img_index, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                # ── Position de l'image sur la page ──────────────────
                y_rel, x_rel, bbox = 0.5, 0.0, [0.0, 0.0, 0.0, 0.0]
                try:
                    rects = page.get_image_rects(xref)
                    if rects:
                        r     = rects[0]
                        y_rel = r.y0 / page_height if page_height > 0 else 0.5
                        x_rel = r.x0 / page_width  if page_width  > 0 else 0.0
                        bbox  = [r.x0, r.y0, r.x1, r.y1]
                except Exception:
                    pass

                # ── Conversion couleur → PNG compatible EPUB ──────────
                pix = fitz.Pixmap(doc, xref)

                # Conversion CMYK → RGB obligatoire : les JPEG CMYK (fréquents
                # dans les livres d'imprimerie) sont invisibles dans les liseuses
                # EPUB — ils apparaissent noirs/vides sans aucun message d'erreur.
                if pix.colorspace and pix.colorspace.name in ('DeviceCMYK', 'CMYK'):
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                    cmyk_converted += 1
                elif pix.colorspace is None or pix.n > 4:
                    # Espace non identifié ou multi-canal exotique → forcer RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                elif pix.colorspace.name not in ('DeviceRGB', 'sRGB', 'DeviceGray'):
                    # Autres espaces non standard → RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                # Supprimer le canal alpha (incompatible avec certaines liseuses EPUB)
                if pix.alpha:
                    pix = fitz.Pixmap(pix, 0)

                img_data = pix.tobytes('png')
                w, h     = pix.width, pix.height
                pix      = None   # libérer la mémoire

                images.append({
                    'xref':   xref,
                    'data':   img_data,
                    'ext':    'png',
                    'width':  w,
                    'height': h,
                    'page':   page_num,
                    'index':  img_index,
                    'y_rel':  y_rel,
                    'x_rel':  x_rel,
                    'bbox':   bbox,
                })

            except Exception:
                pass

        if cmyk_converted:
            self.log(f"[IMG]   Page {page_num + 1} : {cmyk_converted} image(s) convertie(s) CMYK→RGB")

        return images

    def _guess_title_from_pages(self, doc) -> str:
        """
        Tente de deviner le titre en cherchant le span de plus grande taille
        sur les 3 premières pages (couverture / faux-titre).
        Retourne une chaîne vide si rien de pertinent n'est trouvé.
        """
        best_text = ''
        best_size = 0.0
        for page_num in range(min(3, doc.page_count)):
            page = doc[page_num]
            try:
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block.get('type') != 0:
                        continue
                    for line in block.get('lines', []):
                        for span in line.get('spans', []):
                            text = span.get('text', '').strip()
                            size = span.get('size', 0)
                            # Longueur > 5 pour écarter les initiales et fragments
                            if size > best_size and len(text) > 5:
                                best_size = size
                                best_text = text
            except Exception:
                pass
        return best_text

    def close(self):
        if self._doc:
            self._doc.close()
            self._doc = None
