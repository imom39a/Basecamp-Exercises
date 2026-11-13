"""Variants = named sets of levers, each with the hypothesis it tests and what it predicts.

Design: baseline -> each lever alone (is it SUFFICIENT?) -> all -> all-minus-one (is it NECESSARY?).
`v_all` uses list_tool for catalog visibility; `v_all_catprompt` swaps it for cat_prompt, so the
5a-vs-5b question is answered both alone (v5a vs v5b) and in combination.
"""
from levers import ALL_LEVERS

_ALL = [l for l in ALL_LEVERS if l != "cat_prompt"]  # v_all: list_tool flavor

VARIANTS = {
    "v0_baseline": dict(levers=[],
        hypothesis="Shipped agent, unchanged.",
        predicts="Low. Lookups with non-exact names fail; open-ended + negative tasks fail."),
    "v1_prompt": dict(levers=["prompt"],
        hypothesis="H1: the agent doesn't know it's a small clothing shop, so it asks for brand/style/currency.",
        predicts="Fewer clarifying questions, more direct answers; exact-name lookups still brittle."),
    "v2_tool_docs": dict(levers=["tool_docs"],
        hypothesis="H2: tool descriptions are just names, so Claude guesses argument format.",
        predicts="Better arguments (lowercase catalog keys); context problems remain."),
    "v3_errors": dict(levers=["errors"],
        hypothesis="H3: a miss returns `Error: 'x'`, which doesn't tell the agent what IS available.",
        predicts="Self-correction on misses: shoes->sneakers, jean->jeans, after one failed call."),
    "v4_normalize": dict(levers=["normalize"],
        hypothesis="H4: exact-match lookup fails on case/plural/punctuation variants.",
        predicts="jean/TSHIRT/hoodies pass; synonyms (shoes) don't. Must hold on holdout."),
    "v5a_cat_prompt": dict(levers=["cat_prompt"],
        hypothesis="H5a: the agent can't see the catalog. Product names in the system prompt.",
        predicts="catalog_overview + synonym tasks improve; costs tokens every call, can go stale."),
    "v5b_list_tool": dict(levers=["list_tool"],
        hypothesis="H5b: same as H5a, via a list_products tool (always current).",
        predicts="Similar to 5a if the agent thinks to call it; maybe weaker without a prompt nudge."),
    "v6_calc": dict(levers=["calc"],
        hypothesis="H6: calculate silently returns None on an unknown op, so the agent falls back to mental math.",
        predicts="Lower tool-error rate on math tasks; percentage task more reliable."),
    "v_all": dict(levers=_ALL,
        hypothesis="All levers together (list_tool flavor).",
        predicts="Highest score."),
    "v_all_catprompt": dict(levers=[l if l != "list_tool" else "cat_prompt" for l in _ALL],
        hypothesis="All levers, catalog in the prompt instead of a tool.",
        predicts="Within noise of v_all; tells us which catalog option to recommend."),
}

for lever in _ALL:
    VARIANTS[f"v_all_minus_{lever}"] = dict(
        levers=[l for l in _ALL if l != lever],
        hypothesis=f"Is `{lever}` necessary once everything else is in?",
        predicts=f"A drop vs v_all means `{lever}` carries weight nobody else covers.")

SCREEN = ["v0_baseline", "v1_prompt", "v2_tool_docs", "v3_errors", "v4_normalize",
          "v5a_cat_prompt", "v5b_list_tool", "v6_calc", "v_all", "v_all_catprompt"]
ABLATION = [f"v_all_minus_{l}" for l in _ALL]

# Added after the Haiku 5.5 ablation: only `prompt` and the catalog lever were necessary there.
VARIANTS["v_min"] = dict(levers=["prompt", "cat_prompt"],
    hypothesis="Minimal set from the h55 ablation: shop prompt + catalog names; tool code left as shipped.",
    predicts="Ties v_all_catprompt on dev; holdout tells whether errors/normalize/calc earn their keep.")
