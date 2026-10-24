# 10-minute field validation with an admission cell

Goal: one real conversation with the people who file admission data for AICTE, and one real quote we may use in the deck. It takes ten minutes and adds more credibility than any feature.

## Who to talk to

Pick one, in this order: the admission cell in-charge, the registrar or deputy registrar (academics), the exam section head, or the principal's office staff who prepare AICTE returns. One person is enough; two is better.

## Before you go

- Take a phone or laptop with the live demo open: https://vidya-pramaan-sih26263.onrender.com (open it a minute early; the free server sleeps).
- Print or open the form at the end of this file.
- Ask for 10 minutes, not "an interview".

## Opening (say this)

> We are students building a prototype for Smart India Hackathon on how colleges submit student data to AICTE using APAAR IDs. Could we ask you a few questions about how admissions data is filed today? It takes ten minutes. We will only quote you if you agree, and only with your role, not your name, unless you say otherwise.

## Questions (write down their words; do not correct them)

1. Which student data do you send to AICTE or the university each year, and in what form (portal, Excel, letters)?
2. Roughly how many days or person-days does the admission season's reporting take you?
3. How do you check that admissions in each programme stay within the approved intake, including quota seats (TFW, foreign nationals, lateral entry)?
4. Have you seen a student admitted at two colleges at once, or a duplicate record? How was it found?
5. How many students this year had trouble with APAAR IDs: missing, wrong name or date of birth, or opted out? What did you do?
6. When an employer, university or scholarship body asks to verify a student, how do they ask and how long does the reply take?
7. (Show the prototype for 2–3 minutes: upload the demo file, the rejected rows with reasons, the seat ledger.) Would this help? What is missing or wrong?
8. May we quote one sentence from what you said, with your role and institution type (for example "Admission cell in-charge, private engineering college, Maharashtra")?

## After the talk

- Read the quote back to them and get a clear yes.
- Fill `ppt/field_validation.json` (below) with their exact words. Leave it empty if they said no.
- Rebuild the deck: `cd ppt && ../.venv/bin/python build_template_deck.py --team-id <ID>`. The quote appears as one line under References on slide 6, and in the speaker notes.
- Keep your notes; a judge may ask how many people you spoke to and what changed.

## `ppt/field_validation.json`

```json
{
  "quote": "Exact words, one or two sentences",
  "speaker_role": "Admission cell in-charge",
  "institution": "Private engineering college, Pune",
  "date": "2026-10-25",
  "permission_to_quote": true,
  "people_spoken_to": 1
}
```

The deck shows the quote only when `quote` is filled and `permission_to_quote` is `true`.

## Form (copy per conversation)

| | |
|---|---|
| Date / place | |
| Role (name optional) | |
| Institution type and state | |
| Q1 Data sent and how | |
| Q2 Days spent on reporting | |
| Q3 Intake and quota checks | |
| Q4 Duplicate admissions seen | |
| Q5 APAAR problems this year | |
| Q6 Verification requests and turnaround | |
| Q7 Reaction to the prototype; what is missing | |
| Q8 Quote (exact words) and permission (yes / no) | |
