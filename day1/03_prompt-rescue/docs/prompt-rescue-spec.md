# Spec: Rescue the TechSupport Corp ticket-processing prompt (day1/03_prompt-rescue)

> **Status: implemented.** Final prompt v4 (principle-based) scored 18/21 (86%) on both runs, against a baseline of 5–6/21. This spec has been updated to match what was built and accepted. The experiment history and the reasons behind each decision are in `docs/reflection.md`.

## Problem Statement

TechSupport Corp's support-ticket processor is one Claude Haiku prompt that does three jobs in a single call: it assigns a priority (P1–P4), extracts entities (product, version, error codes, affected users), and drafts a reply to the customer, all returned as JSON. It works on clean tickets but fails on real-world input. At baseline it passed 5 of 21 eval cases (24%). Messy tickets get the wrong priority, made-up entities and broken JSON. Their renewal review is imminent. They can't upgrade the model, and their pipeline has a 5-second latency budget per ticket, so more than 3 sequential calls needs a justification.

As the participant, I need to show more than a higher score: I need a *diagnosed, defensible* fix. That means a root cause I can name, techniques I chose for stated reasons, a quantitative before/after, and a debrief I can give a technical buyer. The score must also come from general guidance, not from rules fitted to the test cases.

## Solution

Replace the broken prompt with **one principle-based prompt (v4)**, derived from a per-check diagnosis of the baseline failures. Same contract: a raw ticket goes in, and the same JSON shape comes out from one call.

**Diagnosis (baseline, by check):** 13 of 16 failures included an entity error (9 failed on nothing else), 6 had wrong priority (5 of them pushed up), 1 had a JSON structure error, and none failed the response judge. Three structural causes:
1. "Always include all JSON fields even if empty" makes the model **fill fields**: it paraphrases product labels, adds notes to counts, writes out "Unknown" strings, and invents error codes.
2. Priority is defined only by user count: **no rule against judging by tone, none for unconfirmed scope, none for defect vs request.**
3. **No rule for the output's shape**: a multi-issue ticket produced one object per issue.

**Fix: five principles (v4):**
1. **Impact over tone.** Decide from the effect the ticket describes. Urgency words, capitals, threats and the customer's own label are not evidence.
2. **Confirmed, not assumed.** Raise priority only for impact and scope the ticket states. When it's unclear, choose the lower level and ask.
3. **Defect vs request.** Wrong, missing or hidden behaviour is a defect (P3 or higher). New capability is a request (P4), however urgently it's phrased.
4. **Evidence-only fields.** Copy entities exactly as written; otherwise use the JSON literal `null`.
5. **Reply matches the decision.** Never promise more than the priority supports. Ask questions when information is missing.

Plus: exactly one JSON object with no code fences, and three short examples (an angry feature request, a vague ticket, a multi-issue ticket).

**Validated** with an A/B suite that uses the notebook's own harness, with repeat runs. **Process audit:** Claude's plain rewrite, made with no diagnosis, scores 57–62%, which shows how much of the gain the diagnosis added.

**Targets:** ≥75% to pass (**met: 86%**). Tier 1 is ≥90% plus an iteration log plus a monitoring prompt: the iteration log is done; the 90% was only reached by v3a, which was rejected as fitted to the test; the monitoring prompt is not written. Tier 2, a self-repairing chain, was not attempted.

## User Stories

1. As a participant, I want to run the setup cell and see a verified connection, so that I know eval runs will reach Claude.
2. As a participant, I want to confirm the evals run on Haiku even though the banner names the default model, so that I trust the "no model upgrade" constraint holds.
3. As a participant, I want a baseline eval of the broken prompt, so that I have a fixed reference score to measure against.
4. As a participant, I want the baseline broken down by category, so that I can see the categories at zero (multi-issue, vague).
5. As a participant, I want pass counts for each check (JSON, priority, entities, response), so that I can see which failure mode dominates.
6. As a participant, I want to read the model's raw output on failing cases, so that I fix the actual behaviour instead of guessing.
7. As a participant, I want to know exactly how each check scores a case, so that my fixes target real pass/fail criteria.
8. As a participant, I want to write my own diagnosis before fixing anything, so that every fix follows from evidence.
9. As a participant, I want entity values copied exactly from the ticket or set to `null`, so that the processor never invents products, versions or codes.
10. As a participant, I want missing values written as JSON `null`, never as "Unknown" strings, so that downstream code can tell what's missing.
11. As a participant, I want `affected_users` to be a number copied from the ticket, or `null`, so that counts aren't annotated or estimated.
12. As a participant, I want `error_codes` to contain only codes or messages that appear literally in the ticket, so that symptoms aren't turned into fake codes.
13. As a participant, I want priority decided from the described impact, not the customer's tone, so that angry or urgent wording doesn't push it up.
14. As a participant, I want priority raised only for impact and scope the ticket confirms, so that vague or unconfirmed tickets default lower and get clarifying questions.
15. As a participant, I want a clear defect-vs-request rule, so that feature requests are P4 and real defects (including hidden or missing information) are at least P3.
16. As a participant, I want one priority per ticket, taken from the most severe issue, so that multi-issue tickets are neither under-rated nor split.
17. As a participant, I want exactly one top-level JSON object with no code fences, so that the output always parses.
18. As a participant, I want the reply to match the priority, cover every issue, and never promise more than the priority supports, so that the response judge passes it and customers aren't misled.
19. As a participant, I want the confidence field to reflect how complete the information is, so that uncertain classifications are flagged.
20. As a participant, I want a few short examples written from scratch, so that Haiku sees each principle applied without being trained on the test tickets.
21. As a participant, I want an A/B suite that scores variants with the notebook's own harness, so that results from the terminal match the notebook.
22. As a participant, I want repeat runs per variant, with the min–max spread, so that I don't mistake Haiku's run-to-run variation for improvement.
23. As a participant, I want the judge's one-line reason recorded for failed replies, so that I can tell a prompt problem from a judge problem.
24. As a participant, I want every run logged with its variant, checks, categories and failing outputs, so that the iteration history can be rebuilt and presented.
25. As a participant, I want all A/B runs to appear in the notebook's Iteration Log without re-running them, so that the score progression is visible in one place.
26. As a participant, I want to compare a single prompt against a chain only if the data shows task interference, so that I don't triple latency to fix a failure I can't detect.
27. As a participant, I want to judge structured outputs on evidence, so that I adopt them where they help (production) and not where they can't move the score (the fixed harness).
28. As a participant, I want to review my rules for test-case fitting (rules that name specific tickets, rules shaped by the grader), so that the reported score is defensible.
29. As a participant, I want a principle-based rewrite compared against the case-specific version, so that I can measure how much of the score was test fitting.
30. As a participant, I want the final prompt to be the most general one that clears the bar, not the highest-scoring one, so that it generalises to production tickets.
31. As a participant, I want a process audit against Claude's plain rewrite (no diagnosis), so that I can show what my methodology added.
32. As a participant, I want clean tickets checked for regressions on every run, so that fixes for hard cases don't break easy ones.
33. As a participant, I want reflection answers in the form "I added X because I diagnosed Y", so that I can explain my engineering separately from Claude's built-in capability.
34. As a participant, I want a timeline of experiments from baseline to v4, so that I can present the iteration story.
35. As a participant, I want a 90-second CTO pitch and a prevention checklist, so that I can debrief an enterprise buyer.
36. As a Tier 1 participant, I want a monitoring prompt that checks production outputs, so that the customer can catch regressions after launch. *(Not yet done.)*
37. As a Tier 2 participant, I want a final check-and-correct step, so that the pipeline repairs itself. *(Not attempted.)*
38. As a TechSupport Corp stakeholder, I want the same ticket-in, JSON-out contract and one call per ticket, so that my pipeline and latency budget don't change.
39. As a TechSupport Corp stakeholder, I want the fix to stay on Haiku, so that cost doesn't change.
40. As a TechSupport Corp stakeholder, I want structured outputs recommended for production, so that the JSON contract is guaranteed by the API, not only by the prompt.
41. As a TechSupport Corp stakeholder, I want grader-shaped extraction rules flagged, so that we can decide what production actually needs (for example, per-issue user counts).
42. As a facilitator, I want scores backed by a diagnosis, an iteration log and an honest note on test fitting, so that I can grade method as well as score.

## Implementation Decisions

- **Modules changed:**
  - The notebook's prompt cells: the final v4 prompt cell, the Iteration Log cell, and the process-audit cell.
  - A new A/B suite: a runner, a file of prompt variants, and a run log.

  The eval harness cell is unchanged and read-only.
- **Output contract (fixed):** a JSON object with:
  - `priority` (one of the strings `P1`–`P4`)
  - `entities` (an object with `product`, `version`, `error_codes` as a list, and `affected_users`)
  - `response` (string)
  - `confidence` (`high`, `medium` or `low`)

  Missing entities are JSON `null` (`[]` for error codes).
- **Architecture: one prompt, one call.** No chain. No case failed the response judge at any stage, so task interference was never measurable, and a 3-step chain would triple latency against the 5-second budget. The chain stays the next experiment if production data shows replies pulling priority.
- **Priority policy (v4):**
  - P1: the product is unusable for essentially everyone, or a business-critical process is completely blocked right now.
  - P2: important functionality broken for many users (scope stated, not guessed), or partly failing in production.
  - P3: a real defect with limited or unconfirmed impact, including degraded performance of unknown scope; also the default for vague tickets.
  - P4: a request for new capability, or a purely visual issue that hides or corrupts no information.
  - Tone is ignored, the most severe issue sets the priority, and when unclear go lower.
- **Entity policy:** copy exactly or `null`; never infer, paraphrase, label or annotate. `affected_users` is one number copied from the ticket (the largest if there are several). *Known compromise:* the single number and the null-instead-of-label rules follow the grader's substring matching; production may want per-issue counts.
- **Reply policy:**
  - Professional, 2–5 sentences, covering every issue.
  - P4: logged for the product team, with no fix, date, workaround or alternative, and no urgency echoed.
  - Missing information: ask specific questions.
  - P1/P2: say it has been escalated and give next steps.
- **Examples:** three, written from scratch and illustrating the principles. Never taken from the hidden eval cases.
- **Rejected alternatives:**
  - **v3a/v3b (95–100%):** rules that name details of specific test cases (quarter-end, tooltips, "other departments", sales offers). Rejected as test fitting. v4's two extra misses (cases 3 and 17) are exactly the cases those rules named.
  - **Structured outputs in the scored runs:** the harness's API call is fixed, and JSON was already 21/21. Recommended for production instead: `output_config.format` with a JSON schema, enums for `priority` and `confidence`, and string-or-null types for entities.
- **Integrity:** the base64 eval cases embedded in the notebook were never decoded. Diagnosis used only the harness's own output (failure reasons, model outputs, judge reasons).

## Testing Decisions

- **One seam: the harness's eval entry point.** The notebook calls `run_eval_suite`. The A/B suite runs the notebook's setup cell and harness cell as-is and calls the same `run_eval` and scoring, so terminal and notebook scores are directly comparable. No new seams were introduced. The only addition is a wrapper that records the judge's reason without changing its verdict.
- **A good test checks external behaviour only:** given a raw ticket, is the JSON valid, is the priority correct, do all entities appear in the ticket, and does the judge accept the reply? Prompt wording is never asserted.
- **Results per check and per category on every run**, not just the total. This breakdown is what identified entities as the main failure mode.
- **Repeat runs:** each variant runs at least twice and is reported with its min–max spread. A difference of ±1 case is treated as noise.
- **Regression guard:** clean and previously passing categories are checked on every run.
- **Control:** the process audit (Claude's plain rewrite, generated once and saved so every run scores the same text) is the baseline for "what the methodology added".
- **Known limitation:** no held-out set. The 21 eval cases were used for both tuning and reporting. v4 is the version least fitted to them, but its 86% is still measured on tickets we iterated against.
- **Prior art:** the notebook's baseline run, its A/B comparison cell, the iteration log and the process audit cell.

## Out of Scope

- Changing the eval harness, the judge prompt, the scoring rules or the hidden test cases.
- Switching to a model other than Haiku.
- Changing the input or output contract.
- Decoding or tuning against the embedded eval cases.
- A held-out evaluation set (considered and deliberately skipped).
- The Tier 2 self-repairing chain.
- Production deployment, real latency measurement, and wiring structured outputs into TechSupport Corp's pipeline.

## Further Notes

- **Final results:**

  | Version | Score |
  |---|---|
  | Baseline | 24–29% |
  | Claude plain rewrite | 57–62% |
  | v1 | 76–81% |
  | v2 | 86–90% |
  | v3a (rejected) | 95–100% |
  | **v4 (final)** | **86%** |

- **The remaining v4 misses:**
  - Case 3: truncated tooltip, rated P4 instead of P3.
  - Case 17: crash at quarter-end, rated P3 instead of P1.
  - Case 11: the judge contradicts itself on an urgent feature request (the priority, P4, is correct).
- **Open items:**
  - The Tier 1 monitoring prompt.
  - The reflection's "what surprised you" answer.
  - One full Run All of the notebook in a kernel, to save outputs.
