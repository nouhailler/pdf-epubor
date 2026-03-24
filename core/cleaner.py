"""Heuristiques de nettoyage du texte extrait"""

import re
import unicodedata
from collections import Counter
from typing import Callable, Optional


# Caractères de puce détectés comme marqueurs de liste
PUCE_CHARS = frozenset('•▶→►·◆▸')
PUCE_FONTS = frozenset(['puces', 'puce', 'bullet', 'zapfdingbats'])

# Titres d'encadrés latéraux Eyrolles
NOTE_LABELS = frozenset([
    'À RETENIR', 'A RETENIR', 'RÉFÉRENCE', 'REFERENCE',
    'CONTEXTE', 'EN PRATIQUE', 'ATTENTION', 'CONSEIL',
    'DÉFINITION', 'DEFINITION', 'RAPPEL', 'NOTE',
    'SOUS LINUX', 'SOUS WINDOWS',
])

# Ligatures Unicode communes
LIGATURE_MAP = {
    '\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl',
    '\ufb03': 'ffi', '\ufb04': 'ffl',
    '\u0153': 'oe', '\u0152': 'OE',
    '\u00e6': 'ae', '\u00c6': 'AE',
}

# ── Détection ASCII art / code monospace ─────────────────────────────────
# Caractères de tracé de boîtes et flèches ASCII
_BOX_CHARS = frozenset(
    '╔╗╚╝║═╠╣╦╩╬'   # boîtes doubles
    '┌┐└┘│─├┤┬┴┼'   # boîtes simples
    '▼▲►◄→←↑↓'      # flèches
    '■□▪▫●○'         # puces graphiques
)
# Mots-clés indiquant une police monospace dans le nom fitz
_MONO_KEYWORDS = (
    'courier', 'mono', 'consolas', 'menlo', 'inconsolata',
    'source code', 'fira code', 'jetbrains', 'hack', 'fixed',
    'typewriter', 'lucida console', 'andale', 'ocr',
    'tt277',    # police PGP Command Line dans les livres Eyrolles
)


def _is_ascii_art(text: str, font_name: str = '') -> bool:
    """
    Renvoie True si ce span est de l'ASCII art ou du code monospace.

    Critère 1 (fort)  : ≥ 3 caractères de tracé de boîtes dans le texte.
    Critère 2 (police): la police est identifiée comme monospace.

    Les deux critères sont volontairement indépendants pour couvrir :
    - les lignes de cadre (║══╔) → critère 1
    - le contenu texte à l'intérieur des boîtes (même police) → critère 2
    """
    if sum(1 for c in text if c in _BOX_CHARS) >= 3:
        return True
    if font_name:
        fl = font_name.lower()
        if any(kw in fl for kw in _MONO_KEYWORDS):
            return True
    return False


class Cleaner:
    def __init__(self, config: dict, log_fn: Optional[Callable] = None):
        self.config = config
        self.log = log_fn or (lambda msg: None)
        self._stats = {
            'headers_removed': 0,
            'footers_removed': 0,
            'page_numbers_removed': 0,
            'images_kept': 0,
            'images_ignored': 0,
            'hyphens_fixed': 0,
            'ascii_art_detected': 0,
            'bullets_tagged': 0,
        }

    def get_stats(self) -> dict:
        return dict(self._stats)

    def clean(self, raw_data: dict) -> dict:
        """Nettoie les données extraites selon la configuration."""
        pages  = raw_data['pages']
        images = raw_data.get('images', [])
        toc    = raw_data.get('toc', [])

        header_patterns = self._detect_repeated(pages, 'header')
        footer_patterns = self._detect_repeated(pages, 'footer')

        cleaned_pages = []
        for page_data in pages:
            cleaned_pages.append(self._clean_page(page_data, header_patterns, footer_patterns))

        cleaned_images = self._filter_images(images)

        if not toc and self.config.get('extract_toc', True):
            toc = self._detect_toc_heuristic(cleaned_pages)

        # Détecter et injecter les annexes / index manquants dans la TOC
        toc = self._inject_special_chapters(raw_data['pages'], toc)

        # Exclure les pages catalogue éditeur de fin de livre
        catalog_pages = self._detect_catalog_pages(raw_data['pages'])

        chapters = self._group_into_chapters(cleaned_pages, toc, catalog_pages)
        self._inject_images_into_chapters(chapters, cleaned_images)

        if self._stats['ascii_art_detected']:
            self.log(
                f"ASCII art : {self._stats['ascii_art_detected']} span(s) monospace détecté(s)"
            )

        return {
            'chapters': chapters,
            'images': cleaned_images,
            'toc': toc,
            'metadata': raw_data.get('metadata', {}),
        }

    # ------------------------------------------------------------------ #
    #  Détection des répétitions header/footer                            #
    # ------------------------------------------------------------------ #

    def _detect_repeated(self, pages: list, zone: str) -> set:
        header_thr = self.config.get('header_threshold', 0.10)
        footer_thr = self.config.get('footer_threshold', 0.90)
        repeat_min = self.config.get('repeat_min', 3)

        counter = Counter()
        for page in pages:
            seen = set()
            for block in page.get('blocks', []):
                y = block.get('y_rel', 0.5)
                t = block['text'].strip()
                if not t:
                    continue
                if zone == 'header' and y < header_thr:
                    seen.add(t)
                elif zone == 'footer' and y > footer_thr:
                    seen.add(t)
            for t in seen:
                counter[t] += 1

        return {t for t, count in counter.items() if count >= repeat_min}

    # ------------------------------------------------------------------ #
    #  Nettoyage page par page                                            #
    # ------------------------------------------------------------------ #

    def _clean_page(self, page_data: dict, header_patterns: set, footer_patterns: set) -> dict:
        config        = self.config
        header_thr    = config.get('header_threshold', 0.10)
        footer_thr    = config.get('footer_threshold', 0.90)

        cleaned_blocks   = []
        _next_is_bullet  = False   # le span précédent était un glyphe puce seul
        _in_bullet_item  = False   # on accumule des lignes d'un même item de liste
        _bullet_x_rel    = 0.0    # x_rel du premier span de l'item en cours
        _prev_y          = -1.0   # y_rel du dernier span (détection même ligne)

        for block in page_data.get('blocks', []):
            text      = block['text'].strip()
            y         = block.get('y_rel', 0.5)
            x_rel     = block.get('x_rel', 0.0)
            font_name = block.get('font_name', '')
            size      = block.get('font_size', 12) or 12

            # Toujours mettre à jour _prev_y en tête de boucle, avant tout continue.
            _last_y  = _prev_y
            _prev_y  = y

            if not text:
                continue

            # ── ASCII art / code monospace — court-circuit total ──────
            # Ces blocs doivent être préservés tels quels (aucun filtre,
            # aucune normalisation ne doit altérer les caractères spéciaux
            # ou la structure spatiale du schéma).
            if _is_ascii_art(text, font_name):
                block = dict(block)
                block['text']        = text   # strip() uniquement, pas de normalize
                block['is_ascii_art'] = True
                cleaned_blocks.append(block)
                self._stats['ascii_art_detected'] += 1
                continue

            # ── Numéros de page ───────────────────────────────────────
            # BUG CORRIGÉ : on ne supprime les spans purement numériques
            # QUE s'ils sont dans la zone header (y < seuil_haut) ou
            # footer (y > seuil_bas). Les numéros de section en milieu
            # de page ("2 Agents...", "3 Théories...") commencent
            # souvent par un span "2" ou "3" isolé — ne pas les supprimer.
            if config.get('remove_page_numbers', True):
                if re.match(r'^\d+$', text):
                    if y < header_thr or y > footer_thr:
                        self._stats['page_numbers_removed'] += 1
                        continue
                    # Hors zone header/footer → possiblement numéro de section,
                    # on le conserve.

            # ── En-têtes répétés ─────────────────────────────────────
            if config.get('remove_headers', True):
                if y < header_thr and text in header_patterns:
                    self._stats['headers_removed'] += 1
                    continue

            # ── Pieds de page répétés ─────────────────────────────────
            if config.get('remove_footers', True):
                if y > footer_thr and text in footer_patterns:
                    self._stats['footers_removed'] += 1
                    continue

            # ── Normalisation ─────────────────────────────────────────
            cleaned_text = self._normalize_text(text)

            if config.get('fix_hyphenation', True):
                cleaned_text, fixed = self._fix_hyphenation(cleaned_text)
                self._stats['hyphens_fixed'] += fixed

            block = dict(block)
            block['text'] = cleaned_text

            # ── Détection des puces ───────────────────────────────────
            font_lower = font_name.lower()
            is_puce_font = any(p in font_lower for p in PUCE_FONTS)

            if is_puce_font and len(cleaned_text) <= 3:
                # Glyphe puce seul (police "Puces") → marquer le span suivant
                _next_is_bullet = True
                _in_bullet_item = False
                continue
            elif _next_is_bullet:
                block['is_bullet'] = True
                _next_is_bullet  = False
                _in_bullet_item  = True
                _bullet_x_rel    = x_rel
                self._stats['bullets_tagged'] += 1
            elif is_puce_font:
                block['is_bullet'] = True
                _in_bullet_item  = True
                _bullet_x_rel    = x_rel
                self._stats['bullets_tagged'] += 1
            elif cleaned_text and cleaned_text[0] in PUCE_CHARS:
                rest = cleaned_text[1:].lstrip()
                if not rest:
                    # Glyphe puce seul (•). Distinguer séparateur inline vs marqueur de liste.
                    if abs(y - _last_y) < 0.015:
                        continue  # même ligne → séparateur TOC, ignorer
                    else:
                        _next_is_bullet = True
                        _in_bullet_item = False
                        continue
                block['text']    = rest
                block['is_bullet'] = True
                _in_bullet_item  = True
                _bullet_x_rel    = x_rel
                self._stats['bullets_tagged'] += 1
            elif _in_bullet_item:
                # Vérifier si c'est une continuation du même item ou un retour au corps.
                # Fin de liste : titre de section (≥14pt) ou retour à la marge gauche
                # (x_rel nettement plus petit que le point d'entrée du bullet).
                is_title = size >= 14
                is_body  = x_rel < _bullet_x_rel - 0.04 and size >= 10
                if is_title or is_body:
                    _in_bullet_item = False
                    _next_is_bullet = False
                    # Laisser le bloc se traiter normalement (pas de continue)
                else:
                    block['is_bullet_continuation'] = True
            else:
                _next_is_bullet = False
                _in_bullet_item = False

            if block['text']:
                cleaned_blocks.append(block)

        page = dict(page_data)
        page['blocks'] = cleaned_blocks
        return page

    def _normalize_text(self, text: str) -> str:
        # Supprimer les caractères de remplacement Unicode (U+FFFD) générés par des
        # polices spéciales (EuropeanPi-One, symboles de renvoi ❷❸❹…) et les caractères
        # de contrôle encodés via des polices dingbats (U+0001–U+001F sauf \t\n\r).
        text = text.replace('\ufffd', '')
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        if '  ' in text:
            text = re.sub(r' {2,}', ' ', text)
        text = text.strip()

        for char, replacement in LIGATURE_MAP.items():
            text = text.replace(char, replacement)
        return unicodedata.normalize('NFC', text)

    def _fix_hyphenation(self, text: str) -> tuple:
        original = text
        # Césure avec saut de ligne explicite dans un même span (rare mais possible)
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        # NE PAS supprimer les tirets finaux de span individuels :
        # le tiret final "con-" sera recollé avec le span suivant
        # lors de la jointure des paragraphes dans epub_builder (flush_para).
        return text, (1 if text != original else 0)

    # ------------------------------------------------------------------ #
    #  Filtrage images                                                     #
    # ------------------------------------------------------------------ #

    def _filter_images(self, images: list) -> list:
        if not self.config.get('keep_images', True):
            return []
        min_size = self.config.get('min_image_size', 100)
        filtered = []
        for img in images:
            w, h = img.get('width', 0), img.get('height', 0)
            data  = img.get('data', b'')

            # Taille minimale (les deux dimensions doivent être satisfaites)
            if w < min_size or h < min_size:
                self._stats['images_ignored'] += 1
                continue

            # Ratio > 10 : filet horizontal ou vertical (élément décoratif)
            if w > 0 and h > 0 and max(w, h) / min(w, h) > 10:
                self._stats['images_ignored'] += 1
                continue

            # Données < 1 Ko : pixel ou élément graphique minimal
            if len(data) < 1024:
                self._stats['images_ignored'] += 1
                continue

            filtered.append(img)
            self._stats['images_kept'] += 1
        return filtered

    # ------------------------------------------------------------------ #
    #  Injection des images dans les chapitres                            #
    # ------------------------------------------------------------------ #

    def _inject_images_into_chapters(self, chapters: list, images: list):
        """
        Insère les images filtrées dans les blocs des chapitres comme blocs de type
        'image', positionnés par (page, y_rel) dans le flux de texte.

        Chaque image est assignée au chapitre qui contient du contenu sur sa page.
        En cas d'ambiguïté (page à cheval entre deux chapitres), l'image va au
        chapitre dont le premier bloc est sur cette page ou avant.
        """
        if not images:
            return

        # Index des images filtrées par page
        imgs_by_page: dict = {}
        for img in images:
            p = img.get('page', 0)
            imgs_by_page.setdefault(p, []).append(img)

        # Pour chaque chapitre, trouver les pages couvertes puis injecter
        total_injected = 0
        for chap in chapters:
            pages_in_chap = set(b.get('page', 0) for b in chap['blocks'])

            img_blocks = []
            for page_num in pages_in_chap:
                for img in imgs_by_page.get(page_num, []):
                    idx = img.get('index', 0)
                    ext = (img.get('ext') or 'png').lower()
                    img_blocks.append({
                        'type':    'image',
                        'page':    page_num,
                        'y_rel':   img.get('y_rel', 0.5),
                        'x_rel':   img.get('x_rel', 0.0),
                        'bbox':    img.get('bbox', [0.0, 0.0, 0.0, 0.0]),
                        'img_key': f'img_{page_num}_{idx}.{ext}',
                        'width':   img.get('width', 0),
                        'height':  img.get('height', 0),
                        'text':    '',   # champ requis par l'interface commune
                    })

            if img_blocks:
                # Fusionner texte et images, trier par page puis Y pour respecter le flux
                combined = chap['blocks'] + img_blocks
                combined.sort(key=lambda b: (b.get('page', 0), b.get('y_rel', 0)))
                chap['blocks'] = combined
                total_injected += len(img_blocks)

        if total_injected:
            self.log(f"  {total_injected} image(s) injectée(s) dans les chapitres")

    # ------------------------------------------------------------------ #
    #  Détection heuristique de la TOC                                    #
    # ------------------------------------------------------------------ #

    def _detect_toc_heuristic(self, pages: list) -> list:
        """
        Détecte les titres de chapitres par taille de police ou motif numéroté.

        Critères stricts (évite les faux positifs sur les pages de couverture) :
        - Taille de police > 1.5 × la médiane du document (pas juste gras)
        - ET longueur > 10 caractères (exclut les fragments courts : noms, initiales)
        - ET position Y dans les 40 % supérieurs de la page (les chapitres débutent en haut)
        OU
        - Titre numéroté : "1 Introduction", "3.2 Chiffrement..." (avec longueur > 10)
        """
        all_sizes = [
            block.get('font_size', 12)
            for page in pages
            for block in page.get('blocks', [])
        ]
        if not all_sizes:
            return []

        all_sizes.sort()
        median_size     = all_sizes[len(all_sizes) // 2]
        # Seuil à 1.8× pour ne détecter que les vrais titres de chapitres
        # (pas les sous-titres de section à ~1.5× ni le texte en gras)
        title_threshold = median_size * 1.8

        # Regex : titre numéroté type "2 Agents...", "3.1 Théories..."
        # Contraintes : max 2 chiffres par segment, doit commencer par 1-9 (pas 0),
        # et le texte qui suit DOIT commencer par une MAJUSCULE (française ou anglaise).
        # Rejette : "128 bits...", "0 = la clé...", "31 clés depuis...", "1 key found..."
        numbered_re = re.compile(r'^[1-9]\d{0,1}(\.\d{1,2})*\s+[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜŒÆÇ]')

        toc = []
        for page_data in pages:
            # ── Collecter TOUS les spans à grande taille sur cette page ──
            # pour reconstituer les titres multi-lignes (ex : "À quoi servent"
            # + "la cryptographie et OpenPGP ?" → titre complet).
            large_spans   = []   # (text, size, y_rel, page_num)
            numbered_match = None

            for block in page_data.get('blocks', []):
                size     = block.get('font_size', 12) or 12
                text     = block.get('text', '').strip()
                y_rel    = block.get('y_rel', 0.5)
                page_num = block.get('page', 0)

                if not text or len(text) > 200:
                    continue

                if size >= title_threshold and y_rel < 0.40:
                    large_spans.append((text, size, y_rel, page_num))
                elif not numbered_match and bool(numbered_re.match(text)) and len(text) > 10:
                    numbered_match = (text, page_num)

            # ── Construire l'entrée TOC de cette page ────────────────────
            if large_spans:
                # Trier par Y et concaténer → titre complet sur plusieurs lignes
                large_spans.sort(key=lambda x: x[2])
                # Garder uniquement les lignes proches de la taille max (± 20 %)
                max_size = max(s[1] for s in large_spans)
                title_lines = [
                    s[0] for s in large_spans
                    if s[1] >= max_size * 0.8
                ]
                full_title = re.sub(r'\s+', ' ', ' '.join(title_lines)).strip()
                if len(full_title) > 10:
                    toc.append({
                        'level': 1,
                        'title': full_title,
                        'page':  large_spans[0][3],
                    })
            elif numbered_match:
                toc.append({
                    'level': 1,
                    'title': numbered_match[0],
                    'page':  numbered_match[1],
                })

        return toc[:50]

    # ------------------------------------------------------------------ #
    #  Regroupement en chapitres — travail au niveau BLOC, pas PAGE       #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  Détection des annexes, index et pages catalogue                   #
    # ------------------------------------------------------------------ #

    def _inject_special_chapters(self, raw_pages: list, toc: list) -> list:
        """
        Scanne les pages brutes pour détecter :
        - Les titres d'annexes (lettre unique très grande : A, B…)
        - La page "Index" (grand titre)
        Injecte les entrées manquantes dans la TOC et retourne la TOC enrichie.
        """
        existing_pages = {e.get('page', -1) for e in toc}
        extra: list = []

        for page_data in raw_pages:
            page_num = page_data.get('page_num', 0)
            if page_num in existing_pages:
                continue

            # raw_pages contient des spans PLATS produits par PDFExtractor._extract_page
            # (pas les blocs fitz bruts avec 'type'/'lines'/'spans')
            blocks = page_data.get('blocks', [])
            annexe_letter = ''
            title_parts: list = []   # fragments du titre d'annexe (peut tenir sur 2 spans)
            index_found   = False

            for block in blocks:
                text = block.get('text', '').strip()
                size = block.get('font_size', 0)
                if not text:
                    continue

                # Lettre unique très grande → titre d'annexe (A, B…)
                if size >= 60 and len(text) == 1 and text.isalpha():
                    annexe_letter = text.upper()

                # Grand titre — peut tenir sur plusieurs spans ("Introduction à" + "PGP…")
                if size >= 30 and len(text) > 3:
                    if text.lower() == 'index':
                        index_found = True
                    elif annexe_letter:
                        title_parts.append(text)

            annexe_title = ' '.join(title_parts) if title_parts else ''

            if index_found and page_num not in existing_pages:
                extra.append({'level': 1, 'title': 'Index', 'page': page_num})
                existing_pages.add(page_num)
            elif annexe_letter and page_num not in existing_pages:
                full = (
                    f'Annexe {annexe_letter} — {annexe_title}'
                    if annexe_title else f'Annexe {annexe_letter}'
                )
                extra.append({'level': 1, 'title': full, 'page': page_num})
                existing_pages.add(page_num)

        if extra:
            combined = sorted(toc + extra, key=lambda e: e.get('page', 0))
            for e in extra:
                self.log(f"  Chapitre détecté (heuristique) : «{e['title']}» p.{e['page'] + 1}")
            return combined
        return toc

    def _detect_catalog_pages(self, raw_pages: list) -> set:
        """
        Retourne les numéros des pages catalogue éditeur à exclure.
        Critère : tous les blocs texte contiennent des marqueurs commerciaux
        ("Dans la collection", "Autres parutions", "du même auteur").
        """
        _CATALOG_MARKERS = {
            'dans la collection', 'autres parutions', 'du même auteur',
            'du meme auteur', 'à paraître', 'a paraitre', 'chez le même',
        }
        catalog: set = set()
        for page_data in raw_pages:
            blocks = page_data.get('blocks', [])
            if not blocks:
                continue
            # Spans plats (PDFExtractor) : chaque bloc a directement un champ 'text'
            texts = [
                block.get('text', '').strip().lower()
                for block in blocks
                if block.get('text', '').strip()
            ]
            if texts and any(
                any(m in t for m in _CATALOG_MARKERS) for t in texts
            ):
                catalog.add(page_data.get('page_num', -1))
        if catalog:
            self.log(f"[CLEAN] {len(catalog)} page(s) catalogue éditeur exclues")
        return catalog

    def _group_into_chapters(self, pages: list, toc: list, catalog_pages: set = None) -> list:
        """
        Regroupe les blocs en chapitres selon la TOC.

        Améliorations par rapport à la version précédente :
        - Pages liminaires (couverture, faux-titre…) regroupées en un chapitre «Couverture»
        - Seules les entrées TOC de niveau minimal (niveau 1) délimitent des chapitres ;
          les niveaux 2+ deviennent des sections visuelles dans le rendu HTML
        - Les chapitres trop courts (< 500 car.) sont fusionnés avec le précédent
        """
        prelim_pages  = self.config.get('prelim_pages', 5)
        min_chars     = 500
        catalog_pages = catalog_pages or set()

        # ── Aplatir tous les blocs dans l'ordre des pages (hors catalogue) ─
        all_blocks = []
        for page in pages:
            if page.get('page_num', 0) in catalog_pages:
                continue
            all_blocks.extend(page.get('blocks', []))

        # ── Séparer les blocs liminaires du corps principal ───────────────
        prelim_blocks = [b for b in all_blocks if b.get('page', 0) < prelim_pages]
        main_blocks   = [b for b in all_blocks if b.get('page', 0) >= prelim_pages]

        chapters: list = []

        # Chapitre «Couverture» pour les pages liminaires
        if prelim_blocks:
            char_count = sum(len(b.get('text', '')) for b in prelim_blocks)
            self.log(
                f"Pages liminaires ({prelim_pages} p.) → «Couverture» : "
                f"{len(prelim_blocks)} blocs, {char_count} car."
            )
            chapters.append({'title': 'Couverture', 'blocks': prelim_blocks, 'page': 0})

        if not toc:
            char_count = sum(len(b.get('text', '')) for b in main_blocks)
            self.log(f"Pas de TOC → 1 chapitre : {len(main_blocks)} blocs / {char_count} car.")
            chapters.append({'title': 'Document', 'blocks': main_blocks, 'page': prelim_pages})
            return chapters

        # ── Filtrer la TOC : exclure les pages liminaires ─────────────────
        toc_main = [e for e in toc if e.get('page', 0) >= prelim_pages]
        if not toc_main:
            toc_main = toc  # fallback : utiliser toute la TOC

        # Garder uniquement le niveau hiérarchique le plus élevé (min level)
        # pour éviter que chaque sous-section devienne un chapitre EPUB séparé.
        min_level    = min(e.get('level', 1) for e in toc_main)
        toc_chapters = sorted(
            [e for e in toc_main if e.get('level', 1) <= min_level],
            key=lambda e: e.get('page', 0),
        )

        # ── Trouver les points de coupe dans main_blocks ──────────────────
        split_points = []
        for entry in toc_chapters:
            idx = self._find_chapter_start(main_blocks, entry)
            if idx is not None:
                split_points.append((idx, entry))

        if not split_points:
            char_count = sum(len(b.get('text', '')) for b in main_blocks)
            self.log(f"Aucun point de coupe trouvé → 1 chapitre : {char_count} car.")
            chapters.append({'title': 'Document', 'blocks': main_blocks, 'page': prelim_pages})
            return chapters

        # Trier et dédupliquer (deux entrées sur le même bloc → décaler +1)
        split_points.sort(key=lambda x: x[0])
        unique: list = []
        occupied: set = set()
        for idx, entry in split_points:
            while idx in occupied and idx < len(main_blocks):
                idx += 1
            if idx < len(main_blocks):
                occupied.add(idx)
                unique.append((idx, entry))

        if not unique:
            chapters.append({'title': 'Document', 'blocks': main_blocks, 'page': prelim_pages})
            return chapters

        # Blocs avant le premier point de coupe → intro ou ajout aux liminaires
        if unique[0][0] > 0:
            intro_blocks = main_blocks[:unique[0][0]]
            if chapters:
                chapters[-1]['blocks'].extend(intro_blocks)
            else:
                chapters.append({'title': 'Introduction', 'blocks': intro_blocks, 'page': prelim_pages})

        # ── Construire les chapitres bruts ────────────────────────────────
        raw_chapters = []
        for i, (idx, entry) in enumerate(unique):
            next_idx   = unique[i + 1][0] if i + 1 < len(unique) else len(main_blocks)
            blocks     = main_blocks[idx:next_idx]
            char_count = sum(len(b.get('text', '')) for b in blocks)
            raw_chapters.append({
                'title':       entry['title'],
                'blocks':      blocks,
                'page':        entry.get('page', 0),
                'level':       entry.get('level', 1),
                '_char_count': char_count,
            })

        # ── Fusionner les chapitres trop courts ───────────────────────────
        merged: list = []
        for chap in raw_chapters:
            char_count = chap.pop('_char_count')
            if merged and char_count < min_chars:
                merged[-1]['blocks'].extend(chap['blocks'])
                self.log(
                    f"  Fusion de «{chap['title'][:40]}» ({char_count} car.) "
                    f"→ «{merged[-1]['title'][:40]}»"
                )
            else:
                merged.append(chap)
                self.log(
                    f"  Ch.{len(chapters) + len(merged)} «{chap['title'][:50]}» "
                    f"— {len(chap['blocks'])} blocs, {char_count} car. "
                    f"(p.{chap.get('page', 0) + 1})"
                )

        chapters.extend(merged)
        return chapters

    def _find_chapter_start(self, blocks: list, entry: dict) -> Optional[int]:
        """
        Trouve l'index du premier bloc correspondant à cette entrée TOC dans
        la liste de blocs fournie (peut être all_blocks ou main_blocks).

        Stratégie :
        1. Correspondance textuelle sur la page cible (longueur bloc ≥ 3) :
           - le titre commence par le texte du bloc (span de début de titre)
           - ou le bloc commence par le titre (titre entier dans un seul span)
        2. Fallback : premier bloc de la page cible.
        3. Sinon : None.
        """
        target_page = entry.get('page', 0)
        title       = (entry.get('title') or '').strip()
        title_lower = title.lower()

        # Essai 1 : correspondance textuelle
        for i, block in enumerate(blocks):
            if block.get('page', -1) != target_page:
                continue
            btext = block.get('text', '').strip()
            if not btext:
                continue
            btext_lower = btext.lower()

            # Le titre commence par ce bloc (ex: bloc="Chapitre", titre="Chapitre 1...")
            # Longueur minimale 3 pour éviter les correspondances sur des articles courts
            if len(btext) >= 3 and title_lower.startswith(btext_lower):
                return i
            # Ce bloc commence par le titre (titre entier dans un span)
            if len(title) >= 3 and btext_lower.startswith(title_lower[:min(len(title), 30)]):
                return i

        # Essai 2 : premier bloc de la page cible
        for i, block in enumerate(blocks):
            if block.get('page', -1) == target_page:
                return i

        return None
