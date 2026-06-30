from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'context_lab.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    DATA_DIR = Path(os.environ.get("DATA_DIR", DATA_DIR))
    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.1.249:11434")
    LLM_MODELS = {
        "orchestrator": os.environ.get("LLM_ORCHESTRATOR_MODEL", "llama3.2"),
        "chat_answering": os.environ.get("LLM_CHAT_MODEL", "llama3.2"),
    }
    ALLOWED_UPLOAD_EXTENSIONS = {
        ".pdf",
        ".docx",
        ".xlsx",
        ".txt",
        ".eml",
        ".msg",
        ".csv",
    }
