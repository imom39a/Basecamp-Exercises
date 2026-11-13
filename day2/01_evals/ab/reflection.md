# Reflection: what's breaking boutique, and why

Working notes. Evidence first, conclusions second. Each hypothesis maps to a variant in `ab/variants.py`
(levers in `ab/levers.py`). Raw data: `ab/runs.jsonl`. Slice write-ups from the parallel subagents:
`ab/notes/*.md`.

**Setup:** Round 1 uses the shipped configuration: agent = judge = claude-haiku-4-5. **Round 2** (the one that
counts) uses agent = judge = claude-haiku-5-5, with the harness fix. Within a round the judge is pinned for every run. Dev set = 11 tasks, frozen before any fix existed (`tasks_dev.py`). Holdout = 11 tasks written blind by a
subagent (`tasks_holdout.py`).

## Spec decisions (yours)

- Close but not carried ("shoes"): suggest the closest item (sneakers) with its real price.
- Not carried at all ("piano", brands): say so, and never invent a product or price.
- Single-turn: every task is one self-contained message (the harness has no memory).
- Model sweeps: Haiku / Sonnet only, no Opus.
- `best_value_100`: correct = includes jeans + a shirt (t-shirt counts), total ≤ $100, real prices. It doesn't have to fill the budget.
- _Open:_ "pants" in the holdout maps to jeans only (subagent's call, not confirmed yet).

## What we observed

**From your chat session (before any eval):**
- It asked about brand, style, color and currency for a 12-item shop with one price per item.
- It invented Levi's products and "Levi's shoes".
- It forgot the budget between messages. That's the harness (single-turn), not the model.
- It said honestly that it had no tool to list the catalog.

**Baseline (v0, 3 trials): 13/33 (39%), pass^k 4/11. 12 of 32 tool calls errored.**
- **It doesn't realize it has a price tool.** On `multi_shirts_belts` it says: *"I need to know the prices of the shirts and belts. Could you please provide: 1. The price of each shirt…"*. On `discount_jacket`: *"I need to know the original price of the jacket first."* It made zero tool calls in both.
- `singular_jean`: *"Are you asking about a specific brand or style of jeans?"*, which repeats your chat message #1.
- `off_catalog_piano`: it called `get_product("piano")`, got `Error: 'piano'`, then **quoted piano price ranges anyway**, which is a made-up answer.
- `brand_not_carried`: it called `get_product("Levi's jeans")`, got a KeyError, and never offered the jeans the shop does carry.
- Passes: the exact-name lookups (`price_jeans`, `price_tshirt`), `budget_4_jeans` and `best_value_100`, 3/3 each.

## Grader caveats

From `grader_tests.py`: 11/16 cases agree with the ideal verdict, and the judge got 5/5.

| Grader | Hole | Effect on our numbers |
|---|---|---|
| `response_contains` | Passes on *"I can't confirm 49.99"* and *"we don't carry sneakers"* | Can count a refusal as a correct answer |
| `response_numeric` | Passes if the number appears anywhere (e.g. next to a made-up discount); misreads `19.99-49.99` as −49.99 | Credit for invented extras; rare false fails |
| `tool_use` | Passes when `calculate` was called but returned `None` (e.g. `op="add"`) | Hides silent tool failures. **Mitigation:** the suite reports a separate `tool errors / calls` number. |
| `tool_use` **with arguments** | **A lever triggers it:** with `normalize`, `get_product("jean")` *succeeds*, the agent answers *"Jeans cost $49.99"*, and the check for `product="jeans"` fails it | **False fail.** It explains `singular_jean` dropping to 0/3 under v4 and 1/3 under v_all. The check enforces the *path*, not the *grounding*. See open question 1. |

Rule we're following: **the graders and tasks stay frozen during the comparison.** Holes get written down here and discounted when reading results, not patched mid-run.

## Suspects in the levers (from the notebook code)

| # | Where | Text | Why it could produce what we saw |
|---|---|---|---|
| H1 | `SYSTEM_PROMPT` | `"You are a helpful assistant."` | No shop, no catalog, no "use your tools", so it asks the customer for prices |
| H2 | tool specs | `"description": "get_product"`, `"description": "calculator"`, param `"product"` | Nothing says the tool gives prices, or what format the names take |
| H3 | `get_product` | `return catalog[product]`, so a miss returns `Error: 'piano'` | The error doesn't tell the agent what *is* available, so it can't correct itself and makes something up instead |
| H4 | `get_product` | exact dict key | "jean", "TSHIRT", "hoodies" all miss |
| H5 | the tool set | no way to list the catalog | Can't answer "what do you sell", can't find sneakers from "shoes" |
| H6 | `calculate` | `elif` chain with no `else`, so an unknown op returns `None` | Silent failure, then mental math. Seen live: `calculate(op="add")` → `None` in v1. |

## Experiments: screening round (dev, haiku-4-5, 3 trials each)

| variant | levers | pass | pass^k | tool err | $/trial | read |
|---|---|---|---|---|---|---|
| v0_baseline | none | 13/33 (39%) | 4/11 | 12/32 | 0.0022 | Asks the customer for prices; makes up a price on a miss |
| v1_prompt | prompt | 26/33 (79%) | 8/11 | 7/57 | 0.0032 | **Biggest single lever.** Math tasks go 0→3/3 and piano 0→3/3. New problems: `catalog_overview` 1/3 (*"We carry a fixed catalog"* but names nothing), `best_value_100` 3→1/3 (says *"we only carry jeans and shirts"*, which is false, and uses `op="add"` → None) |
| v2_tool_docs | tool_docs | 25/33 (76%) | 7/11 | 6/53 | 0.0031 | Almost as good as the prompt alone. **Telling it the tool returns prices is enough** to stop it asking the customer. |
| v3_errors | errors | 18/33 (55%) | 6/11 | 11/35 | 0.0022 | Fixes `singular_jean` 1→3 and piano 0→3 by retrying after a useful error. Doesn't help math (it never calls a tool to begin with). |
| v4_normalize | normalize | 13/33 (39%) | 4/11 | 10/37 | 0.0023 | No net gain. `singular_jean` 1→0 is the **grader false fail** above. Alone, it still asks clarifying questions. |
| v5a_cat_prompt | cat_prompt | 28/33 (85%) | 9/11 | 4/52 | 0.0028 | Product names in the prompt act as shop context too. `catalog_overview` 3/3. Still 0/3 on `synonym_shoes`. |
| v5b_list_tool | list_tool | 30/33 (91%) | 9/11 | 8/79 | 0.0038 | **Best single lever.** The only one that gets `synonym_shoes` (2/3), because it lists the catalog and finds sneakers. Uses the most tool calls (79). |
| v6_calc | calc | 13/33 (39%) | 4/11 | 11/36 | 0.0024 | No change alone. The baseline never reaches `calculate`, so there's nothing for this lever to fix yet. |
| v_all | everything except cat_prompt | 28/33 (85%) | 7/11 | 3/59 | 0.0038 | No better than v5b alone. `singular_jean` 1/3 is the grader false fail. **Can't separate the levers yet at 3 trials; see the ablation.** |
| v_all_catprompt | all, catalog in the prompt | **31/33 (94%)** | **9/11** | **0/48** | 0.0033 | Best so far, and cheaper than v_all (no list_products round trip). Remaining fails: `synonym_shoes` 2/3, `brand_not_carried` 2/3. |

**How to read this:** with 3 trials, ±1 per task is noise. The *big* moves are real: baseline 39% → 76–91% from a single context lever (prompt, tool docs, or catalog). Differences among the top variants (85 / 91 / 94%) are not yet.

## Measurement problems found by the subagents (`notes/failure_analysis.md`, `notes/holdout.md`)

The blind failure analyst classified 57 failed trials. **9 were grader false fails, not agent failures:**

| Pattern | Trials | Example |
|---|---|---|
| `tool_use` exact argument | 4 dev, 1 holdout | `get_product("jean")` / `("sock")` returned the right price, and the answer was right. Rejected because the check wants `"jeans"` / `"socks"`. |
| **Harness keeps only the last text block** | ~2 dev, 2 holdout | `parse_transcript` sets `final_text = block.text` for *every* text block, so only the last one survives. A recommendation written next to a tool call is dropped, and the judge sees only *"Let me know if you'd like anything else."* This is a **runner bug**, found independently by two subagents. |
| `brand_not_carried` numeric 49.99 | 2 | The task description asks "offer our jeans", but the check requires the *price*. It's stricter than the spec. |
| Over-strict judge | 1 | It rejected *"1 jeans + 1 shirt = $79.98"* for not naming which jeans. |

**False passes:**
- A t-shirt quoted at the shirt's price ($29.99) passed "every price matches".
- "Pants" listed as a shop item passed "nothing outside the catalog".
- Hedged Levi's answers (*"I can't confirm"*) passed.
- `calculate(op="add")` → `None` passed the `tool_use` check.

**Corrected (agent-only) dev scores:** v4 13→15, v1 26→28, v_all 28→32, v_all_catprompt 31→32. **The v_all vs v_all_catprompt gap was mostly measurement.**

**Holdout (haiku-4-5, 3 trials): no overfitting in the combined variants.**

| variant | dev % | holdout % | read |
|---|---|---|---|
| v0_baseline | 48* | 15 | Holdout is harder (more synonyms and odd wording) |
| v4_normalize | 39 | 21 | |
| v5a_cat_prompt | 85 | 73 | Single levers lose about 12 points: "pants" 0/3, Nike 0/3 |
| v5b_list_tool | 91 | 79 | |
| v_all | 84 | **94** | Both failures are artifacts (sock/socks, last-text-block). Corrected: 33/33. |
| v_all_catprompt | 100* | 91 | 2 real failures: asked *"Would you like to know the price?"* instead of calling `get_product` |

\* latest record per variant; it includes the 5-trial ablation re-run of v_all.

Real failures left in the strong variants:
- It offers the item but doesn't quote the price, *asking* whether you want it.
- One invented price: *"sneakers for $60.00"* with no lookup.

**Ablation (haiku-4-5, v_all minus each lever, 5 trials; `notes/ablation.md`).** v_all raw 46/55, corrected 51/55. The 5 points are all from `singular_jean`: every v_all trial called `get_product("jean")`, got 49.99 and answered *"Jeans are $49.99."*

| lever | removing it (corrected Δ) | verdict | evidence |
|---|---|---|---|
| prompt | −6 | **necessary** | Without it the agent finds sneakers, then asks *"Would you like to know the price of sneakers?"*. `synonym_shoes` 5→0, `brand_not_carried` 2→0. |
| list_tool | −6 | **necessary** (in this flavor) | It never checks the catalog. `synonym_shoes` 5→0 with one invented *"sneakers for $65.00"*, `catalog_overview` 5→1. |
| tool_docs | −5 | necessary (moderate confidence) | `synonym_shoes` 5→1, the same follow-up-question failure |
| errors | −2 | not necessary | `list_tool` already tells the agent what's available |
| normalize | 0 | **not necessary** | Its raw +5 is entirely the grader false fail. Without it the agent passes `"jeans"`, or retries after the *"Available items"* error. |
| calc | −2 | untested | No dev trial hit a calculate error, and the math tasks were 5/5 either way |

A side effect of `list_tool`: on `brand_not_carried` it lists products, then stops without the price (3/5).

**Model sweep (old harness, haiku-4-5 judge; `notes/model_sweep.md`).** *Is it the model?*

| model | baseline | fixed (v_all_catprompt) | $/trial base → fixed |
|---|---|---|---|
| haiku-4-5 | 13/33 | 31/33 | 0.0022 → 0.0033 |
| haiku-5-5 | 16/33 | **33/33** | **0.0003 → 0.0004** |
| sonnet-5 | 21/33 | 33/33 | 0.0082 → 0.0084 |
| sonnet-5-5 | 24/33 | 33/33 | 0.0061 → 0.0094 |

- **A stronger model fixes initiative, not missing information.** Sonnet looks up the shirt and belt prices without being told to (*"Your total is $139.95"*), where Haiku 4.5 asks the customer for them.
- `synonym_shoes`, `catalog_overview` and `off_catalog_piano` fail **0/3 on every model**. No model can know a catalog it's never shown. Sonnet 5.5 says the lookup *"returned an error both times"* and then guesses *"digital pianos usually cost a few hundred to a few thousand dollars."*
- Baseline tops out at 73% even on Sonnet 5.5. The levers take every model to 94–100%.
- **Same conclusion as day 1: it's not the model.**

## Model switch: Haiku 5.5 / Sonnet 5.5

Your call: they're cheaper to run. Haiku 5.5 costs **$0.10 / $0.50** per 1M tokens, 10× cheaper than Haiku 4.5. Sonnet 5.5 costs $2 / $10, the same as Sonnet 5 and 2× Haiku 4.5. Both think by default, and thinking is billed as output, so we compare measured $/trial, not list price.

- **Judge recalibrated on Haiku 5.5:** 5/5 known-answer cases, two runs in a row. The parser skips thinking blocks now; on 5.5 the first block is thinking, so `content[0].text` broke.
- The Haiku 4.5 results above stay as the record of the shipped configuration. **They are not comparable with 5.5 runs**, because both the agent and the judge change. The whole comparison is re-run on 5.5.

**Your decisions (Nov 13):**
- **Fix the harness only.** `final_text` = every text block of the *final* assistant message, which is exactly what `run_agent` shows the customer in normal mode. It's overridden in `ab_suite.py`, and the notebook is untouched. Text from *earlier* messages still doesn't count, because the customer never sees it either.
- **Keep the strict argument checks**, and report raw and corrected scores side by side.
- **Haiku 5.5 is the main agent and the judge**, with Sonnet 5.5 as the check. New records carry `"harness": "final-msg-text"`.

Also fixed: `redirect_stdout` in worker threads was swallowing the suite's output. Threads now silence `print` in their own namespace instead.

## Round 2: Haiku 5.5 agent + judge, fixed harness

Notes: `notes/h55_screen.md`, `notes/h55_ablation.md`, `notes/h55_holdout_sonnet.md`. Round 1 notes (haiku-4-5): `notes/ablation.md`, `notes/holdout.md`, `notes/model_sweep.md`, `notes/failure_analysis.md`.

**Screen (dev, 3 trials):**

| variant | pass | read |
|---|---|---|
| v0_baseline | 17/33 | Newer model, same failure modes: no catalog, made-up piano prices |
| v1_prompt | 30/33 | Fails only `catalog_overview` |
| v2_tool_docs | 20/33 | Mattered much less than on 4.5 (+3 vs +12) |
| v3_errors | 23/33 | The *"Available items"* error lets it find sneakers |
| v4_normalize | 12/33 raw, 15 corrected | No help anywhere on dev |
| **v5a_cat_prompt** | **33/33** | **One lever fixes everything** |
| v5b_list_tool | 22/33 | Fixes catalog/shoes/piano, but **after listing it stops calling `calculate`**, so math tasks score 0/3 even though the answers (*"$71.99"*) are right |
| v6_calc | 20/33 | |
| v_all, v_all_catprompt | 33/33 each | |

**Ablation (dev, 5 trials, minus each lever from v_all):** only **prompt** (−7 raw, −5 corrected) and **list_tool** (−3, all on `catalog_overview`) are necessary. Without the prompt it skips `calculate` and does mental math. `tool_docs`, `errors`, `normalize` and `calc` each score 55/55 when removed. `calc` stays **untested**, because no dev task sends a bad operation.

**The minimal variant `v_min` = prompt + cat_prompt, with the tool code left as shipped:**

| variant | dev (5 trials) | holdout (5 trials) | tool errors | $/trial |
|---|---|---|---|---|
| v_min | **55/55** | **55/55** | 3/116 dev, 0/124 holdout | 0.0004 |
| v_all_catprompt | 55/55 | 55/55 | 0/104, 0/122 | 0.0004 |

**Sonnet 5.5 check (3 trials):**
- Baseline: Sonnet 5.5 scores 70% on dev and holdout, against Haiku 5.5's 52% / 42%.
- Fixed agent: **100% on both models and both sets**, but Sonnet costs $0.0083–0.0095 per trial against Haiku's $0.0004, about 20× more for no measured gain.
- Sonnet still fails, on baseline: TSHIRT, cap, pants, laptop, shoes, catalog and piano. Every one of those depends on knowing the catalog.

**Spend:** about $5 across both rounds, including the Sonnet runs.

## What was shipped to the notebook (Nov 13, your call: Haiku 5.5 for cost)

- **Setup cell:** `connect(model="claude-sonnet-5-5", fast_model="claude-haiku-5-5")`, so the agent and judge run on Haiku 5.5 and Sonnet 5.5 is available as `MODEL` for comparison.
- **Agent cell:** `v_all_catprompt`, verified to match the suite's variant exactly (prompt, specs, and tool behavior on probe inputs). It scored 22/22 running the notebook code directly.
- **Judge hint (Part 6):** skip thinking blocks, because `content[0]` is a thinking block on 5.5.
- Restored the `### Available graders` heading, which an accidental paste had overwritten.
- **The baseline is frozen** in `ab/shipped/Building_an_Eval.shipped.ipynb` (git HEAD). `nbload.py` reads it from there, so `v0_baseline` stays the shipped agent.

**Notebook completed (Nov 13): Haiku 5.5 only, every slot.**
- **Part 3:** the 6 deterministic dev tasks.
- **Part 6:** the judge, with two known-answer sanity checks, plus the 5 judge tasks. These are the same 11 ids as `tasks_dev.py`.
- **Part 2 runner:** the same `final_text` fix as the suite.
- **Findings section:** a live before/after.
- Interactive chat is off so Run All completes.
- **Executed end to end:** improved agent 11/11 × 3 runs, judge sanity 2/2, and the shipped vs improved table is **17/33 (52%) → 33/33 (100%)**. That matches the suite's Haiku 5.5 numbers.

**Why ship v_all_catprompt and not v_min**, when they tie? The tool fixes cost nothing and remove failure modes this eval doesn't exercise:
- `calculate` returning `None` on an unknown op. That happened live in round 1: `op="add"` → None.
- A bare `Error: 'x'` with no hint about what's available.
- v_min still had 3 tool errors on dev, where v_all_catprompt had 0.

This is a judgment call, not a measured win. If you'd rather ship only what the eval proves, ship v_min.

## Open questions for you

1. **The `tool_use` argument checks penalize a valid path.** `singular_jean` requires `get_product(product="jeans")`. Under `normalize`, `get_product("jean")` returns 49.99 and the answer is right. Two options:
   - Loosen the check to `{"tool_name": "get_product"}` plus the numeric check. This keeps the grounding requirement and drops the path requirement.
   - Keep it strict, because the *argument* is the point.

   If you loosen it, the dev set changes, so every variant gets re-run on that task. The holdout's `ho_price_tshirt_caps` and `ho_plural_hoodies` have the same shape.
2. **v1 introduced a new false claim** (*"we only carry jeans and shirts"*) while fixing other things. Do we treat that as a regression to fix before shipping? I'd say yes: it's the kind of thing that's easy to miss without an eval.
3. **Catalog: prompt or tool?** v_all_catprompt (94%, $0.0033) beats v_all with the tool (85%, $0.0038) on this run. The tool stays correct when the catalog changes, but the prompt is cheaper and scored higher. This is a business call; let's see whether the ablation and holdout change the picture.

## Conclusions

Draft. Your call on the framing.

1. **It's not the model.** Every model, Sonnet 5.5 included, tops out at 52–73% on the shipped agent. The same catalog-dependent tasks fail everywhere. Sonnet 5.5 says *"the lookup returned an error both times"* and then guesses piano prices anyway.
2. **Root cause: the agent has never been told where it works or what's in the catalog.** `"You are a helpful assistant."` plus 12 product names it can't see. That one gap explains:
   - asking the customer for prices,
   - asking about brands and currency,
   - inventing Levi's lines and piano prices,
   - missing shoes → sneakers.
3. **The fix is two prompt changes**, the shop context plus the catalog names (`v_min`). They take Haiku 5.5 from 52% to **100% on dev and on blind holdout** (110/110). The tool-code fixes are defensive hardening; the eval doesn't measure them.
4. **Catalog in the prompt beats a `list_products` tool** on Haiku 5.5: same or higher score, about 15% cheaper, no tool errors. Once the agent has listed the catalog it gets lazy and skips `calculate`. The tool is the better choice only when the catalog is too large or changes too often to put in the prompt.
5. **Model choice: Haiku 5.5.** It ties Sonnet 5.5 at 100% and costs about 20× less ($0.0004 vs ~$0.009 per query), and about 8× less than Haiku 4.5.
6. **Measure the ruler before trusting it.** 9 of 57 round-1 failures were scoring errors:
   - strict argument matching,
   - a harness bug that graded only the last text block,
   - checks stricter than the spec.

   Without the grader tests and the blind failure review, we'd have concluded that `normalize` hurts and that v_all is worse than v_all_catprompt. Neither is true.
7. **Some levers change value with the model.** `tool_docs` was necessary on Haiku 4.5 (−5) and redundant on 5.5. `list_tool` dropped from +17 to +5. When you change models, re-run the eval; don't carry the old conclusions over.

**Still open:**
- `calc` is untested: add a task that tempts a bad operation (e.g. "what's 15 mod 4?").
- "pants" → jeans is still unconfirmed.
- The strict argument checks keep producing false fails; the raw-vs-corrected column is the workaround.
- The notebook's own Part 3 task list and Part 6 judge are still yours to fill in. The suite's versions are in `ab/tasks_dev.py` and `ab/judge.py` if you want to compare after writing your own.
