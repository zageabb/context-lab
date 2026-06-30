from __future__ import annotations

import math
import re
from collections import Counter

from models import DocumentChunk, EnvironmentDocument, SharedRAGChunk, SharedRAGDocument


def chunk_text(text: str, chunk_size: int = 1400, overlap: int = 250) -> list[str]:
    normalized = " ".join((text or "").split())
    if not normalized:
        return []
    if chunk_size <= overlap:
        overlap = 0
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = end - overlap if overlap > 0 else end
    return chunks


def refresh_document_chunks(document: EnvironmentDocument, chunk_size: int, overlap: int) -> int:
    document.chunks.clear()
    chunks = chunk_text(document.extracted_text or "", chunk_size=chunk_size, overlap=overlap)
    for index, chunk in enumerate(chunks):
        document.chunks.append(
            DocumentChunk(
                chunk_index=index,
                chunk_text=chunk,
                token_estimate=max(1, math.ceil(len(chunk) / 4)),
            )
        )
    document.rag_ready = bool(chunks)
    return len(chunks)


def refresh_shared_rag_chunks(document: SharedRAGDocument, chunk_size: int, overlap: int) -> int:
    document.chunks.clear()
    chunks = chunk_text(document.extracted_text or "", chunk_size=chunk_size, overlap=overlap)
    for index, chunk in enumerate(chunks):
        document.chunks.append(
            SharedRAGChunk(
                chunk_index=index,
                chunk_text=chunk,
                token_estimate=max(1, math.ceil(len(chunk) / 4)),
            )
        )
    return len(chunks)


def retrieve_relevant_chunks(
    documents: list,
    query: str,
    top_k: int = 6,
    source_label: str = "Environment selection",
) -> list[dict]:
    query_terms = _terms(query)
    if not query_terms:
        return []
    scored: list[tuple[float, object, object]] = []
    for document in documents:
        for chunk in document.chunks:
            chunk_terms = _terms(chunk.chunk_text)
            score = _overlap_score(query_terms, chunk_terms)
            if score <= 0:
                continue
            scored.append((score, document, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for score, document, chunk in scored[:top_k]:
        results.append(
            {
                "document_id": document.id,
                "document_name": getattr(document, "original_filename", None) or getattr(document, "title", "Untitled document"),
                "chunk_index": chunk.chunk_index,
                "score": round(score, 3),
                "text": chunk.chunk_text,
                "source_label": source_label,
            }
        )
    return results


def format_retrieved_context(retrieved_chunks: list[dict]) -> str:
    if not retrieved_chunks:
        return "No highly relevant stored chunks were retrieved from the selected documents."
    sections = []
    for chunk in retrieved_chunks:
        sections.append(
            f"Source: {chunk['source_label']} | Document: {chunk['document_name']} | Chunk: {chunk['chunk_index']} | Score: {chunk['score']}\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(sections)


def _terms(text: str) -> Counter:
    words = re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
    return Counter(words)


def _overlap_score(query_terms: Counter, chunk_terms: Counter) -> float:
    overlap = set(query_terms) & set(chunk_terms)
    if not overlap:
        return 0.0
    return sum(min(query_terms[word], chunk_terms[word]) for word in overlap)
