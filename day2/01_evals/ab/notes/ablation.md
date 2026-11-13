# Ablation: v_all minus one lever

Run: `ab_suite.py v_all ablation --trials 5` on dev (11 tasks x 5 = 55), Haiku 4.5 agent + pinned Haiku judge,
2026-11-13 09:58-10:01 (the `trials: 5` records in `runs.jsonl`). Noise rule: a 1/5 swing on a task is noise.
"Corrected" counts `singular_jean` trials that called `get_product("jean")`, got 49.99 and answered $49.99 as passes (see artifact 1).

| variant | pass (raw) | pass (corrected) | pass^k raw / corr. | Δ vs v_all (corr.) | tasks that moved (raw, v_all -> variant) |
|---|---|---|---|---|---|
| v_all | 46/55 | 51/55 | 8/11 / 9/11 | - | - |
| minus_prompt | 43/55 | 45/55 | 8 / 9 | **-6** | synonym_shoes 5->0, brand_not_carried 2->0, (singular_jean 0->3 artifact) |
| minus_tool_docs | 42/55 | 46/55 | 7 / 8 | **-5** | synonym_shoes 5->1, (singular_jean 0->1 artifact) |
| minus_list_tool | 42/55 | 45/55 | 7 / 8 | **-6** | synonym_shoes 5->0, catalog_overview 5->1, brand_not_carried 2->**4** (up), (singular_jean 0->2 artifact) |
| minus_errors | 47/55 | 49/55 | 7 / 8 | -2 | synonym_shoes 5->3, (singular_jean 0->3 artifact) |
| minus_calc | 46/55 | 49/55 | 8 / 9 | -2 | synonym_shoes 5->3, (singular_jean 0->2 artifact) |
| minus_normalize | 51/55 | 51/55 | 9 / 9 | 0 (raw +5) | singular_jean 0->5 (pure artifact) |

## Per lever

- **prompt: necessary.** Without "answer directly instead of asking follow-up questions", the agent stops after the miss and asks:
  `get_product("shoes")` -> error, then *"we do have **sneakers**! Would you like to know the price of sneakers?"* (5/5 shoes fails).
  Brand 5/5 fails the same way: *"I don't have information about the specific brand ... I can tell you the price of our jeans if you'd like"* (never calls get_product).
- **list_tool: necessary** (but has a cost). Without it no trial looks at the catalog first: shoes 0/5, all *"We don't carry shoes, but we do have sneakers ... Would you like to know the price?"*,
  one with an invented price (*"sneakers for $65.00"*). catalog_overview 1/5: no tool call, *"We sell a fixed catalog of clothing items ..."* with <4 names.
  Cost: in v_all, brand_not_carried calls `list_products` 5/5 and then 3/5 stop without the price (*"We have one pair of jeans available. Would you like to know the price?"*);
  without list_tool it calls `get_product("jeans")` directly and passes 4/5. Worth a prompt line ("after listing, look up the price").
- **tool_docs: necessary (moderate confidence).** Shoes 5->1. Like the other minus-variants it skips `list_products` (0/5 list-first vs 4/5 in v_all)
  and then 4/5 ask *"Would you like to know the price of sneakers?"* instead of retrying. The mechanism ("pass the name as it appears in the catalog" pushing the agent to check the catalog) is inferred, not proven.
- **errors: not necessary; redundant with list_tool.** -2 is near noise. When `get_product("shoes")` returns the bare `Error: 'shoes'`, the agent calls `list_products` next, but 2/5 still ask instead of looking up sneakers.
- **calc: not necessary on dev; untested.** There were zero calculate errors in v_all or minus_calc (all math tasks 5/5 either way). The dev set never hits an unknown op or /0. Shoes 5->3 can't come from calc,
  so it's noise (the same swing tells us shoes' list-first habit is fragile). One trial invented *"sneakers for $45.00"*. Decide on calc with the holdout or a dedicated math-error task.
- **normalize: not necessary; redundant with tool_docs + errors.** Without it the agent passes `"jeans"` directly (3/5, tool_docs) or tries `"jean"`, gets the "Available items" error and retries `"jeans"` (2/5).
  The raw +5 is entirely the grader artifact below. Keep it only if the holdout shows variants that errors can't recover.

## Grader artifacts

1. **singular_jean tool_use is a false fail (the big one).** v_all 0/5 raw: every trial called `get_product({"product": "jean"})` -> `49.99` and answered *"Jeans are $49.99."*,
   failing only `get_product not called with {'product': 'jeans'}`. The check penalizes the normalize lever for working. False fails: v_all 5, tool_docs 4, list_tool 3, calc 3, prompt 2, errors 2, normalize 0.
   Fix: grade the tool result (49.99 returned) or accept any argument that resolves to jeans.
2. **best_value_100 judge false fail** (v_all trial 3): jeans + t-shirt = $74.98 with correct prices; the judge's own reason says *"jeans $49.99 + t-shirt $24.99 = $74.98, which is correct"* and fails it anyway.
3. **catalog_overview judge lenient pass** (minus_list_tool trial 3): no tool call; *"I can check prices on items like jeans, t-shirts, hoodies, dresses"* passed "names at least four products". These are guesses that happen to be in the catalog.
4. **response_numeric extracts commas** (`found: [',', ',']`). Harmless here (the expected value was really missing), but the failure messages mislead.
5. brand_not_carried failures are **real**, not artifacts: the agent asks "would you like the price?" instead of quoting $49.99, which the frozen spec says to do.
