# Screen on claude-haiku-5-5

Run: `ab_suite.py screen --trials 3 --parallel 2 --workers 6`, 2026-11-13 10:03-10:06. Dev taskset
(11 tasks x 3 trials). Agent and judge are both claude-haiku-5-5, harness `final-msg-text`. Spend
$0.174. Other processes were writing holdout records at the same time; I used only `taskset: dev`.

## Per variant

Corrected = raw, minus any failure whose only cause is the exact-argument `tool_use` check
rejecting a call that `normalize` made succeed. Only 3 trials needed this: **v4_normalize /
singular_jean t1-t3**. Each called `get_product("jean")`, got `49.99`, and answered "The jean costs
$49.99." No other variant failed this way (v_all and v_all_catprompt passed every trial).

| variant | raw | corrected | pass^k | tool err/calls | agent $/trial |
|---|---|---|---|---|---|
| v0_baseline     | 17/33 (52%)  | 17/33 | 5/11  | 21/54 | 0.00029 |
| v1_prompt       | 30/33 (91%)  | 30/33 | 10/11 | 18/75 | 0.00040 |
| v2_tool_docs    | 20/33 (61%)  | 20/33 | 6/11  | 9/49  | 0.00030 |
| v3_errors       | 23/33 (70%)  | 23/33 | 6/11  | 12/47 | 0.00027 |
| v4_normalize    | 12/33 (36%)  | 15/33 | 3/11 (4/11 corr.) | 18/47 | 0.00026 |
| v5a_cat_prompt  | 33/33 (100%) | 33/33 | 11/11 | 5/64  | 0.00032 |
| v5b_list_tool   | 22/33 (67%)  | 22/33 | 7/11  | 10/69 | 0.00034 |
| v6_calc         | 20/33 (61%)  | 20/33 | 6/11  | 23/63 | 0.00034 |
| v_all           | 33/33 (100%) | 33/33 | 11/11 | 2/82  | 0.00049 |
| v_all_catprompt | 33/33 (100%) | 33/33 | 11/11 | 0/63  | 0.00041 |

Judge cost was about $0.006 per variant. No max_tokens stops and no run errors.

## Each lever alone vs baseline

The baseline fails in four ways. It asks for the price instead of looking it up (discount_jacket:
"I can work that out once I know the jacket's price. What does it cost?"). It says it has no
catalog (catalog_overview). It quotes market prices for pianos ("Used upright pianos: roughly
$500 to $3,000"). And it does arithmetic in its head (budget_4_jeans 0/3, `calculate` never called).

- **prompt (+13).** Fixes shoes, discount, budget and piano (all 0 to 3/3) and multi (2 to 3/3):
  "Boutique doesn't carry pianos. We're a clothing store with a fixed catalog". catalog_overview
  stays 0/3: "I can't browse the full catalog from here".
- **tool_docs (+3).** discount 0 to 3/3, following the docs' worked example: `calculate(*, 89.99, 0.8)`.
  Piano stays 0/3 because the answer hedges ("Pianos may not be sold here"). Catalog fails because
  it names only the three docs examples: "names only three catalog products (jeans, t-shirt, hoodie)".
  multi drops 2 to 1/3 (mental math).
- **errors (+6).** The miss message lists the catalog, so the model self-corrects. shoes 0 to 3/3:
  `get_product(shoes)` returns "not in the catalog. Available items: ...", then `get_product(sneakers)`.
  Piano 0 to 2/3 and budget 0 to 3/3. brand drops 3 to 2/3 and multi 2 to 1/3 (likely noise).
- **normalize (-5 raw, -2 corrected).** singular_jean drops 3 to 0/3 (all artifact, see above). brand
  drops 3 to 0/3, which is not an artifact: the agent stops after two misses, "My product lookup
  returned an error for both 'Levi's jeans' and 'Levis jeans'". The baseline went on to try `jeans`.
  normalize doesn't change those two calls, so this is behaviour variance at n=3, not a lever effect.
- **cat_prompt (+16, 33/33).** Fixes every failure on its own: "Our current range is: Tops: shirt,
  t-shirt, hoodie, sweater ...". Side effect: the model reads the appended line as the shop's name
  and calls it "Items Boutique".
- **list_tool (+5).** catalog, shoes and piano each go 0 to 3/3 ("Boutique's shoe option is the
  sneakers, priced at $74.99"). But once it has called `list_products`, it does math in its head:
  multi 2 to 0/3, budget 0/3, discount 0/3 even though the answer "$71.99" is right. Those
  failures come from the strict `calculate` check. They're not the normalize artifact, so I left
  them uncorrected.
- **calc (+3).** multi 2 to 3/3 and budget 0 to 3/3 (`calculate(*, 49.99, 4)`). It doesn't help
  lookups: 23 tool errors, from shoes and piano retries.

## Compared with the haiku-4-5 screen (directional only)

haiku-4-5 records used the older harness and a haiku-4-5 judge. Gains over baseline, h4.5 vs h5.5:
prompt +13 / +13, tool_docs +12 / +3, errors +5 / +6, normalize 0 / -5 (-2 corrected),
cat_prompt +15 / +16, list_tool +17 / +5, calc 0 / +3. The baseline rose from 13 to 17.

- **Mattered less on h5.5: list_tool and tool_docs.** On h4.5, list_tool was the best single
  lever (30/33). On h5.5 it falls to 22/33, because the model skips `calculate` after listing
  (math tasks 3/3 to 0/3). tool_docs loses budget, multi and piano.
- **Mattered more: errors and calc.** errors now fixes shoes (0 to 3/3). calc lifts budget and
  multi on h5.5 but did nothing on h4.5.
- **Unchanged:** prompt is strong on both. cat_prompt is the best single lever on both. normalize
  helps nowhere on dev; on both models its singular_jean score is the grader artifact.
- Both "all" variants reach 33/33 on h5.5, compared with 28 and 31 on h4.5, at about 1/8 the
  agent cost per trial ($0.0004-0.0005 vs $0.0033-0.0038).

Caveat: 3 trials per cell, so changes of 1-2 trials per task are within noise.
