from __future__ import annotations

from models import AppSetting


DEFAULT_SETTINGS = {
    "ollama_url": {
        "value": "http://192.168.1.249:11434",
        "description": "Base URL for the Ollama server.",
    },
    "llm_orchestrator_model": {
        "value": "llama3.2",
        "description": "Model used for lightweight intent classification.",
    },
    "llm_chat_model": {
        "value": "llama3.2",
        "description": "Model used for final chat answers.",
    },
    "retrieval_chunk_size": {
        "value": "1400",
        "description": "Approximate character size for each stored retrieval chunk.",
    },
    "retrieval_chunk_overlap": {
        "value": "250",
        "description": "Approximate character overlap between retrieval chunks.",
    },
    "retrieval_top_k": {
        "value": "6",
        "description": "How many top document chunks to inject into chat answers.",
    },
}

TASK_MODEL_SETTING_KEYS = {
    "orchestrator": "llm_orchestrator_model",
    "chat_answering": "llm_chat_model",
}


def ensure_default_settings(db) -> None:
    existing_keys = {setting.key for setting in AppSetting.query.all()}
    changed = False
    for key, payload in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            db.session.add(
                AppSetting(
                    key=key,
                    value=payload["value"],
                    description=payload["description"],
                )
            )
            changed = True
    if changed:
        db.session.commit()


def get_setting(key: str, fallback: str | None = None) -> str | None:
    setting = AppSetting.query.filter_by(key=key).first()
    if setting is not None and setting.value is not None:
        return setting.value
    default = DEFAULT_SETTINGS.get(key)
    if default is not None:
        return default["value"]
    return fallback


def get_task_model(task_name: str, fallback: str | None = None) -> str | None:
    setting_key = TASK_MODEL_SETTING_KEYS.get(task_name)
    if setting_key is None:
        return fallback
    return get_setting(setting_key, fallback)
