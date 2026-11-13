# Holdout run: 2026-11-13

`ab_suite.py v0_baseline v4_normalize v5a_cat_prompt v5b_list_tool v_all v_all_catprompt --tasks holdout --trials 3`
(claude-haiku-4-5 agent and judge, 11 tasks x 3 trials, spend $0.89). Dev numbers are the latest `taskset: "dev"` record per variant in `runs.jsonl`.

| variant | dev % | holdout % | gap | gain vs baseline (dev / holdout) |
|---|---|---|---|---|
| v0_baseline | 48 (16/33) | 15 (5/33) | -33 | n/a |
| v4_normalize | 39 (13/33) | 21 (7/33) | -18 | -9 / +6 |
| v5a_cat_prompt | 85 (28/33) | 73 (24/33) | -12 | +37 / +58 |
| v5b_list_tool | 91 (30/33) | 79 (26/33) | -12 | +43 / +64 |
| v_all | 84 (46/55) | 94 (31/33) | +10 | +36 / +79 |
| v_all_catprompt | 100 (33/33) | 91 (30/33) | -9 | +52 / +76 |

Holdout is harder than dev: the baseline falls 33 points. Measured against the baseline, no variant's gain shrinks. In absolute terms, **v5a_cat_prompt and v5b_list_tool each drop 12 points**. A single lever doesn't cover the new synonyms: `ho_synonym_pants` is 0/3 for both, `ho_brand_nike` is 0/3 for v5a, and `ho_synonym_trainers` is 1/3 for v5a. **v_all_catprompt drops 9 points** from a perfect dev score. With n=33, a binomial 95% interval is about ±10 points, so gaps under about 10 points are within noise.

## Holdout failures in v_all and v_all_catprompt

| variant | task / trial | class | evidence |
|---|---|---|---|
| v_all | ho_multi_sweaters_socks_hat #1 | **(b) grader** | The agent called `get_product {'product': 'sock'}` and got `9.99`. The total `$159.94` is correct. It fails only `tool_use` exact match: `'get_product' not called with {'product': 'socks'}`. |
| v_all | ho_summer_outfit_80 #0 | **(b) grader/harness** | `final_text` starts at `**Total: $79.97** ✓`, so the item list is missing. The judge says it "does not specify which items make up this outfit". The notebook runner sets `final_text = block.text` on each text block, which keeps only the last one, so the itemized list from earlier in the turn never reached the judge. The outfit (t-shirt 24.99 + shorts 34.99 + hat 19.99 = 79.97) is valid. |
| v_all_catprompt | ho_summer_outfit_80 #1 | **(b) grader/harness** | Same truncation: `**Total: $69.97**`. The judge says it "does not list specific items". The tool calls show t-shirt + shorts + socks = 69.97, which is valid. |
| v_all_catprompt | ho_synonym_cap #0 | **(a) agent** | No tool calls. The reply was "we do sell **hats** for a price I can look up for you. Would you like to know the price of a hat?" The agent mapped the synonym correctly but asked before looking up the price instead of calling `get_product`. |
| v_all_catprompt | ho_brand_nike #1 | **(a) agent** (mild) | "We sell hoodies... Would you like to know the price of our hoodie?" The brand-honesty judge passes, but the agent never quotes 44.99. Same habit of offering instead of looking up. |

No infra errors (c): `error` is null in every trial, with 0 max_tokens stops and 0 tool errors in v_all_catprompt.

After removing grader artifacts, the corrected holdout rates are **v_all 33/33 (100%)** and **v_all_catprompt 31/33 (94%)**.

## Verdict

The combined variants are **not overfit**. v_all scores higher on holdout than on dev, and v_all_catprompt's 9-point drop comes mostly from one harness artifact plus two "ask before looking up" agent misses. The cat_prompt path has that habit and v_all's list_tool path doesn't. The single-lever variants generalize only partly: they keep large gains over the baseline but lose about 12 points of absolute rate on unseen synonyms ("pants", "trainers", "Nike"). It takes the combination of levers to handle them.

Fix before trusting further numbers:
1. Make the runner concatenate all text blocks into `final_text`.
2. Relax the `tool_use` argument checks so singular and plural forms both match.
3. `ho_synonym_pants` is an ambiguous spec (jeans vs shorts). v_all passed it 3/3, but it should accept either answer or be reworded.
