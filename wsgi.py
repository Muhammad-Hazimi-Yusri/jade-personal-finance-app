"""WSGI entry point for Gunicorn.

Usage:
    gunicorn --bind 0.0.0.0:8000 --workers 1 --timeout 60 wsgi:app
"""

from app import create_app

app = create_app()
