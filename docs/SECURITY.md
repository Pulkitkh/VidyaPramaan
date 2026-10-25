# Security and privacy

What the prototype does today, how it maps to the obligations a government platform holding student data faces, and what production adds. This is an engineering note, not legal advice.

## Data minimisation

- **No Aadhaar is collected or stored.** APAAR is the key. Foreign nationals, OCI students and students who decline APAAR get a provisional AICTE ID (rules APR-005 / APR-007) and are never rejected for it.
- APAAR IDs are masked (`XXXX-XXXX-1234`) in every AICTE, regulator and review view. Full IDs appear only to the student, their own institution, and the affiliating university's degree-print feed (PS requirement 10). Every feed view and export is audited.
- Mobile numbers and e-mails are masked outside the owning institution. Shared-contact findings show masked contacts only.
- **Encryption at rest:** mobile numbers, e-mails, passport and OCI card numbers are stored AES-256-GCM encrypted, one random nonce per value (`app/fieldcrypt.py`). The database file, a dump or a replica holds only ciphertext for them. The key comes from `VP_DATA_KEY` (a secrets manager or KMS in production, kept apart from the database). `test_contact_details_and_document_numbers_are_encrypted_at_rest` reads the raw table to prove it. Names and dates of birth stay searchable for identity matching; production adds disk-level encryption (managed PostgreSQL) for the rest.
- The QR carries minimal claims (name, masked APAAR, student ID, institution, programme, status at issue). Everything else needs the student's consent.

## Lawful basis and consent

- AICTE's use of admission data for approvals and monitoring is a statutory regulatory function (DPDP Act s.7 "legitimate uses"). Each statutory lookup needs a purpose of at least 10 characters and appears in the student's own access log.
- Any disclosure to employers or other verifiers needs the student's consent per request, per field. The student approves with an OTP, can deny or revoke, and sees every access. The access window (24 h) starts when the student approves.
- APAAR consent on upload is recorded explicitly as GIVEN or REFUSED. A blank is flagged (APR-008) and stored as NOT_RECORDED; consent is never assumed.
- The reply to a consent request is the same whether or not the APAAR ID exists, so verifiers cannot probe the registry.

## Authentication and access

| Role | Sees | Can change |
|---|---|---|
| AICTE officer | National data, student-level review items (masked IDs) | Review decisions (reason required), scans, reports |
| Auditor | Same as AICTE, read-only | Nothing; reading never creates records |
| State regulator | National aggregates; institution detail for its own state | Nothing; no student-level screens |
| University | Its affiliated colleges; degree-print feed | Issues credentials for printing |
| Institution | Its own records and uploads | Uploads, corrections, exits, API keys |
| Verifier | Only what a student consented to | Consent requests |
| Student | Own record, credentials, access log | Consent decisions |

- Demo sign-in, on-screen OTPs and demo reset exist only when `VP_DEMO_MODE=1` (off by default). Resetting the shared demo needs `VP_DEMO_PIN`.
- Sessions are HMAC-signed with an 8-hour expiry. Session tokens never go into URLs: files download with the Authorization header, and the live event stream uses a 60-second, single-purpose ticket. Each live event goes only to the roles and people it concerns.
- ERP integration uses per-institution API keys (only a SHA-256 hash is stored, the key is shown once and can be revoked) and idempotency keys.
- OTPs come from a CSPRNG and are stored as a keyed hash bound to the request. After 5 wrong attempts the request locks.
- Rate limits apply to sign-in, public QR verification, consent requests and reset. A public QR scan is logged in the student's history at most once per 10 minutes.

## Integrity

- **Credentials:** Ed25519 signatures. The key is derived from the deployment secret (HKDF) or supplied as `VP_ISSUER_KEY`, so no key file ships in the image. A correction to name, date of birth or gender supersedes the old credential; an exit revokes it. The public verifier shows VERIFIED, SUPERSEDED, REVOKED or TAMPERED. The signature is also checked on the verifier's own device (WebCrypto Ed25519), which works offline.
- **Issuer identity:** the issuer is a resolvable `did:web` for the host that serves it (`/.well-known/did.json` lists the signing key), not a placeholder. Production sets `VP_ISSUER_DID=did:web:aicte.gov.in` and publishes the document on AICTE's domain. Credentials say plainly that the prototype issuer is not an official AICTE issuer.
- **Revocation offline:** `/api/credentials/status-list` is a signed list of every revoked or superseded credential, valid 24 hours. The verifier's device caches it while online and verifies its signature on every use, so an offline check reports "not revoked as of <time>" (or "unknown") instead of implying current status. An edited list fails its signature.
- **Audit trail:** each event hashes the previous one. After each national scan the chain head is signed and published at `/api/audit/checkpoints`. That makes a rewrite of the whole history (edit, then recompute every hash) or a deleted tail detectable; the Audit screen demonstrates all three attacks on an in-memory copy. Appends cannot fork the chain: a process lock, a PostgreSQL advisory lock shared by every app instance, and a unique index on the previous-hash column, so the database itself refuses a second event claiming the same predecessor. If the lock cannot be taken the change is refused (HTTP 503), never written out of order. Tests cover both.
- **Key rotation** is not hidden: credentials and checkpoints are re-signed and the rotation is written to the audit trail.

## Web hardening

- Content-Security-Policy (`default-src 'self'`, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, HSTS over HTTPS, `Cache-Control: no-store` on the API.
- Static files are served only from inside the built web folder. Path traversal was found and fixed; a regression test covers encoded `../` forms.
- Uploads are capped at 10 MB and 5,000 rows. Excel files are checked for zip bombs before parsing. Exports neutralise spreadsheet formulas (including tab and carriage-return prefixes). Query limits are bounded.
- `test_no_secrets.py` fails the build if a private key, token or credential-type file is committed.

## Evidence run on every push (CI)

| Check | Result at last run |
|---|---|
| Unit and API tests, SQLite and PostgreSQL 16 | 65 / 65 pass |
| Line coverage of `app/` | 93% (build fails below 90%) |
| Schema migrations (Alembic): upgrade, drift check against the models, full rollback, upgrade again | pass on PostgreSQL 16 and SQLite |
| Static analysis (bandit) | 0 findings (4 reviewed false positives annotated in code) |
| Python dependencies (pip-audit) | 0 known vulnerabilities |
| Shipped JavaScript dependencies (npm audit, runtime) | 0 known vulnerabilities (React Router upgraded to 7.18.4 to close two advisories) |
| Accessibility (axe-core, WCAG 2.1 A/AA), 17 screens at desktop and 390 px phone width | 0 violations (contrast, keyboard-reachable scroll areas and meter labels fixed); report in `docs/accessibility_report.json` |
| Seven-role browser walkthrough (Playwright, Chromium) | pass, no console errors |

Not covered by these: an independent penetration test, cross-browser runs beyond Chromium, and load testing at national scale. They are planned for the pilot (STQC / CERT-In-empanelled auditor).

## Mapping to obligations

| Obligation | Prototype | Production |
|---|---|---|
| DPDP Act 2023 / Rules 2025 (consent, notice, purpose limitation; most duties from May 2027) | Per-request field-level consent, revocation, purpose on every statutory lookup, access log | Consent-manager integration (DigiLocker), notices in Indian languages, retention schedule, breach runbook |
| Supreme Court direction that APAAR is voluntary (Jul 2026) | Provisional IDs; opt-out is never a defect | Same |
| CERT-In directions 2022 (6-hour incident reporting, 180-day logs in India, NTP sync) | Append-only signed audit; structured logs | Log shipping to an India-region SIEM, NIC NTP, incident runbook |
| MeitY cloud empanelment and data localisation | Demo on a free cloud instance (Singapore region) | MeitY-empanelled India-region cloud or NIC MeghRaj |
| GIGW 3.0 / WCAG 2.1 AA | Automated axe-core check on every screen passes; keyboard skip link, labelled controls, text labels on every colour-coded status, Hindi toggle | Manual audit with screen-reader users and STQC certification |

## Known gaps

- No SSO/MFA yet; demo sessions only. Production uses the government SSO (e.g. Parichay / MeriPehchaan) with MFA for officers.
- Tenant isolation is enforced in the API layer (every query is scoped by role, institution, university or state, with tests); PostgreSQL row-level security as a second layer is planned.
- Rate limits are in-process, so they protect one instance; production puts them in an API gateway shared by all instances.
- Checkpoints are signed and public, so anyone can keep copies, but they are not yet anchored to an external timestamping service (RFC 3161).
- The issuer key is derived from the deployment secret; production keeps it in an HSM.
- No independent security audit or penetration test yet.
