# Prompt Rescue: reflection

**Final prompt: v4 (principle-based). 18/21 (86%) on both runs, against a baseline of 5–6/21 (24–29%).**
Single prompt, 1 call per ticket (about 2s), `claude-haiku-4-5`, about 1,100 tokens. It is in the notebook as `system_prompt_v4` and in `ab/variants.py` as `V4`.

## Results

| Version | Runs | Score | JSON | Priority | Entities | Response | Size | Status |
|---|---|---|---|---|---|---|---|---|
| Baseline | 5, 6, 6 | 24–29% | 20 | 14 | 7–8 | 21 | ~200 tok | Starting point |
| v1 | 16, 17 | 76–81% | 21 | 17–18 | **21** | 20 | ~1,330 tok | Superseded |
| v2 | 19, 18, 19, 19 | 86–90% | 21 | 19–20 | 21 | 20 | ~1,520 tok | Superseded |
| v3a | 21, 20 | 95–100% | 21 | 21 | 21 | 20–21 | ~1,700 tok | Rejected: fitted to the test |
| v3b | 20, 21 | 95–100% | 21 | 21 | 21 | 20–21 | ~2,000 tok | Rejected: examples added nothing |
| **v4** | **18, 18** | **86%** | 21 | 19 | 21 | 20 | **~1,110 tok** | **Accepted** |

All runs went through the A/B suite (`ab/ab_suite.py`), which uses the notebook's own eval harness unchanged; its log is in `ab/runs.jsonl`. Haiku is non-deterministic, so differences of ±1 case are treated as noise.

## Timeline: how we got to v4

**1. Baseline and diagnosis (5/21).**
Instead of reading only the total, I counted failures per check. 13 of 16 failures included an entity error (9 failed on nothing else), 6 had wrong priority (5 of them pushed up), 1 had a JSON structure error, and **none failed the response judge**. The two categories at zero were multi-issue and vague. This changed my first draft of the spec in two ways:
- Its P1 rule ("production systems serving the customer's own customers are P1") was wrong: case 9 expected P2.
- Its plan to make chaining the main fix wasn't supported: task interference wasn't visibly breaking replies.

**2. v1: fix the three root causes in one prompt (16–17/21).**
- An entity rule: exact text from the ticket, or `null`.
- Priority decided by content, not tone; a P3 default for vague tickets; P4 only for feature requests and cosmetic issues.
- Exactly one top-level JSON object.
- Three examples written from scratch.

Entities went from 7 to 21 in one change.

**3. v2: boundary rules from v1's own failing outputs (18–19/21).**
I extended the A/B suite to keep the raw output of failing cases, then read the model's actual answers instead of guessing.
- A truncated tooltip had been called "cosmetic".
- A quarter-end crash had been given the vague-ticket default of P3.
- Slowness of unknown scope had been rated P2.

I added a rule for each. This passed the 80–85% target, and I stopped.

**4. Considered structured outputs. Not used for scoring.**
Haiku 4.5 supports `output_config.format` with a JSON schema, but:
- JSON was already 21/21.
- A schema guarantees the shape of the output, not that priority or entities are right.
- The harness's API call is fixed, so adding it would have made the score incomparable.

It's recommended for production instead (see below).

**5. Pushed for 95%: v3a against v3b (20–21/21 each).**
- v3a added a two-part P2 check ("a feature is *broken*, not just slow, **and** many users are *confirmed*"), named truncated tooltips explicitly, and banned offers of alternatives in P4 replies.
- v3b added two boundary examples on top of v3a. They made no measurable difference.

I also added logging of the judge's reasons. It showed the one remaining failure (case 11) is the judge contradicting itself between runs.

**6. Overfitting review: we were tuning to the test.**
Looking back at v2 and v3a honestly:
- Several rules named the details of a specific case ("quarter-end, payroll, board reporting", "a tooltip, a label", "'other departments' without a count", "no sales offers").
- The failure messages give away the expected answers, so the eval had become our training data.
- Some rules suit the grader more than a real support team, such as `affected_users` as one bare number.

The 95% was not a defensible number.

**7. v4: principle-based rewrite. Accepted (18/21 on both runs).**
I replaced every case-specific rule with the general principle behind it. Five principles, at about 1,100 tokens (smaller than v1). The result:
- **Keeps nearly all the gain:** 86%, the same as v2's typical score.
- **Most consistent:** the same score on both runs.
- **The two cases it misses are exactly the two that v3a's case-specific rules named** (tooltip, quarter-end). That confirms those rules were fitted to the test.

## The five principles in v4

1. **Impact over tone.** Decide from the effect the ticket describes. Urgency words, capitals, threats and the customer's own label are not evidence.
2. **Confirmed, not assumed.** Raise priority only for impact and scope the ticket states. When it's unclear, go lower and ask.
3. **Defect vs request.** If something exists but behaves wrongly, or information is missing, wrong or hidden, it is a defect (P3 or higher). New capability is a request (P4), however urgently it's phrased.
4. **Evidence-only fields.** Copy entities exactly as written; otherwise use the JSON literal `null`.
5. **Reply matches the decision.** Never promise more than the priority supports. Ask questions when information is missing.

## 1. Where my prompt engineering did the work

**a. I added the "evidence-only fields" rule (copy exactly or `null`) because I diagnosed fabricated and paraphrased entities as the main failure mode.**
The instruction "Always include all JSON fields even if empty" made the model fill every field. Breaking the failures down showed four distinct patterns:
- paraphrased product labels ("CRM Platform", "Data Sync Service")
- notes added to counts ("200+ (export feature), 3 (billing accuracy)")
- "Unknown - not specified" written out as a string
- symptoms turned into made-up error codes ("DUPLICATE_RECORDS_ON_SYNC")

**Entities went from 7/21 to 21/21 and stayed there on every run.** This one decision accounts for most of the overall gain.

**b. I added "impact over tone" and "confirmed, not assumed" because I diagnosed priority being pushed up by tone and by assumed scope.**
Five of the six baseline priority errors pushed the priority up:
- an urgent-sounding feature request rated P1
- "very urgent production" rated P1 instead of P2
- vague tickets rated P2 instead of P3

The original rules defined priority only by how many users were affected. Priority went from 14 to 19.

**c. I added "exactly one JSON object, never an array" because I diagnosed a structure failure on a multi-issue ticket.**
On case 6 the model split the ticket into one object per issue, so all four top-level fields were missing. With the rule plus a multi-issue example, **JSON went to 21/21 and multi-issue to 2/2 on every run.**

## 2. What I deliberately did *not* do

- **No 3-step chain.** No case ever failed the response judge, so task interference wasn't measurable. A chain would triple latency against a 5-second budget to fix a failure I couldn't detect. It stays the next A/B test if production shows replies pulling priority.
- **No structured outputs in the scored runs.** The harness call is fixed, and JSON was already 21/21. Recommended for production: the output always parses, priority and confidence are restricted to fixed values, and missing entities are always real `null`s.
- **No case-specific rules in the final prompt.** v3a's extra 2–3 points came from wording that named specific test cases. I chose the lower, honest number.

## 3. Where Claude's capability did the work

- **Non-native English** went from 1/3 to 3/3 with no language-specific instruction. Once it was no longer forced to fill every field, Haiku read "webhook is not fire correctly … 50 customer" correctly.
- **Reply quality:** the judge passed 20/21 replies. I wrote the rules (consistent with the priority, ask when information is missing, P4 means no promises), but the wording, empathy and coverage of each issue came from the model.
- **Applying principles to new tickets:** five abstract principles were enough for Haiku to classify tickets that look nothing like the three examples.

## 4. What v4 still misses, and why I accepted it

- **Case 3** (truncated tooltip, rated P4 instead of P3). The general "hidden information is a defect" principle doesn't change Haiku's view that a tooltip is visual. Only naming tooltips fixed it, which is fitting to the test.
- **Case 17** (crash at quarter-end, rated P3 instead of P1). "Blocked right now" doesn't cover a crash at a deadline. Only naming quarter-end fixed it.
- **Case 11** (urgent SSO feature request). Priority is correct (P4), but the judge contradicts itself between runs: one run says the P4 rating itself is wrong, another wants *more* urgency in the reply, another *less*. No reply can satisfy all three. I'd raise with the customer that the eval's judge needs a clear rule for urgent feature requests.

## 5. Honesty notes for the debrief

- The eval was used for both tuning and reporting; there is no held-out set. v4 is the version least fitted to it, but its 86% is still measured on tickets we iterated against.
- Some extraction rules follow the grader's substring matching (one bare number for affected users, `null` instead of a descriptive product label). In production I'd revisit them with the customer: a support team may want "200 (export), 3 (billing)".

## 6. Process audit: my method against Claude's direct rewrite

I gave Claude (`claude-sonnet-5`) only the notebook's Step 2 instruction ("Rewrite it to fix the failures. Return only the improved prompt.") and the broken prompt, in one fresh call: no diagnosis, examples or eval loop. The rewrite is in `ab/claude_direct_fix.txt` and in the notebook's audit cell.

| | JSON | Priority | Entities | Response | Score |
|---|---|---|---|---|---|
| Baseline | 20 | 14 | 7–8 | 21 | 24–29% |
| Claude direct rewrite | 21 | 15–16 | 16–17 | 21 | **57–62%** (12, 13) |
| v4 (diagnosis-led) | 21 | 19 | 21 | 20 | **86%** (18, 18) |

**What the direct rewrite got right without any diagnosis:** the output format (JSON 21/21: "no code fences", one object) and the multi-issue rule ("prioritize the most severe issue"). Those are general prompt-writing knowledge.

**What it got wrong, exactly where the diagnosis came from the data:**
- **It made the priority errors worse by design.** "If ambiguous … default to the **higher** priority tier (err on the side of caution)." Our baseline data showed 5 of 6 priority errors were already pushed up. All its priority misses (cases 7, 9, 10, 11, 13, 21) are pushed up.
- **It kept the entity failure mode alive.** It allows `affected_users` to be "several" or "unknown" ("Never leave this blank"), and has no rule against descriptive product labels. 4–5 cases still fail on "CRM platform", "data sync service", "cloud-hosted platform".
- **Nothing on tone.** The SSO feature request (case 11) still goes to P2.

**The answer to "did you do the work, or did Claude?":** Claude's general knowledge recovers about half the gap (24% → ~60%). The other ~25 points came from decisions made from the failure data: "go lower when unclear", "copy or `null`", "tone is not evidence". A rewrite without that data can't make those decisions, and here it made the opposite call on two of them. The rewrite follows sensible-sounding defaults ("err on the side of caution"); the diagnosis showed that default is exactly what fails.

## 7. For the CTO (90 seconds)

"Your prompt wasn't failing because of the model. It was failing because of three unclear instructions. 'Include all fields' made Claude invent data. Priority had no rule for tone or unconfirmed scope. And the output format didn't say 'one object'. I replaced them with five general principles and measured every change with an automated eval: 24% to 86%, consistent across runs, on the same Haiku model, one call per ticket, about 2 seconds. I could have reached 95% with rules that name specific test tickets, but that only teaches the prompt the test. For production, add structured outputs so the JSON is guaranteed. Before shipping any new prompt, check: does every field have an explicit 'not present' value, is every priority decided from stated impact rather than tone, and is the output format stated as exactly one object?"
