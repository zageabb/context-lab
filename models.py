from __future__ import annotations

from datetime import datetime

from database import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class ContextEnvironment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(100), default="Draft", nullable=False)
    notes = db.Column(db.Text)

    documents = db.relationship("EnvironmentDocument", back_populates="environment", cascade="all, delete-orphan")
    prompts = db.relationship("EnvironmentPrompt", back_populates="environment", cascade="all, delete-orphan")
    chat_sessions = db.relationship("ChatSession", back_populates="environment", cascade="all, delete-orphan")


class EnvironmentDocument(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    environment_id = db.Column(db.Integer, db.ForeignKey("context_environment.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    extracted_text = db.Column(db.Text)
    extracted_text_path = db.Column(db.String(500))
    processed = db.Column(db.Boolean, default=False, nullable=False)
    processing_notes = db.Column(db.Text)
    rag_ready = db.Column(db.Boolean, default=False, nullable=False)

    environment = db.relationship("ContextEnvironment", back_populates="documents")
    chunks = db.relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("environment_document.id"), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    token_estimate = db.Column(db.Integer, nullable=False, default=0)

    document = db.relationship("EnvironmentDocument", back_populates="chunks")


class EnvironmentPrompt(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    environment_id = db.Column(db.Integer, db.ForeignKey("context_environment.id"), nullable=False)
    key = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    content = db.Column(db.Text, nullable=False)

    environment = db.relationship("ContextEnvironment", back_populates="prompts")


class AppSetting(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)


class ChatSession(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    environment_id = db.Column(db.Integer, db.ForeignKey("context_environment.id"))
    page_context_json = db.Column(db.Text)

    environment = db.relationship("ContextEnvironment", back_populates="chat_sessions")
    messages = db.relationship("ChatMessage", back_populates="chat_session", cascade="all, delete-orphan")
    uploads = db.relationship("ChatUpload", back_populates="chat_session", cascade="all, delete-orphan")


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    intermediate_steps_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    chat_session = db.relationship("ChatSession", back_populates="messages")


class ChatUpload(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    extracted_text = db.Column(db.Text)
    processing_notes = db.Column(db.Text)

    chat_session = db.relationship("ChatSession", back_populates="uploads")
