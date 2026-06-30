from __future__ import annotations

from flask import Blueprint, render_template

from models import ContextEnvironment, EnvironmentDocument


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    environments = ContextEnvironment.query.order_by(ContextEnvironment.updated_at.desc()).limit(6).all()
    environment_count = ContextEnvironment.query.count()
    document_count = EnvironmentDocument.query.count()
    processed_count = EnvironmentDocument.query.filter_by(processed=True).count()
    return render_template(
        "dashboard.html",
        environments=environments,
        environment_count=environment_count,
        document_count=document_count,
        processed_count=processed_count,
        chat_context={"page": "dashboard"},
    )
