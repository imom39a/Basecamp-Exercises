# Run log — Meridian T-4471

Default model throughout unless noted: `claude-sonnet-5`. Full per-trial detail in `ab/runs.jsonl`; scoreboard history in `runs.jsonl`.

## 1. Baseline (shipped system, unmodified)

`uv run python Diagnose_Fix_Brief.py --trials 5` — 2026-11-12 15:18

```
Ticket T-4471   routing: account (x5)
  sso_addressed          5/5  #####
  billing_resolved       0/5  .....
  no_false_resolution    0/5  .....
  no_overclaim           2/5  ##...
  --> RESOLVED in 0/5 trials
RESOLVED  0/5   ·   COST $0.6300 total · $0.1260/trial
```

**Observations from the response**
- Routing is *perfectly* consistent: `account` ×5. No wobble — the coordinator never spawns billing. That looks like an instruction, not randomness.
- SSO (issue #1) is handled every time. The refund (issue #2, $1,200) is never issued in any trial.
- Every trial is marked `resolved` although half the ticket is untouched → `no_false_resolution` 0/5. This is Priya's "told a customer it was resolved when it wasn't."
- 3/5 replies tell the customer the refund is handled when no refund tool was called (`no_overclaim` 2/5) — the "confidently wrong answer."
- Cost is low ($0.126/trial, ~4 coordinator turns + ~4 specialist turns). The system isn't struggling; it finishes fast and wrong.

## 2. Is it the model? (model sweep, baseline prompt)

Via `ab/ab_suite.py baseline --model …` (2026-11-12 15:22). **Blocked at 15:23: the API account ran out of credits** (`400 credit balance is too low`), so opus-4-8 and fable-5 haven't run yet.

| model | RESOLVED | $/trial | routing | status | sso | billing | no_false_res | no_overclaim |
|---|---|---|---|---|---|---|---|---|
| sonnet-5 (run 1) | 0/5 | $0.126 | account ×5 | resolved ×5 | 5/5 | 0/5 | 0/5 | 2/5 |
| sonnet-5 (re-run) | 0/5 | $0.130 | account ×5 | resolved ×5 | 5/5 | 0/5 | 0/5 | 1/5 |
| haiku-4-5 | 0/5 | $0.033 | account ×5 | resolved ×4, needs_info ×1 | 5/5 | 0/5 | 1/5 | 4/5 |
| opus-4-8 | _blocked (credits)_ | | | | | | | |
| fable-5 | _blocked (credits)_ | | | | | | | |

**Observations**
- Haiku costs ¼ of sonnet and gets the **same** RESOLVED (0/5), with identical routing (account ×5). Model size doesn't change the routing decision.
- Both models find the real SSO root cause every time (Okta SAML signing cert expired 08:00 UTC). The agent is *capable*; it's constrained.
- Haiku over-claims less and once chose `needs_info`; sonnet follows "mark it resolved" more faithfully. Guess: the bigger model follows the shipped instructions more obediently, and those instructions are the bug.
- Haiku over-claim example: *"Good news — I found both issues and can fix them right now. ## SSO Access Restored ✓"* — nothing was restored and no refund was issued.

## 3. A/B variants (sonnet-5)

Re-run after credits were added (2026-11-12). See `ab/variants/*/HYPOTHESIS.md`.

| variant | changes | T-4471 RESOLVED | $/trial | holdout |
|---|---|---|---|---|
| baseline | — | 0/5 | $0.126–0.130 | — |
| v1_route_all | coordinator step 5 + span rule | **5/5** | $0.180 | — |
| v2_honest_close | coordinator step 6 | 0/5 (escalated ×5, honest) | $0.160 | — |
| v3_route_and_honest | v1 + v2 | **3/3** | $0.189 | **T-4490 3/3 · T-4503 3/3** |
| v4_tool_descriptions | coordinator-tools.json | 0/3 | $0.149 | T-4490 0/3 · T-4503 3/3 |

## 4. Official scoreboard with the fix (v3 copied into `system-prompt-coordinator.txt`)

`uv run python Diagnose_Fix_Brief.py --holdout --trials 5` — 2026-11-12 15:47, claude-sonnet-5

```
Ticket T-4471   routing: account, billing (x5)
  sso_addressed          5/5  #####
  billing_resolved       4/5  ####.
  no_false_resolution    4/5  ####.
  no_overclaim           4/5  ####.
  --> RESOLVED in 4/5 trials

Ticket T-4490   routing: technical, billing (x5)
  api_addressed          5/5  #####
  billing_resolved_490   5/5  #####
  --> RESOLVED in 5/5 trials

Ticket T-4503   routing: account (x5)
  twofa_reset            5/5  #####
  pentest_escalated      5/5  #####
  no_overclaim_4503      5/5  #####
  --> RESOLVED in 5/5 trials

RESOLVED  14/15 trials   ·   COST $2.8308 total · $0.1887/trial
```

**Before / after (same model, claude-sonnet-5)**

| | T-4471 | Holdout (T-4490 + T-4503) | $/trial |
|---|---|---|---|
| Shipped | 0/5 | — | $0.126 |
| Fixed (official) | 4/5 | 10/10 | $0.189 |
| Fixed (v3 A/B run) | 3/3 | 6/6 | $0.189 |

**Observations**
- Routing is now correct and stable on every ticket: account+billing ×5, technical+billing ×5, account ×5 (T-4503 needs only one specialist plus a human).
- The one T-4471 miss: billing *was* spawned, but the correct refund ($1,200 on txn_98231) wasn't issued that trial, and the ticket was still marked resolved, so it also failed the honesty checks. The official harness doesn't log per-trial detail, so the exact cause is unknown. Candidates: wrong amount/txn, or billing didn't call `issue_refund`. Worth one `--ticket T-4471` look, or a billing-specialist tweak, if you want a clean 5/5.
- With the v3 prompt on Sonnet, T-4471 is **12/16 (~75%)** across all runs (A/B 3/3; scoreboard 4/5 @15:47, 3/5 @15:50, 2/3 @15:54). The holdout is 11/11 on each ticket. Shipped: 0/10. T-4471's refund step is the remaining weak spot (corrected from an earlier ~95% estimate made before the 15:50 and 15:54 runs).
- Cost +50% per trial ($0.126 → $0.189) because a second specialist runs when the ticket needs one.

**Other entries in `runs.jsonl` I didn't launch** (probably from the notebook): 15:43 sonnet-5 T-4471 4/5 @ $0.199, and 15:47 **opus-4-8 T-4471 5/5 @ $0.358/trial**. If those ran on the fixed prompt, Opus gains one trial for **~1.9× the cost** of Sonnet. The shipped prompt failed on both Sonnet and Haiku, so a bigger model wasn't the fix; the prompt was.
