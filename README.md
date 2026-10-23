# Vidya Pramaan

**APAAR ID-based student data management and verification platform for AICTE-approved institutions.**
Prototype for Smart India Hackathon 2026, problem statement **SIH26263** (AICTE, Regulation Bureau · Software · Smart Automation). Team **AI Riders**.

> One student. One APAAR ID. One verifiable record.

All institutions, students and APAAR IDs in this repository are **synthetic**. Nothing here connects to a real APAAR, DigiLocker or AICTE system.

![AICTE national dashboard](docs/screenshots/10_aicte_dashboard.png)

## What it does

Institution → student data upload → APAAR validation → data verification → AICTE central repository → analytics & monitoring → authorised verification

| PS requirement | Where it lives in the prototype |
|---|---|
| 1. Secure upload/update API keyed on APAAR | Excel / CSV upload screen (re-uploads update existing records) + `POST /api/v1/students:validate` and `:submit` (JSON) |
| 2. Intake, enrolment, supernumerary, NRI, OCI, FN fields | Upload template columns; per-programme seat ledger with supernumerary caps |
| 3. Automated validation (duplicates, invalid/missing APAAR, excess intake, inconsistencies, cross-institution duplicates) | `backend/app/validation.py` (25 rule codes) + `backend/app/scan.py` (national scan) |
| 4. Real-time dashboards for AICTE and institutions | AICTE national overview (live via Server-Sent Events), institution overview |
| 5. Secure verification for stakeholders | Public QR verification + consent-based verification (student approves by OTP) |
| 6. Verifiable student records | W3C Verifiable Credential signed with Ed25519, compact signed QR token |
| 7. Integration with existing systems | REST API with OpenAPI docs at `/docs`; registry adapter for DigiLocker / API Setu |
| 8. Security, privacy, RBAC, audit, consent | Role-based access, masked APAAR IDs, consent ledger, student-visible access log, hash-chained audit log |
| 9. Reports | Excess-intake CSV, state summary XLSX (intake, utilisation, risk, findings, diversity) |
| 10. APAAR ID + student ID on certificates | Certificate PDF with APAAR ID, roll number and verification QR; `GET /api/v1/certificate-data/{id}` |

### Beyond collection

- **Explainable validation.** Every flag has a stable rule code, severity, plain-language message, evidence and ruleset version.
- **Live seat ledger.** Admission #61 in a 60-seat programme is rejected at upload. Supernumerary quotas (FN/OCI/PIO, TFW, lateral, EWS) are capped separately and configured in `backend/app/config.py`.
- **Cross-institution identity matching.** The same APAAR active at two institutions (DUP-002), and the same person under a different APAAR, found by blocking on date of birth and fuzzy-matching names and father's names (DUP-003).
- **Explainable risk score.** An Isolation Forest over peer-relative features plus rule evidence ranks institutions, with the reasons shown.
- **Consent-first verification.** Verifiers request specific fields. The student approves with an OTP, sees every access, and can revoke.
- **Inclusive by design.** Students who decline APAAR, and FN/OCI students (APAAR needs Aadhaar-based KYC), get a provisional ID. They are noted (APR-005 / APR-007), not rejected.
- **Tamper-evident audit.** Each audit event hashes the previous one. The audit screen can simulate a direct database edit and shows where the chain breaks.

## Quick start

Requires Python 3.11+ and Node 18+.

```bash
./run.sh                 # installs, seeds synthetic data, builds the UI, serves on :8000
RESEED=1 ./run.sh        # start again from a fresh dataset
```

Open http://localhost:8000 and choose a demo user. API reference: http://localhost:8000/docs.

**Demo day tips**
- To repeat the walkthrough, sign in as the AICTE officer and press **Reset demo** on the national overview. It removes everything submitted through the portal; the audit trail is kept and records the reset.
- To let judges scan the certificate QR with a phone, start the server with the laptop's address so the QR points to it, for example `VP_PUBLIC_BASE_URL=http://192.168.1.20:8000 ./run.sh`, and keep the phone on the same Wi-Fi.
- Sessions expire after 8 hours; sign in again if a screen asks you to.

Manual steps:

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
cd backend && ../.venv/bin/python -m app.seed && ../.venv/bin/uvicorn app.main:app --port 8000
```

For frontend development, run `npm run dev` in `frontend/` (it proxies `/api` to port 8000).

## Five-minute demo script

1. **Institution admin** → Overview shows B.Tech CSE has no data yet → **Upload students** (Excel or CSV) → *Try the demo file*. 77 rows: 65 accepted, 6 with review flags, 12 rejected, with codes for missing / invalid / unregistered APAAR, registry mismatch, duplicates within the file and across institutions, admissions #61–#63 beyond intake, the 4th TFW seat over its cap, FN without passport, OCI without card, and more.
2. **Submit 65 valid rows to AICTE.** The national scan re-runs. The seat ledger shows 60/60 and never exceeds intake.
3. **AICTE officer** → National overview: KPIs, state tile map, highest-risk institutions with reasons → open one to see its seat ledger and why it scored high.
4. **Review queue** → filter `DUP-003` → open an item: both records side by side with the evidence → resolve, dismiss or escalate (recorded in the audit trail).
5. **Employer / verifier** → request consent for the student's APAAR (fields: enrolment status, programme, institution).
6. **Student** → approve with the demo OTP; see the credential QR, download the certificate PDF, and check who accessed the record.
7. **Employer** → *Fetch result*: only the approved fields are shown. Sign out and open the QR link: **Verified**. Change one character of the token and it fails.
8. **AICTE officer** → **Audit trail** → *Verify chain* → *Simulate DB tampering* → tampering is detected at the edited event → *Restore*.

## Measured on the synthetic dataset

`cd backend && python -m scripts.benchmark` (on a freshly seeded database). Result in [`docs/benchmark.json`](docs/benchmark.json):

| Metric | Result |
|---|---|
| Planted defect types caught in the upload file | 16 / 16 |
| False flags on clean rows in the upload file | 0 of 56 |
| Planted dual enrolments found (DUP-002) | 181 / 181 |
| Planted same-person-different-APAAR cases found (DUP-003) | 60 / 60 |
| Planted anomalous institutions in the top-42 risk ranking | 41 / 42 |
| Validate 77 uploaded rows | 57 ms |
| National scan over 48,053 enrolments | ≈1 s |

These numbers come from synthetic data with known, planted anomalies. Real data will be noisier, so thresholds are configurable and every flag goes to a human reviewer.

## Architecture

```
frontend/ (React + TypeScript + Tailwind + Recharts)
   │  REST + Server-Sent Events
backend/app/
   main.py            FastAPI routes, RBAC, reports, SPA hosting
   validation.py      row-level rule engine (25 rule codes)
   scan.py            national scan: intake overruns, dual enrolment, identity duplicates, registry gaps
   anomaly.py         Isolation Forest + rule evidence → institution risk score with reasons
   apaar_registry.py  registry adapter: MockApaarRegistry now, DigiLocker / API Setu stub for production
   credentials.py     W3C VC + compact QR token, Ed25519 signatures, public JWK
   certificates.py    certificate PDF with APAAR ID, student ID and QR
   audit.py           hash-chained, append-only audit log
   seed.py            synthetic national dataset with planted anomalies + demo upload file
```

Production would swap in PostgreSQL (row-level security, encrypted PII columns, partitioning by academic year), AICTE SSO / Keycloak (OIDC + MFA), the DigiLocker / API Setu connector once AICTE is onboarded as a partner, and hosting on NIC / MeghRaj for data localisation.

## Rule catalogue

| Code | Severity | Meaning |
|---|---|---|
| SCH-001/002/003 | Error | Missing field, invalid value, invalid date |
| PRG-001 | Error | Programme not approved for this institution |
| APR-001 | Error | APAAR missing and no consent refusal recorded |
| APR-002 / 003 / 006 | Error | APAAR format invalid / not in registry / deactivated |
| APR-004 | Warning | Name or date of birth differs from the registry |
| APR-005 | Info | Student declined APAAR; provisional ID issued |
| APR-007 | Info | FN / OCI student; APAAR not applicable; provisional ID issued |
| DUP-001 | Error | Duplicate APAAR or roll number within the upload |
| DUP-002 | Warning | Already actively enrolled at another institution |
| DUP-003 | Warning | Probably the same person under a different APAAR |
| UPD-001 | Info | Existing record will be updated |
| INT-001 | Error | Admission beyond approved intake |
| INT-002 | Error | Supernumerary quota cap exceeded |
| CON-001…008 | Error / Warning | FN without passport, OCI without card, nationality conflicts, NRI without country, lateral entry not in year 2, admission outside window, implausible age, quota/nationality mismatch |

Supernumerary caps and the admission window in `config.py` are **demo values** modelled on the AICTE Approval Process Handbook. Check them against the handbook in force before any real use.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q          # 16 API tests on an isolated database
cd e2e && npm install && npx playwright install chromium && npm test   # browser walkthrough (server running on :8000)
```

The API tests cover every planted defect, seat numbering, role-based access, the intake never being exceeded on commit, re-uploads updating records instead of creating new admissions, Excel upload, demo reset, session expiry, export sanitising, risk ranking, consent-scoped disclosure, QR forgery detection, the certificate PDF, audit tamper detection and the reports.

The browser walkthrough resets the demo, then drives all five roles through the eight demo steps above, fails on any browser console error, and saves the screenshots in `docs/screenshots/`.

## Not built yet (production work)

- Live APAAR lookups: the registry adapter uses a mock. Real lookups need AICTE to be onboarded as a DigiLocker / API Setu partner.
- AICTE SSO (OIDC + MFA), rate limiting and mTLS. The prototype uses signed demo sessions with role-based access and 8-hour expiry.
- PostgreSQL with encrypted PII columns and row-level security. The prototype uses SQLite.
- Real OTP delivery. The demo shows the OTP on screen.
- Hindi covers navigation and headline labels, not every screen.
- No public deployment; it runs locally with `./run.sh`.

## Submission deck

`ppt/SIH26263_AI_Riders_Idea.pptx` and `.pdf`: six slides in SIH idea-template order (title, proposed solution, technical approach, feasibility & viability, impact & benefits, research & references). Rebuild with `cd ppt && npm install && npm run build` after refreshing `docs/screenshots/`. Fill in the Team ID on slide 1 and copy the content onto the official SIH template if your institute requires it.
