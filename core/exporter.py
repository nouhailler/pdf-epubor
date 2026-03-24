"""Export en formats TXT et HTML"""

import os
from typing import Callable, Optional


class Exporter:
    def __init__(self, log_fn: Optional[Callable] = None):
        self.log = log_fn or (lambda msg: None)

    def to_txt(self, cleaned_data: dict, output_path: str):
        """Exporte en texte brut."""
        chapters = cleaned_data.get('chapters', [])
        lines = []

        for chapter in chapters:
            title = chapter.get('title', '')
            if title:
                lines.append(f"\n{'='*60}\n{title}\n{'='*60}\n")
            for block in chapter.get('blocks', []):
                text = block.get('text', '').strip()
                if text:
                    lines.append(text)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        self.log(f"TXT exporté : {output_path}")

    def to_html(self, cleaned_data: dict, output_path: str):
        """Exporte en HTML autonome."""
        chapters = cleaned_data.get('chapters', [])

        html_parts = [
            '<!DOCTYPE html>',
            '<html lang="fr">',
            '<head><meta charset="utf-8">',
            '<style>',
            'body { font-family: Georgia, serif; max-width: 800px; margin: 2em auto; line-height: 1.6; }',
            'h1 { border-bottom: 2px solid #333; }',
            'h2 { color: #444; }',
            'p { text-align: justify; margin: 0.5em 0; }',
            '</style></head><body>',
        ]

        for chapter in chapters:
            title = chapter.get('title', '')
            if title:
                html_parts.append(f'<h2>{self._esc(title)}</h2>')
            para_texts = []
            for block in chapter.get('blocks', []):
                text = block.get('text', '').strip()
                if text:
                    para_texts.append(text)
            if para_texts:
                html_parts.append(f'<p>{self._esc(" ".join(para_texts))}</p>')

        html_parts.append('</body></html>')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        self.log(f"HTML exporté : {output_path}")

    @staticmethod
    def _esc(text: str) -> str:
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;'))
