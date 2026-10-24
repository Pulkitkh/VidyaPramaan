# Security and privacy

What the prototype does today, how it maps to the obligations a government platform holding student data faces, and what production adds. This is an engineering note, not legal advice.

## Data minimisation

- **No Aadhaar is collected or stored.** APAAR is the key. Foreign nationals, OCI students and students who decline APAAR get a provisional AICTE ID (rules APR-005 / APR-007) and are never rejected for it.
- APAAR IDs are masked (`XXXX-XXXX-1234`) in every AICTE, regulator and review view. Full IDs appear only to the student, their own institution, and the affiliating university's degree-print feed (PS requirement 10). Every feed view and export is audited.
- Mobile numbers and e-mails are masked outside the owning institution. Shared-contact findings show masked contacts only.
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
- **Audit trail:** each event hashes the previous one. After each national scan the chain head is signed and published at `/api/audit/checkpoints`. That makes a rewrite of the whole history (edit, then recompute every hash) or a deleted tail detectable; the Audit screen demonstrates all three attacks on an in-memory copy. Appends are serialised so concurrent writers cannot fork the chain.
- **Key rotation** is not hidden: credentials and checkpoints are re-signed and the rotation is written to the audit trail.

## Web hardening

- Content-Security-Policy (`default-src 'self'`, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, HSTS over HTTPS, `Cache-Control: no-store` on the API.
- Static files are served only from inside the built web folder. Path traversal was found and fixed; a regression test covers encoded `../` forms.
- Uploads are capped at 10 MB and 5,000 rows. Excel files are checked for zip bombs before parsing. Exports neutralise spreadsheet formulas (including tab and carriage-return prefixes). Query limits are bounded.
- `test_no_secrets.py` fails the build if a private key, token or credential-type file is committed.

## Mapping to obligations

| Obligation | Prototype | Production |
|---|---|---|
| DPDP Act 2023 / Rules 2025 (consent, notice, purpose limitation; most duties from May 2027) | Per-request field-level consent, revocation, purpose on every statutory lookup, access log | Consent-manager integration (DigiLocker), notices in Indian languages, retention schedule, breach runbook |
| Supreme Court direction that APAAR is voluntary (Jul 2026) | Provisional IDs; opt-out is never a defect | Same |
| CERT-In directions 2022 (6-hour incident reporting, 180-day logs in India, NTP sync) | Append-only signed audit; structured logs | Log shipping to an India-region SIEM, NIC NTP, incident runbook |
| MeitY cloud empanelment and data localisation | Demo on a free cloud instance (Singapore region) | MeitY-empanelled India-region cloud or NIC MeghRaj |
| GIGW 3.0 / WCAG 2.1 AA | Keyboard skip link, labelled controls, text labels on every colour-coded status, Hindi toggle | Full accessibility audit and STQC certification |

## Known gaps

- No SSO/MFA yet; demo sessions only.
- PII columns are not encrypted at rest; PostgreSQL row-level security is not configured.
- Rate limits are in-process; production puts them in an API gateway.
- Checkpoints are signed and public but not yet anchored to an external timestamping service.
