"""Cloudflare Access JWT verification middleware.

Adds a defence-in-depth layer on top of Cloudflare Access. Every request that
reaches Flask must carry a valid `Cf-Access-Jwt-Assertion` header (or the
equivalent `CF_Authorization` cookie) signed by Cloudflare for the configured
Access application audience tag. Requests that miss/fail verification are
rejected with `403` — even if they somehow bypass the tunnel and Access
(e.g. via a misconfiguration, a stale public hostname, or direct LAN access
to the container).

Activation:
    Set both `CF_ACCESS_AUD` and `CF_ACCESS_TEAM_DOMAIN`. With either unset,
    the middleware is a no-op so dev/test environments work unchanged.

Bypass paths:
    - `/health`              — Docker healthcheck runs from inside the
                                container, no JWT involved.
    - `DEMO_MODE=true`       — `jade-demo.*` is intentionally public.

JWKS keys are fetched from
`https://<team>.cloudflareaccess.com/cdn-cgi/access/certs` once, cached
in-process for one hour, with a one-shot refresh on unknown `kid` to handle
key rotation without per-request fetches.
"""

import json
import time
import urllib.request
from threading import Lock
from typing import Any

import jwt
from flask import Flask, jsonify, request

_JWKS_TTL_SECONDS = 3600


class JWKSCache:
    """In-process JWKS cache with TTL refresh and rotation handling."""

    def __init__(self, jwks_url: str, ttl: int = _JWKS_TTL_SECONDS) -> None:
        self._url = jwks_url
        self._ttl = ttl
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0
        self._lock = Lock()

    def get_signing_key(self, kid: str | None) -> Any:
        """Return the public key matching `kid`, refreshing JWKS if needed."""
        if not kid:
            raise jwt.InvalidKeyError("Token header missing 'kid'")

        with self._lock:
            if not self._keys or (time.time() - self._fetched_at) > self._ttl:
                self._refresh()
            if kid not in self._keys:
                self._refresh()
            if kid not in self._keys:
                raise jwt.InvalidKeyError(f"No JWK matches kid={kid}")
            return self._keys[kid]

    def _refresh(self) -> None:
        with urllib.request.urlopen(self._url, timeout=10) as resp:
            payload = json.loads(resp.read())
        keyset = jwt.PyJWKSet.from_dict(payload)
        self._keys = {k.key_id: k.key for k in keyset.keys}
        self._fetched_at = time.time()


def init_app(app: Flask) -> None:
    """Register the Cloudflare Access JWT verification before-request hook.

    No-op unless both `CF_ACCESS_AUD` and `CF_ACCESS_TEAM_DOMAIN` are
    configured. The active `JWKSCache` instance is stored on
    `app.extensions["cf_access_jwks"]` so tests can swap or pre-populate it.
    """
    aud = app.config.get("CF_ACCESS_AUD")
    team_domain = app.config.get("CF_ACCESS_TEAM_DOMAIN")

    if not (aud and team_domain):
        app.logger.info(
            "Cloudflare Access JWT verification disabled "
            "(CF_ACCESS_AUD / CF_ACCESS_TEAM_DOMAIN not set)."
        )
        return

    issuer = f"https://{team_domain}"
    jwks = JWKSCache(f"https://{team_domain}/cdn-cgi/access/certs")
    app.extensions["cf_access_jwks"] = jwks

    @app.before_request
    def verify_cf_access_jwt():
        if app.config.get("DEMO_MODE"):
            return None
        if request.path == "/health":
            return None

        token = (
            request.headers.get("Cf-Access-Jwt-Assertion")
            or request.cookies.get("CF_Authorization")
        )
        if not token:
            return jsonify({"error": "Missing Cloudflare Access token"}), 403

        try:
            unverified_header = jwt.get_unverified_header(token)
            signing_key = app.extensions["cf_access_jwks"].get_signing_key(
                unverified_header.get("kid")
            )
            jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=aud,
                issuer=issuer,
            )
        except Exception as exc:  # noqa: BLE001 — log and reject all failures uniformly
            app.logger.warning("Cloudflare Access JWT verification failed: %s", exc)
            return jsonify({"error": "Invalid Cloudflare Access token"}), 403

        return None
