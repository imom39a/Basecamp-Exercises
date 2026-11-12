"""A/B test suite for Prompt Rescue.

Runs prompt variants (from variants.py) through the notebook's own eval harness, so the
scoring is identical to run_eval_suite(). Adds what the notebook doesn't show at a glance:
per-check tallies, per-category scores, repeat runs (Haiku is non-deterministic), and a
side-by-side table. Every run is appended to ab/runs.jsonl.

Usage (from day1/03_prompt-rescue):
    uv run python ab/ab_suite.py baseline v1            # one run each
    uv run python ab/ab_suite.py v1 v2 --repeat 2       # two runs each, averaged
    uv run python ab/ab_suite.py --list                 # show available variants
"""
import argparse
import contextlib
import io
import json
import pathlib
import sys
import time
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
EXERCISE = HERE.parent
NOTEBOOK = EXERCISE / "Prompt_Rescue_solo.ipynb"
RUNS = HERE / "runs.jsonl"
CHECKS = ["json_valid", "priority_correct", "entities_accurate", "response_coherent"]


def load_harness():
    """Exec the notebook's setup cell and eval-harness cell into one namespace."""
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    code = ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]
    setup = next(c for c in code if "from basecamp_setup import connect" in c)
    harness = next(c for c in code if "EVAL HARNESS" in c and "def run_eval(" in c)
    ns = {"__name__": "prompt_rescue_harness"}
    exec(compile(setup, "notebook:setup", "exec"), ns)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(harness, "notebook:harness", "exec"), ns)
    # Record the judge's one-line reason (the harness throws it away). Scoring is unchanged.
    original_judge = ns["judge_response"]
    ns["_judge_reasons"] = []

    def judge_with_reason(client, input_text, priority, response_text):
        ok, reason = original_judge(client, input_text, priority, response_text)
        ns["_judge_reasons"].append((response_text, reason))
        return ok, reason

    ns["judge_response"] = judge_with_reason
    return ns


def run_variant(ns, name, prompts, verbose):
    client = ns["claude"].make_client(timeout=600.0)
    cases = ns["_load_cases"](ns["_EVAL_CASES_B64"])
    buf = io.StringIO()
    ns["_judge_reasons"].clear()
    t0 = time.time()
    with contextlib.redirect_stdout(sys.stdout if verbose else buf):
        result = ns["run_eval"](client, prompts, cases)
    elapsed = time.time() - t0
    checks = {k: sum(r["criteria"][k]["pass"] for r in result["results"]) for k in CHECKS}
    reasons = dict(ns["_judge_reasons"])

    def why(r):
        parts = []
        for k in CHECKS:
            if r["criteria"][k]["pass"]:
                continue
            text = r["criteria"][k]["reason"]
            if k == "response_coherent":
                parsed, _ = ns["parse_output"](r["raw_output"])
                text = reasons.get((parsed or {}).get("response", ""), text)
            parts.append(f"{k}: {text}")
        return "; ".join(parts)

    failures = {r["case_id"]: why(r) for r in result["results"] if not r["pass"]}
    outputs = {r["case_id"]: r["raw_output"] for r in result["results"] if not r["pass"]}
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "variant": name, "steps": len(prompts), "model": ns["MODEL"],
        "passed": result["total_passed"], "total": result["total_cases"],
        "checks": checks,
        "categories": {k: [v["passed"], v["total"]] for k, v in result["categories"].items()},
        "failures": failures,
        "failed_outputs": outputs,
        "seconds": round(elapsed, 1),
    }
    with RUNS.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def print_run(rec):
    pct = round(100 * rec["passed"] / rec["total"])
    print(f"\n[{rec['variant']}] {rec['passed']}/{rec['total']} ({pct}%)  "
          f"{rec['steps']}-step  {rec['seconds']}s")
    print("  checks:     " + "  ".join(f"{k.split('_')[0]}={v}" for k, v in rec["checks"].items()))
    print("  categories: " + "  ".join(f"{k}={p}/{t}" for k, (p, t) in rec["categories"].items()))
    for cid, why in sorted(rec["failures"].items()):
        print(f"  FAIL case {cid:>2}: {why}")


def print_table(by_variant):
    names = list(by_variant)
    first = by_variant[names[0]][0]
    rows = [("TOTAL", lambda r: r["passed"], first["total"])]
    rows += [(k, (lambda k: lambda r: r["checks"][k])(k), first["total"]) for k in CHECKS]
    rows += [(k, (lambda k: lambda r: r["categories"][k][0])(k), t)
             for k, (_, t) in first["categories"].items()]
    w = max(14, *(len(n) for n in names))
    print("\n" + "=" * (22 + (w + 2) * len(names)))
    print(f"{'metric':<20}" + "".join(f"{n:>{w + 2}}" for n in names))
    print("-" * (22 + (w + 2) * len(names)))
    for label, get, total in rows:
        cells = []
        for n in names:
            vals = [get(r) for r in by_variant[n]]
            avg = sum(vals) / len(vals)
            spread = f" [{min(vals)}-{max(vals)}]" if len(vals) > 1 else ""
            cells.append(f"{avg:.1f}/{total}{spread}" if len(vals) > 1 else f"{vals[0]}/{total}")
        print(f"{label:<20}" + "".join(f"{c:>{w + 2}}" for c in cells))
    print("=" * (22 + (w + 2) * len(names)))


def main():
    sys.path.insert(0, str(HERE))
    import variants

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="variant names from variants.VARIANTS")
    ap.add_argument("--repeat", type=int, default=1, help="runs per variant (default 1)")
    ap.add_argument("--verbose", action="store_true", help="show the harness's per-case progress")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.names:
        for n, p in variants.VARIANTS.items():
            steps = 1 if isinstance(p, str) else len(p)
            print(f"  {n:<16} {steps}-step")
        return
    unknown = [n for n in args.names if n not in variants.VARIANTS]
    if unknown:
        sys.exit(f"Unknown variant(s): {', '.join(unknown)}. Use --list.")

    ns = load_harness()
    print(f"Model: {ns['MODEL']}")
    by_variant = {}
    for name in args.names:
        p = variants.VARIANTS[name]
        prompts = [p] if isinstance(p, str) else list(p)
        for i in range(args.repeat):
            print(f"\nRunning {name} (run {i + 1}/{args.repeat})...", flush=True)
            rec = run_variant(ns, name, prompts, args.verbose)
            print_run(rec)
            by_variant.setdefault(name, []).append(rec)
    print_table(by_variant)


if __name__ == "__main__":
    main()
