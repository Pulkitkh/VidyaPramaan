"""Verifiable enrolment credentials (W3C VC data model, Ed25519 signatures).

Two artefacts are issued per credential:
  * the full VC JSON (with a JWS proof) for the student's wallet / DigiLocker;
  * a compact signed token with minimal claims, embedded in the certificate QR.
Anyone holding the issuer public key can verify either one offline.
"""
import base64
import json
import os
import uuid
from datetime import datetime
from urllib.parse import quote, urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .apaar_registry import mask
from .config import DATA_DIR, PUBLIC_BASE_URL, SECRET_KEY, SECRET_KEY_FROM_ENV

KEY_PATH = DATA_DIR / "issuer_ed25519.pem"


def did_web(base_url: str) -> str:
    """did:web identifier for the host serving /.well-known/did.json (a port is written as %3A)."""
    parts = urlsplit(base_url)
    path = ":".join(quote(p, safe="") for p in parts.path.strip("/").split("/") if p)
    return "did:web:" + quote(parts.netloc, safe="") + (f":{path}" if path else "")


# The issuer is the deployment itself, resolvable by any did:web resolver. In production this would be
# AICTE's own domain (VP_ISSUER_DID=did:web:aicte.gov.in, with did.json published there).
ISSUER_DID = os.getenv("VP_ISSUER_DID") or did_web(PUBLIC_BASE_URL)
ISSUER_NAME = os.getenv("VP_ISSUER_NAME", "Vidya Pramaan prototype issuer (not an official AICTE credential)")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _load_key() -> Ed25519PrivateKey:
    """Issuer key, in order of preference:

    1. VP_ISSUER_KEY: a PEM (or base64 of one), e.g. from a secrets manager or HSM export;
    2. derived from VP_SECRET_KEY with HKDF, so a deployment that sets one secret gets a stable
       signing key without storing a key file in the image;
    3. a local key file, generated on first run (development only).
    """
    env_key = os.getenv("VP_ISSUER_KEY", "").strip()
    if env_key:
        pem = env_key.encode() if env_key.startswith("-----") else base64.b64decode(env_key)
        return serialization.load_pem_private_key(pem, password=None)
    if SECRET_KEY_FROM_ENV:
        seed = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"vidya-pramaan",
                    info=b"issuer-ed25519-v1").derive(SECRET_KEY.encode())
        return Ed25519PrivateKey.from_private_bytes(seed)
    if KEY_PATH.exists():
        return serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    KEY_PATH.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return key


_KEY = _load_key()
_PUB: Ed25519PublicKey = _KEY.public_key()


def key_id() -> str:
    """Short fingerprint of the issuer public key (changes only when the key is rotated)."""
    raw = _PUB.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    import hashlib
    return hashlib.sha256(raw).hexdigest()[:16]


def public_jwk() -> dict:
    raw = _PUB.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {"kty": "OKP", "crv": "Ed25519", "x": _b64(raw), "kid": f"{ISSUER_DID}#key-1"}


def did_document() -> dict:
    """DID document served at /.well-known/did.json, so the issuer key can be resolved from the DID."""
    jwk = {k: v for k, v in public_jwk().items() if k != "kid"}
    vm = f"{ISSUER_DID}#key-1"
    return {
        "@context": ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/suites/jws-2020/v1"],
        "id": ISSUER_DID,
        "verificationMethod": [{"id": vm, "type": "JsonWebKey2020", "controller": ISSUER_DID, "publicKeyJwk": jwk}],
        "assertionMethod": [vm],
    }


def sign_compact(claims: dict) -> str:
    header = _b64(_canonical({"alg": "EdDSA", "typ": "vp-qr+jws", "kid": f"{ISSUER_DID}#key-1"}))
    payload = _b64(_canonical(claims))
    sig = _KEY.sign(f"{header}.{payload}".encode())
    return f"{header}.{payload}.{_b64(sig)}"


def verify_compact(token: str) -> tuple[bool, dict | None]:
    try:
        header, payload, sig = token.strip().split(".")
        _PUB.verify(_unb64(sig), f"{header}.{payload}".encode())
        return True, json.loads(_unb64(payload))
    except (ValueError, InvalidSignature, json.JSONDecodeError, UnicodeDecodeError):
        try:
            return False, json.loads(_unb64(token.split(".")[1]))
        except Exception:
            return False, None


def build_credential(student, enrolment) -> tuple[str, dict, str]:
    cred_id = f"urn:uuid:{uuid.uuid4()}"
    issued = datetime.now().astimezone().isoformat(timespec="seconds")
    inst, prog = enrolment.institution, enrolment.programme
    vc = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential", "AICTEEnrolmentCredential"],
        "id": cred_id,
        "issuer": {"id": ISSUER_DID, "name": ISSUER_NAME},
        "issuanceDate": issued,
        "credentialSubject": {
            "apaarId": student.apaar_id,
            "name": student.name,
            "dateOfBirth": student.dob.isoformat(),
            "studentId": enrolment.roll_no,
            "institution": inst.name,
            "aictePermanentId": inst.aicte_pid,
            "programme": prog.name,
            "level": prog.level,
            "admissionYear": enrolment.admission_year,
            "enrolmentStatus": enrolment.status,
        },
        "credentialStatus": {"id": f"{PUBLIC_BASE_URL}/api/credentials/{cred_id}/status",
                             "type": "RegistryStatusCheck"},
    }
    jws = sign_compact(vc)
    vc["proof"] = {"type": "Ed25519Signature2020-JWS", "verificationMethod": f"{ISSUER_DID}#key-1",
                   "created": issued, "jws": jws}
    qr_claims = {
        "cid": cred_id, "a": mask(student.apaar_id), "n": student.name, "sid": enrolment.roll_no,
        "i": inst.name, "pid": inst.aicte_pid, "p": prog.name, "y": enrolment.admission_year,
        "s": enrolment.status, "iat": issued[:10],
    }
    return cred_id, vc, sign_compact(qr_claims)


def verify_vc(vc: dict) -> bool:
    body = {k: v for k, v in vc.items() if k != "proof"}
    jws = (vc.get("proof") or {}).get("jws", "")
    ok, claims = verify_compact(jws)
    return ok and claims == json.loads(_canonical(body))


def resign_token(token: str) -> str:
    """Re-sign the same claims with the current key (used when the issuer key is rotated)."""
    return sign_compact(json.loads(_unb64(token.split(".")[1])))


def resign_vc(vc: dict) -> dict:
    body = {k: v for k, v in vc.items() if k != "proof"}
    proof = dict(vc.get("proof") or {})
    proof["jws"] = sign_compact(body)
    return {**body, "proof": proof}
