# Model sweep: is it the model?

Question: does a stronger model make up for the shipped agent's bad prompt and tool specs,
and what does the fixed agent (`v_all_catprompt`) cost on each model?

Setup: dev taskset (11 tasks) x 3 trials; judge pinned to claude-haiku-4-5; Haiku/Sonnet only.
Data: latest 3-trial `runs.jsonl` records for each model (haiku-4-5 from 09:55-09:56, the
others from the 09:58-10:00 sweep runs). Costs are agent-only, computed by `ab_suite.py` from its
`PRICES` table.

| model | baseline pass | fixed pass | agent $/trial (baseline, fixed) | max_tokens stops |
|---|---|---|---|---|
| claude-haiku-4-5  | 13/33 (39%) | 31/33 (94%)  | $0.00221, $0.00328 | 0 / 0 |
| claude-haiku-5-5  | 16/33 (48%) | 33/33 (100%) | $0.00028, $0.00039 | 0 / 0 |
| claude-sonnet-5   | 21/33 (64%) | 33/33 (100%) | $0.00819, $0.00837 | 0 / 0 |
| claude-sonnet-5-5 | 24/33 (73%) | 33/33 (100%) | $0.00607, $0.00936 | 0 / 0 |

Harness check: newer models use adaptive thinking by default and the agent has `max_tokens=1024`,
but no run hit a `max_tokens` stop, no trial had an empty `final_text`, and no run errors were
recorded. None of the scores above come from truncation.

Baseline tool errors grow with model strength (12/32 on haiku-4-5, 29/74 on sonnet-5-5). Stronger
models call the bad tools more often and retry more. They don't get more out of them.

## Per-task baseline (passes out of 3)

| task | h4.5 | h5.5 | s5 | s5.5 |
|---|---|---|---|---|
| multi_shirts_belts | 0 | 0 | 3 | 3 |
| discount_jacket    | 0 | 0 | 2 | 3 |
| brand_not_carried  | 0 | 2 | 3 | 3 |
| singular_jean      | 1 | 3 | 1 | 3 |
| synonym_shoes      | 0 | 0 | 0 | 0 |
| catalog_overview   | 0 | 0 | 0 | 0 |
| off_catalog_piano  | 0 | 0 | 0 | 0 |

(price_jeans, price_tshirt, budget_4_jeans and best_value_100 pass on every model.)

**A stronger model fixes these on its own:** multi_shirts_belts and discount_jacket (Sonnet),
brand_not_carried (Haiku 5.5 partly, Sonnet fully), and singular_jean (noisy). These are
reasoning and initiative failures: a capable model works out that it should use the tools.

Example, multi_shirts_belts ("3 shirts and 2 belts, what's my total?"). Haiku 4.5 calls no tools:
> "I'd be happy to help you calculate the total cost! However, I need to know the prices of the
> shirts and belts. Could you please provide: 1. The price of each shirt 2. The price of each belt"

Sonnet 5.5 looks up shirt and belt, then does three `calculate` calls:
> "Your total is **$139.95**. - 3 shirts at $29.99 each: $89.97 - 2 belts at $24.99 each: $49.98"

**No model fixes these:** synonym_shoes, catalog_overview and off_catalog_piano. These are
information failures. The baseline prompt and tool spec never say what the catalog contains,
and unknown items return a bare `Error: 'piano'`. No amount of reasoning can recover facts the
agent never receives.

Example, off_catalog_piano, Sonnet 5.5 (tools: `get_product("piano")` and `get_product("Piano")`,
both `Error`):
> "I couldn't get a price for a piano. The product lookup returned an error both times I tried...
> For a rough idea in the meantime, digital pianos usually cost a few hundred to a few thousand
> dollars."

It fails both judge checks: it reads the error as a lookup failure instead of "not carried", and
it estimates a price. synonym_shoes is the same pattern: Sonnet 5.5 tries "shoes", "shoe" and
"Shoes" and never reaches "sneakers", because nothing tells it that sneakers exist.

## Answer

Partly. Moving from Haiku 4.5 to Sonnet 5.5 lifts the baseline from 39% to 73%, but it stops
there. The three information-gap tasks fail 0/3 on every model. The fix lifts every model to
94-100%, and 100% on every model except Haiku 4.5. The prompt and tool fixes are what close the
gap. The model alone doesn't.

## Recommendation

**Ship the fixed agent on claude-haiku-5-5.** It holds the full fixed score (33/33, the same as
both Sonnets) at $0.00039 per trial. That is about 8x cheaper than the current Haiku 4.5 fixed
run ($0.00328, 31/33) and about 21-24x cheaper than Sonnet ($0.0084-0.0094). Upgrading to Sonnet
buys nothing on this taskset once the agent is fixed.

Caveats: 3 trials x 11 dev tasks is small, so confirm on the holdout set before switching. The
cost ratios depend on the `PRICES` table in `ab_suite.py` (Haiku 5.5 is listed at $0.10/$0.50 per
MTok), so check that against current pricing.
