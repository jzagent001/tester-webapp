"""Cloudflare Access sign-in: tokens are verified, never trusted blindly."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlmodel import select

from app import auth, config
from app.models import User

TEAM = "myteam.cloudflareaccess.com"
AUD = "test-aud-tag"


class _FakeJWKS:
    """Stands in for PyJWKClient, serving our test public key."""

    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, _token):
        return type("Key", (), {"key": self.public_key})()


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def cloudflare(monkeypatch, signing_key):
    monkeypatch.setattr(config, "AUTH_MODE", "cloudflare")
    monkeypatch.setattr(config, "CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setattr(config, "CF_ACCESS_AUD", AUD)
    monkeypatch.setattr(auth, "_jwks_client", lambda _team: _FakeJWKS(signing_key.public_key()))


def token(key, email="Carol@Example.com", aud=AUD, iss=f"https://{TEAM}", expires_in=600):
    now = datetime.now(UTC)
    claims = {"email": email, "aud": [aud], "iss": iss, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(claims, key, algorithm="RS256")


def test_valid_token_signs_in_and_creates_user(client, session, cloudflare, signing_key):
    r = client.get("/", headers={auth.TOKEN_HEADER: token(signing_key)})
    assert r.status_code == 200
    assert "carol@example.com" in r.text
    assert session.exec(select(User).where(User.email == "carol@example.com")).one()


def test_token_cookie_also_works(client, cloudflare, signing_key):
    client.cookies.set(auth.TOKEN_COOKIE, token(signing_key))
    assert client.get("/").status_code == 200


def test_sign_out_link_shown_in_cloudflare_mode(client, cloudflare, signing_key):
    r = client.get("/", headers={auth.TOKEN_HEADER: token(signing_key)})
    assert "/cdn-cgi/access/logout" in r.text


@pytest.mark.parametrize(
    "make_token",
    [
        lambda key: token(key, expires_in=-60),
        lambda key: token(key, aud="some-other-app"),
        lambda key: token(key, iss="https://evil.cloudflareaccess.com"),
        lambda key: token(key, email=""),
        lambda _key: token(rsa.generate_private_key(public_exponent=65537, key_size=2048)),
        lambda _key: "not-a-jwt",
    ],
    ids=["expired", "wrong-audience", "wrong-issuer", "no-email", "wrong-key", "garbage"],
)
def test_bad_tokens_rejected(client, cloudflare, signing_key, make_token):
    r = client.get("/", headers={auth.TOKEN_HEADER: make_token(signing_key)})
    assert r.status_code == 401


def test_no_token_rejected(client, cloudflare):
    assert client.get("/").status_code == 401
    assert client.get("/question-writing-kit.zip").status_code == 401


def test_plain_email_header_is_not_trusted(client, cloudflare):
    r = client.get("/", headers={"Cf-Access-Authenticated-User-Email": "alice@example.com"})
    assert r.status_code == 401


def test_healthz_needs_no_sign_in(client, cloudflare):
    assert client.get("/healthz").json() == {"ok": True}


def test_single_mode_shows_user_without_sign_out(client):
    r = client.get("/")
    assert "alice@example.com" in r.text
    assert "/cdn-cgi/access/logout" not in r.text


@pytest.mark.parametrize(
    "settings, problem",
    [
        ({"AUTH_MODE": "single", "SINGLE_USER_EMAIL": ""}, "SINGLE_USER_EMAIL"),
        ({"AUTH_MODE": "cloudflare", "CF_ACCESS_TEAM_DOMAIN": "", "CF_ACCESS_AUD": "x"}, "CF_ACCESS_TEAM_DOMAIN"),
        ({"AUTH_MODE": "cloudflare", "CF_ACCESS_TEAM_DOMAIN": "x", "CF_ACCESS_AUD": ""}, "CF_ACCESS_AUD"),
        ({"AUTH_MODE": "open"}, "AUTH_MODE must be"),
    ],
)
def test_settings_errors(monkeypatch, settings, problem):
    for name, value in settings.items():
        monkeypatch.setattr(config, name, value)
    assert any(problem in e for e in config.settings_errors())


def test_good_settings_pass(monkeypatch):
    monkeypatch.setattr(config, "AUTH_MODE", "cloudflare")
    monkeypatch.setattr(config, "CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setattr(config, "CF_ACCESS_AUD", AUD)
    assert config.settings_errors() == []
