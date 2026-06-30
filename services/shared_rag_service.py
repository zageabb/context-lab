from __future__ import annotations

from models import EnvironmentDocument, SharedRAGDocument
from services.rag_service import refresh_shared_rag_chunks


def promote_environment_document_to_shared_rag(document: EnvironmentDocument, chunk_size: int, overlap: int) -> SharedRAGDocument:
    shared = document.shared_rag_document
    if shared is None:
        shared = SharedRAGDocument(
            title=document.original_filename,
            source_type="environment_document",
            original_filename=document.original_filename,
            file_type=document.file_type,
            extracted_text=document.extracted_text,
            processing_notes=document.processing_notes,
            source_environment_id=document.environment_id,
            source_document=document,
            active=True,
        )
    else:
        shared.title = document.original_filename
        shared.original_filename = document.original_filename
        shared.file_type = document.file_type
        shared.extracted_text = document.extracted_text
        shared.processing_notes = document.processing_notes
        shared.source_environment_id = document.environment_id
        shared.active = True
    refresh_shared_rag_chunks(shared, chunk_size=chunk_size, overlap=overlap)
    return shared


def sync_shared_rag_document(document: EnvironmentDocument, chunk_size: int, overlap: int) -> None:
    shared = document.shared_rag_document
    if shared is None:
        return
    shared.title = document.original_filename
    shared.original_filename = document.original_filename
    shared.file_type = document.file_type
    shared.extracted_text = document.extracted_text
    shared.processing_notes = document.processing_notes
    shared.source_environment_id = document.environment_id
    shared.active = bool(document.extracted_text)
    if document.extracted_text:
        refresh_shared_rag_chunks(shared, chunk_size=chunk_size, overlap=overlap)
    else:
        shared.chunks.clear()
