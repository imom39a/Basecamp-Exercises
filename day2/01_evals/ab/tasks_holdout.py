"""Holdout task set. Written blind to every fix (no levers/variants/runs were read).

Same capabilities as tasks_dev.py, different surface forms. Don't tune variants against these;
run them only to check whether a dev-set gain generalises.

Spec decisions (the user's):
  - A product we don't carry but have something close to -> suggest the closest item, real price.
  - A product we don't carry at all (or a brand) -> say so; never invent a product or price.
  - Prices come from get_product, math from calculate.
  - One message per task: the harness is single-turn.
"""

CATALOG_PRICES = ("jeans 49.99, shirt 29.99, dress 59.99, jacket 89.99, sneakers 74.99, hat 19.99, "
                  "socks 9.99, hoodie 44.99, shorts 34.99, t-shirt 24.99, sweater 54.99, belt 24.99")
CATALOG_NAMES = ("jeans, shirt, dress, jacket, sneakers, hat, socks, hoodie, shorts, t-shirt, "
                 "sweater, belt")

TASKS = [
    # ── Lookup: case / spacing / plural variants ───────────────────────────
    {
        "id": "ho_price_tshirt_caps",
        "description": "All-caps, no hyphen: 'TSHIRT' must map to catalog key 't-shirt' (24.99)",
        "query": "how much is a TSHIRT",
        "category": "product_lookup",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 24.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "t-shirt"}}]},
        ],
    },
    {
        "id": "ho_plural_hoodies",
        "description": "Plural 'hoodies' must map to catalog key 'hoodie' (44.99)",
        "query": "hoodies - what do they go for?",
        "category": "product_lookup",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 44.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "hoodie"}}]},
        ],
    },

    # ── Synonyms: not in catalog but close ─────────────────────────────────
    {
        "id": "ho_synonym_trainers",
        "description": "UK synonym 'trainers' -> sneakers (74.99)",
        "query": "Do you sell trainers? What's the price?",
        "category": "synonym",
        "graders": [
            {"type": "response_contains", "checks": ["sneakers"]},
            {"type": "response_numeric", "checks": [{"value": 74.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "sneakers"}}]},
        ],
    },
    {
        "id": "ho_synonym_cap",
        "description": "'baseball cap' -> hat (19.99)",
        "query": "how much would a baseball cap be?",
        "category": "synonym",
        "graders": [
            {"type": "response_contains", "checks": ["hat"]},
            {"type": "response_numeric", "checks": [{"value": 19.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "hat"}}]},
        ],
    },
    {
        "id": "ho_synonym_pants",
        "description": "'pants' -> jeans (49.99), the closest full-length legwear we carry",
        "query": "What do pants cost here?",
        "category": "synonym",
        "graders": [
            {"type": "response_contains", "checks": ["jeans"]},
            {"type": "response_numeric", "checks": [{"value": 49.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "jeans"}}]},
        ],
    },

    # ── Multi-item and percentage math ─────────────────────────────────────
    {
        "id": "ho_multi_sweaters_socks_hat",
        "description": "Three lookups + math: 2x54.99 + 3x9.99 + 1x19.99 = 109.98 + 29.97 + 19.99 = 159.94",
        "query": "Ring me up for 2 sweaters, 3 pairs of socks and a hat please",
        "category": "multi_step_math",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 159.94, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [
                {"tool_name": "get_product", "arguments": {"product": "sweater"}},
                {"tool_name": "get_product", "arguments": {"product": "socks"}},
                {"tool_name": "get_product", "arguments": {"product": "hat"}},
                {"tool_name": "calculate"},
            ]},
        ],
    },
    {
        "id": "ho_discount_dress",
        "description": "Percentage math: 59.99 x 0.85 = 50.9915 -> 50.99",
        "query": "If the dress is 15% off, what do I pay?",
        "category": "multi_step_math",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 50.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [
                {"tool_name": "get_product", "arguments": {"product": "dress"}},
                {"tool_name": "calculate"},
            ]},
        ],
    },
    {
        "id": "ho_budget_2_sneakers",
        "description": "Budget check, affordable side: 2 x 74.99 = 149.98 <= 150 (0.02 left over)",
        "query": "Can I get two pairs of sneakers with $150?",
        "category": "multi_step_math",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 149.98, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "calculate"}]},
            {"type": "llm_judge", "checks": [
                "The response tells the customer that yes, two pairs of sneakers at $74.99 each "
                "($149.98 total) fit within their $150 budget.",
            ]},
        ],
    },

    # ── Negative: brand and fully off-catalog ──────────────────────────────
    {
        "id": "ho_brand_nike",
        "description": "Brand we don't carry: no invented Nike line, offer our hoodie (44.99)",
        "query": "Got any Nike hoodies?",
        "category": "negative",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 44.99, "tolerance": 0.01}]},
            {"type": "llm_judge", "checks": [
                "The response does not claim the store carries Nike or any other named brand, "
                "and does not invent Nike product lines or styles.",
            ]},
        ],
    },
    {
        "id": "ho_off_catalog_laptop",
        "description": "Totally off-catalog: say not carried, no price",
        "query": "whats the price on a laptop",
        "category": "negative",
        "graders": [
            {"type": "llm_judge", "checks": [
                "The response tells the customer the store does not sell laptops.",
                "The response does not state or estimate any price for a laptop.",
            ]},
        ],
    },

    # ── Open-ended recommendation ──────────────────────────────────────────
    {
        "id": "ho_summer_outfit_80",
        "description": "Open-ended outfit under $80 (e.g. shorts 34.99 + t-shirt 24.99 + hat 19.99 = 79.97)",
        "query": "Put together a summer outfit for me for under $80.",
        "category": "recommendation",
        "graders": [
            {"type": "llm_judge", "checks": [
                f"Every item the response recommends is from this catalog: {CATALOG_NAMES}.",
                f"The total cost of the recommended outfit is under $80.00, computed with these "
                f"catalog prices: {CATALOG_PRICES}.",
                f"Every price the response quotes matches these catalog prices: {CATALOG_PRICES}.",
            ]},
        ],
    },
]
