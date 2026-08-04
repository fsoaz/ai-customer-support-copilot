"""Hybrid dense + lexical retrieval with RRF and optional cross-encoder rerank."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from evals.harness.rerank import CrossEncoderReranker
from evals.harness.rrf import collapse_chunks_to_docs, reciprocal_rank_fusion
from evals.harness.store import ChunkStore


@dataclass(frozen=True)
class RetrieveResult:
    """Document-level ranking after collapsing chunk hits."""

    ranked_docs: list[tuple[str, float]]  # (gold_doc_id, score)
    dense_chunk_ids: list[str]
    lexical_chunk_ids: list[str]
    reranked: bool


class HybridRetriever:
    def __init__(
        self,
        store: ChunkStore,
        *,
        embeddings: np.ndarray,
        chunk_ids: list[str],
        doc_ids: list[str],
        dense_top_k: int = 50,
        lexical_top_k: int = 50,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        lexical_weight: float = 1.0,
        reranker: CrossEncoderReranker | None = None,
        rerank_candidates: int = 50,
    ) -> None:
        if embeddings.ndim != 2:
            raise ValueError("embeddings must be 2-D")
        if len(chunk_ids) != embeddings.shape[0] or len(doc_ids) != embeddings.shape[0]:
            raise ValueError("chunk_ids/doc_ids length must match embedding rows")
        self.store = store
        self.embeddings = embeddings
        self.chunk_ids = chunk_ids
        self.doc_ids = doc_ids
        self.dense_top_k = dense_top_k
        self.lexical_top_k = lexical_top_k
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.lexical_weight = lexical_weight
        self.reranker = reranker
        self.rerank_candidates = rerank_candidates
        self._id_to_doc = dict(zip(chunk_ids, doc_ids, strict=True))

    @classmethod
    def from_store(
        cls,
        store: ChunkStore,
        *,
        dense_top_k: int = 50,
        lexical_top_k: int = 50,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        lexical_weight: float = 1.0,
        reranker: CrossEncoderReranker | None = None,
        rerank_candidates: int = 50,
    ) -> HybridRetriever:
        chunk_ids, doc_ids, matrix = store.load_all_embeddings()
        return cls(
            store,
            embeddings=matrix,
            chunk_ids=chunk_ids,
            doc_ids=doc_ids,
            dense_top_k=dense_top_k,
            lexical_top_k=lexical_top_k,
            rrf_k=rrf_k,
            dense_weight=dense_weight,
            lexical_weight=lexical_weight,
            reranker=reranker,
            rerank_candidates=rerank_candidates,
        )

    def dense_search(self, query_vec: np.ndarray, *, top_k: int | None = None) -> list[str]:
        if self.embeddings.size == 0:
            return []
        k = top_k if top_k is not None else self.dense_top_k
        k = min(k, self.embeddings.shape[0])
        # Rows are L2-normalized → cosine = dot product.
        scores = self.embeddings @ query_vec.astype(np.float32)
        if k == self.embeddings.shape[0]:
            idx = np.argsort(-scores)
        else:
            part = np.argpartition(-scores, k - 1)[:k]
            idx = part[np.argsort(-scores[part])]
        return [self.chunk_ids[i] for i in idx]

    def lexical_search(self, query: str, *, top_k: int | None = None) -> list[str]:
        k = top_k if top_k is not None else self.lexical_top_k
        hits = self.store.lexical_search(query, top_k=k)
        return [chunk_id for chunk_id, _doc, _score in hits]

    def retrieve(self, query: str, query_vec: np.ndarray) -> RetrieveResult:
        dense_ids = self.dense_search(query_vec)
        lexical_ids = self.lexical_search(query)
        fused = reciprocal_rank_fusion(
            [dense_ids, lexical_ids],
            k=self.rrf_k,
            weights=[self.dense_weight, self.lexical_weight],
        )

        if self.reranker is None:
            chunk_ranked: list[tuple[str, str, float]] = []
            for chunk_id, score in fused:
                gold = self._id_to_doc.get(chunk_id)
                if gold is None:
                    continue
                chunk_ranked.append((chunk_id, gold, score))
            docs = collapse_chunks_to_docs(chunk_ranked)
            return RetrieveResult(
                ranked_docs=docs,
                dense_chunk_ids=dense_ids,
                lexical_chunk_ids=lexical_ids,
                reranked=False,
            )

        # Deduplicate to unique docs before CE (Task 0.8): score one passage per doc
        # using the highest-RRF chunk text. Cuts CE cost ~30% vs chunk-level pools and
        # matches gate metrics which are document-level.
        doc_chunk: list[tuple[str, str]] = []  # (doc_id, chunk_id)
        seen_docs: set[str] = set()
        for chunk_id, _score in fused:
            gold = self._id_to_doc.get(chunk_id)
            if gold is None or gold in seen_docs:
                continue
            seen_docs.add(gold)
            doc_chunk.append((gold, chunk_id))
            if len(doc_chunk) >= self.rerank_candidates:
                break

        chunk_ids = [cid for _doc, cid in doc_chunk]
        texts = self.store.get_chunk_texts(chunk_ids)
        # Passage id = gold_doc_id so CE scores map straight to documents.
        passages = [
            (doc_id, texts[cid]) for doc_id, cid in doc_chunk if cid in texts
        ]
        hits = self.reranker.rerank(query, passages)
        docs = [(hit.chunk_id, hit.score) for hit in hits]
        return RetrieveResult(
            ranked_docs=docs,
            dense_chunk_ids=dense_ids,
            lexical_chunk_ids=lexical_ids,
            reranked=True,
        )
