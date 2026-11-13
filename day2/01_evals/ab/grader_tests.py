"""Grade the graders before trusting them.

Each case is a made-up agent result where WE know the right verdict. If the grader disagrees,
that's a FALSE PASS (grader too lenient) or FALSE FAIL (grader too strict). Known holes stay
visible here so you can discount them when reading eval results.

Usage (from day2/01_evals):
    uv run python ab/grader_tests.py            # deterministic graders only (free)
    uv run python ab/grader_tests.py --judge    # also the LLM judge (a few Haiku calls)
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from nbload import fresh_namespace  # noqa: E402
from tasks_dev import CATALOG_NAMES, CATALOG_PRICES  # noqa: E402


def fake(text="", calls=()):
    return {"final_text": text, "tool_calls": [dict(c) for c in calls], "messages": []}


GP = lambda p, r="": {"name": "get_product", "arguments": {"product": p}, "result": r}  # noqa: E731
CALC = lambda op, a, b, r: {"name": "calculate", "arguments": {"op": op, "input1": a, "input2": b}, "result": r}  # noqa: E731

# (label, grader, check, fake result, ideal verdict: True = should pass)
CASES = [
    # response_contains
    ("contains: plain correct answer", "response_contains", "49.99",
     fake("Jeans are $49.99."), True),
    ("contains: number inside a denial", "response_contains", "49.99",
     fake("Sorry, I can't confirm whether jeans are still 49.99 — please check in store."), False),
    ("contains: 'sneakers' when agent says it doesn't carry them", "response_contains", "sneakers",
     fake("We don't carry shoes or sneakers, sorry!"), False),

    # response_numeric
    ("numeric: correct total", "response_numeric", {"value": 139.95, "tolerance": 0.01},
     fake("3 shirts (89.97) + 2 belts (49.98) = **$139.95**"), True),
    ("numeric: thousands separator", "response_numeric", {"value": 1234.5, "tolerance": 0.01},
     fake("That comes to $1,234.50."), True),
    ("numeric: wrong total, right subtotals", "response_numeric", {"value": 139.95, "tolerance": 0.01},
     fake("3 shirts = 89.97, 2 belts = 49.98. Total: 129.95"), False),
    ("numeric: right number, then a made-up discount", "response_numeric", {"value": 139.95, "tolerance": 0.01},
     fake("Subtotal 139.95, and with our member discount you pay 125.96!"), False),
    ("numeric: price after a hyphen ('19.99-49.99')", "response_numeric", {"value": 49.99, "tolerance": 0.01},
     fake("Our prices run 19.99-49.99; jeans are the top of that range."), True),

    # tool_use
    ("tool_use: arg case differs", "tool_use", {"tool_name": "get_product", "arguments": {"product": "t-shirt"}},
     fake("", [GP("T-Shirt", "24.99")]), True),
    ("tool_use: called with wrong arg", "tool_use", {"tool_name": "get_product", "arguments": {"product": "t-shirt"}},
     fake("", [GP("tshirt", "Error: 'tshirt'")]), False),
    ("tool_use: calculate called but returned None (bad op)", "tool_use", {"tool_name": "calculate"},
     fake("20% off is $71.99", [GP("jacket", "89.99"), CALC("%", 89.99, 20, "None")]), False),
]

JUDGE_CASES = [
    ("judge: lists real products", f"The response names at least four products from this catalog: {CATALOG_NAMES}.",
     "What do you sell?", "We carry jeans, shirts, dresses, jackets, sneakers, hats and more.", True),
    ("judge: invents electronics", f"The response does not offer any product or category outside this catalog ({CATALOG_NAMES}), such as electronics, home goods, or brands.",
     "What do you sell?", "We sell clothing like jeans and hoodies, plus headphones and phone chargers.", False),
    ("judge: refuses piano but guesses price", "The response does not state or estimate any price for a piano.",
     "How much is a piano?", "We don't sell pianos, but they usually run around $3,000.", False),
    ("judge: basket over budget", f"The total cost of the recommended purchase is $100.00 or less, computed with these catalog prices: {CATALOG_PRICES}.",
     "I have $100 and need at least 1 jeans and 1 shirt.", "Get jeans ($49.99), a shirt ($29.99) and a hoodie ($44.99) — great value!", False),
    ("judge: basket fills budget exactly right", f"The total cost of the recommended purchase is $100.00 or less, computed with these catalog prices: {CATALOG_PRICES}.",
     "I have $100 and need at least 1 jeans and 1 shirt.", "Jeans ($49.99) + shirt ($29.99) + hat ($19.99) = $99.97.", True),
]


def verdict(ideal, got):
    if ideal == got:
        return "ok"
    return "FALSE PASS" if got else "FALSE FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true")
    args = ap.parse_args()

    reg = fresh_namespace()["GRADER_REGISTRY"]
    rows = []
    for label, gname, check, result, ideal in CASES:
        g = reg[gname](result, check, {"query": ""})
        rows.append((label, ideal, g["score"] == 1.0, g["reason"]))
    if args.judge:
        from judge import grade_llm_judge
        for label, check, query, text, ideal in JUDGE_CASES:
            g = grade_llm_judge(fake(text), check, {"query": query})
            rows.append((label, ideal, g["score"] == 1.0, g["reason"]))

    w = max(len(r[0]) for r in rows)
    print(f"{'case':<{w}}  {'should':<6}  {'grader':<6}  verdict")
    print("-" * (w + 34))
    for label, ideal, got, reason in rows:
        print(f"{label:<{w}}  {'pass' if ideal else 'fail':<6}  {'pass' if got else 'fail':<6}  {verdict(ideal, got)}")
    bad = [r for r in rows if r[1] != r[2]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} agree with the ideal verdict.")
    for label, ideal, got, reason in bad:
        print(f"  - {label}: {reason[:140]}")


if __name__ == "__main__":
    main()
