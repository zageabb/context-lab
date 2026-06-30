from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from database import db
from models import ChatSession, ChatUpload, ContextEnvironment
from services.chat_service import (
    build_chat_response,
    classify_message_intent,
    get_or_create_session,
    get_recent_messages,
    log_chat_exchange,
)
from services.document_extraction import extract_text
from services.file_storage import save_chat_upload
from services.ollama_client import OllamaClient
from services.settings_service import get_setting, get_task_model


chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


@chat_bp.route("/history", methods=["POST"])
def history():
    payload = request.get_json(force=True)
    page_context = payload.get("context") or {}
    environment_id = page_context.get("environment_id")
    session = get_or_create_session(db, environment_id, page_context)
    db.session.commit()
    return jsonify({"messages": get_recent_messages(session)})


@chat_bp.route("/clear", methods=["POST"])
def clear():
    payload = request.get_json(force=True)
    page_context = payload.get("context") or {}
    environment_id = page_context.get("environment_id")
    query = ChatSession.query
    if environment_id is None:
        query = query.filter(ChatSession.environment_id.is_(None))
    else:
        query = query.filter_by(environment_id=environment_id)
    sessions = query.all()
    cleared = 0
    for session in sessions:
        for upload in session.uploads:
            if upload.file_path and os.path.exists(upload.file_path):
                try:
                    os.remove(upload.file_path)
                except OSError:
                    pass
        db.session.delete(session)
        cleared += 1
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "message": "Chat cleared for this environment." if cleared else "There was no saved chat history for this context.",
        }
    )


@chat_bp.route("/message", methods=["POST"])
def message():
    payload = request.get_json(force=True)
    user_message = payload.get("message", "").strip()
    page_context = payload.get("context") or {}
    environment_id = page_context.get("environment_id")
    environment = ContextEnvironment.query.get(environment_id) if environment_id else None
    session = get_or_create_session(db, environment_id, page_context)
    classifier_steps: list[str] = []
    intent_hint = None
    answer_client = None
    answer_model_name = None
    try:
        ollama_url = get_setting("ollama_url", current_app.config["OLLAMA_URL"])
        classifier_model = get_task_model("orchestrator", current_app.config["LLM_MODELS"]["orchestrator"])
        answer_model_name = get_task_model("chat_answering", current_app.config["LLM_MODELS"]["chat_answering"])
        answer_client = OllamaClient(ollama_url)
        intent_hint, classifier_steps = classify_message_intent(
            answer_client,
            classifier_model,
            environment,
            page_context.get("selected_document_ids"),
            user_message,
        )
    except Exception as exc:
        classifier_steps = [f"Intent classifier setup failed: {exc}"]

    response_payload = build_chat_response(
        user_message,
        page_context,
        environment,
        selected_document_ids=page_context.get("selected_document_ids"),
        answer_client=answer_client,
        answer_model_name=answer_model_name,
        intent_hint=intent_hint,
        retrieval_top_k=int(get_setting("retrieval_top_k", "6") or "6"),
    )
    if classifier_steps:
        response_payload["intermediate_steps"] = classifier_steps + response_payload.get("intermediate_steps", [])
    log_chat_exchange(db, session, user_message, response_payload)
    db.session.commit()
    return jsonify(response_payload)


@chat_bp.route("/upload", methods=["POST"])
def upload():
    upload = request.files.get("file")
    page_context = json.loads(request.form.get("context", "{}"))
    environment_id = page_context.get("environment_id")
    session = get_or_create_session(db, environment_id, page_context)
    if upload is None:
        return jsonify({"ok": False, "message": "A file is required."}), 400
    original_name, stored_name, saved_path = save_chat_upload(current_app.config["DATA_DIR"], session.id, upload)
    text, error = extract_text(saved_path)
    chat_upload = ChatUpload(
        chat_session=session,
        original_filename=original_name,
        stored_filename=stored_name,
        file_path=str(saved_path),
        file_type=Path(original_name).suffix.lower().lstrip("."),
        extracted_text=text or None,
        processing_notes=error or "Uploaded via assistant panel.",
    )
    db.session.add(chat_upload)
    db.session.commit()
    if text:
        message_text = (
            f"I received {original_name} and extracted text from it. "
            "If you want this to affect persistent retrieval tests, upload it into a saved environment instead of general chat."
        )
    else:
        message_text = f"I received {original_name}, but I could not extract readable text yet: {error}."
    return jsonify({"ok": True, "message": message_text, "chat_upload_id": chat_upload.id})
