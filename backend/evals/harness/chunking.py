"""Token-window chunking for Stage 0 (~512 tokens, ~15% overlap)."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Whitespace-delimited tokens approximate LLM tokens closely enough for Stage 0
# sweeps; record the scheme in ingest_meta so runs stay comparable.
_TOKEN_RE = re.compile(r"\S+")

DEFAULT_CHUNK_TOKENS = 512
DEFAULT_OVERLAP_RATIO = 0.15


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    token_count: int


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def chunk_text(
    text: str,
    *,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
) -> list[Chunk]:
    """Split text into overlapping windows of roughly ``chunk_tokens`` tokens.

    Overlap is ``floor(chunk_tokens * overlap_ratio)`` tokens. Empty/whitespace-only
    input yields no chunks. Short documents yield a single chunk.
    """
    if chunk_tokens < 1:
        raise ValueError(f"chunk_tokens must be >= 1, got {chunk_tokens}")
    if not 0.0 <= overlap_ratio < 1.0:
        raise ValueError(f"overlap_ratio must be in [0, 1), got {overlap_ratio}")

    tokens = tokenize(text)
    if not tokens:
        return []

    overlap = int(chunk_tokens * overlap_ratio)
    step = max(chunk_tokens - overlap, 1)

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        window = tokens[start:end]
        content = " ".join(window)
        chunks.append(Chunk(index=index, content=content, token_count=len(window)))
        index += 1
        if end >= len(tokens):
            break
        start += step
    return chunks
