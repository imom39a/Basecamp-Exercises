"""LLM-as-judge grader for the A/B suite.

Same contract as the notebook's Part 6 stub: grade(result, check, context) -> {"score", "reason"}.
The judge model is PINNED (one model per comparison, recorded in runs.jsonl) for every variant and every model in the sweep: if the ruler
changed between runs, score differences could come from the ruler instead of the agent.

The notebook's own Part 6 cell is still yours to write; this one keeps the suite runnable.
"""
import json
import threading

import os

JUDGE_MODEL = os.environ.get("BOUTIQUE_JUDGE", "claude-haiku-5-5")  # override: --judge-model / BOUTIQUE_JUDGE

JUDGE_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "One sentence, citing the response."},
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
        },
        "required": ["reason", "verdict"],
        "additionalProperties": False,
    },
}

JUDGE_SYSTEM = (
    "You grade one response from a shopping assistant against ONE criterion. "
    "Judge only that criterion: ignore tone, length, and anything the criterion doesn't mention. "
    "Use any ground truth given in the criterion; don't rely on outside knowledge of prices. "
    "If the response is empty or doesn't address the criterion, the verdict is FAIL. "
    "Write the reason first, then the verdict."
)

USAGE = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
_lock = threading.Lock()
_client = None


def _get_client():
    global _client
    if _client is None:
        from nbload import connection
        _client = connection().make_client(timeout=120.0)
    return _client


def grade_llm_judge(result, check, context=None):
    query = (context or {}).get("query", "")
    prompt = (
        f"<customer_query>\n{query}\n</customer_query>\n\n"
        f"<assistant_response>\n{result['final_text']}\n</assistant_response>\n\n"
        f"<criterion>\n{check}\n</criterion>"
    )
    resp = _get_client().messages.create(
        model=JUDGE_MODEL,
        max_tokens=4000,  # room for adaptive thinking on 5.5-series judges
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": JUDGE_SCHEMA},
    )
    with _lock:
        USAGE["input_tokens"] += resp.usage.input_tokens
        USAGE["output_tokens"] += resp.usage.output_tokens
        USAGE["calls"] += 1
    text = next(b.text for b in resp.content if b.type == "text")  # skip thinking blocks (5.5 models)
    data = json.loads(text)
    return {"score": 1.0 if data["verdict"] == "PASS" else 0.0, "reason": f"judge: {data['reason']}"}
