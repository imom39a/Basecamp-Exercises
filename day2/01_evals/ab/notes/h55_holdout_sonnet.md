# Holdout + model check on Haiku 5.5 / Sonnet 5.5 (2026-11-13)

Data: `runs.jsonl` records with `harness: "final-msg-text"`, `judge_model: claude-haiku-5-5`, 3 trials,
latest record per (variant, model, taskset). Haiku 5.5 holdout ran 10:04-10:05, Sonnet 5.5 dev 10:04-10:05
and holdout 10:06. Haiku 5.5 dev comes from the concurrent screen run (10:03-10:06, 3 trials). The 5-trial
dev runs of v_all and v_all_catprompt from the ablation run (10:04) both scored 55/55, which agrees. No Opus was used.
Spend: Haiku holdout $0.10, Sonnet dev $0.85, Sonnet holdout $0.91.

"Corrected" re-scores a failed trial as a pass only when every failing grade is an exact-argument
`tool_use` check and the agent called that tool with a singular/plural variant that returned a real
price (for example `get_product("sock")` -> 9.99 under the normalize lever). This was the only artifact
found. A dash means the variant wasn't run on that model.

| variant | H5.5 dev | H5.5 holdout raw / corr | S5.5 dev | S5.5 holdout | $/trial H dev / H ho / S dev / S ho |
|---|---|---|---|---|---|
| v0_baseline | 17/33 (52%) | 14/33 (42%) / same | 23/33 (70%) | 23/33 (70%) | .00029 / .00044 / .0060 / .0087 |
| v5a_cat_prompt | 33/33 (100%) | 30/33 (91%) / same | - | - | .00032 / .00034 / - / - |
| v5b_list_tool | 22/33 (67%) | 25/33 (76%) / same | - | - | .00034 / .00041 / - / - |
| v_all | 33/33 (100%) | **30/33 (91%) / 33/33 (100%)** | 33/33 | 33/33 | .00049 / .00054 / .0097 / .0102 |
| v_all_catprompt | 33/33 (100%) | **33/33 (100%) / same** | 33/33 | 33/33 | .00041 / .00044 / .0095 / .0083 |

Sonnet raw and corrected scores are the same, because Sonnet never called `"sock"`. No run had a run error or a max_tokens stop.
With n=33, a binomial 95% interval is about ±10 points.

## (a) Do the fixes generalize on Haiku 5.5?
Yes, for the combined variants. **v_all_catprompt is 33/33 on dev and 33/33 on holdout, with 0 tool
errors.** v_all is also 100% once the plural artifact is removed. The single levers only partly
generalize. v5a falls 9 points (dev 100% -> holdout 91%). v5b is weak on both sets (67% / 76%). Their holdout
misses are real process failures: neither variant has the `prompt`/`calc` levers, so the agent does
the math in its head. v5b skipped `calculate` in 8 trials, on multi_sweaters_socks_hat 0/3, budget_2_sneakers 0/3 and
discount_dress 1/3. Its totals were correct, but the spec says math comes from `calculate`. v5a also missed
pants once: it said "closest items are jeans and shorts. I can look up the price" and quoted no price.

## (b) Is it the model?
Partly. Sonnet 5.5 lifts the baseline from 52% to 70% on dev and from 42% to 70% on holdout. Its holdout misses are all
information gaps that reasoning can't close. TSHIRT tried "TSHIRT"/"tshirt"/"T-shirt", all `Error`. Cap tried
"baseball cap"/"cap"/"baseball_cap". Pants tried "pants"/"Pants"/"trousers" and failed 0/3. Laptop said "the product lookup
returned an error" instead of "we don't sell laptops" and failed 0/3. The dev pattern repeats: synonym_shoes,
catalog_overview and off_catalog_piano are each 0/3. Both models hit 100% only with the fixes.

## (c) Is Sonnet 5.5 worth its price for the fixed agent?
No. v_all_catprompt scores 100% on both sets with both models. Sonnet costs about $0.0083-0.0095 per trial and
Haiku 5.5 about $0.00041-0.00044, roughly 19-23x more for no measured gain. Recommendation: **ship
v_all_catprompt on claude-haiku-5-5.** The cost ratio depends on the `PRICES` table in `ab_suite.py`.

## Holdout failures of the best variant
**v_all_catprompt had none, 0/33 on both models.** The runner-up v_all's three failures on Haiku 5.5 are all grader artifacts:

| task / trial | class | evidence |
|---|---|---|
| ho_multi_sweaters_socks_hat #0, #1, #2 | grader artifact | `get_product {'product': 'sock'}` -> `9.99`, then 4 `calculate` calls, "**Total: $159.94**" (correct). It fails only on `'get_product' not called with {'product': 'socks'}`. |

## Spec ambiguity: "pants" -> jeans
`ho_synonym_pants` requires jeans at 49.99. That choice came from the subagent that wrote the holdout set; the user
never confirmed it. Shorts are an equally reasonable reading. Every passing trial got through by quoting jeans
first. Haiku: "our jeans are the closest match, and they're $49.99. We also carry shorts...". Sonnet
looked up both: "**Jeans:** $49.99 / **Shorts:** $34.99". An agent that answered only shorts would fail, and
that failure would be a spec ambiguity, not an agent error. Confirm the intended mapping with the user, or accept either answer.
