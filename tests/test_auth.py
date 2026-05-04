"""Tests for the Cloudflare Access JWT verification middleware (Phase 7)."""

import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(
    private_key,
    *,
    aud: str = "test-aud",
    iss: str = "https://test.cloudflareaccess.com",
    kid: str = "kid-1",
    exp_offset: int = 300,
    **overrides,
) -> str:
    payload = {
        "aud": aud,
        "iss": iss,
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
        "email": "owner@example.com",
        **overrides,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


def _make_app(tmp_path, *, public_key=None, demo: bool = False, configured: bool = True):
    """Build a Jade app with an in-memory JWKS pre-populated for tests."""
    config = {
        "DATABASE_PATH": str(tmp_path / "jade.db"),
        "DEMO_MODE": demo,
    }
    if configured:
        config["CF_ACCESS_AUD"] = "test-aud"
        config["CF_ACCESS_TEAM_DOMAIN"] = "test.cloudflareaccess.com"

    app = create_app(config)
    cache = app.extensions.get("cf_access_jwks")
    if cache is not None and public_key is not None:
        cache._keys = {"kid-1": public_key}
        cache._fetched_at = time.time()
    return app


def test_disabled_when_envs_unset(tmp_path):
    app = _make_app(tmp_path, configured=False)
    assert "cf_access_jwks" not in app.extensions
    resp = app.test_client().get("/api/meta")
    assert resp.status_code == 200


def test_demo_mode_bypasses_jwt(tmp_path, rsa_keypair):
    _, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub, demo=True)
    resp = app.test_client().get("/api/meta")
    assert resp.status_code == 200


def test_health_endpoint_bypasses_jwt(tmp_path, rsa_keypair):
    _, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    resp = app.test_client().get("/health")
    assert resp.status_code == 200


def test_missing_token_rejected(tmp_path, rsa_keypair):
    _, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    resp = app.test_client().get("/api/meta")
    assert resp.status_code == 403
    assert "Missing" in resp.get_json()["error"]


def test_valid_token_allowed(tmp_path, rsa_keypair):
    priv, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    token = _make_token(priv)
    resp = app.test_client().get(
        "/api/meta", headers={"Cf-Access-Jwt-Assertion": token}
    )
    assert resp.status_code == 200


def test_wrong_audience_rejected(tmp_path, rsa_keypair):
    priv, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    token = _make_token(priv, aud="other-app")
    resp = app.test_client().get(
        "/api/meta", headers={"Cf-Access-Jwt-Assertion": token}
    )
    assert resp.status_code == 403


def test_wrong_issuer_rejected(tmp_path, rsa_keypair):
    priv, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    token = _make_token(priv, iss="https://attacker.example.com")
    resp = app.test_client().get(
        "/api/meta", headers={"Cf-Access-Jwt-Assertion": token}
    )
    assert resp.status_code == 403


def test_expired_token_rejected(tmp_path, rsa_keypair):
    priv, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    token = _make_token(priv, exp_offset=-60)
    resp = app.test_client().get(
        "/api/meta", headers={"Cf-Access-Jwt-Assertion": token}
    )
    assert resp.status_code == 403


def test_unknown_kid_rejected(tmp_path, rsa_keypair):
    priv, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    token = _make_token(priv, kid="rotated-kid")
    cache = app.extensions["cf_access_jwks"]
    # Pretend a refresh happened but the new kid still isn't present.
    with patch.object(cache, "_refresh", lambda: None):
        resp = app.test_client().get(
            "/api/meta", headers={"Cf-Access-Jwt-Assertion": token}
        )
    assert resp.status_code == 403


def test_cookie_token_accepted(tmp_path, rsa_keypair):
    priv, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    token = _make_token(priv)
    client = app.test_client()
    client.set_cookie("CF_Authorization", token)
    resp = client.get("/api/meta")
    assert resp.status_code == 200


def test_garbage_token_rejected(tmp_path, rsa_keypair):
    _, pub = rsa_keypair
    app = _make_app(tmp_path, public_key=pub)
    resp = app.test_client().get(
        "/api/meta", headers={"Cf-Access-Jwt-Assertion": "not-a-real-jwt"}
    )
    assert resp.status_code == 403
