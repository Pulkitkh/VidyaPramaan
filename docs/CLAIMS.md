# Evidence for every claim in the idea deck

Each statement on the slides maps to an automated check, a measured result or a cited source. Run them yourself:

```bash
cd backend && ../.venv/bin/python -m pytest -q                                   # 58 tests (SQLite)
VP_DATABASE_URL=postgresql+psycopg://user:pw@host/db ../.venv/bin/python -m pytest -q   # same 58 on PostgreSQL 16
cd backend && python -m app.seed && python -m scripts.benchmark                   # docs/benchmark.json
cd backend && python -m scripts.identity_eval                                     # name-matching precision / recall
cd e2e && npm test                                                                # browser walkthrough, server on :8000
```

Tests named below live in `backend/tests/test_flow.py` and `backend/tests/test_platform.py`. "Walkthrough" means `e2e/demo_walkthrough.mjs`.

## Slide 1: title
| Claim | Evidence |
|---|---|
| PS ID SIH26263, exact title, theme Smart Automation, category Software | Official SIH 2026 listing (AICTE, Regulation Bureau) |
| Working prototype at the live URL | Render service `vidya-pramaan-sih26263`; walkthrough runs against any base URL (`BASE_URL=...`) |

## Slide 2: proposed solution
| Claim | Evidence |
|---|---|
| Upload by Excel, CSV or ERP API | `test_excel_upload_matches_csv`, `test_json_api_validate_and_submit`, `test_erp_headers_are_mapped_automatically`, `test_api_keys_and_idempotent_submit` |
| 31 explained rules | `test_rule_catalogue_has_31_explained_rules` |
| AISHE data 2–3 years late | AISHE 2022-23 and 2023-24 reports released together in 2026 (deck reference 5) |
| Excess admission = 5× fee per student | *FORE School of Management v AICTE*, Supreme Court, 21 Jun 2019 (reference 3); rules file `excess_admission_penalty` |
| Seat #61 of 60 blocked at upload and at submit | `test_intake_overflow_counts_seats`, `test_commit_never_exceeds_intake`, `test_commit_revalidates_a_stale_batch` |
| Cross-college match + shared-contact rings | DUP-002 / DUP-003 in `test_upload_flags_every_planted_defect`; `test_shared_contact_clusters_are_found_with_members` |
| Signed QR checks offline; consent for more | `test_qr_token_verifies_and_detects_tampering`; walkthrough asserts "On this device: signature valid"; `test_consent_flow_discloses_only_scope` |
| Twin-safe matching (Mohd = Mohammed, Rohit ≠ Mohit) | `test_matcher_keeps_twins_apart_and_joins_spelling_variants`, `test_seeded_twins_are_not_flagged_as_duplicates` |
| Ghost-admission map (1 phone, 8 students, 2 colleges) | `test_shared_contact_clusters_are_found_with_members`; screenshot `19_review_shared_contact_cluster.png` |
| Decisions kept: reason required, never re-flagged | `test_decisions_need_a_reason_and_survive_the_next_scan` |
| Signed checkpoints catch a full history rewrite | `test_signed_checkpoints_catch_rewrites_and_truncation`; screenshot `18_audit_rewrite_detected.png` |
| Rules as data, 2026-27 caps by level with sources | `test_near_cap_note_and_supernumerary_caps_by_level`; `backend/app/rules/aicte_2026_27.json` |
| APAAR on degrees: university print feed with QR | `test_university_gets_degree_print_feed_for_affiliated_colleges_only` |

## Slide 3: technical approach
| Claim | Evidence |
|---|---|
| Python · FastAPI, REST + OpenAPI | `test_json_api_validate_and_submit` checks `/openapi.json` |
| React · TypeScript, installable PWA | `frontend/package.json`; `frontend/public/manifest.webmanifest`, `sw.js` |
| PostgreSQL 16 (SQLite in the demo) | Full suite passes on PostgreSQL 16 (command above) |
| scikit-learn Isolation Forest; name matcher | `backend/app/anomaly.py`, `backend/app/matching.py` |
| Ed25519 · W3C credential, signed QR + audit | `backend/app/credentials.py`, `backend/app/audit.py`; QR forgery and checkpoint tests |
| Errors return with reasons; fix and re-upload | Upload tests; `test_reupload_applies_corrections` |
| National scan: duplicates, intake, contacts | `backend/app/scan.py`; runs in the background after every submission |
| Risk vs peers, with reasons | `test_risk_scores_come_with_plain_reasons` (reasons name the peer group) |
| Screenshot: 77 rows → 65 accepted, 12 returned | `test_upload_flags_every_planted_defect` (77 rows, 12 errors); `test_commit_never_exceeds_intake` (65 created) |
| 7 demo roles | `main.demo_users`; walkthrough signs in as each |

## Slide 4: feasibility
| Claim | Evidence |
|---|---|
| 0.79 / 0.92 held-out precision / recall (old matcher 0.65 / 0.68) | `scripts/identity_eval.py` on `tests/data/identity_pairs_holdout.csv`; `test_identity_matching_beats_previous_matcher_on_held_out_pairs` |
| 0 / 80 twins wrongly merged | `docs/benchmark.json` `twins_wrongly_flagged`; `test_seeded_twins_are_not_flagged_as_duplicates` |
| 17/17 planted error types; 0 false flags on 56 clean rows | `docs/benchmark.json` |
| 164 · 57 · 4 planted dual enrolments, identity duplicates, contact rings found | `docs/benchmark.json` (recall 164/164, 57/57, 4/4) |
| 42/46 top-ranked colleges truly anomalous | `docs/benchmark.json` `risk_precision_at_k` |
| 58 tests, SQLite + PostgreSQL 16; 7-role walkthrough | Commands above |
| Planted figures are regression checks, not real-world accuracy | Stated on the slide and in `scripts/benchmark.py` |
| Provisional ID; mother's or guardian's name accepted | `test_provisional_ids_for_students_without_apaar`, `test_mother_or_guardian_is_enough` |
| Consent per field, masked IDs, no Aadhaar stored, access log | `test_consent_flow_discloses_only_scope`, `test_apaar_ids_are_masked_in_aicte_views`, `test_consent_revocation_and_access_log`; no Aadhaar column exists (`models.py`) |
| Officer decides with a reason; decision remembered | `test_decisions_need_a_reason_and_survive_the_next_scan`, `test_officer_decision_is_audited` |
| Rules file per academic year with sources | `backend/app/rules/aicte_2026_27.json`; *Rules in force* page (`26_rules_in_force.png`) |
| ERP headers auto-mapped, Excel template, API keys, Hindi, phone app | `test_erp_headers_are_mapped_automatically`, `test_excel_template_has_dropdowns_and_report_has_diversity`, `test_api_keys_and_idempotent_submit`; walkthrough Hindi step and 390 px mobile screenshot; PWA manifest |
| Roadmap and cost | Plan and estimate, not measured. Cost basis: about 1 crore active records, two app servers plus managed PostgreSQL with backups on MeitY-empanelled cloud, priced at public cloud rates in India |

## Slide 5: impact
| Claim | Evidence |
|---|---|
| Excess and dual enrolment caught at submission | Upload and commit tests |
| Universities print APAAR + student ID | Degree-feed test; `28_university_degree_feed.png` |
| Employers: instant QR check, even offline | Walkthrough on-device check; `frontend/src/lib/offline.ts` |
| Students control who sees the record | Consent approve / deny / revoke and access-log tests |
| Audited evidence pack for review and show-cause | `test_evidence_pack_for_show_cause` |
| Certificate with APAAR ID + student ID + QR; QR verified | `test_certificate_pdf`; screenshots `25_certificate.png`, `23_public_qr_verified.png` |
| Open-source, no licence cost | All dependencies are MIT / BSD / Apache licensed; project is MIT (`LICENSE`) |

Impact statements about fairness, paperwork and fraud are expected benefits, not measured results.

## Slide 6: research
| Claim | Evidence |
|---|---|
| NAD / DigiLocker offers consent-based verification of academic awards | NAD FAQ (nad.digilocker.gov.in) |
| ABC holds credits keyed to APAAR | NCERT APAAR brochure; ABC documentation |
| AISHE publishes institution-level aggregates with a 2–3 year lag | AISHE 2022-23 and 2023-24 reports released in 2026 |
| No published APAAR check digit | No official specification found; assumption A-02 in `docs/ASSUMPTIONS.md` |
| FN/OCI/PIO caps 15% UG, 25% PG for 2026-27 | APH 2026-27 addendum (reported by Careers360); rules file marks it verified |
| APAAR is voluntary | MoE consent guidance; Supreme Court proceedings on APAAR opt-out (2026) |
| DPDP Act 2023, Rules 2025 phased to 2027 | Law-firm summaries of the notified rules (L&S, AZB, SCC Online) |
