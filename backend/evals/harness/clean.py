"""Strip Auth0 markdown articles down to plain text for chunking."""

from __future__ import annotations

import re

_FRONTMATTER_RE = re.compile(r"^---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```[\w+-]*\r?\n(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_EMPHASIS_RE = re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def markdown_to_text(raw: str) -> str:
    """Convert a markdown article to plain text suitable for embedding."""
    text = raw.replace("\r\n", "\n")
    text = _FRONTMATTER_RE.sub("", text, count=1)
    text = _CODE_FENCE_RE.sub(lambda m: m.group(1).strip(), text)
    text = _IMAGE_RE.sub(lambda m: m.group(1).strip(), text)
    text = _LINK_RE.sub(lambda m: m.group(1), text)
    text = _INLINE_CODE_RE.sub(lambda m: m.group(1), text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HEADING_RE.sub("", text)
    text = _EMPHASIS_RE.sub(lambda m: m.group(1), text)
    text = text.replace("|", " ")
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()
