"""Dev task set — FROZEN. Approved 2026-11-13, before any fix existed.

Don't edit these to make a variant pass. If a task turns out to be unfair, write down why in
reflection.md, change it, and re-run *every* variant so the comparison stays apples to apples.

Spec decisions (yours):
  - A product we don't carry but have something close to ("shoes") -> suggest the closest item.
  - A product we don't carry at all ("piano", brands) -> say so; never invent a product or price.
  - One message per task: the harness is single-turn, so nothing relies on memory.
"""

CATALOG_PRICES = ("jeans 49.99, shirt 29.99, dress 59.99, jacket 89.99, sneakers 74.99, hat 19.99, "
                  "socks 9.99, hoodie 44.99, shorts 34.99, t-shirt 24.99, sweater 54.99, belt 24.99")
CATALOG_NAMES = ("jeans, shirt, dress, jacket, sneakers, hat, socks, hoodie, shorts, t-shirt, "
                 "sweater, belt")

TASKS = [
    # ── From the notebook's five queries ───────────────────────────────────
    {
        "id": "price_jeans",
        "description": "Direct price lookup for jeans (reference task)",
        "query": "How much do jeans cost?",
        "category": "product_lookup",
        "graders": [
            {"type": "response_contains", "checks": ["49.99"]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "jeans"}}]},
        ],
    },
    {
        "id": "price_tshirt",
        "description": "Hyphenated product name",
        "query": "Price of a t-shirt?",
        "category": "product_lookup",
        "graders": [
            {"type": "response_contains", "checks": ["24.99"]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "t-shirt"}}]},
        ],
    },
    {
        "id": "synonym_shoes",
        "description": "Not in catalog but close: should suggest sneakers",
        "query": "How much for shoes?",
        "category": "synonym",
        "graders": [
            {"type": "response_contains", "checks": ["sneakers"]},
            {"type": "response_numeric", "checks": [{"value": 74.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "sneakers"}}]},
        ],
    },
    {
        "id": "multi_shirts_belts",
        "description": "Two lookups + math: 3x29.99 + 2x24.99 = 139.95",
        "query": "3 shirts and 2 belts, what's my total?",
        "category": "multi_step_math",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 139.95, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [
                {"tool_name": "get_product", "arguments": {"product": "shirt"}},
                {"tool_name": "get_product", "arguments": {"product": "belt"}},
                {"tool_name": "calculate"},
            ]},
        ],
    },
    {
        "id": "discount_jacket",
        "description": "Percentage math: 89.99 x 0.8 = 71.99",
        "query": "What's 20% off a jacket?",
        "category": "multi_step_math",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 71.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [
                {"tool_name": "get_product", "arguments": {"product": "jacket"}},
                {"tool_name": "calculate"},
            ]},
        ],
    },
    {
        "id": "catalog_overview",
        "description": "Open-ended: describe what the shop sells",
        "query": "What do you sell?",
        "category": "catalog",
        "graders": [
            {"type": "llm_judge", "checks": [
                f"The response names at least four products from this catalog: {CATALOG_NAMES}.",
                f"The response does not offer any product or category outside this catalog "
                f"({CATALOG_NAMES}), such as electronics, home goods, or brands.",
            ]},
        ],
    },

    # ── From your chat session ─────────────────────────────────────────────
    {
        "id": "singular_jean",
        "description": "Casual singular wording ('jean')",
        "query": "jean? how much?",
        "category": "product_lookup",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 49.99, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "get_product", "arguments": {"product": "jeans"}}]},
        ],
    },
    {
        "id": "budget_4_jeans",
        "description": "Budget check: 4 x 49.99 = 199.96 > 100",
        "query": "I have $100 and need 4 jeans. Can I afford it?",
        "category": "multi_step_math",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 199.96, "tolerance": 0.01}]},
            {"type": "tool_use", "checks": [{"tool_name": "calculate"}]},
            {"type": "llm_judge", "checks": [
                "The response clearly tells the customer that 4 pairs of jeans cost more than their $100 budget.",
            ]},
        ],
    },
    {
        "id": "brand_not_carried",
        "description": "Brand we don't carry: no invented Levi's, offer our jeans",
        "query": "Do you have Levi's jeans?",
        "category": "negative",
        "graders": [
            {"type": "response_numeric", "checks": [{"value": 49.99, "tolerance": 0.01}]},
            {"type": "llm_judge", "checks": [
                "The response does not claim the store carries Levi's or any other named brand, "
                "and does not invent Levi's product lines or styles.",
            ]},
        ],
    },
    {
        "id": "off_catalog_piano",
        "description": "Totally off-catalog: say not carried, no price",
        "query": "How much is a piano?",
        "category": "negative",
        "graders": [
            {"type": "llm_judge", "checks": [
                "The response tells the customer the store does not sell pianos.",
                "The response does not state or estimate any price for a piano.",
            ]},
        ],
    },
    {
        "id": "best_value_100",
        "description": "Open-ended recommendation under a budget",
        "query": "I have $100 and need at least 1 jeans and 1 shirt. What's the best value I can get?",
        "category": "recommendation",
        "graders": [
            {"type": "llm_judge", "checks": [
                "The recommended purchase includes at least one pair of jeans and at least one shirt "
                "(the catalog item 'shirt' or 't-shirt' both count as a shirt).",
                f"The total cost of the recommended purchase is $100.00 or less, computed with these "
                f"catalog prices: {CATALOG_PRICES}.",
                f"Every price the response quotes matches these catalog prices: {CATALOG_PRICES}.",
            ]},
        ],
    },
]
