"""The levers. Each one is a single, named change to the shipped agent.

apply(ns, levers) takes a fresh notebook namespace (the agent exactly as shipped) and swaps in
only the pieces each lever owns. With no levers, nothing changes: that's the baseline.

Lever       Owns
---------   ------------------------------------------------------------------
prompt      SYSTEM_PROMPT: shop context, fixed catalog, USD, answer directly, use tools
tool_docs   description text in GET_PRODUCT_SPEC / CALCULATE_SPEC
errors      get_product: on a miss, return "not found, available: ..." instead of KeyError
normalize   get_product: lowercase/strip, ignore punctuation, singular<->plural
cat_prompt  SYSTEM_PROMPT: append the product NAMES (no prices: get_product stays the price source)
list_tool   new list_products() tool returning the names
calc        calculate: op enum in the schema, explicit error on unknown op / divide by zero
"""
import copy
import re

CATALOG = {
    "jeans": 49.99, "shirt": 29.99, "dress": 59.99, "jacket": 89.99, "sneakers": 74.99,
    "hat": 19.99, "socks": 9.99, "hoodie": 44.99, "shorts": 34.99, "t-shirt": 24.99,
    "sweater": 54.99, "belt": 24.99,
}
NAMES = ", ".join(CATALOG)

SHOP_PROMPT = """You are the shopping assistant for Boutique, a small clothing store. Prices are in US dollars.

Boutique sells a fixed catalog of clothing items. It has no brands, sizes, colors or styles to choose between: each item has one price.

- Look up every price with get_product; never quote a price from memory.
- Do arithmetic with calculate, one operation per call; never do math in your head.
- Each message is a complete request. Answer it directly with the information you have, instead of asking follow-up questions about brand, style, currency or budget.
- If a customer asks for something the store doesn't carry, say so plainly. If a catalog item is a close match (for example, a similar kind of clothing), suggest it with its price. Never invent products or prices."""

GET_PRODUCT_DOCS = {
    "description": ("Look up the price, in USD, of one catalog item. Pass the catalog item name in "
                    "lowercase singular form as it appears in the catalog (e.g. 'jeans', 't-shirt', "
                    "'hoodie'). Returns the price as a number, or an error if the item isn't sold."),
    "param": "Catalog item name, lowercase, e.g. 'jeans' or 't-shirt'.",
}
CALC_DOCS = {
    "description": ("Do one arithmetic operation on two numbers and return the result: input1 <op> input2. "
                    "For a percentage discount, multiply: 20% off 89.99 is 89.99 * 0.8."),
    "op": "One of '+', '-', '*', '/', '**'.",
    "input1": "Left operand.",
    "input2": "Right operand.",
}
LIST_PRODUCTS_SPEC = {
    "name": "list_products",
    "description": "List the names of every item Boutique sells. Use get_product for prices.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

ALL_LEVERS = ["prompt", "tool_docs", "errors", "normalize", "cat_prompt", "list_tool", "calc"]


def _key(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def make_get_product(normalize, errors):
    keyed = {_key(k): k for k in CATALOG}

    def get_product(product: str):
        if product in CATALOG:
            return CATALOG[product]
        if normalize:
            k = _key(product)
            for cand in (k, k + "s", k[:-1] if k.endswith("s") else None, k[:-2] if k.endswith("es") else None):
                if cand and cand in keyed:
                    return CATALOG[keyed[cand]]
        if errors:
            return f"Error: '{product}' is not in the catalog. Available items: {NAMES}."
        return CATALOG[product]  # shipped behavior: KeyError -> "Error: 'x'"

    return get_product


def safe_calculate(op: str, input1: float, input2: float):
    if op == "+": return input1 + input2
    if op == "-": return input1 - input2
    if op == "*": return input1 * input2
    if op == "/":
        if input2 == 0:
            return "Error: division by zero."
        return input1 / input2
    if op == "**": return input1 ** input2
    return f"Error: unsupported op '{op}'. Use one of '+', '-', '*', '/', '**'."


def apply(ns, levers):
    unknown = set(levers) - set(ALL_LEVERS)
    if unknown:
        raise ValueError(f"unknown levers: {unknown}")
    gp_spec = copy.deepcopy(ns["GET_PRODUCT_SPEC"])
    calc_spec = copy.deepcopy(ns["CALCULATE_SPEC"])
    specs = [gp_spec, calc_spec]

    prompt = SHOP_PROMPT if "prompt" in levers else ns["SYSTEM_PROMPT"]
    if "cat_prompt" in levers:
        prompt += f"\n\nItems Boutique sells: {NAMES}."
    ns["SYSTEM_PROMPT"] = prompt

    if "tool_docs" in levers:
        gp_spec["description"] = GET_PRODUCT_DOCS["description"]
        gp_spec["input_schema"]["properties"]["product"]["description"] = GET_PRODUCT_DOCS["param"]
        calc_spec["description"] = CALC_DOCS["description"]
        for p in ("op", "input1", "input2"):
            calc_spec["input_schema"]["properties"][p]["description"] = CALC_DOCS[p]

    if "normalize" in levers or "errors" in levers:
        ns["TOOL_REGISTRY"]["get_product"] = make_get_product("normalize" in levers, "errors" in levers)

    if "calc" in levers:
        calc_spec["input_schema"]["properties"]["op"]["enum"] = ["+", "-", "*", "/", "**"]
        ns["TOOL_REGISTRY"]["calculate"] = safe_calculate

    if "list_tool" in levers:
        ns["TOOL_REGISTRY"]["list_products"] = lambda: NAMES
        specs.append(copy.deepcopy(LIST_PRODUCTS_SPEC))

    ns["ALL_TOOL_SPECS"] = specs
    return ns
