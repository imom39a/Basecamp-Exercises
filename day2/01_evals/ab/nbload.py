"""Load the agent, graders and runner straight from Building_an_Eval.ipynb.

One source of truth: the notebook. Each call to fresh_namespace() re-executes the notebook's
code cells into a brand-new dict, so variants can't leak into each other.
"""
import contextlib
import io
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# The BASELINE is the notebook as shipped (git HEAD before any fix), frozen here so that editing the
# live notebook can't silently turn v0_baseline into the fixed agent.
NOTEBOOK = HERE / "shipped" / "Building_an_Eval.shipped.ipynb"
LIVE_NOTEBOOK = HERE.parent / "Building_an_Eval.ipynb"
ROOT = next(d for d in [HERE, *HERE.parents] if (d / "basecamp_setup.py").is_file())
sys.path.insert(0, str(ROOT))

# Cells are found by what they contain, not by index, so adding cells to the notebook is safe.
MARKERS = {
    "agent": "def run_agent(",
    "graders": "GRADER_REGISTRY = {",
    "runner": "def run_eval(",
}

_claude = None


def connection():
    global _claude
    if _claude is None:
        from basecamp_setup import connect
        with contextlib.redirect_stdout(io.StringIO()):
            _claude = connect(model="claude-haiku-5-5", fast_model="claude-haiku-5-5", big_model="claude-haiku-5-5")
    return _claude


def _cells(path=None):
    nb = json.loads((path or NOTEBOOK).read_text())
    code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    found = {}
    for key, marker in MARKERS.items():
        hits = [c for c in code if marker in c]
        if len(hits) != 1:
            raise SystemExit(f"Expected exactly one notebook cell containing {marker!r}, found {len(hits)}")
        found[key] = hits[0]
    return found


def fresh_namespace(path=None):
    claude = connection()
    ns = {
        "__name__": "boutique_nb",
        "claude": claude,
        "MODEL": claude.model, "FAST_MODEL": claude.fast_model, "BIG_MODEL": claude.big_model,
    }
    ns["print"] = lambda *a, **k: None  # silence the cells' banners; redirect_stdout isn't thread-safe
    cells = _cells(path)
    for key in ("agent", "graders", "runner"):
        exec(compile(cells[key], f"<notebook:{key}>", "exec"), ns)
    return ns
