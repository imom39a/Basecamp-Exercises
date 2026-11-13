# Ablation on claude-haiku-5-5: v_all minus one lever

Run: `ab_suite.py v_all v_all_catprompt ablation --trials 5 --parallel 2 --workers 6` on dev (11 tasks x 5 = 55),
agent = judge = claude-haiku-5-5, harness `final-msg-text`, 2026-11-13 10:04-10:09 (the `trials: 5` haiku-5-5 records in `runs.jsonl`).
Noise rule: a 1/5 swing on a task is noise. "Corrected" counts `singular_jean` trials that called `get_product("jean")`,
got 49.99 and answered $49.99 as passes (the kept exact-argument artifact).

| variant | raw | corrected | pass^k raw / corr. | Δ vs v_all (corr.) | tasks that moved | agent $/trial | tool calls (errors) |
|---|---|---|---|---|---|---|---|
| v_all | 55/55 | 55/55 | 11 / 11 | - | - | $0.00048 | 134 (5) |
| v_all_catprompt | 55/55 | 55/55 | 11 / 11 | 0 | - | **$0.00041** | 106 (0) |
| minus_prompt | 48/55 | 50/55 | 8 / 9 | **-5** | multi_shirts_belts 5->2, budget_4_jeans 5->3, (singular_jean 5->3 artifact) | $0.00036 | 112 (10) |
| minus_list_tool | 52/55 | 52/55 | 10 / 10 | **-3** | catalog_overview 5->2 | $0.00043 | 127 (11) |
| minus_tool_docs | 55/55 | 55/55 | 11 / 11 | 0 | - | $0.00050 | 153 (0) |
| minus_errors | 55/55 | 55/55 | 11 / 11 | 0 | - | $0.00047 | 129 (5) |
| minus_normalize | 55/55 | 55/55 | 11 / 11 | 0 | - | $0.00048 | 130 (9) |
| minus_calc | 55/55 | 55/55 | 11 / 11 | 0 | - | $0.00047 | 129 (3) |

Tool errors in v_all are harmless: `get_product("shoe"/"shoes"/"piano")` misses that the agent recovers from on the next call.

## Per lever

- **prompt: necessary.** Its contribution is the "do arithmetic with calculate" rule. Without it the agent gets the right numbers but does the math in its head: 3/5 shirts+belts and 2/5 budget trials never call `calculate` (*"Your total is **$139.95**: 3 shirts at $29.99 each = $89.97 ..."*, with tool calls `get_product(shirt), get_product(belt)` only). These count as real fails: the frozen spec requires the tool, but the answers are correct. It also brings back `get_product("jean")` (2/5), which normalize rescues; that is the artifact. The haiku-4-5 failure (asking follow-up questions) is gone: brand_not_carried and shoes stay 5/5 without the prompt.
- **list_tool: necessary, for one task.** catalog_overview 5->2. With no way to list the catalog the agent probes with `get_product` (3, 5 or 13 calls, including a made-up `skirt`), and 3/5 stop at three items: *"I don't have a full list I can browse ... Jeans, T-shirt, Hoodie"*. One trial makes no calls and names only the examples from the tool_docs description ("jeans", "t-shirt"). Every other task is unchanged.
- **tool_docs: redundant.** 55/55, 0 tool errors. Without it the agent calls `list_products` before every lookup (shoes and brand_not_carried 5/5 list-first, vs 4/5 and 1/5 in v_all), which costs more calls (153 vs 134) and a bit more money.
- **errors: redundant.** 55/55. The bare shipped `Error: 'shoe'` is enough: the agent calls `list_products` next and then `get_product("sneakers")`.
- **normalize: redundant.** 55/55. With prompt and tool_docs in place the agent passes `"jeans"` for "jean? how much?" in all 5 trials, so the normalizer never fires. It only matters when the prompt is missing (minus_prompt, 2/5 `jean`).
- **calc: redundant on dev, and untested.** No unknown op or divide-by-zero happens in any variant, so the dev set can't exercise this lever.

No lever is harmful: none of the removals scored above v_all.

## Minimal lever set and catalog choice

- **Minimal set: `prompt` + `list_tool`.** These are the only two removals that lose points beyond noise. That exact pair was not run as a variant (it would need a new entry in `variants.py`, which this slice can't edit), so treat it as the prediction for the next run. Supporting evidence from the concurrent 3-trial screen: `v1_prompt` alone scores 30/33 and fails only catalog_overview (0/3), which is the task list_tool fixes.
- **Catalog in the prompt beats the list_products tool here.** Score is tied (55/55 both, 0 tool errors with catprompt), and catprompt is about 15% cheaper ($0.00041 vs $0.00048 per trial: 106 vs 134 tool calls, ~2.8k vs ~3.4k input tokens per trial) because the agent goes straight to `get_product("sneakers")` instead of listing first. On the concurrent holdout run, v_all_catprompt scores 33/33 and v_all 30/33 (ho_multi_sweaters_socks_hat 0/3). With catprompt, the candidate minimal set is `prompt` + `cat_prompt`. That pair also needs its own run. The 3-trial screen shows `v5a_cat_prompt` alone at 33/33 on dev and 30/33 on holdout. The cost of the catprompt approach is the usual one: the names can go stale.

## What changed vs the haiku-4-5 ablation

- v_all goes from 46 raw / 51 corrected to **55/55**, and the per-trial cost falls about 8x ($0.00381 -> $0.00048).
- **The jean artifact is gone from v_all.** haiku-4-5 called `get_product("jean")` 5/5; haiku-5-5 calls `"jeans"` 5/5. Raw and corrected are now the same everywhere except minus_prompt.
- **synonym_shoes no longer depends on any lever.** On 4-5 it collapsed in almost every minus-variant (5->0/1/3). On 5-5 it is 5/5 in every variant: the agent always retries a miss with `sneakers`.
- **brand_not_carried is fixed.** 4-5 stopped at *"Would you like to know the price?"* (2/5 in v_all). 5-5 quotes $49.99 5/5 in every variant.
- **tool_docs went from necessary (-5) to redundant.** The prompt's failure mode changed from "asks follow-up questions" to "skips calculate". list_tool is still the only source for catalog_overview. errors, normalize and calc were redundant before and still are.
- The grader artifacts in `ablation.md` (singular_jean exact-args, the best_value judge false fail) did not show up in v_all this time. The exact-args one only appears in minus_prompt (2 trials).
