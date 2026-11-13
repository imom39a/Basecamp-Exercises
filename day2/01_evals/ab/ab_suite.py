"""A/B suite for the boutique agent (day 2 · evals).

The agent, graders and runner come from Building_an_Eval.ipynb unchanged (see nbload.py).
A variant is a named set of levers (variants.py); a lever is one change (levers.py).
The LLM judge is pinned to Haiku 4.5 for every run (judge.py).

What it adds over the notebook's run_eval: per-task pass^k / pass@k, tool-error rate (a tool
was called but returned an error or None, which the tool_use grader can't see), cost,
a turn guard, per-trial detail in ab/runs.jsonl, and a side-by-side table.

Usage (from day2/01_evals):
    uv run python ab/ab_suite.py --list
    uv run python ab/ab_suite.py v0_baseline v1_prompt --trials 3
    uv run python ab/ab_suite.py screen --trials 3            # baseline, each lever, v_all
    uv run python ab/ab_suite.py ablation --trials 3          # v_all minus each lever
    uv run python ab/ab_suite.py v_all --tasks holdout --trials 5
    uv run python ab/ab_suite.py v0_baseline v_all --model claude-sonnet-5
    uv run python ab/ab_suite.py --table v0_baseline v_all    # reprint from runs.jsonl, no API calls
"""
import argparse
import json
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import judge  # noqa: E402
import levers as L  # noqa: E402
from nbload import fresh_namespace  # noqa: E402
from variants import ABLATION, SCREEN, VARIANTS  # noqa: E402

RUNS = HERE / "runs.jsonl"
DEFAULT_MODEL = "claude-haiku-5-5"          # switched from the notebook's haiku-4-5 (10x cheaper per token)
SWEEP_OK = {"claude-haiku-4-5", "claude-haiku-5-5", "claude-sonnet-5", "claude-sonnet-5-5"}
PRICES = {  # USD per 1M tokens (input, output)
    "claude-haiku-4-5": (1.00, 5.00), "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5": (2.00, 10.00), "claude-sonnet-5-5": (2.00, 10.00),
}
MAX_CALLS = 12  # per query; the shipped loop has no limit


def load_tasks(which):
    out = []
    if which in ("dev", "both"):
        from tasks_dev import TASKS as dev
        out += dev
    if which in ("holdout", "both"):
        from tasks_holdout import TASKS as ho
        out += ho
    return out


def build_agent(variant):
    ns = fresh_namespace()
    L.apply(ns, VARIANTS[variant]["levers"])
    ns["GRADER_REGISTRY"]["llm_judge"] = judge.grade_llm_judge
    ns["print"] = lambda *a, **k: None  # silence run_eval's progress lines (redirect_stdout isn't thread-safe)

    local = threading.local()
    inner_call = ns["call_claude"]

    def guarded_call(messages, tools, model=None):
        local.calls += 1
        if local.calls > MAX_CALLS:
            raise RuntimeError(f"turn guard: more than {MAX_CALLS} model calls")
        resp = inner_call(messages, tools, model=model)
        local.stops.append(resp.stop_reason)
        return resp

    ns["call_claude"] = guarded_call

    # Harness fix (approved): the notebook's parse_transcript keeps only the LAST text block
    # (`final_text = block.text` in a loop). The customer actually sees what run_agent returns in
    # normal mode: every text block of the FINAL assistant message, joined. Grade exactly that.
    inner_parse = ns["parse_transcript"]
    TextBlock = ns["TextBlock"]

    def parse_transcript(messages):
        out = inner_parse(messages)
        last = next((m for m in reversed(messages) if m["role"] == "assistant"), None)
        if last is not None:
            out["final_text"] = "\n".join(b.text for b in last["content"] if isinstance(b, TextBlock))
        return out

    ns["parse_transcript"] = parse_transcript
    stops = {}

    def agent_fn(query, eval_mode=False, model=None):
        local.calls, local.stops = 0, []
        try:
            return ns["run_agent"](query, eval_mode=eval_mode, model=model)
        finally:
            stops[query] = list(local.stops)

    return ns, agent_fn, stops


def tool_results(r):
    """(name, args, result) for each tool call, from the runner's transcript."""
    uses = {b["id"]: b for b in r.get("transcript", []) if isinstance(b, dict) and b.get("type") == "tool_use"}
    out = []
    for b in r.get("transcript", []):
        if isinstance(b, dict) and b.get("type") == "tool_result":
            u = uses.get(b["tool_use_id"], {})
            out.append({"name": u.get("name"), "args": u.get("input"), "result": str(b.get("content", ""))})
    return out


def is_tool_error(res):
    return res.startswith("Error") or res == "None"


def run_variant(variant, tasks, trials, model, workers, taskset):
    ns, agent_fn, stops = build_agent(variant)
    j0 = dict(judge.USAGE)
    t0 = time.time()
    per_task = {t["id"]: [] for t in tasks}
    for _ in range(trials):
        res = ns["run_eval"](agent_fn, tasks, model=model, num_runs=1, max_workers=workers)
        for r in res["runs"][0]:
            calls = tool_results(r)
            m = r.get("metrics", {})
            per_task[r["task_id"]].append({
                "passed": r["passed"],
                "error": (r.get("error") or "")[-300:] or None,
                "final_text": r.get("final_text", ""),
                "tools": calls,
                "tool_errors": sum(is_tool_error(c["result"]) for c in calls),
                "stops": stops.get(r["query"], []),
                "grades": [{"type": g["type"], "check": g["check"], "pass": g["score"] == 1.0,
                            "why": g["reason"]} for g in r.get("grades", [])],
                "in": m.get("input_tokens", 0), "out": m.get("output_tokens", 0),
                "turns": m.get("turns", 0), "secs": m.get("time", 0),
            })
    pin, pout = PRICES[model]
    tasks_out, n, passed, cost, tcalls, terrs = {}, 0, 0, 0.0, 0, 0
    for t in tasks:
        ts = per_task[t["id"]]
        k = sum(x["passed"] for x in ts)
        tasks_out[t["id"]] = {
            "category": t.get("category", ""), "passes": k, "trials": len(ts),
            "tool_calls": sum(len(x["tools"]) for x in ts), "tool_errors": sum(x["tool_errors"] for x in ts),
            "errors": sum(bool(x["error"]) for x in ts), "trials_detail": ts,
        }
        n += len(ts); passed += k
        cost += sum(x["in"] * pin + x["out"] * pout for x in ts) / 1e6
        tcalls += tasks_out[t["id"]]["tool_calls"]; terrs += tasks_out[t["id"]]["tool_errors"]
    jin = judge.USAGE["input_tokens"] - j0["input_tokens"]
    jout = judge.USAGE["output_tokens"] - j0["output_tokens"]
    rec = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "variant": variant, "levers": VARIANTS[variant]["levers"], "model": model,
        "judge_model": judge.JUDGE_MODEL, "harness": "final-msg-text", "taskset": taskset, "trials": trials,
        "passed": passed, "n": n,
        "pass_all": sum(v["passes"] == v["trials"] for v in tasks_out.values()),
        "pass_any": sum(v["passes"] > 0 for v in tasks_out.values()),
        "num_tasks": len(tasks),
        "tool_calls": tcalls, "tool_errors": terrs,
        "agent_cost": round(cost, 4), "cost_per_trial": round(cost / max(n, 1), 5),
        "judge_cost": round((jin * PRICES[judge.JUDGE_MODEL][0] + jout * PRICES[judge.JUDGE_MODEL][1]) / 1e6, 4),
        "max_tokens_stops": sum(x["stops"].count("max_tokens") for v in tasks_out.values() for x in v["trials_detail"]),
        "seconds": round(time.time() - t0, 1),
        "tasks": tasks_out,
    }
    import fcntl  # several suite processes may append at once (parallel subagents)
    with RUNS.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(rec, default=str) + "\n")
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)
    return rec


def short(name):
    return name.replace("v_all_minus_", "-").replace("v_all_catprompt", "all_catp").replace("v0_baseline", "base")


def print_table(recs):
    names = [short(r["variant"]) + ("" if r["model"] == DEFAULT_MODEL else "@" + r["model"].replace("claude-", ""))
             for r in recs]
    w = max(9, *(len(n) for n in names)) + 1
    tids = list(recs[0]["tasks"])
    rows = [
        ("PASS (task-trials)", lambda r: f"{r['passed']}/{r['n']}"),
        ("  rate", lambda r: f"{100 * r['passed'] / r['n']:.0f}%"),
        (f"pass^k (all trials)", lambda r: f"{r['pass_all']}/{r['num_tasks']}"),
        (f"pass@k (any trial)", lambda r: f"{r['pass_any']}/{r['num_tasks']}"),
        ("tool errors / calls", lambda r: f"{r['tool_errors']}/{r['tool_calls']}"),
        ("max_tokens stops", lambda r: str(r["max_tokens_stops"])),
        ("agent $/trial", lambda r: f"{r['cost_per_trial']:.4f}"),
    ]
    for tid in tids:
        rows.append((f"  {tid}", lambda r, tid=tid: (lambda t: f"{t['passes']}/{t['trials']}" + ("!" if t["errors"] else ""))(r["tasks"][tid])))
    lw = max(len(l) for l, _ in rows) + 2
    bar = "=" * (lw + w * len(names))
    print("\n" + bar)
    print(f"{'metric':<{lw}}" + "".join(f"{n:>{w}}" for n in names))
    print("-" * len(bar))
    for label, get in rows:
        print(f"{label:<{lw}}" + "".join(f"{get(r):>{w}}" for r in recs))
    print(bar)
    print(f"model {recs[0]['model']} unless @noted · judge {recs[0]['judge_model']} · "
          f"taskset {recs[0]['taskset']} · trials {recs[0]['trials']} · '!' = run error (infra, not a grade)")


def print_failures(rec):
    print(f"\n[{rec['variant']}] {rec['passed']}/{rec['n']}  ${rec['agent_cost']:.3f} agent + ${rec['judge_cost']:.3f} judge  "
          f"{rec['seconds']}s  levers: {', '.join(rec['levers']) or '(none)'}")
    for tid, t in rec["tasks"].items():
        if t["passes"] == t["trials"]:
            continue
        print(f"  {tid}: {t['passes']}/{t['trials']}")
        for i, d in enumerate(t["trials_detail"], 1):
            if d["passed"]:
                continue
            if d["error"]:
                print(f"    t{i} ERROR {d['error'].strip().splitlines()[-1][:120]}")
                continue
            calls = " ".join(f"{c['name']}({','.join(str(v) for v in (c['args'] or {}).values())})"
                             f"{'✗' if is_tool_error(c['result']) else ''}" for c in d["tools"]) or "(no tools)"
            fails = "; ".join(f"{g['type']}: {g['why'][:90]}" for g in d["grades"] if not g["pass"])
            print(f"    t{i} {calls[:110]}\n       ✗ {fails[:220]}")


def last_records(names, model, taskset):
    recs = {}
    if RUNS.exists():
        for line in RUNS.read_text().splitlines():
            r = json.loads(line)
            if r["variant"] in names and r["model"] == model and r["taskset"] == taskset:
                recs[r["variant"]] = r
    missing = [n for n in names if n not in recs]
    if missing:
        sys.exit(f"No saved runs for {missing} (model {model}, taskset {taskset}).")
    return [recs[n] for n in names]


def expand(names):
    out = []
    for n in names:
        out += SCREEN if n == "screen" else ABLATION if n == "ablation" else [n]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="variant names, or the groups 'screen' / 'ablation'")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--tasks", choices=["dev", "holdout", "both"], default="dev")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=8, help="parallel tasks within a variant")
    ap.add_argument("--parallel", type=int, default=2, help="variants run at the same time")
    ap.add_argument("--judge-model", default=None, help="judge model (default: judge.JUDGE_MODEL)")
    ap.add_argument("--table", action="store_true", help="reprint the table from runs.jsonl; no API calls")
    ap.add_argument("--quiet", action="store_true", help="skip the per-trial failure detail")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.names:
        for n, v in VARIANTS.items():
            print(f"  {n:<24} {', '.join(v['levers']) or '(none)'}\n  {'':<24} {v['hypothesis']}")
        return
    names = expand(args.names)
    unknown = [n for n in names if n not in VARIANTS]
    if unknown:
        sys.exit(f"Unknown variant(s): {unknown}. Use --list.")
    if args.model not in SWEEP_OK:
        sys.exit(f"Model {args.model!r} not allowed here. Use one of {sorted(SWEEP_OK)} (Haiku/Sonnet only).")

    if args.judge_model:
        if args.judge_model not in SWEEP_OK:
            sys.exit(f"Judge {args.judge_model!r} not allowed (Haiku/Sonnet only).")
        judge.JUDGE_MODEL = args.judge_model
    if args.table:
        print_table(last_records(names, args.model, args.tasks))
        return

    from nbload import connection
    connection()  # connect once, in the main thread, before any worker threads start
    tasks = load_tasks(args.tasks)
    print(f"Model {args.model} · judge {judge.JUDGE_MODEL} · {len(tasks)} {args.tasks} tasks × {args.trials} trials · "
          f"{len(names)} variant(s)", flush=True)
    recs = {}
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(run_variant, n, tasks, args.trials, args.model, args.workers, args.tasks): n for n in names}
        for f in futs:
            n = futs[f]
            recs[n] = f.result()
            r = recs[n]
            print(f"  done {n:<24} {r['passed']}/{r['n']}  ({r['seconds']}s)", flush=True)
    ordered = [recs[n] for n in names]
    if not args.quiet:
        for r in ordered:
            print_failures(r)
    print_table(ordered)
    total = sum(r["agent_cost"] + r["judge_cost"] for r in ordered)
    print(f"spend this run: ${total:.3f}")


if __name__ == "__main__":
    main()
