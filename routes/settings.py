from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from database import db
from models import AppSetting
from services.ollama_client import OllamaClient
from services.settings_service import DEFAULT_SETTINGS, ensure_default_settings


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET", "POST"])
def index():
    ensure_default_settings(db)
    settings = {setting.key: setting for setting in AppSetting.query.order_by(AppSetting.key.asc()).all()}
    if request.method == "POST":
        for key in DEFAULT_SETTINGS:
            record = settings.get(key)
            if record is None:
                continue
            record.value = request.form.get(key, "").strip()
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("settings.index"))
    return render_template(
        "settings/index.html",
        settings=settings,
        defaults=DEFAULT_SETTINGS,
        chat_context={"page": "settings"},
    )


@settings_bp.route("/test-ollama", methods=["POST"])
def test_ollama():
    ensure_default_settings(db)
    ollama_record = AppSetting.query.filter_by(key="ollama_url").first()
    ollama_url = ollama_record.value if ollama_record and ollama_record.value else current_app.config["OLLAMA_URL"]
    try:
        client = OllamaClient(ollama_url)
        models = client.list_models()
        preview = ", ".join(models[:5]) if models else "no models returned"
        flash(f"Ollama connection OK. Available models: {preview}", "success")
    except Exception as exc:
        flash(f"Ollama connection failed: {exc}", "danger")
    return redirect(url_for("settings.index"))
