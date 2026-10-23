"""Demo authentication with role-based access control.

Tokens are HMAC-signed claims. Production would replace this with Keycloak /
AICTE SSO (OIDC + MFA); endpoints only depend on `current_user` and `require`.
"""
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, fields

from fastapi import Depends, Header, HTTPException

from .config import SECRET_KEY

ROLES = ("AICTE_ADMIN", "INSTITUTION_ADMIN", "VERIFIER", "STUDENT", "AUDITOR")
TOKEN_TTL_SECONDS = 8 * 3600


@dataclass
class User:
    username: str
    role: str
    display_name: str
    institution_id: int | None = None
    student_id: int | None = None
    org: str | None = None


def issue_token(user: User) -> str:
    claims = {**user.__dict__, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_token(token: str) -> User:
    try:
        payload, sig = token.rsplit(".", 1)
    except ValueError:
        raise HTTPException(401, "Malformed token")
    expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(401, "Invalid token")
    claims = json.loads(base64.urlsafe_b64decode(payload))
    if claims.get("exp", 0) < time.time():
        raise HTTPException(401, "Session expired, please sign in again")
    return User(**{f.name: claims.get(f.name) for f in fields(User)})


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
