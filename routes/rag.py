from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, url_for

from database import db
from models import ContextEnvironment, EnvironmentDocument, SharedRAGDocument
from services.shared_rag_service import promote_environment_document_to_shared_rag
from services.settings_service import get_setting


rag_bp = Blueprint("rag", __name__, url_prefix="/rag")


@rag_bp.route("/")
def index():
    shared_documents = SharedRAGDocument.query.filter_by(active=True).order_by(SharedRAGDocument.updated_at.desc()).all()
    environments = ContextEnvironment.query.order_by(ContextEnvironment.name.asc()).all()
    return render_template(
        "rag/index.html",
        shared_documents=shared_documents,
        environments=environments,
        chat_context={"page": "shared-rag"},
    )


@rag_bp.route("/promote/<int:environment_id>/<int:document_id>", methods=["POST"])
def promote_document(environment_id: int, document_id: int):
    environment = ContextEnvironment.query.get_or_404(environment_id)
    document = EnvironmentDocument.query.filter_by(environment_id=environment.id, id=document_id).first_or_404()
    if not document.processed or not document.extracted_text:
        flash("Only processed documents with extracted text can be added to shared RAG.", "warning")
        return redirect(url_for("environments.view_environment", environment_id=environment.id))
    chunk_size = int(get_setting("retrieval_chunk_size", "1400") or "1400")
    chunk_overlap = int(get_setting("retrieval_chunk_overlap", "250") or "250")
    shared = promote_environment_document_to_shared_rag(document, chunk_size=chunk_size, overlap=chunk_overlap)
    db.session.add(shared)
    db.session.commit()
    flash(f"Added {document.original_filename} to shared RAG.", "success")
    return redirect(url_for("environments.view_environment", environment_id=environment.id))


@rag_bp.route("/remove/<int:shared_document_id>", methods=["POST"])
def remove_document(shared_document_id: int):
    shared_document = SharedRAGDocument.query.get_or_404(shared_document_id)
    title = shared_document.title
    source_environment_id = shared_document.source_environment_id
    db.session.delete(shared_document)
    db.session.commit()
    flash(f"Removed {title} from shared RAG.", "success")
    if source_environment_id:
        return redirect(url_for("environments.view_environment", environment_id=source_environment_id))
    return redirect(url_for("rag.index"))
