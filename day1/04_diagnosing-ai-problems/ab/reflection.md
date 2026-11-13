# Reflection — what's breaking Meridian, and why

Working notes. Evidence first, conclusions second. Each hypothesis maps to a variant in `ab/variants/`.

## What we observed (baseline, sonnet-5, 0/5)

- Coordinator routes to **one** specialist (`account`) in 5/5 trials. Billing never spawned → refund never issued.
- Ticket closed `resolved` in 5/5 trials; reply over-claims the refund in 3/5.
- The customer explicitly said "Two things" and "Separately" — the multi-issue shape is not subtle.
- **The refund evidence is found every time and then dropped.** The account specialist runs `check_audit_log` in 5/5 trials and confirms the Scale→Growth downgrade on Feb 26, before the March 1 charge. It has no refund tool, so the evidence goes nowhere.
- **The replies invent a handoff to billing** that never happens: *"I've handed this over to our billing team… you should see the credit reflected… No further action needed."* No billing specialist was spawned and nothing was escalated.
- **Haiku 4.5 fails the same way at ¼ the cost** (0/5, $0.033/trial, account ×5). It once chose `needs_info`, but even it says *"I'm issuing a $1,200 refund to your account today"* with no refund call.
- **Grader caveat (observed, not changed):** `no_overclaim` matches `refund` plus `processed|issued|refunded|credited|done|complete`. "I'm *issuing* a refund" doesn't match, so that score undercounts over-claims. Rely on `billing_resolved` / `no_false_resolution` instead.

## Suspects in the levers (quoted from the shipped files)

| # | Where | Text | Why it could produce what we saw |
|---|---|---|---|
| H1 | coordinator step 5 | "Each ticket is owned by exactly ONE specialist… do not spawn more than one specialist" | Directly forbids routing the refund to billing. Explains `account ×5`. |
| H1 | classification guide | "If a ticket spans more than one category, still route it to a single category… One ticket, one specialist." | Same rule, said twice. |
| H2 | coordinator step 6 | "When the specialist returns, the ticket is handled… call write_response with resolution_status \"resolved\"" | Hard-codes `resolved` regardless of outcome → false resolution. |
| H2 | coordinator step 6 | "Escalating to a human is a last resort: escalations count against the team's SLA… acknowledge it… and close the ticket — do not leave tickets open." | Incentive to close rather than escalate; "acknowledge" invites a vague reply that reads like it's done → overclaim. |
| H4 | coordinator-tools.json | `spawn_specialist`: "Spawns a specialist agent for the given category." · `write_response`: "Writes the response." · `escalate_to_human`: "Escalates to a human." | Nothing says a specialist can only *act* in its category, or what each status means. |
| — | coordinator-tools.json | 17 tools incl. `helper`, `process`, `get_data`, `tool_3_v2`, 5 near-duplicate customer lookups | Noise / wasted turns. Probably cost, not correctness — not tested yet. |
| — | spawn_specialist schema | only `category` + `ticket_id` — specialist re-reads the whole ticket | Account specialist sees the refund but has no refund tool; it can only "note it". |
| — | examples 1–5 | all single-issue tickets | Few-shot never shows a multi-issue ticket being split. |

## Experiments

| variant | hypothesis | result | read |
|---|---|---|---|
| v1_route_all | H1 only | **5/5 RESOLVED**, $0.180/trial · routing account+billing ×5 · refund $1,200 on txn_98231 ×5 · all 4 checks 5/5 | **The lever.** Removing the one-specialist rule fixes T-4471 by itself. Step 6 still says 'resolved', but now it's true. Cost +39% (one more specialist). |
| v2_honest_close | H2 only | 0/5 · account ×5 · **escalated ×5** · no_false_resolution 5/5 · no_overclaim 1/5 | Honesty without capability. Stops the false 'resolved' but the refund still never happens. The overclaim fails are a **grader false positive**: replies say *'refund request escalated'* and *'downgrade was processed'*, and the regex matches `refund` + `processed` anywhere in the text. The replies are honest. |
| v3_route_and_honest | H1 + H2 | **9/9 RESOLVED** (3 trials × 3 tickets), $0.189/trial · T-4471 3/3: account+billing, resolved ×3 · T-4490 3/3: technical+billing, resolved ×1 / needs_info ×2 · T-4503 3/3: account only, **escalated ×3** (2FA reset done, pentest handed to a human) · every check passed | **The general fix.** It picks the right specialist pair on a ticket it was never tuned on (T-4490), and on T-4503 it escalates the part only a human can grant instead of claiming it. Minor quirk: T-4490 marked `needs_info` 2/3 times although both issues were actioned — a little over-cautious, and the grader doesn't penalise it. Check the reply wording before the brief. |
| v4_tool_descriptions | H4 only (prompt still says ONE) | **3/9**, $0.149/trial · T-4471 0/3: account only, resolved ×2 / escalated ×1 · T-4490 0/3: technical only, duplicate charge never refunded, resolved ×3 · T-4503 3/3: account, escalated ×3 | **When the tool descriptions and the prompt disagree, the prompt wins on routing.** The tool docs now say 'call this once per category', yet it still spawns one specialist 9/9 because the prompt says ONE twice. The tool docs *do* change closing behaviour at the margin: T-4471 escalated 1/3 (baseline 0/5) and T-4503 escalated 3/3. T-4503 only needs one specialist, so it can pass on honest closing alone. Tool descriptions help, but they can't override an explicit rule in the prompt. |
| model sweep | "it's the model" | haiku 0/5 @ $0.033 · sonnet 0/5 @ $0.13 · opus/fable blocked | same failure at every price so far |

## Open questions for you

1. Step 5 justifies the one-specialist rule ("duplicate actions and conflicting replies"). Is that a real concern worth keeping in a narrower form (e.g. never two of the *same* category)?
2. The SLA pressure on escalation is a *business* incentive written into a prompt. Would you tell Priya that's the root cause, or the routing rule?
3. T-4503 needs a human for the pentest authorization. Does any fix that only adds routing pass it? _Still open: v1 hasn't been run on the holdout. v4 passing T-4503 with only better escalation docs suggests the honest-closing half is what T-4503 tests._

## Conclusions

Draft. Your call on the framing for Priya.

1. **It's not the model.** Haiku (¼ the price) and Sonnet both fail identically: 0/5, account-only routing, false 'resolved'. Both diagnose the SSO cert expiry correctly every time and both find the refund evidence. The capability is there.
2. **Root cause #1: a routing rule.** "Each ticket is owned by exactly ONE specialist", repeated in the classification guide. On a two-issue ticket, the second issue can never reach the specialist who owns the tools for it. Removing it (v1) takes T-4471 from 0/5 to 5/5 on its own.
3. **Root cause #2: a closing rule with an incentive attached.** Step 6 hard-codes `resolved`, and calls escalation "a last resort" that "counts against the SLA". That turns "couldn't do it" into "told the customer it's done". Fixing it alone (v2) makes the agent honest (escalated 5/5) but not useful (0/5).
4. **The fix is both together (v3), and it generalises:** 9/9 across T-4471 and both held-out tickets, including a different specialist pair (T-4490) and a request only a human can grant (T-4503).
5. **Where the fix has to live:** the prompt's explicit rule overrode better tool descriptions (v4: 3/9). The fix belongs in the coordinator prompt; better tool descriptions are a supporting change, not a substitute.
6. **Cost:** $0.13 → $0.19/trial (+45%) because a second specialist runs when the ticket needs one. That buys going from 0% to 100% resolved. Haiku is cheaper still but untested with the fix (next experiment).

| | RESOLVED | $/trial |
|---|---|---|
| shipped (sonnet-5) | 0/5 | $0.13 |
| shipped (haiku-4-5) | 0/5 | $0.03 |
| v3 fix (sonnet-5) | 9/9 incl. holdout | $0.19 |

**Not yet done:** v3 on the full 5-trial scoreboard by editing the real `system-prompt-coordinator.txt`; v1 on the holdout; v3 on Haiku; opus/fable baselines (optional now — the model question is already answered).
