# Data dictionary

## Upload template (one row per student)

The same columns are accepted by CSV, Excel and the JSON API. Common ERP header spellings are recognised automatically (for example *Student Name*, *APAAR No*, *Date of Birth*, *Roll Number*, *Mother's Name*, *Course Code*, *Mobile No*); the upload screen shows the mapping it applied.

| Column | Required | Values | Rule codes |
|---|---|---|---|
| `apaar_id` | Unless FN/OCI or consent REFUSED | 12 digits | APR-001/002/003/004/006, DUP-001/002 |
| `apaar_consent` | Yes (blank is flagged) | GIVEN, REFUSED (also Yes/No) | APR-005, APR-008 |
| `roll_no` | Yes | Institution's student ID; unique per institution | DUP-001, UPD-001 |
| `name` | Yes | Letters (any Indian script), spaces, `.` `'` `-` | SCH-002, APR-004 |
| `dob` | Yes | YYYY-MM-DD or DD-MM-YYYY | SCH-003, CON-007 |
| `gender` | Yes | M, F, T (also Male/Female/Transgender) | SCH-002 |
| `category` | Yes | GEN, OBC, SC, ST, EWS (also General, OBC-NCL) | SCH-002 |
| `father_name`, `mother_name`, `guardian_name` | At least one | Name characters | SCH-001, DUP-003 |
| `programme_code` | Yes | A programme approved for the institution this year | PRG-001 |
| `admission_year` | No (defaults to the current year) | 2000 to current year | CON-010 |
| `year_of_study` | No (defaults to 1) | 1 to 6 | SCH-002, CON-005, CON-010 |
| `admission_type` | Yes | REGULAR, LATERAL | CON-005 |
| `quota` | Yes | STATE_CAP, MANAGEMENT, NRI, TFW, FN_OCI_PIO, EWS_SN, LATERAL | INT-001/002, CON-008 |
| `nationality` | No (defaults to Indian) | Country | CON-003 |
| `fn_status`, `oci_status`, `nri_status`, `pwd` | No | Y or N | SCH-002, CON-001/002/004 |
| `oci_card_no`, `passport_no` | When OCI / FN | Text | CON-001, CON-002 |
| `nri_country` | When NRI | Country | CON-004 |
| `admission_date` | Yes | Date in the admission window, not in the future | CON-006, CON-009 |
| `mobile` | No | 10-digit Indian mobile (+91 accepted) | SCH-002, DUP-004 |
| `email` | No | E-mail address | SCH-002, DUP-004 |

## Stored entities

| Entity | Key fields | Notes |
|---|---|---|
| Institution | AICTE Permanent ID, state, type, affiliating university, risk score and reasons | |
| Programme | Code, level (UG / PG / Diploma), academic year, approved intake | Supernumerary caps come from the rules file by level |
| Student | APAAR ID or provisional ID, name, DOB, gender, category, parents/guardian, contact, nationality flags, APAAR consent | One person, one row; APAAR is the join key |
| Enrolment | Student, institution, programme, roll number, admission year, year of study, quota, seat type, admission date, status, exit date and reason | Status: ACTIVE, WITHDRAWN, TRANSFERRED_OUT, GRADUATED, DROPPED. Never deleted |
| Upload batch | Rows as received, column mapping, row results, idempotency key | |
| Finding | Rule code, severity, message, evidence, ruleset version, fingerprint, status, reason, decided by/at | Status: OPEN, RESOLVED, DISMISSED, ESCALATED, REJECTED |
| Credential | Signed credential (JSON), compact QR token, status and reason | ACTIVE, SUPERSEDED, REVOKED |
| Consent request | Verifier, purpose, fields requested, status, OTP hash, attempts, expiry | PENDING, APPROVED, DENIED, REVOKED, EXPIRED, LOCKED |
| Verification log | Who saw what, on which basis (consent, statutory, QR scan) | Shown to the student |
| Audit event | Time, actor, role, action, entity, details, previous hash, hash | Append-only chain |
| Audit checkpoint | Event count, head event, head hash, Ed25519 signature | Public |
| API key | Institution, label, prefix, SHA-256 hash, last used, revoked | Key shown once |
