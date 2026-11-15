"""Who is making this request.

The app has no accounts or passwords of its own. In `cloudflare` mode, Cloudflare
Access signs users in (email one-time code) and adds a signed JWT to every request
it forwards. We verify that token's signature, audience and issuer against the
team's public keys; the email inside it identifies the user. Never trust the plain
`Cf-Access-Authenticated-User-Email` header: anyone who reaches the app without
going through Cloudflare could set it.

In `single` mode every request is SINGLE_USER_EMAIL.

Settings are read from app.config at call time so tests can change them.
"""

from datetime import timedelta
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import config
from app.db import SessionDep
from app.models import User, utcnow

TOKEN_HEADER = "Cf-Access-Jwt-Assertion"
TOKEN_COOKIE = "CF_Authorization"
LAST_SEEN_RESOLUTION = timedelta(hours=1)  # don't write to the database on every request


@lru_cache(maxsize=4)
def _jwks_client(team_domain: str) -> jwt.PyJWKClient:
    # Fetches and caches the team's signing keys; refetches when it sees an unknown key id.
    return jwt.PyJWKClient(f"https://{team_domain}/cdn-cgi/access/certs", cache_keys=True)


def verify_access_token(token: str) -> str:
    """Return the email from a valid Cloudflare Access token, or raise jwt.PyJWTError."""
    team = config.CF_ACCESS_TEAM_DOMAIN
    key = _jwks_client(team).get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=config.CF_ACCESS_AUD,
        issuer=f"https://{team}",
        options={"require": ["exp", "iat", "aud", "iss"]},
    )
    email = str(claims.get("email", "")).strip().lower()
    if not email:
        raise jwt.InvalidTokenError("token has no email claim")
    return email


def request_email(request: Request) -> str:
    if config.AUTH_MODE == "single":
        return config.SINGLE_USER_EMAIL
    token = request.headers.get(TOKEN_HEADER) or request.cookies.get(TOKEN_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in through Cloudflare Access first.")
    try:
        return verify_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Your sign-in is invalid or has expired.") from None


def get_or_create_user(session: Session, email: str) -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email)
        session.add(user)
        try:
            session.commit()
        except IntegrityError:  # two first requests at once
            session.rollback()
            return session.exec(select(User).where(User.email == email)).one()
        session.refresh(user)
    elif utcnow() - user.last_seen_at > LAST_SEEN_RESOLUTION:
        user.last_seen_at = utcnow()
        session.add(user)
        session.commit()
    return user


def get_current_user(request: Request, session: SessionDep) -> User:
    user = get_or_create_user(session, request_email(request))
    request.state.user = user  # for templates (base.html shows who is signed in)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
