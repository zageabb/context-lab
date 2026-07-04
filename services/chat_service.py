from __future__ import annotations

import json

from flask import current_app

from models import (
    ChatMessage,
    ChatSession,
    ChatUpload,
    ContextEnvironment,
    EnvironmentDocument,
    SharedRAGDocument,
    StructuredDataTable,
)
from services.prompt_service import get_prompt_content, render_template_text
from services.rag_service import format_retrieved_context, retrieve_relevant_chunks
from services.structured_data_service import (
    format_structured_row_context,
    retrieve_structured_rows,
    summarize_structured_tables,
)

MAX_SELECTED_DOCUMENT_CONTEXT_CHARS = 18000
BASE_CHAT_GROUNDING_INSTRUCTIONS = (
    "Base grounding rules for this answer:\n"
    "- Use the supplied environment details, selected documents, shared RAG context, structured data summaries, "
    "structured row matches, and retrieved chunks as valid evidence sources.\n"
    "- Treat structured data as first-class context, especially for numeric, tabular, status, schedule, and comparison questions.\n"
    "- If documents and structured data conflict, call out the conflict explicitly instead of silently choosing one.\n"
    "- Prefer structured data for exact values and documents for explanatory narrative or policy wording.\n"
    "- Be explicit about which evidence source supports the answer.\n"
    "- Do not invent facts or claim certainty beyond the provided context.\n"
)
REQUIRED_PROMPT_SECTIONS = (
    ("selected_documents_context", "Selected document summaries"),
    ("shared_rag_context", "Shared RAG library summary"),
    ("structured_data_context", "Structured data summary"),
    ("structured_row_context", "Structured data rows matched for this question"),
    ("retrieved_context", "Retrieved RAG chunks"),
)


def get_or_create_session(db, environment_id: int | None, page_context: dict | None) -> ChatSession:
    query = ChatSession.query
    if environment_id is None:
        query = query.filter(ChatSession.environment_id.is_(None))
    else:
        query = query.filter_by(environment_id=environment_id)
    session = query.order_by(ChatSession.updated_at.desc()).first()
    if session is None:
        session = ChatSession(environment_id=environment_id, page_context_json=json.dumps(page_context or {}))
        db.session.add(session)
        db.session.flush()
    else:
        session.page_context_json = json.dumps(page_context or {})
    return session


def add_chat_message(
    db,
    chat_session: ChatSession,
    role: str,
    message_text: str,
    intermediate_steps: list[str] | None = None,
) -> ChatMessage:
    message = ChatMessage(
        chat_session=chat_session,
        role=role,
        message_text=message_text,
        intermediate_steps_json=json.dumps(intermediate_steps or []),
    )
    db.session.add(message)
    return message


def log_chat_exchange(db, session: ChatSession, user_message: str, response_payload: dict) -> None:
    add_chat_message(db, session, "user", user_message)
    add_chat_message(
        db,
        session,
        "assistant",
        response_payload.get("message", ""),
        intermediate_steps=response_payload.get("intermediate_steps", []),
    )


def get_recent_messages(chat_session: ChatSession | None, limit: int = 24) -> list[dict]:
    if chat_session is None:
        return []
    messages = (
        ChatMessage.query.filter_by(chat_session_id=chat_session.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    payload = []
    for message in messages:
        try:
            steps = json.loads(message.intermediate_steps_json) if message.intermediate_steps_json else []
        except json.JSONDecodeError:
            steps = []
        payload.append(
            {
                "role": message.role,
                "message_text": message.message_text,
                "intermediate_steps": steps,
                "created_at": message.created_at.isoformat(),
            }
        )
    return payload


def classify_message_intent(client, model_name: str, environment: ContextEnvironment | None, selected_document_ids: list[int] | None, message: str) -> tuple[str | None, list[str]]:
    if client is None or not model_name or environment is None:
        return None, []
    prompt = render_template_text(
        get_prompt_content(environment, "intent_classifier"),
        user_message=message,
        has_environment_context="yes" if environment else "no",
        has_selected_documents="yes" if selected_document_ids else "no",
    )
    parsed, raw_response, error = client.generate_json(model_name, prompt)
    if parsed is None:
        return None, [f"Intent classifier returned unreadable JSON: {error or raw_response[:160]}"]
    intent = parsed.get("intent")
    reason = parsed.get("reason") or "No classifier reason provided."
    confidence = parsed.get("confidence")
    return intent, [f"Intent classifier: {intent or 'none'} (confidence: {confidence}, reason: {reason})"]


def build_chat_response(
    message: str,
    page_context: dict | None,
    environment: ContextEnvironment | None,
    selected_document_ids: list[int] | None,
    answer_client=None,
    answer_model_name: str | None = None,
    intent_hint: str | None = None,
    retrieval_top_k: int = 6,
) -> dict:
    if environment is None:
        latest_upload = ChatUpload.query.order_by(ChatUpload.created_at.desc()).first()
        if latest_upload and latest_upload.extracted_text:
            return {
                "response_type": "answer",
                "message": (
                    f"I can see the uploaded file `{latest_upload.original_filename}` in general chat. "
                    "Create a saved environment to persist instructions, document sets, and retrieval experiments."
                ),
                "intermediate_steps": [
                    "No saved environment was selected.",
                    "A general chat upload exists, but environment-scoped retrieval is not available until an environment is created.",
                ],
            }
        return {
            "response_type": "answer",
            "message": "Create or open a saved environment to test document context, RAG retrieval, and per-session instructions.",
            "intermediate_steps": [
                "No environment context was available.",
                "Returned the generic onboarding response.",
            ],
        }

    selected_documents = _selected_documents(environment, selected_document_ids)
    shared_rag_documents = _shared_rag_documents()
    structured_tables = _structured_tables(environment)
    if intent_hint == "retrieval_advice":
        response_payload = {
            "response_type": "answer",
            "message": _retrieval_advice(environment, selected_documents, shared_rag_documents, structured_tables, message),
            "intermediate_steps": [
                "The intent classifier marked this as a retrieval-advice request.",
                f"Checked {len(selected_documents)} selected documents and {len(shared_rag_documents)} shared RAG documents for likely relevance.",
            ],
        }
        response_payload["intermediate_steps"] = _finalize_thinking_steps(
            response_payload["intermediate_steps"],
            selected_documents=selected_documents,
            shared_rag_documents=shared_rag_documents,
            retrieved_chunks=[],
            structured_tables=structured_tables,
            structured_rows=[],
        )
        return response_payload

    if answer_client is None or not answer_model_name:
        response_payload = {
            "response_type": "answer",
            "message": "The chat model is not configured, so I can only report that the selected documents are ready for retrieval testing.",
            "intermediate_steps": [
                "Environment context was available.",
                "LLM answer generation was unavailable, so no model call was made.",
            ],
        }
        response_payload["intermediate_steps"] = _finalize_thinking_steps(
            response_payload["intermediate_steps"],
            selected_documents=selected_documents,
            shared_rag_documents=shared_rag_documents,
            retrieved_chunks=[],
            structured_tables=structured_tables,
            structured_rows=[],
        )
        return response_payload

    selected_context = _serialize_selected_documents(selected_documents)
    shared_rag_context = _serialize_shared_rag_library(shared_rag_documents)
    structured_data_context = summarize_structured_tables(structured_tables)
    selected_chunks = retrieve_relevant_chunks(selected_documents, message, top_k=retrieval_top_k, source_label="Environment selection")
    shared_chunks = retrieve_relevant_chunks(shared_rag_documents, message, top_k=retrieval_top_k, source_label="Shared RAG")
    structured_rows = retrieve_structured_rows(
        current_app.config["DATA_DIR"],
        environment.id,
        structured_tables,
        message,
        row_limit=retrieval_top_k,
    )
    retrieved_chunks = sorted(selected_chunks + shared_chunks, key=lambda chunk: chunk["score"], reverse=True)[:retrieval_top_k]
    rag_context = format_retrieved_context(retrieved_chunks)
    structured_row_context = format_structured_row_context(structured_rows)
    system_prompt = f"{BASE_CHAT_GROUNDING_INSTRUCTIONS}\n{get_prompt_content(environment, 'chat_system').strip()}"
    prompt_values = {
        "system_prompt": system_prompt,
        "environment_context": _serialize_environment_context(environment),
        "page_context": _serialize_page_context(page_context),
        "selected_documents_context": selected_context,
        "shared_rag_context": shared_rag_context,
        "structured_data_context": structured_data_context,
        "structured_row_context": structured_row_context,
        "retrieved_context": rag_context,
        "user_message": message,
    }
    answer_template = get_prompt_content(environment, "chat_answer")
    answer_prompt = render_template_text(answer_template, **prompt_values)
    answer_prompt = _append_missing_prompt_sections(answer_prompt, answer_template, prompt_values)
    answer = answer_client.generate_text(answer_model_name, answer_prompt)
    response_payload = {
        "response_type": "answer",
        "message": answer or "The model returned an empty response.",
        "intermediate_steps": [
            f"Selected document count: {len(selected_documents)}",
            f"Shared RAG document count: {len(shared_rag_documents)}",
            f"Retrieved chunk count: {len(retrieved_chunks)}",
            f"Chat model: {answer_model_name}",
            "Built the final answer prompt from the environment's saved instruction templates.",
        ],
        "retrieved_chunks": retrieved_chunks,
    }
    response_payload["intermediate_steps"] = _finalize_thinking_steps(
        response_payload["intermediate_steps"],
        selected_documents=selected_documents,
        shared_rag_documents=shared_rag_documents,
        retrieved_chunks=retrieved_chunks,
        structured_tables=structured_tables,
        structured_rows=structured_rows,
    )
    return response_payload


def _selected_documents(environment: ContextEnvironment, selected_document_ids: list[int] | None) -> list[EnvironmentDocument]:
    if not selected_document_ids:
        return []
    selected_ids = {int(document_id) for document_id in selected_document_ids}
    return [document for document in environment.documents if document.id in selected_ids and document.processed]


def _shared_rag_documents() -> list[SharedRAGDocument]:
    return (
        SharedRAGDocument.query.filter_by(active=True)
        .order_by(SharedRAGDocument.updated_at.desc())
        .all()
    )


def _structured_tables(environment: ContextEnvironment) -> list[StructuredDataTable]:
    tables: list[StructuredDataTable] = []
    for source in environment.structured_data_sources:
        tables.extend(source.tables)
    return sorted(tables, key=lambda table: table.updated_at, reverse=True)


def _serialize_environment_context(environment: ContextEnvironment) -> str:
    return "\n".join(
        [
            f"Name: {environment.name}",
            f"Status: {environment.status}",
            f"Description: {environment.description or '-'}",
            f"Notes: {environment.notes or '-'}",
            f"Document count: {len(environment.documents)}",
        ]
    )


def _serialize_page_context(page_context: dict | None) -> str:
    if not page_context:
        return "No explicit page context was supplied."
    return "\n".join(f"- {key}: {value}" for key, value in page_context.items())


def _serialize_selected_documents(documents: list[EnvironmentDocument], limit: int = MAX_SELECTED_DOCUMENT_CONTEXT_CHARS) -> str:
    if not documents:
        return "No processed documents are currently selected for this answer."
    sections: list[str] = []
    total_length = 0
    for document in documents:
        body = (document.extracted_text or "").strip()
        if not body:
            continue
        section = f"Document: {document.original_filename}\n{body}"
        remaining = limit - total_length
        if remaining <= 0:
            break
        if len(section) > remaining:
            section = section[:remaining].rstrip() + "\n[Document text truncated]"
        sections.append(section)
        total_length += len(section) + 2
        if total_length >= limit:
            break
    if not sections:
        return "Selected documents do not yet have extracted text."
    return "\n\n---\n\n".join(sections)


def _serialize_shared_rag_library(documents: list[SharedRAGDocument]) -> str:
    if not documents:
        return "No shared RAG documents are currently available."
    lines = [
        f"- {document.title} ({len(document.chunks)} chunks)"
        for document in documents[:30]
    ]
    return "\n".join(lines)


def _retrieval_advice(
    environment: ContextEnvironment,
    selected_documents: list[EnvironmentDocument],
    shared_rag_documents: list[SharedRAGDocument],
    structured_tables: list[StructuredDataTable],
    message: str,
) -> str:
    if not environment.documents and not shared_rag_documents and not structured_tables:
        return "There are no environment documents, structured data tables, or shared RAG documents yet. Upload a few files first so we can compare what happens when context changes."
    if not selected_documents and shared_rag_documents:
        return (
            f"No environment documents are selected right now, but {len(shared_rag_documents)} shared RAG document(s) are available across all environments. "
            "Select a focused local subset when you want to compare environment-only context against the shared baseline."
        )
    if not selected_documents:
        ready_count = sum(1 for document in environment.documents if document.processed)
        if ready_count:
            return (
                f"This environment has {ready_count} processed document(s), but none are selected for chat context right now. "
                "Select one focused subset, ask your question again, then expand the set to compare the answer."
            )
        return "The uploaded documents are not processed yet, so there is no environment-specific context to compare."
    chunk_ready = sum(1 for document in selected_documents if document.rag_ready)
    names = ", ".join(document.original_filename for document in selected_documents[:5])
    return (
        f"For this question, start with the currently selected documents: {names}. "
        f"{chunk_ready} of {len(selected_documents)} selected document(s) have retrieval chunks ready, there are {len(shared_rag_documents)} shared RAG document(s) available globally, and {len(structured_tables)} structured table(s) available locally. "
        "To test context effects, keep instructions fixed and change one thing at a time: selected docs, structured-data imports, shared RAG membership, or prompt wording."
    )


def _finalize_thinking_steps(
    steps: list[str],
    selected_documents: list[EnvironmentDocument],
    shared_rag_documents: list[SharedRAGDocument],
    retrieved_chunks: list[dict],
    structured_tables: list[StructuredDataTable],
    structured_rows: list[dict],
) -> list[str]:
    thinking_steps = [
        "Visible reasoning trace only: this shows orchestration and evidence used, not the model's hidden chain-of-thought.",
        f"Local selected documents: {', '.join(document.original_filename for document in selected_documents[:6]) or 'none'}",
        f"Shared RAG available: {len(shared_rag_documents)} document(s)",
        f"Structured tables available: {len(structured_tables)}",
        *steps,
    ]
    if retrieved_chunks:
        thinking_steps.append("Evidence retrieved for this answer:")
        for chunk in retrieved_chunks[:6]:
            thinking_steps.append(
                f"{chunk['source_label']} -> {chunk['document_name']} (chunk {chunk['chunk_index']}, score {chunk['score']})"
            )
    else:
        thinking_steps.append("No high-scoring retrieval chunks were attached to this answer.")
    if structured_rows:
        thinking_steps.append("Structured rows matched for this answer:")
        for row in structured_rows[:6]:
            thinking_steps.append(f"{row['table_name']} (score {row['score']})")
    else:
        thinking_steps.append("No structured-data rows were matched for this answer.")
    return thinking_steps


def _append_missing_prompt_sections(prompt: str, template: str, prompt_values: dict[str, str]) -> str:
    sections_to_add: list[str] = []
    for key, label in REQUIRED_PROMPT_SECTIONS:
        if f"{{{{{key}}}}}" in template:
            continue
        value = (prompt_values.get(key) or "").strip()
        if not value:
            continue
        sections_to_add.append(f"{label}:\n{value}")
    if not sections_to_add:
        return prompt
    return prompt.rstrip() + "\n\nSupplemental context added automatically because this environment template omitted some evidence sections:\n\n" + "\n\n".join(sections_to_add) + "\n"
