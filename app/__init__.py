"""Jade — Personal Finance & Trading Journal.

Flask application factory.
"""

import os

__version__ = "0.1.0"

from flask import Flask, send_from_directory

from .db import close_db, init_db


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        test_config: Optional configuration dict for testing. When provided,
            it overrides values loaded from the environment.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=False)

    # --- Default configuration ---
    app.config.from_mapping(
        DATABASE_PATH=os.environ.get("DATABASE_PATH", "data/jade.db"),
        DEMO_MODE=os.environ.get("DEMO_MODE", "false").lower() == "true",
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    # --- Database initialisation (runs pending migrations) ---
    with app.app_context():
        init_db(app)

    # --- Register teardown ---
    app.teardown_appcontext(close_db)

    # --- Register blueprints ---
    # Route blueprints are registered here as they are built out in later phases.
    # (No routes yet in Phase 1.1 — added in 1.4+)

    # --- Serve frontend ---
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

    @app.route("/")
    def index():
        """Serve the SPA entry point."""
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename: str):
        """Serve static frontend assets."""
        return send_from_directory(frontend_dir, filename)

    # --- Security headers ---
    @app.after_request
    def set_security_headers(response):
        """Apply defence-in-depth security headers to every response."""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' cdn.jsdelivr.net unpkg.com; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "font-src fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        if app.config["DEMO_MODE"]:
            response.headers["X-Demo-Mode"] = "true"
        return response

    return app
