"""Jade — Personal Finance & Trading Journal.

Flask application factory.
"""

import os
from pathlib import Path

__version__ = "0.6.14"

import logging

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

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

    # All API routes are JSON; URL canonicalisation isn't needed. Disabling
    # strict_slashes prevents 308 redirects that break HTTPS clients behind a
    # plain-HTTP reverse proxy: cloudflared connects to localhost over HTTP,
    # so wsgi.url_scheme is 'http' and the auto-generated Location header
    # would also be http://, which the browser blocks via mixed-content /
    # CSP connect-src 'self'.
    app.url_map.strict_slashes = False

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

    from .routes.export import bp as export_bp
    app.register_blueprint(export_bp)

    # --- Serve frontend ---
    frontend_dir = Path(__file__).parent.parent / "frontend"

    @app.route("/health")
    def health():
        """Docker / load-balancer health check endpoint."""
        return jsonify({"status": "ok"})

    @app.route("/api/meta")
    def meta():
        """Return app metadata for frontend configuration."""
        return jsonify({
            "version": __version__,
            "demo_mode": app.config["DEMO_MODE"],
        })

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

    # --- Demo-mode write protection ---
    # When DEMO_MODE is enabled, reject any mutating HTTP method so visitors
    # cannot persist changes to the shared database. GET/HEAD/OPTIONS pass
    # through unchanged. The daily reset container also guarantees a clean
    # snapshot, but this middleware is defence-in-depth.
    _WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    @app.before_request
    def block_writes_in_demo_mode():
        if app.config["DEMO_MODE"] and request.method in _WRITE_METHODS:
            return jsonify({"error": "Demo mode — changes are disabled"}), 403
        return None

    # --- Global error handlers ---
    # All handlers return JSON in the shape `{"error": "<message>"}` to match
    # the format already used by route-level handlers in app/routes/*.py.
    # This prevents the default HTML error pages from leaking into JSON
    # clients and gives the frontend a single shape to parse.
    @app.errorhandler(404)
    def handle_not_found(_err):
        # API misses always return JSON so URL typos surface clearly to
        # the frontend instead of being masked as HTML.
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        # Asset-shaped paths (anything with a file extension in the last
        # segment) should also 404 honestly — serving index.html for a
        # missing /js/foo.js would just hide a typo.
        last_segment = request.path.rsplit("/", 1)[-1]
        if "." in last_segment:
            return jsonify({"error": "Not found"}), 404
        # SPA routes (clean paths like /transactions) fall back to the
        # shell so client-side routing can render its own 404 view.
        response = send_from_directory(frontend_dir, "index.html")
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response, 200

    @app.errorhandler(405)
    def handle_method_not_allowed(_err):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(413)
    def handle_payload_too_large(_err):
        return jsonify({"error": "Payload too large (max 10MB)"}), 413

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return jsonify({"error": err.description or err.name}), err.code or 500

    @app.errorhandler(Exception)
    def handle_unexpected_exception(err: Exception):
        app.logger.exception("Unhandled exception: %s", err)
        return jsonify({"error": "Internal server error"}), 500

    if not app.debug:
        logging.basicConfig(level=logging.INFO)

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
