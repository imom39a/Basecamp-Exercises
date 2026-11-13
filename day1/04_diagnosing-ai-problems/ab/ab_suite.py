"""A/B test suite for Diagnose, Fix, Brief (Meridian).

Each variant is a folder under ab/variants/<name>/ holding ONLY the lever files it changes
(system-prompt-*.txt, *-tools.json) plus a HYPOTHESIS.md. Any file a variant doesn't override
comes from the exercise folder as shipped. The agent loop, tickets, graders and scoring are
imported from Diagnose_Fix_Brief.py unchanged — this script only swaps which lever files load.

What it adds over the scoreboard: per-trial detail (routing, resolution_status, escalations,
every grader's reason, the customer reply) saved to ab/runs.jsonl, and a side-by-side table.

Usage (from day1/04_diagnosing-ai-problems):
    uv run python ab/ab_suite.py baseline                 # 5 trials on T-4471
    uv run python ab/ab_suite.py baseline v1 --trials 5   # side by side
    uv run python ab/ab_suite.py v1 --holdout --trials 3  # T-4471 + held-out tickets
    uv run python ab/ab_suite.py --list
"""
import argparse
import contextlib
import io
import json
import os
import pathlib
import sys
import time
from collections import Counter
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
EXERCISE = HERE.parent
VARIANTS = HERE / "variants"
RUNS = HERE / "runs.jsonl"
LEVERS = sorted(p.name for p in EXERCISE.iterdir()
                if (p.name.startswith("system-prompt-") and p.suffix == ".txt")
                or p.name.endswith("-tools.json"))

sys.path.insert(0, str(EXERCISE))
with contextlib.redirect_stdout(io.StringIO()):
    import Diagnose_Fix_Brief as dfb  # noqa: E402

_orig_load_prompt, _orig_load_tools = dfb.load_prompt, dfb.load_tools


def use_variant(name):
    """Point the harness's lever loaders at the variant folder, falling back to shipped files."""
    vdir = VARIANTS / name

    def pick(fname):
        return vdir / fname if (vdir / fname).exists() else None

    def load_prompt(fname):
        p = pick(fname)
        if not p:
            return _orig_load_prompt(fname)
        text = p.read_text()
        text = text.replace("{{ current_timestamp }}", "2026-03-11T13:52:14Z")
        return text.replace("{{ request_id }}", "req_9c4e7a2b1f8d")

    def load_tools(fname):
        p = pick(fname)
        return json.loads(p.read_text())["tools"] if p else _orig_load_tools(fname)

    dfb.load_prompt, dfb.load_tools = load_prompt, load_tools
    return [f for f in LEVERS if (vdir / f).exists()]


def list_variants():
    return sorted(p.name for p in VARIANTS.iterdir() if p.is_dir())


def run_variant(name, trials, holdout, model, verbose):
    overrides = use_variant(name)
    tasks = dfb.TASKS + (dfb.HOLDOUT_TASKS if holdout else [])
    t0 = time.time()
    buf = io.StringIO()
    with contextlib.redirect_stdout(sys.stdout if verbose else buf):
        report = dfb.run_eval(model=model, tasks=tasks, num_runs=trials)
    elapsed = time.time() - t0

    tickets, cost_total, res_total, n_total = {}, 0.0, 0, 0
    for row in report["rows"]:
        ts = row["trials"]
        detail = []
        for t in ts:
            r = t["result"]
            detail.append({
                "resolved": t["resolved"],
                "spawned": r["spawned"],
                "resolution_status": r["resolution_status"],
                "escalated": len(r["escalated"]),
                "tools": [f'{c["agent"]}:{c["name"]}' for c in r["tool_calls"]],
                "refunds": [c["arguments"] for c in r["tool_calls"] if c["name"] == "issue_refund"],
                "grades": {g: {"pass": s == 1.0, "why": why} for g, s, why in t["grades"]},
                "reply": r["final_text"],
                "cost": round(t["cost"], 4),
            })
        checks = {g: sum(d["grades"][g]["pass"] for d in detail) for g in detail[0]["grades"]}
        resolved = sum(d["resolved"] for d in detail)
        cost = sum(d["cost"] for d in detail)
        tickets[row["task"]] = {
            "resolved": resolved, "trials": len(ts), "checks": checks,
            "routing": dict(Counter(", ".join(d["spawned"]) or "nobody" for d in detail)),
            "status": dict(Counter(d["resolution_status"] for d in detail)),
            "trials_detail": detail,
        }
        cost_total += cost; res_total += resolved; n_total += len(ts)

    rec = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "variant": name, "overrides": overrides, "model": report["model"],
        "resolved": res_total, "trials": n_total,
        "cost_total": round(cost_total, 4), "cost_per_trial": round(cost_total / max(n_total, 1), 4),
        "seconds": round(elapsed, 1), "tickets": tickets,
    }
    with RUNS.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def print_run(rec):
    print(f"\n[{rec['variant']}] RESOLVED {rec['resolved']}/{rec['trials']}  "
          f"${rec['cost_per_trial']}/trial  {rec['seconds']}s  "
          f"overrides: {', '.join(rec['overrides']) or '(none)'}")
    for tid, t in rec["tickets"].items():
        print(f"  {tid}: resolved {t['resolved']}/{t['trials']}  routing {t['routing']}  "
              f"status {t['status']}")
        print("    checks: " + "  ".join(f"{k}={v}" for k, v in t["checks"].items()))
        for i, d in enumerate(t["trials_detail"], 1):
            fails = [f"{g}: {v['why']}" for g, v in d["grades"].items() if not v["pass"]]
            print(f"    trial {i}: {'RESOLVED' if d['resolved'] else 'fail    '} "
                  f"spawned={d['spawned']} status={d['resolution_status']} "
                  f"esc={d['escalated']}" + (f"  | {'; '.join(fails)}" if fails else ""))


def print_table(by_variant):
    names = list(by_variant)
    tids = list(by_variant[names[0]]["tickets"])
    rows = [("RESOLVED", lambda r: f"{r['resolved']}/{r['trials']}"),
            ("$/trial", lambda r: f"${r['cost_per_trial']:.4f}")]
    for tid in tids:
        rows.append((f"{tid} resolved", lambda r, tid=tid: "{resolved}/{trials}".format(**r["tickets"][tid])))
        for g in by_variant[names[0]]["tickets"][tid]["checks"]:
            rows.append((f"  {g}", lambda r, tid=tid, g=g:
                         f"{r['tickets'][tid]['checks'][g]}/{r['tickets'][tid]['trials']}"))
    w = max(12, *(len(n) for n in names))
    lw = max(len(l) for l, _ in rows) + 2
    print("\n" + "=" * (lw + (w + 2) * len(names)))
    print(f"{'metric':<{lw}}" + "".join(f"{n:>{w + 2}}" for n in names))
    print("-" * (lw + (w + 2) * len(names)))
    for label, get in rows:
        print(f"{label:<{lw}}" + "".join(f"{get(by_variant[n]):>{w + 2}}" for n in names))
    print("=" * (lw + (w + 2) * len(names)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="variant folder names under ab/variants/")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--holdout", action="store_true", help="also run held-out tickets T-4490, T-4503")
    ap.add_argument("--model", default=dfb.MODEL, help="test only — the fix must hold on the default model")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.names:
        for n in list_variants():
            over = [f for f in LEVERS if (VARIANTS / n / f).exists()]
            print(f"  {n:<20} overrides: {', '.join(over) or '(none)'}")
        return
    unknown = [n for n in args.names if not (VARIANTS / n).is_dir()]
    if unknown:
        sys.exit(f"Unknown variant(s): {', '.join(unknown)}. Use --list.")

    model = dfb._model(args.model)
    print(f"Model: {model}   trials/ticket: {args.trials}   holdout: {args.holdout}")
    by_variant = {}
    for name in args.names:
        print(f"\nRunning {name}...", flush=True)
        rec = run_variant(name, args.trials, args.holdout, model, args.verbose)
        print_run(rec)
        by_variant[name] = rec
    print_table(by_variant)


if __name__ == "__main__":
    main()
