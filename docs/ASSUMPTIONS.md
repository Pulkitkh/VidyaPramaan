# Assumptions register

Decisions the prototype makes where the problem statement, AICTE rules or APAAR documentation leave room. Each one is easy to change. Most are configuration.

| # | Assumption | Why | Where |
|---|---|---|---|
| A-01 | There is no public APAAR/ABC lookup API; the registry is reached through a DigiLocker / API Setu partner connector. The demo uses a mock registry behind the same interface. | No public endpoint is documented; API Setu partner onboarding is the known route. | `apaar_registry.py` |
| A-02 | An APAAR ID is 12 digits, not starting with 0. No checksum is applied. | No official check-digit specification was found; inventing one would reject valid IDs. | `apaar_registry.is_valid_format` |
| A-03 | APAAR is voluntary. Students who decline it, and FN/OCI students (APAAR needs Aadhaar-based KYC), are admitted with a provisional AICTE ID. | Supreme Court direction (Jul 2026); MoE consent guidance. | APR-005, APR-007 |
| A-04 | FN/OCI/PIO supernumerary cap: 15% of approved intake for UG, 25% for PG (2026-27 addendum). Diploma assumed as UG. | APH 2026-27 addendum; CIWG share reverted by circular of 28 Sep 2026. | `rules/aicte_2026_27.json` |
| A-05 | TFW 5%, lateral entry 10% (UG/Diploma only), EWS 10% where sanctioned as supernumerary. Marked `verified: false`. | Commonly cited values not re-verified against APH 2024-27. | rules file |
| A-06 | Admission window 1 Jun to 30 Sep 2026; outside it is a warning (CON-006), not a rejection. A date in the future is rejected (CON-009). | Late admissions happen with approval; future dates are data errors. | rules file |
| A-07 | Seats freed by withdrawal before the cut-off can be refilled, so only ACTIVE enrolments count against intake. | Common practice; confirm against the handbook in force. | `IntakeLedger`, `scan.py` |
| A-08 | Being active at two institutions is a WARNING (DUP-002), not a rejection. | UGC (Apr 2022) allows two programmes at once in some modes; an officer decides. | DUP-002 |
| A-09 | Dates are ISO (YYYY-MM-DD) or day-first (DD-MM-YYYY, DD/MM/YYYY). Month-first is never assumed. | Indian convention; avoids silently swapping day and month. | `validation._date` |
| A-10 | At least one of father's, mother's or guardian's name is required; none is mandatory on its own. | Single-parent and orphaned students must not be excluded. | SCH-001 |
| A-11 | A shared mobile number or e-mail is flagged at 4 or more students across 2 or more institutions, or 6 or more at one institution. | Siblings commonly share a parent's phone; agent desks do not. | `scan.CLUSTER_*` |
| A-12 | Identity duplicates need: same gender, same date of birth (or day/month swapped), matching name and matching parent name. A changed letter in a given name never matches. | Keeps twins and rhyming siblings apart; every match is a review item. | `matching.py` |
| A-13 | Risk scores compare an institution with peers of the same type (engineering, management, pharmacy, polytechnic) when 12 or more peers exist. | Different institution types have different normal profiles. | `anomaly.py` |
| A-14 | A correction to name, date of birth or gender replaces the student's credential and raises a review item; other corrections apply directly. | Identity changes are where fraud and errors matter most. | UPD-002 |
| A-15 | The degree-print feed shows full APAAR IDs to the affiliating university. | PS requirement 10: degree-awarding bodies print APAAR ID with the student ID. | `/api/university/degree-feed` |
| A-16 | All data is synthetic: 240 institutions, about 49,000 students, with planted anomalies and planted hard negatives (twins). | No real student data may be used in a public prototype. | `seed.py` |
