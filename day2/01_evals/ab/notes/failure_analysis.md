# Failure analysis (blind), dev set, claude-haiku-4-5, 3 trials

Source: the latest record per variant in `ab/runs.jsonl` (taskset=dev, trials=3). 11 tasks x 3 = 33 trials per variant.
Pass counts: v0 13, v1 26, v4 13, v5b 30, v_all 28, v_all_catprompt 31. I labelled all 57 failed trials, one bucket each.

## Count table (failed trials)

| variant | wrong/no tool | wrong args | tool limit/error | clarifying Q | invented product/price | wrong math/reasoning | grader false fail | infra | total |
|---|---|---|---|---|---|---|---|---|---|
| v0_baseline     | 0 | 1 | 9 | 7 | 3 | 0 | 0 | 0 | 20 |
| v1_prompt       | 0 | 0 | 5 | 0 | 0 | 0 | 2 | 0 | 7 |
| v4_normalize    | 0 | 0 | 9 | 6 | 3 | 0 | 2 | 0 | 20 |
| v5b_list_tool   | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 3 |
| v_all           | 0 | 0 | 0 | 1 | 0 | 0 | 4 | 0 | 5 |
| v_all_catprompt | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 2 |

What the buckets cover:
- **tool limit/error**: `get_product` returns a bare `Error: 'shoes'` (or `'piano'`, `"Levi's jeans"`) with no catalog hint, so the agent can't map shoes to sneakers. There is also no way to list the catalog, so `catalog_overview` gets "I don't have a catalog".
- **clarifying Q**: in v0/v4 the agent asks the user for the shirt, belt or jacket price without calling `get_product`. In v5b and v_all it knows the item (sneakers, jeans) but asks "would you like the price?" instead of quoting it.
- **invented**: piano price ranges ($300 to $300,000) in v0/v4. In v_all_catprompt `synonym_shoes` t0 it says "sneakers for $60.00" with no tool call (the real price is 74.99).

## Grader false fail patterns (the score is wrong here, not the agent): 9 of 57 failures

1. **`tool_use` matches the argument exactly, so a singular name fails even though the tool accepted it.** 4 trials: v4 t0/t1, v_all t1/t2.
   `singular_jean` v_all t2: `get_product({"product":"jean"}) -> 49.99`, final "A jean costs $49.99." It fails the check `{'tool_name':'get_product','arguments':{'product':'jeans'}}`. The tool resolved "jean" and the answer is right. The check should test what the tool resolved, or accept either form.
2. **`brand_not_carried` requires `response_numeric` 49.99, which the task description doesn't ask for.** 2 trials: v_all t0, v_all_catprompt t1.
   The description says "no invented Levi's, offer our jeans". v_all_catprompt t1 answered: "Boutique carries jeans, but we don't have specific brands... We don't carry Levi's or any other particular brand. Would you like to know the price of our jeans?" This meets the description exactly, and the judge check passed. Only the price check failed.
3. **The LLM judge says the recommendation "doesn't specify which jeans or shirt".** 1 trial: `best_value_100` v1 t0.
   The final text was "1 pair of jeans + 1 shirt = **$79.98** ... leaves you with $20.02." The judge's check 1 expects a model or SKU, but the catalog has one item per name.
4. **The harness keeps only the last text block** (`parse_transcript` sets `final_text = block.text` each time and keeps the last one), so text written alongside the tool calls is dropped. 2 trials, likely cause, since I can't see the dropped text: `best_value_100` v_all t2 (stops `tool_use, tool_use, end_turn`) has final text "With your $20+ remaining, you could add items like socks or a hat..." and fails "no specific purchase recommended". v1 t2 is the same ("**Total: $79.98** ...") but also says "we only carry jeans and shirts", which is a real factual error that no check catches.

A side note, not a false fail: `response_numeric` number extraction returns punctuation tokens (`found: [',', '1.', '2.']`). It looks fragile, but it didn't change any verdict I checked.

## Passing trials that look like false passes

- **Wrong price passed the "every price matches" judge.** `best_value_100` v_all_catprompt t1: "T-shirt: At $29.99 (same as shirt)". The real price is 24.99 and `get_product('t-shirt')` was never called. This also invents a price.
- **A product outside the catalog passed the "no product outside this catalog" judge.** `catalog_overview` v1 t2 lists "Pants" among the shop's items, with no tool call.
- **The brand question is hedged, not answered.** `brand_not_carried` v1 t0-t2 ("I can't confirm whether these are Levi's specifically") and v5b t0 ("contact the Boutique directly to confirm if they stock Levi's"). The spec says to state that we don't carry the brand. These pass because 49.99 appears and nothing was invented.
- **The `tool_use: calculate` check passes even when the calculator returned `None`.** The ops `"add"` and `"multiply"` aren't recognised, and the agent did the math in its head. Seen in v0 `budget_4_jeans` t1, v0 `best_value_100` t2, v4 `best_value_100` t0 (and the failing v1 t2). The check confirms the tool was called, not that the result came from it.
- Small arithmetic slips the graders don't check: v1 `best_value_100` t1 says "$20.11 to spare" (should be 20.02). v5b `budget_4_jeans` t0 says "you could afford 1 pair" (2 are affordable). v4 `budget_4_jeans` t1 writes "4 jeans x $49.99 = $99.98".

## Takeaways

- Correcting the 9 false fails would move v4 from 13 to 15, v1 from 26 to 28, v_all from 28 to 32 and v_all_catprompt from 31 to 32. The gap between v_all and v_all_catprompt mostly disappears.
- The real failures left in the stronger variants are of two kinds: offering the item instead of quoting its price (v5b, v_all), and one invented price (catprompt).
- The judge checks on `best_value_100` and `catalog_overview` pass at least one wrong price and one item outside the catalog. Don't trust those checks without reading the trials by hand.
