"""Notion : Girlypop y écrit tes fiches de cours.

Comment ça marche :
- Tu crées une « intégration » Notion (un compte robot) et tu copies son token dans .env.
- Tu partages UNE page de ton Notion avec elle (ex : « 📚 Cours »). Girlypop ne voit que
  cette page et ce qu'il y a dedans : le reste de ton Notion lui est invisible.
- Elle crée ses fiches comme sous-pages de cette page.

Claude écrit le contenu en Markdown simple (titres, listes, gras...). Notion, lui, ne
comprend pas le Markdown : il veut une liste de « blocs » JSON. La fonction
`markdown_to_blocks` fait la traduction. Elle est pure (pas de réseau) et testée.
"""

import re
from typing import Optional

from notion_client import Client

MAX_TEXT = 2000  # Notion refuse un morceau de texte de plus de 2000 caractères
MAX_BLOCKS_PER_REQUEST = 100  # ...et plus de 100 blocs par requête

# Le gras, l'italique, le code et les liens à l'intérieur d'une ligne.
INLINE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?://[^)]+)\)|\*(.+?)\*")

# Les langages de code que Notion accepte (les autres deviennent "plain text").
CODE_LANGUAGES = {"python", "c", "c++", "java", "javascript", "typescript", "bash", "shell", "sql",
                  "html", "css", "json", "markdown", "r", "latex"}


def rich_text(text: str) -> list[dict]:
    """Une ligne de Markdown -> la liste de morceaux de texte Notion (avec gras, italique...)."""
    parts: list[dict] = []
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            parts += _chunks(text[pos:m.start()])
        bold, code, link_text, url, italic = m.groups()
        if bold is not None:
            parts += _chunks(bold, bold=True)
        elif code is not None:
            parts += _chunks(code, code=True)
        elif link_text is not None:
            parts += _chunks(link_text, url=url)
        else:
            parts += _chunks(italic, italic=True)
        pos = m.end()
    if pos < len(text):
        parts += _chunks(text[pos:])
    return parts


def _chunks(text: str, bold=False, italic=False, code=False, url: Optional[str] = None) -> list[dict]:
    out = []
    for i in range(0, len(text), MAX_TEXT):
        piece: dict = {"type": "text", "text": {"content": text[i:i + MAX_TEXT]}}
        if url:
            piece["text"]["link"] = {"url": url}
        if bold or italic or code:
            piece["annotations"] = {"bold": bold, "italic": italic, "code": code}
        out.append(piece)
    return out


def _block(kind: str, text: str, **extra) -> dict:
    return {"object": "block", "type": kind, kind: {"rich_text": rich_text(text), **extra}}


def markdown_to_blocks(markdown: str) -> list[dict]:
    """Traduit le Markdown simple écrit par Claude en blocs Notion.

    Compris : # ## ### titres, - listes, 1. listes numérotées, - [ ] cases à cocher,
    > citations, ```code```, --- séparateur, et le texte normal (paragraphes).
    """
    blocks: list[dict] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        i += 1

        if not stripped:
            continue
        if stripped.startswith("```"):  # bloc de code : on lit jusqu'au ``` de fin
            language = stripped[3:].strip().lower()
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # saute le ``` de fin
            text = "\n".join(code_lines)
            blocks.append({"object": "block", "type": "code", "code": {
                "rich_text": _chunks(text), "language": language if language in CODE_LANGUAGES else "plain text"}})
        elif stripped in ("---", "***"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif m := re.match(r"^(#{1,3})\s+(.*)", stripped):
            blocks.append(_block(f"heading_{len(m.group(1))}", m.group(2)))
        elif m := re.match(r"^[-*]\s+\[( |x|X)\]\s+(.*)", stripped):
            blocks.append(_block("to_do", m.group(2), checked=m.group(1).lower() == "x"))
        elif m := re.match(r"^[-*]\s+(.*)", stripped):
            blocks.append(_block("bulleted_list_item", m.group(1)))
        elif m := re.match(r"^\d+[.)]\s+(.*)", stripped):
            blocks.append(_block("numbered_list_item", m.group(1)))
        elif stripped.startswith(">"):
            blocks.append(_block("quote", stripped.lstrip("> ")))
        else:
            blocks.append(_block("paragraph", stripped))
    return blocks


def page_title(page: dict) -> str:
    """Retrouve le titre d'une page dans la réponse (un peu touffue) de l'API Notion."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop["title"]) or "(sans titre)"
    return "(sans titre)"


class NotionNotes:
    def __init__(self, token: str, parent_page_id: str):
        self._client = Client(auth=token)
        self._parent = parent_page_id

    def create_page(self, title: str, markdown: str, emoji: str = "📚",
                    parent_page_id: Optional[str] = None) -> dict:
        blocks = markdown_to_blocks(markdown)
        page = self._client.pages.create(
            parent={"page_id": parent_page_id or self._parent},
            icon={"type": "emoji", "emoji": emoji},
            properties={"title": {"title": [{"text": {"content": title[:MAX_TEXT]}}]}},
            children=blocks[:MAX_BLOCKS_PER_REQUEST],
        )
        self._append(page["id"], blocks[MAX_BLOCKS_PER_REQUEST:])
        return {"id": page["id"], "title": title, "url": page.get("url"), "blocks": len(blocks)}

    def append_to_page(self, page_id: str, markdown: str) -> dict:
        blocks = markdown_to_blocks(markdown)
        self._append(page_id, blocks)
        return {"id": page_id, "added_blocks": len(blocks)}

    def search_pages(self, query: str = "") -> list[dict]:
        """Les pages que Girlypop peut voir (donc celles sous ta page partagée) qui contiennent `query`."""
        result = self._client.search(query=query, filter={"property": "object", "value": "page"}, page_size=20)
        return [{"id": p["id"], "title": page_title(p), "url": p.get("url")} for p in result.get("results", [])]

    def _append(self, page_id: str, blocks: list[dict]) -> None:
        for start in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
            self._client.blocks.children.append(block_id=page_id, children=blocks[start:start + MAX_BLOCKS_PER_REQUEST])
