from __future__ import annotations

import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


ENVIRONMENT_SUBDIRECTORIES = (
    "documents",
    "extracted_text",
    "prompts",
)


def environment_dir(base_data_dir: Path, environment_id: int) -> Path:
    return base_data_dir / "environments" / str(environment_id)


def ensure_environment_directories(base_data_dir: Path, environment_id: int) -> Path:
    base_dir = environment_dir(base_data_dir, environment_id)
    for directory in ENVIRONMENT_SUBDIRECTORIES:
        (base_dir / directory).mkdir(parents=True, exist_ok=True)
    return base_dir


def save_environment_upload(base_data_dir: Path, environment_id: int, upload: FileStorage) -> tuple[str, str, Path]:
    base_dir = ensure_environment_directories(base_data_dir, environment_id)
    original_name = secure_filename(upload.filename or "upload")
    extension = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = base_dir / "documents" / stored_name
    upload.save(destination)
    return original_name, stored_name, destination


def save_chat_upload(base_data_dir: Path, session_id: int, upload: FileStorage) -> tuple[str, str, Path]:
    chat_dir = base_data_dir / "chat_uploads" / str(session_id)
    chat_dir.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(upload.filename or "upload")
    extension = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = chat_dir / stored_name
    upload.save(destination)
    return original_name, stored_name, destination
