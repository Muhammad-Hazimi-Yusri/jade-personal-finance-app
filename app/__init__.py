"""Jade — Personal Finance & Trading Journal.

Flask application factory.
"""

import os
from pathlib import Path

__version__ = "0.6.2"

from flask import Flask, jsonify, send_from_directory

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
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # 10 MB upload limit
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    # --- Database initialisation (runs pending migrations) ---
    with app.app_context():
        init_db(app)

    # --- Register teardown ---
    app.teardown_appcontext(close_db)

    # --- Register blueprints ---
    from .routes.transactions import bp as transactions_bp
    app.register_blueprint(transactions_bp)

    from .routes.categories import bp as categories_bp
    app.register_blueprint(categories_bp)

    from .routes.upload import bp as upload_bp
    app.register_blueprint(upload_bp)

    from .routes.category_rules import bp as category_rules_bp
    app.register_blueprint(category_rules_bp)

    from .routes.budgets import bp as budgets_bp
    app.register_blueprint(budgets_bp)

    from .routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    from .routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    from .routes.accounts import bp as accounts_bp
    app.register_blueprint(accounts_bp)

    from .routes.strategies import bp as strategies_bp
    app.register_blueprint(strategies_bp)

    from .routes.tags import bp as tags_bp
    app.register_blueprint(tags_bp)

    from .routes.tags import trades_bp as trade_tags_bp
    app.register_blueprint(trade_tags_bp)

    from .routes.trades import bp as trades_bp
    app.register_blueprint(trades_bp)

    from .routes.journal import bp as journal_bp
    app.register_blueprint(journal_bp)

    from .routes.snapshots import bp as snapshots_bp
    app.register_blueprint(snapshots_bp)

    # --- Serve frontend ---
    frontend_dir = Path(__file__).parent.parent / "frontend"

    @app.route("/health")
    def health():
        """Docker / load-balancer health check endpoint."""
        return jsonify({"status": "ok"})

    @app.route("/")
    def index():
        """Serve the SPA entry point."""
        response = send_from_directory(frontend_dir, "index.html")
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.route("/<path:filename>")
    def static_files(filename: str):
        """Serve static frontend assets.

        Cache-Control strategy:
          - HTML files: no-cache (always revalidate — ensures fresh app shell)
          - CSS / JS / other: public, max-age=3600 (1 hour; ETags handle
            revalidation when content changes)
        """
        response = send_from_directory(frontend_dir, filename)
        if filename.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

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
