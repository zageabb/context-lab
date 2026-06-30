from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from database import db
from models import ContextEnvironment, EnvironmentDocument, EnvironmentPrompt
from services.document_extraction import extract_text
from services.file_storage import ensure_environment_directories, save_environment_upload
from services.prompt_service import ensure_environment_prompts, save_prompt_content
from services.rag_service import refresh_document_chunks
from services.settings_service import get_setting


environments_bp = Blueprint("environments", __name__, url_prefix="/environments")


@environments_bp.route("/")
def list_environments():
    environments = ContextEnvironment.query.order_by(ContextEnvironment.updated_at.desc()).all()
    return render_template(
        "environments/list.html",
        environments=environments,
        chat_context={"page": "environments"},
    )


@environments_bp.route("/new", methods=["GET", "POST"])
def create_environment():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("A name is required.", "danger")
            return render_template("environments/form.html", environment=None, chat_context={"page": "environment-create"})
        slug = _unique_slug(name)
        environment = ContextEnvironment(
            name=name,
            slug=slug,
            description=request.form.get("description", "").strip() or None,
            status=request.form.get("status", "").strip() or "Draft",
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(environment)
        db.session.commit()
        ensure_environment_directories(current_app.config["DATA_DIR"], environment.id)
        ensure_environment_prompts(current_app.config["DATA_DIR"], environment, db)
        flash("Saved environment created.", "success")
        return redirect(url_for("environments.view_environment", environment_id=environment.id))
    return render_template("environments/form.html", environment=None, chat_context={"page": "environment-create"})


@environments_bp.route("/<int:environment_id>", methods=["GET", "POST"])
def view_environment(environment_id: int):
    environment = ContextEnvironment.query.get_or_404(environment_id)
    ensure_environment_prompts(current_app.config["DATA_DIR"], environment, db)
    if request.method == "POST":
        environment.name = request.form.get("name", environment.name).strip() or environment.name
        environment.description = request.form.get("description", "").strip() or None
        environment.status = request.form.get("status", "Draft").strip() or "Draft"
        environment.notes = request.form.get("notes", "").strip() or None
        for prompt in environment.prompts:
            field_name = f"prompt__{prompt.key}"
            if field_name in request.form:
                save_prompt_content(current_app.config["DATA_DIR"], prompt, request.form.get(field_name, ""))
        db.session.commit()
        flash("Environment updated.", "success")
        return redirect(url_for("environments.view_environment", environment_id=environment.id))
    return render_template(
        "environments/detail.html",
        environment=environment,
        prompts=sorted(environment.prompts, key=lambda prompt: prompt.title.lower()),
        chat_context={"page": "environment-detail", "environment_id": environment.id},
    )


@environments_bp.route("/<int:environment_id>/upload", methods=["POST"])
def upload_document(environment_id: int):
    environment = ContextEnvironment.query.get_or_404(environment_id)
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Choose a file to upload.", "danger")
        return redirect(url_for("environments.view_environment", environment_id=environment.id))

    original_name = secure_filename(upload.filename or "upload")
    existing = EnvironmentDocument.query.filter_by(
        environment_id=environment.id,
        original_filename=original_name,
    ).first()
    original_name, stored_name, saved_path = save_environment_upload(current_app.config["DATA_DIR"], environment.id, upload)
    text, error = extract_text(saved_path)
    extracted_text_path = None
    if text:
        base_dir = ensure_environment_directories(current_app.config["DATA_DIR"], environment.id)
        extracted_text_path = base_dir / "extracted_text" / f"{Path(stored_name).stem}.md"
        extracted_text_path.write_text(text, encoding="utf-8")

    if existing is None:
        document = EnvironmentDocument(
            environment=environment,
            original_filename=original_name,
            stored_filename=stored_name,
            file_path=str(saved_path),
            file_type=Path(original_name).suffix.lower().lstrip("."),
            extracted_text=text or None,
            extracted_text_path=str(extracted_text_path) if extracted_text_path else None,
            processed=bool(text),
            processing_notes=error or "Processed during upload.",
        )
        db.session.add(document)
    else:
        existing.stored_filename = stored_name
        existing.file_path = str(saved_path)
        existing.file_type = Path(original_name).suffix.lower().lstrip(".")
        existing.extracted_text = text or None
        existing.extracted_text_path = str(extracted_text_path) if extracted_text_path else None
        existing.processed = bool(text)
        existing.processing_notes = error or "Reprocessed during upload."
        existing.chunks.clear()
        existing.rag_ready = False
        document = existing

    if text:
        chunk_size = int(get_setting("retrieval_chunk_size", "1400") or "1400")
        chunk_overlap = int(get_setting("retrieval_chunk_overlap", "250") or "250")
        chunk_count = refresh_document_chunks(document, chunk_size=chunk_size, overlap=chunk_overlap)
        document.rag_ready = chunk_count > 0
    db.session.commit()
    if text:
        flash(f"Uploaded and processed {original_name}.", "success")
    else:
        flash(f"Uploaded {original_name}, but text extraction failed: {error}", "warning")
    return redirect(url_for("environments.view_environment", environment_id=environment.id))


@environments_bp.route("/<int:environment_id>/documents/<int:document_id>/reprocess", methods=["POST"])
def reprocess_document(environment_id: int, document_id: int):
    environment = ContextEnvironment.query.get_or_404(environment_id)
    document = EnvironmentDocument.query.filter_by(environment_id=environment.id, id=document_id).first_or_404()
    text, error = extract_text(document.file_path)
    document.extracted_text = text or None
    document.processed = bool(text)
    document.processing_notes = error or "Reprocessed manually."
    document.chunks.clear()
    document.rag_ready = False
    if text:
        chunk_size = int(get_setting("retrieval_chunk_size", "1400") or "1400")
        chunk_overlap = int(get_setting("retrieval_chunk_overlap", "250") or "250")
        refresh_document_chunks(document, chunk_size=chunk_size, overlap=chunk_overlap)
    db.session.commit()
    flash("Document reprocessed.", "success" if text else "warning")
    return redirect(url_for("environments.view_environment", environment_id=environment.id))


def _unique_slug(name: str) -> str:
    base = secure_filename(name).lower().strip("-") or "environment"
    slug = base
    counter = 2
    while ContextEnvironment.query.filter_by(slug=slug).first() is not None:
        slug = f"{base}-{counter}"
        counter += 1
    return slug
