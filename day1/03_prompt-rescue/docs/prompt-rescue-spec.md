# Spec: Rescue the TechSupport Corp ticket-processing prompt (day1/03_prompt-rescue)

## Problem Statement

TechSupport Corp's support-ticket processor is one Claude Haiku prompt that does three jobs in a single call: it assigns a priority (P1–P4), extracts entities (product, version, error codes, affected users), and drafts a reply to the customer, all returned as JSON. It works on clean tickets but passes only about 4 of 21 eval cases (19%) on real-world input. Messy tickets get the wrong priority, made-up entities, broken JSON, and replies that contradict the priority or skip some of the issues. Their renewal review is imminent. They can't upgrade the model, and their pipeline has a 5-second latency budget per ticket, so more than 3 sequential calls needs a justification.

As the participant, I need to show more than a higher score: I need a *diagnosed, defensible* fix. That means a root cause I can name, techniques I chose for stated reasons, a quantitative before/after, and a debrief I can give a technical buyer.

## Solution

Replace the single broken prompt with a prompt design built from a written diagnosis. It keeps the same function: a raw ticket goes in and the same JSON shape comes out. The work happens in stages:

1. **Diagnose** with meta-prompting and the baseline eval's category breakdown. Name the structural causes:
   - Task interference: writing the reply pushes the priority up.
   - The "include all fields" instruction makes the model fill fields it should leave empty.
   - Priority follows tone, not content.
   - Business-critical blockers aren't covered by the P1 definition.
   - There is no rule for tickets with several issues.
   - There is no JSON-only output rule.
2. **Fix the single prompt (primary path, per baseline evidence).** Add: entity values must be exact pieces of the ticket text or JSON `null`; priority rules based on content, not tone; feature requests are always P4; any working-functionality defect is at least P3; vague tickets default to P3; P1 only for full outages or a fully blocked critical business process; take the highest severity when there are several issues; exactly one top-level JSON object; a few short examples; reply rules that depend on the priority; JSON-only output.
3. **Chain the prompt (secondary, A/B-tested)** to remove task interference: classify → extract → write the reply and assemble the JSON. Only adopt it if it beats the best single prompt across runs. Optionally merge the classify and extract steps to save latency.
4. **Optional (Tier 2):** a final check-and-correct step that repairs JSON or replies that fail a quality check.
5. **Validate** each version with the harness, compare versions A/B, and keep the iteration log.
6. **Reflect and debrief:** what I engineered vs. what Claude did, and a 3-minute customer story with a prevention checklist.

Targets: ≥75% to pass, ≥90% plus iteration log plus a monitoring prompt design for Tier 1, and a self-healing chain for Tier 2.

## User Stories

1. As a participant, I want to run the setup cell and see a verified connection, so that I know eval runs will reach Claude.
2. As a participant, I want a baseline eval of the broken prompt, so that I have a fixed reference score to measure against.
3. As a participant, I want the baseline broken down by category (clean, multi-issue, vague, non-native, feature request, complex), so that I can see where fixes will help most.
4. As a participant, I want to see the per-check reason for every failed case (JSON, priority, entities, response), so that I can trace each symptom to a cause.
5. As a participant, I want to meta-prompt Claude with the broken prompt and failing examples, so that I get candidate causes to evaluate.
6. As a participant, I want to write my own diagnosis before fixing anything, so that my fixes follow from a diagnosis rather than trial and error.
7. As a participant, I want to know exactly how each check scores a case, so that my fixes target real pass/fail criteria.
8. As a participant, I want the prompt to output null or empty for any entity the ticket doesn't state, so that vague tickets never produce invented products or error codes.
9. As a participant, I want extracted entity values copied as they appear in the ticket, so that they pass the "must appear in the input" check.
10. As a participant, I want priority to depend on business impact, not on the customer's tone, so that angry feature requests aren't promoted.
11. As a participant, I want an explicit rule that feature requests are P4 even when labelled "bug" or "critical", so that the dark-mode case is classified correctly.
12. As a participant, I want P1 reserved for full outages and fully blocked critical business processes (e.g. payroll), with partial or intermittent production problems kept at P2, so that urgent-sounding tickets aren't over-classified while high-impact tickets with few users still reach P1.
13. As a participant, I want a rule for tickets with several issues (take the highest severity, cover every issue), so that combined tickets are neither under-classified nor partly ignored.
14. As a participant, I want vague tickets to default to P3 with low confidence and a reply that asks clarifying questions, so that the model doesn't guess while sounding confident.
14a. As a participant, I want any defect in working functionality rated at least P3, so that minor bugs aren't pushed down to P4.
14b. As a participant, I want `affected_users` to be a bare number that appears in the ticket, or `null`, so that values with notes ("200+ (export)", "3 out of 6") don't fail the entity check.
14c. As a participant, I want missing values written as JSON `null`, never as "Unknown - …" strings, so that they pass as empty.
14d. As a participant, I want `error_codes` to list only code-like tokens that appear literally in the ticket, so that described symptoms aren't turned into made-up codes.
14e. As a participant, I want exactly one top-level JSON object even for tickets with several issues, so that the structure check doesn't fail on arrays or per-issue objects.
15. As a participant, I want the confidence field to reflect how complete the information is, so that downstream users can tell which classifications are uncertain.
16. As a participant, I want the output to be raw JSON only, with no prose and no code fences, so that it always parses.
17. As a participant, I want quotes inside the reply text escaped, so that customer quotes (e.g. "timeout exceeded") don't break the JSON.
18. As a participant, I want every required field always present, so that the structure check never fails.
19. As a participant, I want a few short examples covering the hard categories, so that Haiku can see the expected behaviour rather than infer it.
20. As a participant, I want replies to P4 feature requests to acknowledge the request without promising a "fix", so that customer expectations are set correctly.
21. As a participant, I want replies that are consistent with the assigned priority, so that the response judge doesn't flag contradictions.
22. As a participant, I want replies that stay professional whatever the ticket's tone, so that they read well with hostile customers.
23. As a participant, I want replies to non-native English tickets that address the actual technical content, so that language quality doesn't reduce accuracy.
24. As a participant, I want to A/B-compare my revised single prompt with the baseline, so that I can show the change quantitatively, by category.
25. As a participant, I want to split the work into a classify step, an extract step, and a reply-and-assemble step, so that writing the reply can't affect the classification.
26. As a participant, I want each later chain step to see the original ticket and all earlier outputs, so that the final step can assemble the full JSON.
27. As a participant, I want the last chain step to produce the final, complete JSON, so that the harness scores the chain like a single prompt.
28. As a participant, I want to keep the chain at 3 calls or fewer, or justify any extra, so that the design fits the 5-second latency budget.
29. As a participant, I want to consider merging classification and extraction into one call, so that I can trade a small accuracy risk for lower latency.
30. As a participant, I want clean tickets to keep passing after every change, so that fixes for hard cases don't break easy ones.
31. As a participant, I want a clear label on every eval run, so that the iteration log documents my process.
32. As a participant, I want to view the iteration log and score chart, so that I can present how the score progressed.
33. As a Tier 1 participant, I want to reach ≥90%, so that I meet the Optimizer bar.
34. As a Tier 1 participant, I want a monitoring prompt that checks production outputs (priority sanity, made-up entities, reply consistency), so that the customer can catch regressions after launch.
35. As a Tier 2 participant, I want a final check-and-correct step that validates the JSON, priority and reply and fixes them if they fail, so that the pipeline repairs itself.
36. As a participant, I want to run the "Claude direct fix" process audit, so that I can compare my methodical result with a rewrite done without a method.
37. As a participant, I want to answer the four reflection questions, so that I can separate my engineering decisions from Claude's built-in capability.
38. As a participant, I want a 3-minute debrief (problem → diagnosis → fix → by-category proof → prevention checklist), so that I can present the work to an enterprise buyer.
39. As a TechSupport Corp stakeholder, I want the same ticket-in, JSON-out contract kept, so that my pipeline needs no changes.
40. As a TechSupport Corp stakeholder, I want the fix to stay on Haiku, so that cost and latency don't change.
41. As a TechSupport Corp stakeholder, I want a prevention checklist, so that my team avoids these failure modes in future prompts.
42. As a facilitator, I want participants' scores backed by a written explanation, so that I can grade method as well as score.

## Implementation Decisions

- **Only one module changes: the participant-editable prompt definitions in the notebook.** These are the single prompt in the "YOUR TURN" cell, the three step prompts in the chain-mode cell, variant B in the A/B cell, and the audit rewrite. The eval harness is read-only and stays unchanged.
- **Output contract (fixed):** a JSON object with `priority` (one of the strings `P1`–`P4`), `entities` (an object with `product`, `version`, `error_codes` as a list, and `affected_users`), `response` (string), and `confidence` (`high`/`medium`/`low`). Missing entities are `null`, `""` or `[]`.
- **Policy for entities: exact text from the ticket, or `null`.** The harness only checks that each non-empty value appears in the ticket; it never checks that every entity was found. Null is therefore always safe and inferring is risky. Rules:
  - `product`: the product name exactly as written. When the ticket doesn't name a product, use `null`; never a descriptive label ("CRM Platform", "Data Sync Service").
  - `version`: a version string that appears exactly in the ticket, or `null`.
  - `error_codes`: only code-like tokens copied literally from the ticket; `[]` when there are none.
  - `affected_users`: one bare number copied from the ticket, or `null`. No notes, ranges, "N out of M" or descriptions. When there are several counts, use the largest.
  - Missing means JSON `null`, never strings like "Unknown - not specified".
- **Priority policy, written explicitly in the prompt:**
  - P1: full outage (all or nearly all users unable to use the product), or a critical business process completely blocked (e.g. payroll cannot run). Partial, intermittent or degraded problems are not P1, even in production.
  - P2: a major feature broken or seriously degraded for many users, or a production integration partly failing.
  - P3: a minor bug, limited impact or a workaround exists. **This is the default for vague tickets** that describe no concrete impact, with low confidence.
  - P4: only feature requests and cosmetic issues, whatever the tone or label. Any defect in working functionality is at least P3.
  - Several issues: take the highest severity, but still exactly one priority.
  - Tone, urgency words ("URGENT", "critical", threats to leave) and capitals are explicitly ignored.
- **Reply policy:**
  - Must agree with the priority and cover every issue.
  - P4 replies acknowledge the request and never promise a fix.
  - Vague tickets get clarifying questions.
  - Always professional.
- **Output hygiene:** exactly one top-level JSON object (never an array or one object per issue), JSON only, no markdown code blocks, escaped quotes in strings, all fields present.
- **Order of work, based on the baseline.** At baseline (5/21), 13 of 16 failures include an entity error (9 fail on entities alone), 6 include a priority error, 1 is a JSON structure error and none fail the response judge. So the first lever is a disciplined single prompt; task interference is not yet the bottleneck. Expected ceiling: ~14/21 from the entity fixes alone, ~20/21 with priority calibration.
- **Chain architecture (secondary; adopt only if A/B shows a gain):**
  - Step 1 (classify): returns priority, confidence and short reasoning, ignoring tone.
  - Step 2 (extract): returns entities only, with nulls for anything missing.
  - Step 3 (reply and assemble): writes the reply from the fixed priority and entities, then outputs the final contract JSON.
  - The harness passes each later step the original ticket plus all earlier step outputs, and scores only the last output.
- **Latency:** at most 3 sequential calls. Merging classify and extract is an acceptable option. A 4th check-and-correct step (Tier 2) needs a written latency justification.
- **Self-healing (Tier 2):** the harness runs a fixed list of steps, not a loop. Build "auto-retry" as a final step that checks the earlier output against the contract and policies, then outputs either the same JSON or a corrected version.
- **Examples:** 3–4 short examples written by the participant, covering an angry feature request, a vague ticket, a ticket with several issues, and a clean P1. Base them on the 5 public failing examples or new tickets the participant writes, never on the hidden eval cases.
- **Integrity:** the base64 eval cases embedded in the notebook must not be decoded or used for tuning.

## Testing Decisions

- **One seam: the harness's eval-suite entry point** (`run_eval_suite`, which takes a single prompt or a list of prompts for chain mode, with a label). This seam already exists; no new seams are introduced. A/B comparison (`compare_prompts`) and the iteration log are views over the same seam.
- **A good test checks external behaviour only:** given a raw ticket, is the final JSON valid, is the priority correct, do all entities appear in the input, and does the judge accept the reply? Prompt wording and the outputs of intermediate chain steps are not asserted.
- **What is tested:** the single-prompt version, each chain version, the optional check-and-correct chain, and the "Claude direct fix" audit, all through the same seam.
- **Regression guard:** the clean category must stay fully passing on every run, and any run that drops a category that previously passed is investigated before moving on.
- **Results per check:** on every run, record pass counts for each check (JSON, priority, entities, response) as well as the total. This breakdown is what showed the entity problem at baseline.
- **Non-determinism:** Haiku and the judge are stochastic. Treat a ±1 case change as noise, and rerun close comparisons before claiming one version beats another.
- **Prior art:** the notebook's own baseline run, A/B comparison cell, iteration log and process audit cell. Other day1 exercises (e.g. 04_diagnosing-ai-problems) use the same pattern of driving work from an eval harness.

## Out of Scope

- Changing the eval harness, the judge prompt, the scoring rules or the hidden test cases.
- Switching to a model other than Haiku.
- Changing the input or output contract.
- Decoding or tuning against the embedded eval cases.
- Production deployment, real latency measurement, or wiring into TechSupport Corp's ticketing system.
- Translating non-English tickets as a separate preprocessing service.

## Further Notes

- **Baseline evidence (5/21, Haiku 4.5):** passes 2, 12, 14, 18, 20. Entity-only failures 1, 4, 5, 8, 10, 15, 16, 17, 19. Priority and entity failures 7, 9, 13, 21. Priority-only failures 3, 11. JSON failure 6. Priority errors: 5 of 6 pushed up (11: P1→P4, 9 and 13: P1→P2, 7 and 21: P2→P3); one pushed down (3: P4→P3). Case 9, a production integration affecting 50 customers, is expected as P2, which disproved the original draft's P1 rule.

- Expected scores: baseline ~19%, a good single prompt 43–57%, a strong chain 76–90%, the reference solution 100%.
- The deliverable is graded on rationale as much as score: "a score you can explain is a methodology; one you can't is a demo."
- Never tell the customer "I just asked Claude to fix it". Own the diagnostic judgment.
