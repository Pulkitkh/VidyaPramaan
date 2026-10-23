# Evidence for every claim in the idea deck

Each statement on the slides maps to an automated check or a measured result. Run them yourself:

```bash
cd backend && ../.venv/bin/python -m pytest -q                         # 25 API tests (SQLite)
VP_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>/<db> ../.venv/bin/python -m pytest -q   # same 25 on PostgreSQL
cd backend && python -m app.seed && python -m scripts.benchmark         # detection numbers (docs/benchmark.json)
cd e2e && npm test                                                      # browser walkthrough, server on :8000
```

Tests named below live in `backend/tests/test_flow.py`. "Walkthrough" means `e2e/demo_walkthrough.mjs`.

## Slide 1: title
| Claim | Evidence |
|---|---|
| PS ID SIH26263, exact title, theme Smart Automation, category Software | Official SIH 2026 listing (AICTE, Regulation Bureau) |

## Slide 2: proposed solution
| Claim | Evidence |
|---|---|
| Upload by Excel, CSV or API | `test_excel_upload_matches_csv`, `test_upload_flags_every_planted_defect`, `test_json_api_validate_and_submit` |
| APAAR validation against a registry | APR-001…007 rules; registry is a mock adapter (`apaar_registry.py`), stated on slide 4 |
| 25 explained rules (code, evidence, ruleset version) | `test_rule_catalogue_has_25_explained_rules` |
| One record per student; re-uploads update it | `test_reupload_after_commit_is_update_not_new_admission`, `test_reupload_applies_corrections` |
| Live risk map / monitoring | Walkthrough: dashboard in a second browser updates without reload after a submission (measured 260 ms) |
| Consent + signed QR verification | `test_consent_flow_discloses_only_scope`, `test_qr_token_verifies_and_detects_tampering` |
| Seat #61 in a 60-seat course blocked | `test_intake_overflow_counts_seats`, `test_commit_never_exceeds_intake` |
| Supernumerary (quota) caps | INT-002 in `test_upload_flags_every_planted_defect`; TFW 3/3 in `test_commit_never_exceeds_intake` |
| Cross-college match, exact + fuzzy | DUP-002 / DUP-003 in upload test; benchmark 181/181 and 60/60 |
| ML risk score with plain reasons | `test_national_dashboard_and_risk`, `test_risk_scores_come_with_plain_reasons` |
| Tamper-evident (hash-chained) audit | `test_audit_chain_detects_tampering`, walkthrough tamper step |

## Slide 3: technical approach
| Claim | Evidence |
|---|---|
| Python · FastAPI, REST + OpenAPI | `test_json_api_validate_and_submit` checks `/openapi.json` |
| React · TypeScript · Tailwind · Recharts | `frontend/package.json`; walkthrough |
| SQLite in the demo, PostgreSQL in production | Full suite passes on PostgreSQL 16 (run above) |
| scikit-learn Isolation Forest, RapidFuzz | `backend/app/anomaly.py`, `backend/app/validation.py` |
| Ed25519 · W3C VC · signed QR | `backend/app/credentials.py`; QR forgery test |
| Flow: errors return with reasons, fix and re-upload | Upload tests + re-upload correction test |
| Commit triggers national scan and risk refresh | `services.commit_batch`; commit response includes the scan result |
| Screenshot: 77 rows → 65 accepted, 12 returned | `test_upload_flags_every_planted_defect` (77 rows, 12 errors) |

## Slide 4: feasibility
| Claim | Evidence |
|---|---|
| 16/16, 181/181, 60/60, 41/42, 0 false flags on 56 clean rows, ~1 s scan of 48,053 enrolments | `docs/benchmark.json` from `scripts/benchmark.py` on a fresh seed (re-run after every change) |
| 25 API tests on SQLite and PostgreSQL; walkthrough of all 5 roles | Commands above; walkthrough covers AICTE officer, institution, verifier, student, auditor |
| Provisional ID for students without APAAR, never rejected | `test_provisional_ids_for_students_without_apaar`; APR-005 / APR-007 are INFO |
| Consent per request, masked IDs, access log for the student | `test_consent_flow_discloses_only_scope`, `test_apaar_ids_are_masked_in_aicte_views`, `test_consent_revocation_and_access_log` |
| Flags are review items; officer decides; every action audited | `test_officer_decision_is_audited`, `test_auditor_is_read_only` |
| Excel template with drop-downs, plain errors, Hindi toggle, mobile | `test_excel_template_has_dropdowns_and_report_has_diversity`; walkthrough Hindi step and 390 px mobile screenshot |

## Slide 5: impact
| Claim | Evidence |
|---|---|
| State / gender / category analytics and reports | State-summary XLSX has State, Findings and Diversity sheets (test above) |
| Student controls who sees the record | Consent approve / deny / revoke + access log tests |
| Certificate with APAAR ID + student ID + QR; QR verified | `test_certificate_pdf`; screenshots `25_certificate.png`, `23_public_qr_verified.png` |
| Open-source, no licence cost | All dependencies are MIT / BSD / Apache licensed (FastAPI, React, scikit-learn, SQLAlchemy, RapidFuzz, cryptography) |

Impact statements about fairness, paperwork and fraud are expected benefits, not measured results.

## Slide 6: research
| Finding | Source |
|---|---|
| APAAR is created through Aadhaar-based verification | Vikaspedia APAAR overview; institutional APAAR notices |
| APAAR consent is voluntary | MoE / consent-form guidance; reported Supreme Court direction on opt-out (Jul 2026) |
| DPDP Rules 2025 notified Nov 2025, phased to May 2027 | EY and law-firm summaries of the notified rules |
| AICTE asks for APAAR-linked records on NAD / ABC | AICTE circular, June 2026 (TeamLease RegTech summary) |
| APH 2024-27 sets supernumerary quotas | aicte.gov.in Approval Process Handbook |
