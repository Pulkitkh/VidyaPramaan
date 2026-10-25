# Evidence for every claim in the idea deck

Each statement on the slides maps to an automated check, a measured result or a cited source. Run them yourself:

```bash
cd backend && ../.venv/bin/python -m pytest -q                                   # 65 tests (SQLite)
VP_DATABASE_URL=postgresql+psycopg://user:pw@host/db ../.venv/bin/python -m pytest -q   # same 65 on PostgreSQL 16
cd backend && python -m scripts.evidence                                          # docs/evidence.json (coverage, a11y)
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
| 29.6 lakh enrolments in AICTE institutions, 2025-26 | Lok Sabha reply: 29,58,870 for 2025-26 (reported by Careers360, "342 AICTE-approved technical institutions shut") |
| 24.25 crore APAAR IDs issued (Mar 2026) | Rajya Sabha reply, figure as of 30 Mar 2026 (sansad.in) |
| Only total enrolment reaches AICTE (except PGDM) | SIH26263 problem statement text (reference 1) |
| Records hard to verify at source | SIH26263 problem statement text (reference 1) |
| "What is new": none of APAAR, NAD / DigiLocker, ABC checks admissions against approved intake | NAD FAQ, AISHE reports (refs 4–5); ABC holds credits only; comparison table on slide 6 |
| Monitoring "after every submission"; records "per upload" | Background national scan after each commit (`main.refresh_in_background`); benchmark scan 1.6 s over 49,053 enrolments |
| Upload by Excel, CSV or ERP API | `test_excel_upload_matches_csv`, `test_json_api_validate_and_submit`, `test_erp_headers_are_mapped_automatically`, `test_api_keys_and_idempotent_submit` |
| 31 explained rules | `test_rule_catalogue_has_31_explained_rules` |
| AISHE data 2–3 years late | AISHE 2022-23 and 2023-24 reports released together in 2026 (deck reference 5) |
| Excess admission = 5× fee per student | AICTE Approval Process Handbook (fine of five times the total fee per excess student); *FORE School of Management v AICTE*, Supreme Court, 21 Jun 2019 (reference 3); rules file `excess_admission_penalty` |
| Seat #61 of 60 blocked at upload and at submit | `test_intake_overflow_counts_seats`, `test_commit_never_exceeds_intake`, `test_commit_revalidates_a_stale_batch` |
| Cross-college match + shared-contact rings | DUP-002 / DUP-003 in `test_upload_flags_every_planted_defect`; `test_shared_contact_clusters_are_found_with_members` |
| Signed QR checked even offline (signature + cached signed revocation list); consent for more | `test_issuer_is_a_resolvable_did_web_with_the_signing_key`; revocation list in `test_exit_closes_dual_enrolment_and_revokes_credential`; `test_qr_token_verifies_and_detects_tampering`; walkthrough asserts "On this device: signature valid"; `test_consent_flow_discloses_only_scope` |
| Twin-safe matching (Mohd = Mohammed, Rohit ≠ Mohit) | `test_matcher_keeps_twins_apart_and_joins_spelling_variants`, `test_seeded_twins_are_not_flagged_as_duplicates` |
| Ghost-admission map (1 phone, 8 students, 2 colleges) | `test_shared_contact_clusters_are_found_with_members`; screenshot `19_review_shared_contact_cluster.png` |
| Decisions kept: reason required, never re-flagged | `test_decisions_need_a_reason_and_survive_the_next_scan` |
| Signed checkpoints catch a full history rewrite | `test_signed_checkpoints_catch_rewrites_and_truncation`; screenshot `18_audit_rewrite_detected.png` |
| Rules as data: each value sourced; unconfirmed ones only warn | `backend/app/rules/aicte_2026_27.json` (`verified` per value); `test_unverified_caps_send_rows_for_review_instead_of_rejecting` |
| APAAR on degrees: university print feed with QR | `test_university_gets_degree_print_feed_for_affiliated_colleges_only` |

## Slide 3: technical approach
| Claim | Evidence |
|---|---|
| Python · FastAPI, REST + OpenAPI | `test_json_api_validate_and_submit` checks `/openapi.json` |
| React · TypeScript, installable PWA | `frontend/package.json`; `frontend/public/manifest.webmanifest`, `sw.js` |
| PostgreSQL 16 (SQLite in the demo) | Full suite passes on PostgreSQL 16 (command above) |
| scikit-learn Isolation Forest; name matcher | `backend/app/anomaly.py`, `backend/app/matching.py` |
| Ed25519 · W3C, did:web issuer, AES-GCM | `backend/app/credentials.py` (`/.well-known/did.json`), `backend/app/fieldcrypt.py`; `test_issuer_is_a_resolvable_did_web_with_the_signing_key`, `test_contact_details_and_document_numbers_are_encrypted_at_rest` |
| Built / Simulated / Planned | Built items: tests named on this page. Simulated: `app/apaar_registry.py` (mock registry, `VP_APAAR_REGISTRY=mock`), demo sign-in (`VP_DEMO_MODE`). Planned: roadmap |
| Errors return with reasons; fix and re-upload | Upload tests; `test_reupload_applies_corrections` |
| National scan: duplicates, intake, contacts | `backend/app/scan.py`; runs in the background after every submission |
| Risk vs peers, with reasons | `test_risk_scores_come_with_plain_reasons` (reasons name the peer group) |
| Screenshot: 77 rows → 65 accepted, 12 returned | `test_upload_flags_every_planted_defect` (77 rows, 12 errors); `test_commit_never_exceeds_intake` (65 created) |
| 7 demo roles | `main.demo_users`; walkthrough signs in as each |

## Slide 4: feasibility
| Claim | Evidence |
|---|---|
| Twins flagged: 0/80 seeded, 2/12 held-out (sent for review) | `docs/benchmark.json` `twins_wrongly_flagged`; `identity_matching_labelled_pairs.held_out.current_matcher.by_kind.twin` |
| 0.79 / 0.92 held-out precision / recall (old matcher 0.65 / 0.68) | `scripts/identity_eval.py` on `tests/data/identity_pairs_holdout.csv`; `test_identity_matching_beats_previous_matcher_on_held_out_pairs` |
| 0 / 80 twins wrongly merged | `docs/benchmark.json` `twins_wrongly_flagged`; `test_seeded_twins_are_not_flagged_as_duplicates` |
| 17/17 planted error types; 0 false flags on 56 clean rows | `docs/benchmark.json` |
| 164 · 57 · 4 planted dual enrolments, identity duplicates, contact rings found | `docs/benchmark.json` (recall 164/164, 57/57, 4/4) |
| 42/46 top-ranked colleges were planted anomalies | `docs/benchmark.json` `risk_precision_at_k` |
| 65 tests; 93% coverage; security and WCAG checks in CI | `docs/evidence.json` (from `scripts/evidence.py`); `.github/workflows/ci.yml` (bandit, pip-audit, npm audit, axe-core); `docs/accessibility_report.json` (34 screen checks, 0 violations) |
| All synthetic data; a flag never acts on its own | Stated on the slide and in `scripts/benchmark.py`; findings change only through an officer decision with a reason (`test_decisions_need_a_reason_and_survive_the_next_scan`) |
| Provisional ID; mother's or guardian's name accepted | `test_provisional_ids_for_students_without_apaar`, `test_mother_or_guardian_is_enough` |
| Contacts encrypted at rest | `test_contact_details_and_document_numbers_are_encrypted_at_rest` |
| Rejected rows never reach risk scores; reasons shown | Rows with errors are not committed (`test_commit_never_exceeds_intake`: 65 of 77 created); `test_risk_scores_come_with_plain_reasons` |
| Unconfirmed rule values warn, never reject | `test_unverified_caps_send_rows_for_review_instead_of_rejecting` |
| Consent per field, masked IDs, no Aadhaar stored, access log | `test_consent_flow_discloses_only_scope`, `test_apaar_ids_are_masked_in_aicte_views`, `test_consent_revocation_and_access_log`; no Aadhaar column exists (`models.py`) |
| Officer decides with a reason; decision remembered | `test_decisions_need_a_reason_and_survive_the_next_scan`, `test_officer_decision_is_audited` |
| Rules file per academic year with sources | `backend/app/rules/aicte_2026_27.json`; *Rules in force* page (`26_rules_in_force.png`) |
| ERP headers auto-mapped, Excel template, API keys, Hindi, phone app | `test_erp_headers_are_mapped_automatically`, `test_excel_template_has_dropdowns_and_report_has_diversity`, `test_api_keys_and_idempotent_submit`; walkthrough Hindi step and 390 px mobile screenshot; PWA manifest |
| Roadmap (pilot measures hours saved and false flags) | Plan, not measured |
| No licence fees | All dependencies are MIT / BSD / Apache licensed; project is MIT (`LICENSE`) |

## Slide 5: impact
| Claim | Evidence |
|---|---|
| Excess and dual enrolment caught at submission | Upload and commit tests |
| Universities print APAAR + student ID | Degree-feed test; `28_university_degree_feed.png` |
| Employers: QR check on a phone | Walkthrough on-device check; `frontend/src/lib/offline.ts`; mobile screenshot `30_mobile_dashboard.png` |
| Students control who sees the record | Consent approve / deny / revoke and access-log tests |
| Audited evidence pack for review and show-cause | `test_evidence_pack_for_show_cause` |
| Certificate with APAAR ID + student ID + QR; QR verified | `test_certificate_pdf`; screenshots `25_certificate.png`, `23_public_qr_verified.png` |
| Today: ₹23.1 cr = 42 excess seats × ₹11 lakh fee × 5; AISHE 2022-23 data published in 2026; “a number of students have mismatch in Aadhaar and APAAR ID details” | FORE School of Management v AICTE, Supreme Court, 21 Jun 2019; AISHE 2022-23 and 2023-24 reports (released Jul 2026); Cluster University Srinagar notice on APAAR mismatch (cusrinagar.edu.in), 2026 |
| With Vidya Pramaan: seat #61 refused at upload, the same day; national view refreshed after each submission; mismatch returned with its reason | `test_intake_overflow_counts_seats`; background national scan after each submission; APR-004 findings in `test_upload_flags_every_planted_defect` |
| Economic: no licence fees; one upload serves AICTE and university | Licences as above; `test_university_gets_degree_print_feed_for_affiliated_colleges_only` |
| QR: on-device check + revocation list | `frontend/src/lib/offline.ts`; screenshot `23_public_qr_verified.png` ("not revoked as of …") |
| APAAR opt-outs never refused | Orissa HC, *Rohit Anand Das v State of Odisha* (Dec 2025); Supreme Court direction to add an opt-out to the APAAR consent form (Jul 2026, LiveLaw); `test_provisional_ids_for_students_without_apaar` |
| Fewer paper returns and verification letters | Expected benefit, not measured; the slide says so |

Impact statements about fairness, paperwork and fraud are expected benefits, not measured results; slide 5 says so and the pilot measures them.

## Slide 6: research
| Claim | Evidence |
|---|---|
| NAD / DigiLocker offers consent-based verification of academic awards | NAD FAQ (nad.digilocker.gov.in) |
| ABC holds credits keyed to APAAR | NCERT APAAR brochure; ABC documentation |
| AISHE publishes institution-level aggregates with a 2–3 year lag | AISHE 2022-23 and 2023-24 reports released in 2026 |
| No published APAAR check digit | No official specification found; assumption A-02 in `docs/ASSUMPTIONS.md` |
| FN/OCI/PIO caps 15% UG, 25% PG for 2026-27 | APH 2026-27 addendum (reported by Careers360); rules file marks it verified |
| TFW cap 5% (verified); lateral entry 10% (unverified for 2024-27, so warn-only) | MRSPTU TFW notice 2024-25 and Central University of Punjab notice citing APH 2024-27; lateral 10% from AICTE Handbook 2019-20 via Tamil Nadu G.O. 68 (2019) |
| ✔ = built and covered by a test | Each ✔ row maps to tests listed under slides 2–5 on this page |
| APAAR is voluntary; opt-out must be offered | MoE consent guidance; Orissa HC, Rohit Anand Das (Dec 2025); Supreme Court direction (Jul 2026), reported by LiveLaw and SCC Online |
| AICTE enrolment and APAAR totals | Lok Sabha and Rajya Sabha replies (sansad.in) |
| DPDP Act 2023, Rules 2025 phased to 2027 | Law-firm summaries of the notified rules (L&S, AZB, SCC Online) |

## Field validation (slide 6, when present)
| Claim | Evidence |
|---|---|
| "From the field" quote | Shown only when `ppt/field_validation.json` holds a real quote with `permission_to_quote: true`, collected with `docs/validation/INTERVIEW_KIT.md`. Keep the interview notes. |
