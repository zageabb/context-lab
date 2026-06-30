from __future__ import annotations

from pathlib import Path

from models import ContextEnvironment, EnvironmentPrompt
from services.file_storage import ensure_environment_directories


PROMPT_TEMPLATES = {
    "chat_system": {
        "filename": "chat_system.md",
        "title": "Chat System Prompt",
        "description": "Per-environment instruction file used to shape assistant behaviour for this saved environment.",
        "default_content": (
            "# Context Lab Chat System Prompt\n\n"
            "You are an assistant helping the user test how different context choices affect LLM answers.\n"
            "Use only the supplied environment details, selected document text, and retrieved chunks.\n"
            "Be explicit about what information came from retrieval versus what is missing.\n"
            "Do not invent facts or claim certainty beyond the provided context.\n"
            "When useful, explain how changing selected documents or instructions might change the answer.\n"
        ),
    },
    "chat_answer": {
        "filename": "chat_answer.md",
        "title": "Chat Answer Template",
        "description": "Per-environment answer template used to assemble the final LLM prompt.",
        "default_content": (
            "# Context Lab Chat Answer Template\n\n"
            "{{system_prompt}}\n\n"
            "Environment details:\n{{environment_context}}\n\n"
            "Page context:\n{{page_context}}\n\n"
            "Selected document summaries:\n{{selected_documents_context}}\n\n"
            "Retrieved RAG chunks:\n{{retrieved_context}}\n\n"
            "User question:\n{{user_message}}\n"
        ),
    },
    "intent_classifier": {
        "filename": "intent_classifier.md",
        "title": "Intent Classifier Prompt",
        "description": "Instruction file used to detect whether the user is asking for retrieval advice or a normal answer.",
        "default_content": (
            "# Context Lab Intent Classifier\n\n"
            "Classify the user's message and return JSON only with keys `intent`, `confidence`, and `reason`.\n"
            "Allowed intents: retrieval_advice, answer_question, none.\n"
            "Use retrieval_advice when the user is asking what context should be added, removed, or compared.\n"
            "Use answer_question for regular questions about the supplied documents.\n\n"
            "User message: {{user_message}}\n"
            "Has environment context: {{has_environment_context}}\n"
            "Has selected documents: {{has_selected_documents}}\n"
        ),
    },
}


def ensure_environment_prompts(base_data_dir: Path, environment: ContextEnvironment, db) -> None:
    ensure_environment_directories(base_data_dir, environment.id)
    existing = {prompt.key: prompt for prompt in environment.prompts}
    changed = False
    for key, payload in PROMPT_TEMPLATES.items():
        if key in existing:
            continue
        prompt_path = environment_prompt_path(base_data_dir, environment.id, payload["filename"])
        prompt_path.write_text(payload["default_content"], encoding="utf-8")
        db.session.add(
            EnvironmentPrompt(
                environment=environment,
                key=key,
                title=payload["title"],
                description=payload["description"],
                file_path=str(prompt_path),
                content=payload["default_content"],
            )
        )
        changed = True
    if changed:
        db.session.commit()


def environment_prompt_path(base_data_dir: Path, environment_id: int, filename: str) -> Path:
    return ensure_environment_directories(base_data_dir, environment_id) / "prompts" / filename


def get_prompt_content(environment: ContextEnvironment, key: str) -> str:
    prompt = next((prompt for prompt in environment.prompts if prompt.key == key), None)
    if prompt is None:
        raise KeyError(f"Unknown environment prompt: {key}")
    return prompt.content


def save_prompt_content(base_data_dir: Path, prompt: EnvironmentPrompt, content: str) -> None:
    normalized = content.rstrip() + "\n"
    prompt.content = normalized
    if prompt.file_path:
        Path(prompt.file_path).write_text(normalized, encoding="utf-8")


def render_template_text(content: str, **kwargs: str) -> str:
    rendered = content
    for key, value in kwargs.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered
