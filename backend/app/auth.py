"""Demo authentication with role-based access control.

Tokens are HMAC-signed claims. Production would replace this with Keycloak /
AICTE SSO (OIDC + MFA); endpoints only depend on `current_user` and `require`.

Two short-lived token kinds keep long-lived session tokens out of URLs:
  * stream tickets (60 s) for the Server-Sent Events connection, which cannot send headers;
  * the browser downloads files with the Authorization header, so no token appears in a link.
"""
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, fields

from fastapi import Depends, Header, HTTPException

from .config import SECRET_KEY

ROLES = ("AICTE_ADMIN", "INSTITUTION_ADMIN", "VERIFIER", "STUDENT", "AUDITOR", "REGULATOR", "UNIVERSITY")
TOKEN_TTL_SECONDS = 8 * 3600
TICKET_TTL_SECONDS = 60


@dataclass
class User:
    username: str
    role: str
    display_name: str
    institution_id: int | None = None
    student_id: int | None = None
    org: str | None = None
    university: str | None = None
    state: str | None = None


def _sign(claims: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _verify(token: str) -> dict:
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        raise HTTPException(401, "Malformed token")
    expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(401, "Invalid token")
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except ValueError:
        raise HTTPException(401, "Malformed token")
    if claims.get("exp", 0) < time.time():
        raise HTTPException(401, "Session expired, please sign in again")
    return claims


def otp_hash(consent_id: int, otp: str) -> str:
    """OTPs are stored only as a keyed hash bound to the request they belong to."""
    return hmac.new(SECRET_KEY.encode(), f"{consent_id}:{otp}".encode(), hashlib.sha256).hexdigest()


def issue_token(user: User) -> str:
    return _sign({**user.__dict__, "exp": int(time.time()) + TOKEN_TTL_SECONDS, "kind": "session"})


def issue_ticket(user: User, scope: str) -> str:
    return _sign({**user.__dict__, "exp": int(time.time()) + TICKET_TTL_SECONDS, "kind": "ticket",
                  "scope": scope})


def _user(claims: dict) -> User:
    return User(**{f.name: claims.get(f.name) for f in fields(User)})


def parse_token(token: str) -> User:
    claims = _verify(token)
    if claims.get("kind", "session") != "session":
        raise HTTPException(401, "Not a session token")
    return _user(claims)


def parse_ticket(ticket: str, scope: str) -> User:
    claims = _verify(ticket)
    if claims.get("kind") != "ticket" or claims.get("scope") != scope:
        raise HTTPException(401, "Ticket not valid for this resource")
    return _user(claims)


def current_user(authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Login required")
    return parse_token(authorization.removeprefix("Bearer "))


def require(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Role {user.role} cannot access this resource")
        return user
    return dep
