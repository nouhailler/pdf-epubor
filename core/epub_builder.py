"""Construction de fichier EPUB3 via ebooklib"""

import os
from typing import Callable, Optional
from ebooklib import epub


_CSS = b"""
body {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 1em;
    line-height: 1.7;
    margin: 1.5em 2.5em;
    color: #1a1a1a;
}
h1 { font-size: 1.7em; margin: 1em 0 0.6em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }
h2 { font-size: 1.3em; margin: 1.2em 0 0.4em; }
p  { margin: 0.6em 0; text-align: justify; }
strong { font-weight: bold; }
img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
pre {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.75em;
    white-space: pre;
    overflow-x: auto;
    line-height: 1.2;
    background: #f5f5f5;
    padding: 0.8em 1em;
    margin: 1em 0;
    border: 1px solid #ddd;
    border-radius: 3px;
}
aside.sidebar {
    margin: 2em 0 1em;
    padding: 1em 1.2em;
    border-left: 3px solid #aaa;
    background: #f8f8f8;
    font-size: 0.9em;
    color: #444;
}
aside.sidebar h3 {
    font-size: 1em;
    margin: 0 0 0.6em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #666;
}
ul { margin: 0.6em 0 0.6em 1.5em; padding: 0; list-style-type: disc; }
li { margin: 0.3em 0; }
nav ol { list-style: none; padding: 0; margin: 0.5em 0; }
nav li { margin: 0.5em 0; }
nav a  { text-decoration: none; color: #1a1a1a; }
nav a:hover { text-decoration: underline; }
aside.note {
    margin: 1.5em 0;
    padding: 0.8em 1.2em;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: #f7f7f7;
    font-size: 0.88em;
}
aside.note p.note-label {
    font-weight: bold;
    font-size: 0.8em;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #555;
    margin: 0 0 0.5em;
}
aside.note p { margin: 0.3em 0; }
dl.book-index { column-count: 2; column-gap: 2em; margin: 1em 0; }
dl.book-index dt { font-weight: bold; margin-top: 0.4em; break-after: avoid; }
dl.book-index dt.index-letter {
    font-size: 1.2em; color: #333;
    border-bottom: 1px solid #ccc;
    margin-top: 1em;
}
dl.book-index dd { margin-left: 1em; color: #666; font-size: 0.9em; }
code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.85em;
    background: #f0f0f0;
    padding: 0.1em 0.3em;
    border-radius: 2px;
}
figure {
    margin: 1.5em 0;
    text-align: center;
}
figcaption {
    font-size: 0.85em;
    color: #555;
    font-style: italic;
    margin-top: 0.4em;
}
"""


class EPUBBuilder:
    def __init__(self, config: dict, metadata: dict, log_fn: Optional[Callable] = None):
        self.config = config
        self.metadata = metadata
        self.log = log_fn or (lambda msg: None)

    # ------------------------------------------------------------------ #
    #  Point d'entrée                                                      #
    # ------------------------------------------------------------------ #

    def build(self, cleaned_data: dict, output_path: str):
        """Construit l'EPUB3 et l'enregistre sur disque."""
        book = epub.EpubBook()

        lang    = self.metadata.get('language', 'fr-FR')
        title   = self.metadata.get('title', 'Document sans titre') or 'Document sans titre'
        author  = self.metadata.get('author', '') or ''
        date    = self.metadata.get('date', '')
        lang_bcp = lang  # ex. "fr-FR"
        lang_iso = lang.split('-')[0]  # ex. "fr"

        book.set_identifier(f"pdf-epubor-{abs(hash(title + author))}")
        book.set_title(title)
        book.set_language(lang_iso)
        if author:
            book.add_author(author)
        if date:
            book.add_metadata('DC', 'date', date)

        # ── CSS ────────────────────────────────────────────────────────
        css_item = epub.EpubItem(
            uid="main-css",
            file_name="style/main.css",
            media_type="text/css",
            content=_CSS,
        )
        book.add_item(css_item)

        # ── Images ────────────────────────────────────────────────────
        self._add_images(book, cleaned_data.get('images', []))

        # ── Chapitres ─────────────────────────────────────────────────
        chapters = cleaned_data.get('chapters', [])
        if not chapters:
            self.log("Avertissement : aucun chapitre extrait — EPUB avec page vide.")
            chapters = [{'title': title, 'blocks': [], 'page': 0}]

        export_mode = self.config.get('export_mode', 'structured')
        epub_chapters = []
        self._ascii_art_count = 0   # compteur partagé entre tous les chapitres

        # Détecter le chapitre TOC imprimée pour le remplacer par une TOC propre.
        # La TOC imprimée du PDF est illisible (2 colonnes, points de suspension…)
        # → on génère une <ol> de liens depuis la liste des chapitres détectés.
        _toc_idx = None
        for _i, _ch in enumerate(chapters):
            _tl = (_ch.get('title') or '').lower()
            if any(kw in _tl for kw in ('table', 'sommaire', 'matière', 'matiere', 'contents')):
                _toc_idx = _i
                break

        for i, chap in enumerate(chapters):
            chap_title  = (chap.get('title') or f'Chapitre {i + 1}').strip()
            blocks      = chap.get('blocks', [])
            is_index    = chap_title.strip().lower() == 'index'

            if i == _toc_idx:
                html_bytes = self._render_toc_chapter(chapters, chap_title, lang_bcp, i)
            else:
                html_bytes = self._render_chapter(
                    blocks, chap_title, lang_bcp, export_mode, is_index=is_index
                )

            item = epub.EpubHtml(
                file_name=f"chapter_{i:03d}.xhtml",
                title=chap_title,
            )
            item.set_language(lang_iso)
            item.set_content(html_bytes)
            item.add_link(href="../style/main.css", rel="stylesheet", type="text/css")

            book.add_item(item)
            epub_chapters.append(item)

        if not epub_chapters:
            raise RuntimeError("Aucun contenu à écrire dans l'EPUB.")

        # ── Navigation & spine ────────────────────────────────────────
        # Utilise file_name comme identifiant de lien (compatible toutes versions ebooklib)
        book.toc   = [epub.Link(c.file_name, c.title, c.file_name) for c in epub_chapters]
        book.spine = ['nav'] + epub_chapters

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # ── Écriture ──────────────────────────────────────────────────
        epub.write_epub(output_path, book, {})
        if self._ascii_art_count:
            self.log(
                f"{self._ascii_art_count} bloc(s) ASCII art détecté(s) et encapsulé(s) en <pre>"
            )
        self.log(f"EPUB généré ({len(epub_chapters)} chapitre(s)) : {output_path}")

    # ------------------------------------------------------------------ #
    #  Rendu HTML                                                          #
    # ------------------------------------------------------------------ #

    def _render_toc_chapter(
        self, chapters: list, title: str, lang: str, self_idx: int
    ) -> bytes:
        """
        Remplace la TOC imprimée (illisible car 2 colonnes PDF) par une
        liste de navigation propre générée depuis les titres des chapitres.
        """
        parts = ['<nav epub:type="toc">', '<ol>']
        for j, ch in enumerate(chapters):
            if j == self_idx:
                continue
            ch_title = (ch.get('title') or f'Chapitre {j + 1}').strip()
            fname    = f'chapter_{j:03d}.xhtml'
            parts.append(f'  <li><a href="{fname}">{_esc(ch_title)}</a></li>')
        parts += ['</ol>', '</nav>']
        body = '\n'.join(parts)
        html = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" '
            f'xmlns:epub="http://www.idpf.org/2007/ops" '
            f'xml:lang="{lang}" lang="{lang}">\n'
            '<head>\n'
            '  <meta charset="utf-8"/>\n'
            f'  <title>{_esc(title)}</title>\n'
            '  <link rel="stylesheet" type="text/css" href="../style/main.css"/>\n'
            '</head>\n'
            '<body>\n'
            f'<h1>{_esc(title)}</h1>\n'
            f'{body}\n'
            '</body>\n'
            '</html>\n'
        )
        return html.encode('utf-8')

    def _render_chapter(
        self, blocks: list, title: str, lang: str, mode: str, is_index: bool = False
    ) -> bytes:
        if is_index:
            body = self._index_body(blocks)
        elif mode == 'plain':
            body = self._plain_body(blocks)
        else:
            body = self._structured_body(blocks, title)
            # Post-traitement : résoudre les césures inter-blocs et
            # simplifier les listes à un seul item en paragraphes.
            body = _fix_hyphenation(body)
            body = _fix_singleton_lists(body)

        html = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">\n'
            '<head>\n'
            '  <meta charset="utf-8"/>\n'
            f'  <title>{_esc(title)}</title>\n'
            '  <link rel="stylesheet" type="text/css" href="../style/main.css"/>\n'
            '</head>\n'
            '<body>\n'
            f'<h1>{_esc(title)}</h1>\n'
            f'{body}\n'
            '</body>\n'
            '</html>\n'
        )
        return html.encode('utf-8')

    def _structured_body(self, blocks: list, title: str = '') -> str:
        """Corps HTML structuré : détecte titres, paragraphes et sidebar."""
        main_blocks    = [b for b in blocks if not b.get('is_sidebar')]
        sidebar_blocks = [b for b in blocks if b.get('is_sidebar')]

        parts = self._render_blocks(main_blocks, skip_title=title)

        if not parts:
            parts.append('<p><em>(Contenu non extrait ou supprimé par le nettoyage)</em></p>')

        # Sidebar en annexe (mode 'sidebar_annex') — rendue comme notes structurées
        if sidebar_blocks:
            note_parts = self._render_sidebar_as_notes(sidebar_blocks)
            parts.extend(note_parts)

        return '\n'.join(parts)

    def _render_blocks(self, blocks: list, skip_title: str = '') -> list:
        """
        Transforme une liste de blocs en éléments HTML.

        Les blocs marqués is_ascii_art=True sont regroupés en séquences
        contiguës, puis chaque séquence est reconstruite ligne par ligne
        (via y_rel) et encapsulée dans un <pre>.

        Les blocs normaux sont rendus en <h2>, <strong> ou <p>.

        skip_title : texte du H1 du chapitre — les fragments de ce titre
        (grands blocs en début de chapitre) sont ignorés pour ne pas
        dupliquer le H1 déjà inséré par _render_chapter.
        """
        import re as _re

        # Jeu de labels d'encadrés courants dans les livres techniques (variantes sans accents incluses)
        _NOTE_LABELS_INLINE = frozenset({
            'À RETENIR', 'A RETENIR', 'RETENIR',
            'RÉFÉRENCE', 'REFERENCE',
            'ANALOGIE', 'CONTEXTE',
            'NE VOUS CASSEZ PAS LA TÊTE', 'NE VOUS CASSEZ PAS LA TETE',
            'SOUS LINUX', 'SOUS WINDOWS', 'SOUS MAC',
            'EN PRATIQUE', 'ATTENTION',
            'DÉFINITION', 'DEFINITION',
            'RAPPEL', 'NOTE', 'CONSEIL',
        })
        # Taille de police max pour le corps d'une note en encadré (7-10pt)
        _NOTE_SIZE_MAX = 10.5

        parts       = []
        para_buf    = []   # buffer paragraphe en cours
        ascii_buf   = []   # buffer ASCII art en cours
        bullet_buf  = []   # items finalisés (une chaîne par <li>)
        _cur_li     = []   # fragments de l'item de liste en cours (multi-lignes)
        # Machine à états pour les encadrés de notes (petite police)
        note_mode       = False
        note_label      = ''
        note_body: list = []
        note_x_rel      = -1.0   # x_rel du label de la note en cours (-1 = inconnu)

        # État pour le saut des fragments de titre en début de chapitre
        skip_lower      = skip_title.lower().strip() if skip_title else ''
        skipping_title  = bool(skip_lower)

        # Fragment de petite police précédent pouvant être le début d'un label
        # multi-spans (ex : "À" suivi de "RETENIR" sur la ligne suivante).
        _pending_label_frag = ''

        # Tolérance Y pour considérer deux spans sur la même ligne visuelle.
        # 0.8 % de la hauteur de page = ~6 pt pour une page A4 standard.
        _Y_TOL = 0.008

        def flush_para():
            if para_buf:
                text = ' '.join(para_buf)
                # Récoller les césures cross-span : "con- fi..." → "confi..."
                # Uniquement quand le tiret est en fin de token (pas les tirets
                # légitimes dans "sous-section" ou "Jean-Pierre").
                text = _re.sub(r'([a-zéàèêîôùûçœæ]{2,})-\s+([a-zéàèêîôùûçœæ])',
                               r'\1\2', text)
                parts.append(f'<p>{_esc(text)}</p>')
                para_buf.clear()

        def flush_bullets():
            # D'abord clore l'item en cours si besoin
            if _cur_li:
                item_text = ' '.join(_cur_li)
                item_text = _re.sub(
                    r'([a-zéàèêîôùûçœæ]{2,})-\s+([a-zéàèêîôùûçœæ])', r'\1\2', item_text
                )
                bullet_buf.append(item_text)
                _cur_li.clear()
            if bullet_buf:
                parts.append('<ul>')
                for item in bullet_buf:
                    parts.append(f'  <li>{_esc(item)}</li>')
                parts.append('</ul>')
                bullet_buf.clear()

        def flush_note():
            nonlocal note_mode, note_label, note_body, note_x_rel
            if not note_label and not note_body:
                note_mode  = False
                note_label = ''
                note_body  = []
                return
            lbl  = note_label or 'NOTE'
            slug = (lbl.lower()
                    .replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                    .replace('à', 'a').replace('â', 'a').replace('î', 'i')
                    .replace('ô', 'o').replace('û', 'u').replace('ç', 'c')
                    .replace(' ', '-'))
            parts.append(f'<aside class="note note-{slug}">')
            parts.append(f'  <p class="note-label">{_esc(lbl)}</p>')
            if note_body:
                parts.append(f'  <p>{_esc(" ".join(note_body))}</p>')
            parts.append('</aside>')
            note_mode  = False
            note_label = ''
            note_body  = []
            note_x_rel = -1.0

        def flush_ascii():
            if not ascii_buf:
                return
            import html as _html
            # Regrouper les spans par ligne visuelle (y_rel arrondi)
            lines: dict = {}
            for span in ascii_buf:
                y_key = round(span.get('y_rel', 0) / _Y_TOL) * _Y_TOL
                lines.setdefault(y_key, []).append(span)

            # Reconstruire le texte : trier les lignes par Y, les spans par X
            text_lines = []
            for y_key in sorted(lines):
                row_spans = sorted(lines[y_key], key=lambda s: s.get('x_rel', 0))
                text_lines.append(''.join(s.get('text', '') for s in row_spans))

            content = '\n'.join(text_lines).strip()

            # Certains PDFs produits depuis HTML ont déjà des entités (&lt;, &amp;…)
            # dans le flux texte fitz. On déséchappe d'abord pour ne pas doubler
            # l'échappement (&lt; → &amp;lt; → visible "&lt;" dans la liseuse).
            content = _html.unescape(content)

            # Span monospace court et isolé (valeur saisie en terminal, numéro de menu…)
            # → <code> inline plutôt que <pre> block (évite les <pre>5</pre> parasites)
            if len(text_lines) == 1 and len(content) < 20:
                flush_para()
                parts.append(f'<p><code>{_esc(content)}</code></p>')
            else:
                parts.append(f'<pre>{_esc(content)}</pre>')
                self._ascii_art_count += 1   # un bloc <pre> = un schéma
            ascii_buf.clear()

        for block in blocks:
            # ── Bloc image ────────────────────────────────────────────
            if block.get('type') == 'image':
                flush_para()
                flush_ascii()
                img_key = block.get('img_key', '')
                if img_key:
                    page_label = block.get('page', 0) + 1
                    parts.append(
                        f'<img src="../images/{img_key}" '
                        f'alt="Illustration p.{page_label}" '
                        f'style="max-width:100%;display:block;margin:1.5em auto;"/>'
                    )
                continue

            text = (block.get('text') or '').strip()
            if not text:
                continue

            size     = block.get('font_size', 12) or 12
            flags    = block.get('font_flags', 0) or 0
            is_bold  = bool(flags & (1 << 4))
            x_rel    = block.get('x_rel', 0.0)

            # ── Détection des encadrés de notes (petite police ≤ 10pt) ──
            if size <= _NOTE_SIZE_MAX:
                upper = text.upper().strip()

                # Essayer d'abord la combinaison avec un fragment précédent
                # (ex : "À" + "RETENIR" → "À RETENIR")
                detected_label = ''
                _combined = ''
                if _pending_label_frag and not note_mode:
                    _combined = _pending_label_frag.upper().strip() + ' ' + upper
                    for lbl in _NOTE_LABELS_INLINE:
                        if _combined == lbl or _combined.startswith(lbl + ' '):
                            detected_label = lbl
                            break

                # Sinon essayer le span seul
                if not detected_label:
                    for lbl in _NOTE_LABELS_INLINE:
                        if upper == lbl or upper.startswith(lbl + ' ') or upper.startswith(lbl + '\n'):
                            detected_label = lbl
                            break

                if detected_label:
                    # Si on a consommé le fragment précédent pour former le label,
                    # le retirer du para_buf où il avait été ajouté provisoirement.
                    if _combined and _combined.startswith(detected_label) and _combined != upper:
                        if para_buf and para_buf[-1] == _pending_label_frag:
                            para_buf.pop()
                    _pending_label_frag = ''
                    flush_para(); flush_ascii(); flush_bullets(); flush_note()
                    note_label = detected_label
                    note_mode  = True
                    note_x_rel = x_rel   # ancrer la zone X de la note
                    # Corps inline (label suivi de texte dans le même span)
                    _src = _combined if _combined.startswith(detected_label) else upper
                    inline_body = _src[len(detected_label):].strip()
                    if inline_body:
                        note_body.append(inline_body)
                    continue
                elif note_mode:
                    _pending_label_frag = ''
                    # Vérifier que le span est dans la même zone X que la note
                    # (tolérance ±20% de la largeur page) ; sinon sortir de la note.
                    if note_x_rel >= 0 and abs(x_rel - note_x_rel) > 0.20:
                        flush_note()
                        # Fall through → traiter normalement
                    else:
                        # On est dans une note → accumuler le corps
                        note_body.append(text)
                        continue
                else:
                    # Ce fragment pourrait-il être le début d'un label multi-mots ?
                    if any(lbl.startswith(upper + ' ') for lbl in _NOTE_LABELS_INLINE):
                        _pending_label_frag = text   # mémoriser, émettre provisoirement
                    else:
                        _pending_label_frag = ''
                    # Petit texte hors note (légende, numéro…) → para normal
                    pass

            elif note_mode:
                # Taille normale : fermer la note si elle a du contenu ET qu'on
                # rencontre un titre, OU si elle a déjà accumulé assez de texte,
                # OU si le span est hors de la zone X de la note (corps principal).
                _pending_label_frag = ''
                is_section_title = size > 24 or (size > 14 and is_bold)
                out_of_zone = (note_x_rel >= 0 and abs(x_rel - note_x_rel) > 0.20)
                if is_section_title or len(' '.join(note_body)) > 600 or out_of_zone:
                    flush_note()
                    # Fall through → ce bloc sera traité normalement ci-dessous
                else:
                    note_body.append(text)
                    continue

            # ── Puces ─────────────────────────────────────────────────
            if block.get('is_bullet'):
                flush_para(); flush_ascii()
                # Clore l'item précédent et commencer le nouveau
                if _cur_li:
                    item_text = ' '.join(_cur_li)
                    item_text = _re.sub(
                        r'([a-zéàèêîôùûçœæ]{2,})-\s+([a-zéàèêîôùûçœæ])',
                        r'\1\2', item_text,
                    )
                    bullet_buf.append(item_text)
                    _cur_li.clear()
                _cur_li.append(text)
                continue

            elif block.get('is_bullet_continuation'):
                flush_para(); flush_ascii()
                _cur_li.append(text)   # continuation de la même <li>
                continue

            # Tout bloc non-bullet/-continuation ferme la liste en cours
            flush_bullets()

            if block.get('is_ascii_art'):
                # Passer en mode ASCII art : vider le buffer paragraphe
                flush_para()
                ascii_buf.append(block)
            else:
                # Passer en mode normal : vider le buffer ASCII art
                flush_ascii()

                # Seuils de taille :
                # > 24pt → toujours un titre (même sans bold, ex: titre de chapitre 36pt)
                # > 14pt + bold → sous-titre de section
                is_chapter_title = size > 24
                is_section_title = size > 14 and is_bold

                # ── Sauter les fragments du titre de chapitre (déjà en H1) ──
                if skipping_title and (is_chapter_title or is_section_title):
                    text_lower = text.lower()
                    if (text_lower in skip_lower
                            or skip_lower.startswith(text_lower)
                            or text_lower in skip_lower):
                        continue   # fragment du H1 → ignoré
                    # Texte qui n'appartient pas au titre → fin de la zone de saut
                    skipping_title = False
                elif skipping_title and not is_chapter_title:
                    skipping_title = False  # premier bloc corps → fin du saut

                if is_chapter_title or is_section_title:
                    flush_para()
                    parts.append(f'<h2>{_esc(text)}</h2>')
                elif is_bold:
                    flush_para()
                    parts.append(f'<p><strong>{_esc(text)}</strong></p>')
                else:
                    para_buf.append(text)

        flush_para()
        flush_ascii()
        flush_bullets()
        flush_note()
        return parts

    def _render_sidebar_as_notes(self, blocks: list) -> list:
        """
        Convertit les blocs de sidebar en encadrés <aside class="note">.

        Les titres d'encadrés ("À RETENIR", "RÉFÉRENCE"…) sont détectés par
        accumulation de spans gras consécutifs. Un encadré commence à chaque
        titre détecté et inclut les spans suivants (sous-titre gras + texte).
        Les spans ne formant pas de note reconnue → <aside class="sidebar">.
        """
        _NOTE_LABELS = {
            'À RETENIR', 'A RETENIR', 'RÉFÉRENCE', 'REFERENCE',
            'CONTEXTE', 'EN PRATIQUE', 'ATTENTION', 'CONSEIL',
            'DÉFINITION', 'DEFINITION', 'RAPPEL', 'NOTE',
            'SOUS LINUX', 'SOUS WINDOWS',
        }

        def _css_slug(label: str) -> str:
            return (
                label.lower()
                .replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                .replace('à', 'a').replace('â', 'a').replace('î', 'i')
                .replace('ô', 'o').replace('û', 'u').replace('ç', 'c')
                .replace(' ', '-')
            )

        parts: list = []
        # État courant
        cur_label    = ''
        cur_subtitle = ''
        cur_body: list = []
        label_accum: list = []   # accumule les fragments du label en cours

        def flush_note():
            nonlocal cur_label, cur_subtitle, cur_body, label_accum
            if not cur_label and not cur_body:
                return
            label = cur_label or 'NOTE'
            slug  = _css_slug(label)
            parts.append(f'<aside class="note note-{slug}">')
            parts.append(f'  <h4 class="note-label">{_esc(label)}</h4>')
            if cur_subtitle:
                parts.append(
                    f'  <p class="note-subtitle"><strong>{_esc(cur_subtitle)}</strong></p>'
                )
            if cur_body:
                parts.append(f'  <p>{_esc(" ".join(cur_body))}</p>')
            parts.append('</aside>')
            cur_label = ''
            cur_subtitle = ''
            cur_body = []
            label_accum = []

        # 'seeking' → 'subtitle' → 'body'
        state = 'seeking'

        for block in blocks:
            text  = (block.get('text') or '').strip()
            if not text:
                continue
            size  = block.get('font_size', 12) or 12
            flags = block.get('font_flags', 0) or 0
            is_bold = bool(flags & (1 << 4)) or size > 11

            upper = text.upper()

            # Essayer d'identifier un label en accumulant les fragments gras
            if is_bold:
                label_accum.append(upper)
                candidate = ' '.join(label_accum)
                if candidate in _NOTE_LABELS or upper in _NOTE_LABELS:
                    flush_note()
                    cur_label   = candidate if candidate in _NOTE_LABELS else upper
                    label_accum = []
                    state       = 'subtitle'
                    continue
                # Candidat trop long → ce n'est pas un label
                if len(candidate) > 30:
                    # Traiter l'accumulé comme texte normal
                    if state == 'subtitle':
                        cur_subtitle = ' '.join(b for b in label_accum if b != upper)
                        cur_body.append(text)
                        state = 'body'
                    elif state == 'body':
                        cur_body.append(text)
                    else:
                        # Pas de note en cours → ouvrir une note générique
                        flush_note()
                        cur_label   = 'NOTE'
                        cur_body.append(text)
                        state = 'body'
                    label_accum = []
                    continue
                # Fragment court → attendre le prochain span
                continue

            # Span non-gras : réinitialiser l'accumulateur de label
            label_accum = []

            if state == 'subtitle':
                cur_subtitle = text
                state = 'body'
            elif state == 'body':
                cur_body.append(text)
            else:
                # Texte hors contexte de note → ouvrir une note générique
                flush_note()
                cur_label = 'NOTE'
                cur_body.append(text)
                state = 'body'

        flush_note()
        return parts

    def _index_body(self, blocks: list) -> str:
        """
        Construit un <dl class="book-index"> à partir des blocs de l'index.

        Heuristique : un terme gras (ou de grande taille) est un <dt> ;
        les numéros qui suivent (chiffres/virgules) sont un <dd>.
        Les lettres séparatrices (A, B, C…) reçoivent la classe index-letter.
        """
        import re as _re

        entries: list = []   # [(term, pages_str)]
        current_term  = ''
        current_pages: list = []
        _num_re       = _re.compile(r'^[\d,;\s]+$')

        def flush_entry():
            nonlocal current_term, current_pages
            if current_term:
                entries.append((current_term, ', '.join(current_pages)))
            current_term  = ''
            current_pages = []

        # L'index PDF est souvent en 2 colonnes : fitz extrait les blocs triés
        # par Y global (les deux colonnes sont mélangées). On les retrie par
        # colonne (gauche d'abord) puis par Y pour retrouver l'ordre alphabétique.
        blocks = sorted(
            blocks,
            key=lambda b: (0 if b.get('x_rel', 0) < 0.5 else 1, b.get('y_rel', 0))
        )

        for block in blocks:
            text  = (block.get('text') or '').strip()
            if not text:
                continue
            size  = block.get('font_size', 12) or 12
            flags = block.get('font_flags', 0) or 0
            is_bold = bool(flags & (1 << 4)) or size > 11

            # Séparateur alphabétique visuel du PDF (lettre seule A, B, C…)
            # → ces blocs délimitent les sections mais ne sont pas des termes.
            # La génération de <dt class="index-letter"> est gérée automatiquement
            # par le premier terme de chaque nouvelle lettre.
            if len(text) == 1 and text.isalpha():
                flush_entry()
                continue

            if _num_re.match(text):
                # Numéro(s) de page → associer au terme en cours
                current_pages.extend(p.strip() for p in _re.split(r'[,;]', text) if p.strip())
            elif is_bold:
                flush_entry()
                current_term = text
            else:
                # Texte non gras non numérique : peut être la suite du terme
                if current_term and not current_pages:
                    current_term += ' ' + text
                else:
                    flush_entry()
                    current_term = text

        flush_entry()

        if not entries:
            return '<p><em>(Index non extrait)</em></p>'

        # Clé de tri insensible à la casse et aux accents
        _ACCENT_MAP = str.maketrans(
            'ÉÈÊËÀÂÄÎÏÔÖÙÛÜÇéèêëàâäîïôöùûüç',
            'EEEEAAAIIOOUUUCeeeeaaaiioouuuc',
        )
        def _sort_key(term: str) -> str:
            return term.lower().translate(_ACCENT_MAP)

        # Dédupliquer (même terme normalisé) puis trier alphabétiquement
        seen: set = set()
        unique: list = []
        for term, pages in entries:
            k = _sort_key(term)
            if k not in seen:
                seen.add(k)
                unique.append((term, pages))
        entries = sorted(unique, key=lambda p: _sort_key(p[0]))

        # Table de normalisation pour la lettre initiale (séparateurs)
        _FIRST_NORM = str.maketrans('ÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ', 'EEEEAAAIIOOUUUC')

        html = '<dl class="book-index">\n'
        cur_letter = ''
        for term, pages in entries:
            letter = term[0].upper().translate(_FIRST_NORM) if term else ''
            if letter.isalpha() and letter != cur_letter:
                cur_letter = letter
                html += f'  <dt class="index-letter">{_esc(letter)}</dt>\n'
            html += f'  <dt>{_esc(term)}</dt>\n'
            if pages:
                html += f'  <dd>{_esc(pages)}</dd>\n'
        html += '</dl>\n'
        return html

    def _plain_body(self, blocks: list) -> str:
        """Corps HTML texte brut continu (optimal TTS)."""
        texts = [
            (block.get('text') or '').strip()
            for block in blocks
            if (block.get('text') or '').strip()
        ]
        content = ' '.join(texts) if texts else '(Contenu non extrait)'
        return f'<p>{_esc(content)}</p>'

    # ------------------------------------------------------------------ #
    #  Images                                                              #
    # ------------------------------------------------------------------ #

    def _add_images(self, book: epub.EpubBook, images: list):
        for img in images:
            page  = img.get('page', 0)
            idx   = img.get('index', 0)
            ext   = (img.get('ext') or 'png').lower()
            data  = img.get('data', b'')
            if not data:
                continue
            mime  = 'image/jpeg' if ext in ('jpg', 'jpeg') else f'image/{ext}'
            item  = epub.EpubItem(
                uid=f"img-{page}-{idx}",
                file_name=f"images/img_{page}_{idx}.{ext}",
                media_type=mime,
                content=data,
            )
            book.add_item(item)


# ------------------------------------------------------------------ #
#  Utilitaire                                                          #
# ------------------------------------------------------------------ #

def _esc(text: str) -> str:
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
    )


def _fix_hyphenation(html: str) -> str:
    """
    Résoud les césures typographiques qui ont traversé des frontières de blocs.

    Cas 1 : "com- mande" dans le même nœud texte (défensif).
    Cas 2 : "fin-</p>\\n<p>suite" → les deux moitiés rejointes, balises conservées.
    """
    import re as _re

    # Cas 1 : deux moitiés séparées par un espace dans le même élément
    html = _re.sub(
        r'([A-Za-zÀ-öø-ÿ]{2,})-\s+([a-zàâçéèêëîïôùûüÿœæ])',
        lambda m: m.group(1) + m.group(2),
        html,
    )

    # Cas 2 : césure inter-blocs "...mot-</tag>\n<tag>suite..."
    # Le mot recolle ; les balises fermante et ouvrante sont conservées en place.
    html = _re.sub(
        r'([A-Za-zÀ-öø-ÿ]{2,})-(</(?:p|li|dd|dt)>)(\s*)(<(?:p|li|dd|dt)[^>]*>)'
        r'([a-zàâçéèêëîïôùûüÿœæ]\w*)',
        lambda m: (
            m.group(1) + m.group(5)   # mot complet
            + m.group(2) + m.group(3) # tag fermant + espaces
            + m.group(4)              # tag ouvrant
        ),
        html,
    )
    return html


def _fix_singleton_lists(html: str) -> str:
    """
    Convertit les listes à un seul item en paragraphes simples.
    Les items commençant par '–' sont conservés tels quels (listes réelles sans puce).
    """
    import re as _re

    def _replace(m: '_re.Match') -> str:
        content = m.group(1)
        if content.lstrip().startswith('–'):
            return m.group(0)          # liste réelle → ne pas toucher
        return f'<p>{content}</p>'

    return _re.sub(
        r'<ul>\s*<li>((?:(?!</li>).)*)</li>\s*</ul>',
        _replace,
        html,
        flags=_re.DOTALL,
    )
