"""APAAR registry adapter.

There is no public APAAR/ABC lookup API. Production access goes through the
DigiLocker / API Setu partner onboarding (apply -> API key -> integrate ->
audit -> go-live). The platform therefore talks to the registry only through
this small interface, so the mock used in the demo can be swapped for the real
connector without touching the validation engine.
"""
import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy.orm import Session

from .config import APAAR_REGISTRY
from .models import MockApaarRecord

APAAR_PATTERN = re.compile(r"^[1-9]\d{11}$")


def is_valid_format(apaar_id: str) -> bool:
    return bool(APAAR_PATTERN.match(apaar_id or ""))


def mask(apaar_id: str | None) -> str:
    if not apaar_id:
        return "—"
    return f"XXXX-XXXX-{apaar_id[-4:]}"


@dataclass
class RegistryResult:
    found: bool
    name: str | None = None
    dob: date | None = None
    gender: str | None = None
    status: str | None = None
    source: str = "mock"


class ApaarRegistry(Protocol):
    def lookup(self, apaar_id: str) -> RegistryResult: ...


class MockApaarRegistry:
    """Synthetic registry seeded alongside the demo data."""

    def __init__(self, db: Session):
        self.db = db

    def lookup(self, apaar_id: str) -> RegistryResult:
        rec = self.db.get(MockApaarRecord, apaar_id)
        if rec is None:
            return RegistryResult(found=False)
        return RegistryResult(True, rec.name, rec.dob, rec.gender, rec.status, "mock")


class DigiLockerApaarRegistry:
    """Placeholder for the production connector.

    Expected flow once AICTE holds API Setu credentials: OAuth2 client
    credentials -> consent-backed pull of the student's ABC/APAAR document ->
    compare demographic fields -> cache only the verification outcome.
    """

    def lookup(self, apaar_id: str) -> RegistryResult:
        raise NotImplementedError("Requires DigiLocker / API Setu partner credentials")


def get_registry(db: Session) -> ApaarRegistry:
    if APAAR_REGISTRY == "digilocker":
        return DigiLockerApaarRegistry()
    return MockApaarRegistry(db)
