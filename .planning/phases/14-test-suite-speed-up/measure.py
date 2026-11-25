#!/usr/bin/env python3
"""Phase 14 measurement runner: serial reference, -n/--dist matrix, quick-run
timing (TEST-04), ten-run equality and half-of-baseline check (TEST-05, TEST-08).

Standard library only. Every run is appended to measurements/results.jsonl and
MEASUREMENTS.md is rewritten from that file, so every number reported for the
phase comes from the records, never from hand counting.

Usage (from the repository root, with the venv's interpreter):

    python .planning/phases/14-test-suite-speed-up/measure.py self-test
    python .planning/phases/14-test-suite-speed-up/measure.py baseline
    python .planning/phases/14-test-suite-speed-up/measure.py serial
    python .planning/phases/14-test-suite-speed-up/measure.py full [--n N --dist D]
    python .planning/phases/14-test-suite-speed-up/measure.py matrix [--settings 6:worksteal,8:loadfile]
    python .planning/phases/14-test-suite-speed-up/measure.py quick [--runs 3]
    python .planning/phases/14-test-suite-speed-up/measure.py tenrun [--runs 10]
    python .planning/phases/14-test-suite-speed-up/measure.py choose [--check-pyproject]
    python .planning/phases/14-test-suite-speed-up/measure.py slow-coverage

Options for every subcommand: --out DIR moves the store and the report into DIR
(smoke tests outside the repo), --note TEXT is stored in each record it appends.
Extra pytest selection goes after "--", for example "-- tests/test_sexpr.py";
it is recorded as `selection` and only records with the same selection are
compared with each other.

Interpreter: MEASURE_PYTHON if set, else the running interpreter, else the
repository's env/ interpreter; the first one that imports pytest and xdist wins.
Long runs belong to the orchestrator (see MEASURE.md), not to an executor.
"""

import argparse
import datetime
import json
import os
import re
import shlex
import signal
import statistics
import subprocess
import sys
import time
import tomllib
from pathlib import Path

PHASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PHASE_DIR.parents[2]
BASELINE = PHASE_DIR / "BASELINE.md"
DEFAULT_STORE = PHASE_DIR / "measurements"
DEFAULT_REPORT = PHASE_DIR / "MEASUREMENTS.md"
RESULTS_NAME = "results.jsonl"

QUICK_BUDGET_S = 600
FULL_BUDGET_S = 3600
SERIAL_BUDGET_S = 5400
COUNT_KEYS = ("passed", "skipped", "failed", "errors", "xfailed", "xpassed")
DEFAULT_MATRIX = (
    (4, "worksteal"),
    (6, "worksteal"),
    (8, "worksteal"),
    (4, "loadfile"),
    (6, "loadfile"),
    (8, "loadfile"),
)
GATE_ARGS = ("-x", "-q", "--tb=short")
LOG_TAIL_LINES = 300

# Record kinds that are verdict summaries rather than pytest runs.
_SUMMARY_KINDS = ("quick-batch", "tenrun", "choose")


# -- Parsing -------------------------------------------------------------------

_SUMMARY_RE = re.compile(
    r"^[=\s]*(?P<body>\d+ [A-Za-z]+(?:, \d+ [A-Za-z]+)*|no tests ran)"
    r"\s+in\s+(?P<sec>\d+(?:\.\d+)?)s(?:\s+\([0-9:]+\))?[=\s]*$"
)
_TOKEN_RE = re.compile(r"(\d+) ([A-Za-z]+)")
_WORD_TO_KEY = {
    "passed": "passed",
    "skipped": "skipped",
    "failed": "failed",
    "error": "errors",
    "errors": "errors",
    "xfailed": "xfailed",
    "xpassed": "xpassed",
    "deselected": "deselected",
    "warning": "warnings",
    "warnings": "warnings",
}
_DURATION_RE = re.compile(r"^\s*([0-9.]+)s\s+(setup|call|teardown)\s+(.+?)\s*$")


def parse_summary(text: str) -> dict | None:
    """Parse pytest's final summary line.

    Returns the six COUNT_KEYS plus `deselected`, `warnings` and `seconds`, or
    None when the text has no summary line. Works with and without the `=` padding.
    """
    found = None
    for line in text.splitlines():
        m = _SUMMARY_RE.match(line.strip())
        if m:
            found = m
    if found is None:
        return None
    result: dict = {k: 0 for k in COUNT_KEYS}
    result["deselected"] = 0
    result["warnings"] = 0
    for num, word in _TOKEN_RE.findall(found.group("body")):
        key = _WORD_TO_KEY.get(word)
        if key is not None:
            result[key] += int(num)
    result["seconds"] = float(found.group("sec"))
    return result


def parse_durations(text: str) -> list[tuple[float, str, str]]:
    """Every pytest durations line as (seconds, phase, nodeid)."""
    out = []
    for line in text.splitlines():
        m = _DURATION_RE.match(line)
        if m:
            out.append((float(m.group(1)), m.group(2), m.group(3)))
    return out


def _addopts_values(tokens: list[str]) -> tuple[int | None, str | None]:
    n = None
    dist = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        value = None
        if tok in ("-n", "--numprocesses") and i + 1 < len(tokens):
            value = tokens[i + 1]
            i += 1
            n = int(value) if value.isdigit() else None
        elif tok.startswith("--numprocesses="):
            value = tok.split("=", 1)[1]
            n = int(value) if value.isdigit() else None
        elif tok.startswith("-n") and tok[2:].isdigit():
            n = int(tok[2:])
        elif tok == "--dist" and i + 1 < len(tokens):
            dist = tokens[i + 1]
            i += 1
        elif tok.startswith("--dist="):
            dist = tok.split("=", 1)[1]
        i += 1
    return n, dist


def parse_addopts() -> tuple[int | None, str | None]:
    """The -n and --dist values in pyproject.toml's pytest addopts."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    addopts = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", "")
    tokens = shlex.split(addopts) if isinstance(addopts, str) else [str(t) for t in addopts]
    return _addopts_values(tokens)


def baseline() -> dict:
    """Parse BASELINE.md: {"counts", "seconds", "durations"}; exits 1 when unusable."""
    if not BASELINE.is_file():
        sys.exit(f"measure.py: {BASELINE} is missing (the orchestrator records it before wave 1)")
    text = BASELINE.read_text(encoding="utf-8", errors="replace")
    summ = parse_summary(text)
    if summ is None:
        sys.exit(f"measure.py: no pytest summary line found in {BASELINE}")
    counts = {k: v for k, v in summ.items() if k != "seconds"}
    return {"counts": counts, "seconds": summ["seconds"], "durations": parse_durations(text)}


def baseline_or_none() -> dict | None:
    try:
        return baseline()
    except SystemExit:
        return None


# -- Running pytest ------------------------------------------------------------

_INTERPRETER: str | None = None


def interpreter() -> str:
    """The interpreter that has pytest and xdist (first working candidate)."""
    global _INTERPRETER
    if _INTERPRETER:
        return _INTERPRETER
    candidates = []
    if os.environ.get("MEASURE_PYTHON"):
        candidates.append(os.environ["MEASURE_PYTHON"])
    candidates.append(sys.executable)
    for rel in ("env/Scripts/python.exe", "env/bin/python"):
        p = REPO_ROOT / rel
        if p.is_file():
            candidates.append(str(p))
    for cand in candidates:
        try:
            r = subprocess.run([cand, "-c", "import pytest, xdist"], capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            _INTERPRETER = cand
            return cand
    sys.exit(
        "measure.py: no interpreter with pytest and pytest-xdist found; "
        "set MEASURE_PYTHON to the venv's python"
    )


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%dT%H%M%S")


def _kill_tree(proc: subprocess.Popen) -> None:
    """Stop the pytest process and all its workers, then reap it."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        pass


def _redact(text: str) -> str:
    """Replace the user's home folder (any slash style, case-insensitive) with ~."""
    home = str(Path.home())
    variants = {home, home.replace("\\", "\\\\"), home.replace("\\", "/")}
    for v in sorted(variants, key=len, reverse=True):
        if v:
            text = re.sub(re.escape(v), lambda _m: "~", text, flags=re.IGNORECASE)
    return text


def _args_n_dist(args: list[str]) -> tuple[int | None, str | None]:
    """-n and --dist from a run's own args, else from pyproject addopts."""
    n, dist = _addopts_values(list(args))
    has_n = any(a in ("-n", "--numprocesses") or a.startswith("--numprocesses=")
                or (a.startswith("-n") and a[2:].isdigit()) for a in args)
    has_dist = any(a == "--dist" or a.startswith("--dist=") for a in args)
    if not has_n or not has_dist:
        a_n, a_dist = parse_addopts()
        if not has_n:
            n = a_n
        if not has_dist:
            dist = a_dist
    if n == 0:
        dist = None
    return n, dist


def report_path(store: Path) -> Path:
    return DEFAULT_REPORT if store == DEFAULT_STORE else store / "MEASUREMENTS.md"


def run_pytest(
    label: str,
    kind: str,
    args: list[str],
    budget_s: float,
    store: Path,
    selection: list[str],
    note: str = "",
) -> dict:
    """Run pytest once under a time budget, store its tail log and a result record."""
    store.mkdir(parents=True, exist_ok=True)
    raw = store / f"{label}.raw"
    cmd = [interpreter(), "-m", "pytest", *args, *selection]
    popen_kw: dict = {}
    if sys.platform == "win32":
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True
    n, dist = _args_n_dist(args)
    started = _now_iso()
    t0 = time.monotonic()
    with open(raw, "wb") as out:
        proc = subprocess.Popen(
            cmd, cwd=REPO_ROOT, stdout=out, stderr=subprocess.STDOUT, **popen_kw
        )
        try:
            code: int | str = proc.wait(timeout=budget_s)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            code = "timeout"
        except BaseException:
            _kill_tree(proc)
            raise
    wall = time.monotonic() - t0
    text = raw.read_bytes().decode("utf-8", errors="replace")
    raw.unlink()
    tail = "\n".join(text.splitlines()[-LOG_TAIL_LINES:]) + "\n"
    (store / f"{label}.log").write_text(_redact(tail), encoding="utf-8")
    summ = parse_summary(text)
    counts = {k: v for k, v in summ.items() if k != "seconds"} if summ else None
    record = {
        "label": label,
        "kind": kind,
        "started": started,
        "args": list(args),
        "selection": list(selection),
        "n": n,
        "dist": dist,
        "exit": code,
        "wall_s": round(wall, 2),
        "pytest_s": summ["seconds"] if summ else None,
        "counts": counts,
        "note": note,
    }
    append_record(store, record)
    short = ""
    if counts:
        short = " ".join(f"{k}={counts[k]}" for k in COUNT_KEYS)
    print(f"[{label}] exit={code} wall={record['wall_s']}s {short}".rstrip())
    return record


def append_record(store: Path, record: dict) -> None:
    """Append one JSON line to results.jsonl and rewrite the report."""
    store.mkdir(parents=True, exist_ok=True)
    with open(store / RESULTS_NAME, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    write_report(store, report_path(store))


def load_results(store: Path) -> list[dict]:
    path = store / RESULTS_NAME
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


# -- Report --------------------------------------------------------------------


def _cell(value) -> str:
    if value is None or value == "":
        return "-"
    return str(value).replace("|", "/")


def _sel(selection: list[str] | None) -> str:
    return " ".join(selection) if selection else ""


def _newest(records: list[dict], kind: str) -> dict | None:
    found = [r for r in records if r.get("kind") == kind]
    return found[-1] if found else None


def _suffix(rec: dict) -> str:
    out = ""
    if rec.get("selection"):
        out += f" [selection: {_sel(rec['selection'])}]"
    if rec.get("note"):
        out += f" [note: {rec['note']}]"
    return out


def build_report(records: list[dict], base: dict | None) -> str:
    """MEASUREMENTS.md text from the result records (pure; no file access)."""
    base_s = base["seconds"] if base else None
    lines = ["# Phase 14 measurements", ""]
    lines.append("Generated by measure.py from measurements/results.jsonl. Do not edit by hand.")
    lines.append("")
    if base:
        c = base["counts"]
        lines.append(
            "Baseline (BASELINE.md, serial, unchanged base commit): "
            f"{c['passed']} passed, {c['failed']} failed, {c['skipped']} skipped, "
            f"{c['errors']} errors in {base_s} s."
        )
    else:
        lines.append("Baseline: BASELINE.md missing.")
    lines += ["", "## Runs", ""]
    lines.append(
        "| label | kind | -n | --dist | exit | wall s | wall / baseline | passed | skipped "
        "| failed | errors | deselected | selection | note |"
    )
    lines.append("|" + "---|" * 14)
    for r in records:
        if r.get("kind") in _SUMMARY_KINDS:
            continue
        counts = r.get("counts") or {}
        ratio = f"{r['wall_s'] / base_s:.2f}" if base_s and r.get("wall_s") is not None else None
        lines.append(
            "| " + " | ".join(
                _cell(v) for v in (
                    r.get("label"), r.get("kind"), r.get("n"), r.get("dist"), r.get("exit"),
                    r.get("wall_s"), ratio, counts.get("passed"), counts.get("skipped"),
                    counts.get("failed"), counts.get("errors"), counts.get("deselected"),
                    _sel(r.get("selection")), r.get("note"),
                )
            ) + " |"
        )

    lines += ["", "## Verdicts", ""]
    quick = _newest(records, "quick-batch")
    if quick is None:
        lines.append("TEST-04: not measured")
    else:
        walls = ", ".join(f"{w} s" for w in quick.get("walls", [])[1:])
        if quick.get("ok"):
            lines.append(f"TEST-04: met (runs after the first, gate command: {walls}; each under {QUICK_BUDGET_S} s with exit 0)" + _suffix(quick))
        else:
            lines.append(f"TEST-04: not met (walls {quick.get('walls')}, exits {quick.get('exits')})" + _suffix(quick))
    ten = _newest(records, "tenrun")
    if ten is None:
        lines.append("TEST-05: not measured")
        lines.append("TEST-08: not measured")
    else:
        bound = ten.get("baseline_s")
        bound_txt = f"{0.5 * bound:.2f}" if bound else "?"
        if ten.get("ok") and ten.get("half_ok"):
            lines.append(f"TEST-05: met (slowest {ten.get('max_wall')} s <= {bound_txt} s)" + _suffix(ten))
        elif ten.get("ok"):
            lines.append(f"TEST-05: not met (slowest {ten.get('max_wall')} s > {bound_txt} s)" + _suffix(ten))
        else:
            lines.append(f"TEST-05: not met (the ten-run did not complete; slowest {ten.get('max_wall')} s, bound {bound_txt} s)" + _suffix(ten))
        if ten.get("ok"):
            lines.append(f"TEST-08: met ({ten.get('runs_done')} consecutive runs equal to the serial reference)" + _suffix(ten))
        else:
            lines.append(f"TEST-08: not met ({ten.get('reason', 'unknown')})" + _suffix(ten))
    choice = _newest(records, "choose")
    if choice is None:
        lines.append("Chosen setting: not measured")
    else:
        verdict = "met" if choice.get("half_ok") else "missed"
        lines.append(
            f"Chosen setting: -n {choice.get('n')} --dist {choice.get('dist')} "
            f"(matrix estimate against half the baseline: {verdict}; "
            f"{choice.get('wall_s')} s vs {choice.get('bound_s')} s)" + _suffix(choice)
        )

    lines += ["", "## Before / after", ""]
    lines.append(f"- BASELINE.md serial wall time: {base_s} s" if base_s else "- BASELINE.md serial wall time: not measured")
    serial = _newest(records, "serial")
    lines.append(
        f"- Latest serial reference (this checkout): {serial['wall_s']} s" + _suffix(serial)
        if serial else "- Latest serial reference (this checkout): not measured"
    )
    if quick:
        lines.append(f"- Quick gate command, runs after the first: {', '.join(str(w) + ' s' for w in quick.get('walls', [])[1:])}" + _suffix(quick))
    else:
        lines.append("- Quick gate command, runs after the first: not measured")
    if ten and ten.get("walls"):
        w = ten["walls"]
        parts = []
        for name, val in (("min", min(w)), ("median", statistics.median(w)), ("max", max(w))):
            ratio = f" ({val / base_s:.2f} of baseline)" if base_s else ""
            parts.append(f"{name} {val:.2f} s{ratio}")
        lines.append(f"- Latest ten-run walls ({len(w)} runs): " + ", ".join(parts))
    else:
        lines.append("- Latest ten-run walls: not measured")
    lines.append("")
    return "\n".join(lines)


def write_report(store: Path, report: Path) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(build_report(load_results(store), baseline_or_none()), encoding="utf-8")


# -- Commands ------------------------------------------------------------------


def _rc(records: list[dict]) -> int:
    """1 when a run timed out or pytest exited with 2 or more, else 0."""
    for r in records:
        code = r["exit"]
        if code == "timeout" or (isinstance(code, int) and code >= 2):
            return 1
    return 0


def parse_settings(text: str) -> list[tuple[int, str]]:
    out = []
    for part in text.split(","):
        n, _, dist = part.strip().partition(":")
        out.append((int(n), dist))
    return out


def cmd_baseline(args, selection) -> int:
    b = baseline()
    c = b["counts"]
    print(
        f"baseline counts: {c['passed']} passed, {c['failed']} failed, {c['skipped']} skipped, "
        f"{c['errors']} errors, {c['xfailed']} xfailed, {c['xpassed']} xpassed"
    )
    print(f"baseline wall seconds: {b['seconds']}")
    print(f"baseline durations lines: {len(b['durations'])}")
    return 0


def cmd_serial(args, selection) -> int:
    rec = run_pytest(
        f"serial-{_stamp()}", "serial",
        ["--full", "-n", "0", "-q", "-p", "no:cacheprovider", "--durations=50"],
        SERIAL_BUDGET_S, args.store, selection, args.note,
    )
    base = baseline_or_none()
    if base and rec["counts"]:
        delta = {k: rec["counts"][k] - base["counts"][k] for k in COUNT_KEYS}
        print("count delta against BASELINE.md (informational): "
              + ", ".join(f"{k} {v:+d}" for k, v in delta.items()))
    return _rc([rec])


def cmd_full(args, selection) -> int:
    run_args = ["--full", "-q", "-p", "no:cacheprovider", "--durations=20"]
    if args.n is not None:
        run_args += ["-n", str(args.n)]
    if args.dist:
        run_args += ["--dist", args.dist]
    rec = run_pytest(f"full-{_stamp()}", "full", run_args, FULL_BUDGET_S, args.store, selection, args.note)
    return _rc([rec])


def cmd_matrix(args, selection) -> int:
    settings = parse_settings(args.settings) if args.settings else list(DEFAULT_MATRIX)
    records = []
    for n, dist in settings:
        records.append(run_pytest(
            f"matrix-n{n}-{dist}-{_stamp()}", "matrix",
            ["--full", "-n", str(n), "--dist", dist, "-q", "-p", "no:cacheprovider", "--durations=20"],
            FULL_BUDGET_S, args.store, selection, args.note,
        ))
    return _rc(records)


def cmd_quick(args, selection) -> int:
    records = []
    for i in range(1, args.runs + 1):
        records.append(run_pytest(
            f"quick-{_stamp()}-{i}", "quick", list(GATE_ARGS),
            QUICK_BUDGET_S, args.store, selection, args.note,
        ))
    judged = records[1:]
    ok = bool(judged) and all(r["exit"] == 0 and r["wall_s"] < QUICK_BUDGET_S for r in judged)
    batch = {
        "label": f"quick-batch-{_stamp()}", "kind": "quick-batch", "started": _now_iso(),
        "selection": list(selection), "ok": ok,
        "walls": [r["wall_s"] for r in records], "exits": [r["exit"] for r in records],
        "note": args.note,
    }
    append_record(args.store, batch)
    print(f"TEST-04: {'met' if ok else 'not met'} (walls {batch['walls']}, exits {batch['exits']})")
    return 0 if ok else 1


def same_counts(a: dict | None, b: dict | None) -> bool:
    """True when both count dicts exist and agree on all six COUNT_KEYS."""
    if not a or not b:
        return False
    return all(a.get(k) == b.get(k) for k in COUNT_KEYS)


def latest(records: list[dict], kind: str, selection: list[str]) -> dict | None:
    """The newest record of that kind with the same selection list."""
    found = [r for r in records if r.get("kind") == kind and r.get("selection", []) == list(selection)]
    return found[-1] if found else None


def half_bound(baseline_s: float) -> float:
    """The TEST-05 bound: half the BASELINE.md serial wall time."""
    return 0.5 * baseline_s


def _newest_matrix(records: list[dict], selection: list[str]) -> dict[tuple[int, str], dict]:
    """Newest matrix record per (n, dist): a re-measure supersedes the older run."""
    newest: dict[tuple[int, str], dict] = {}
    for r in records:
        if r.get("kind") == "matrix" and r.get("selection", []) == list(selection):
            newest[(r.get("n"), r.get("dist"))] = r
    return newest


def _newest_tenrun(records: list[dict], selection: list[str]) -> dict[tuple[int, str], dict]:
    """Newest tenrun record per (n, dist): a passing re-measure supersedes an older failed run."""
    newest: dict[tuple[int, str], dict] = {}
    for r in records:
        if r.get("kind") == "tenrun" and r.get("selection", []) == list(selection):
            newest[(r.get("n"), r.get("dist"))] = r
    return newest


def choose_setting(records: list[dict], selection: list[str]) -> tuple[int, str] | None:
    """The fastest matrix setting that matches the serial reference (pure).

    Reference: the latest serial record with this selection. Per (n, dist) only
    the newest matrix record counts. Candidates exited 0 with the reference's
    counts; settings whose newest tenrun record failed are dropped (a later passing
    tenrun reinstates them); smallest wall_s wins, ties to the smaller n.
    """
    ref = latest(records, "serial", selection)
    if ref is None:
        return None
    failed = {key for key, r in _newest_tenrun(records, selection).items() if not r.get("ok")}
    best = None
    for key, r in _newest_matrix(records, selection).items():
        if r.get("exit") != 0 or not same_counts(r.get("counts"), ref.get("counts")):
            continue
        if key in failed:
            continue
        rank = (r["wall_s"], key[0])
        if best is None or rank < best[0]:
            best = (rank, key)
    return best[1] if best else None


def cmd_tenrun(args, selection) -> int:
    records = load_results(args.store)
    ref = latest(records, "serial", selection)
    if ref is None:
        print("measure.py: no serial reference with this selection; run measure.py serial first")
        return 1
    base = baseline()
    n, dist = parse_addopts()
    bound = half_bound(base["seconds"])
    stamp = _stamp()
    walls: list[float] = []
    mismatch_at = None
    reason = ""
    for i in range(1, args.runs + 1):
        rec = run_pytest(
            f"tenrun-{stamp}-{i:02d}", "tenrun-run",
            ["--full", "-q", "-p", "no:cacheprovider"],
            FULL_BUDGET_S, args.store, selection, args.note,
        )
        walls.append(rec["wall_s"])
        if rec["exit"] != 0:
            mismatch_at, reason = i, f"run {i} exited {rec['exit']}"
            break
        if not same_counts(rec["counts"], ref["counts"]):
            mismatch_at, reason = i, f"run {i} counts {rec['counts']} differ from the serial reference {ref['counts']}"
            break
    ok = mismatch_at is None and len(walls) == args.runs
    max_wall = max(walls) if walls else None
    half_ok = max_wall is not None and max_wall <= bound
    record = {
        "label": f"tenrun-{stamp}", "kind": "tenrun", "started": _now_iso(),
        "selection": list(selection), "n": n, "dist": dist, "ok": ok,
        "runs_done": len(walls), "mismatch_at": mismatch_at, "reason": reason,
        "walls": walls, "max_wall": max_wall, "baseline_s": base["seconds"],
        "half_ok": half_ok, "note": args.note,
    }
    append_record(args.store, record)
    print("TEST-08: met" if ok else f"TEST-08: not met ({reason or 'incomplete'})")
    if half_ok:
        print(f"TEST-05: met (slowest {max_wall} s <= {bound:.2f} s)")
    else:
        print(f"TEST-05: not met (slowest {max_wall} s > {bound:.2f} s): see MEASURE.md step 6")
    return 0 if ok and half_ok else 1


def cmd_choose(args, selection) -> int:
    records = load_results(args.store)
    pick = choose_setting(records, selection)
    if pick is None:
        if latest(records, "serial", selection) is None:
            print("measure.py: no serial reference with this selection; run measure.py serial first")
        elif not _newest_matrix(records, selection):
            print("measure.py: no matrix records with this selection; run measure.py matrix first")
        else:
            print("measure.py: no matrix setting exited 0 with the serial reference's counts "
                  "and without a failed ten-run record")
        return 1
    n, dist = pick
    wall = _newest_matrix(records, selection)[pick]["wall_s"]
    bound = half_bound(baseline()["seconds"])
    half_ok = wall <= bound
    print(f"-n {n} --dist {dist}")
    if half_ok:
        print(f"half-of-baseline: met ({wall} s <= {bound:.2f} s)")
    else:
        print(f"half-of-baseline: missed ({wall} s > {bound:.2f} s): see MEASURE.md step 6")
    append_record(args.store, {
        "label": f"choose-{_stamp()}", "kind": "choose", "started": _now_iso(),
        "selection": list(selection), "n": n, "dist": dist, "wall_s": wall,
        "bound_s": round(bound, 2), "half_ok": half_ok, "note": args.note,
    })
    if args.check_pyproject:
        have = parse_addopts()
        if have != (n, dist):
            print(f"pyproject addopts hold -n {have[0]} --dist {have[1]}, not the chosen setting")
            return 1
        print("pyproject addopts hold the chosen setting")
    return 0


_NODE_RE = re.compile(r"^[\w./\\-]+\.py::\S")


def _collect_ids(extra: list[str]) -> set[str] | None:
    cmd = [interpreter(), "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
           "-o", "addopts=--strict-markers", *extra]
    r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, timeout=1200)
    text = r.stdout.decode("utf-8", errors="replace")
    if r.returncode not in (0, 5):
        print(text[-2000:])
        return None
    return {ln.strip().replace("\\", "/") for ln in text.splitlines() if _NODE_RE.match(ln.strip())}


def cmd_slow_coverage(args, selection) -> int:
    base = baseline()
    ids = sorted({nodeid for _s, ph, nodeid in base["durations"] if ph in ("setup", "call")})
    collected = _collect_ids([])
    slow = _collect_ids(["-m", "slow"])
    if collected is None or slow is None:
        print("measure.py: collection failed")
        return 2
    covered = [i for i in ids if i in collected and i in slow]
    not_slow = [i for i in ids if i in collected and i not in slow]
    missing = [i for i in ids if i not in collected]
    print(f"baseline tests: {len(ids)}")
    for name, items in (("covered (collected and slow)", covered),
                        ("not slow (collected, not marked slow)", not_slow),
                        ("missing (not collected here; a warning only)", missing)):
        print(f"{name}: {len(items)}")
        for i in items:
            print(f"  {i}")
    return 1 if not_slow else 0


COMMANDS = {
    "baseline": cmd_baseline,
    "serial": cmd_serial,
    "full": cmd_full,
    "matrix": cmd_matrix,
    "quick": cmd_quick,
    "tenrun": cmd_tenrun,
    "choose": cmd_choose,
    "slow-coverage": cmd_slow_coverage,
}


# -- Self-test -----------------------------------------------------------------


def self_test() -> int:
    s = parse_summary("11660 passed, 8 skipped in 1754.32s (0:29:14)")
    assert s and s["passed"] == 11660 and s["skipped"] == 8 and s["failed"] == 0, s
    assert s["seconds"] == 1754.32, s
    s = parse_summary("==== 1 failed, 11659 passed, 8 skipped, 3 warnings in 900.10s (0:15:00) ====")
    assert s and s["failed"] == 1 and s["passed"] == 11659 and s["warnings"] == 3, s
    assert s["seconds"] == 900.10, s
    s = parse_summary("3 passed, 1 error in 2.00s")
    assert s and s["passed"] == 3 and s["errors"] == 1, s
    s = parse_summary("no tests ran in 0.50s")
    assert s and all(s[k] == 0 for k in COUNT_KEYS) and s["seconds"] == 0.50, s
    s = parse_summary("3400 passed, 4 skipped, 8264 deselected in 250.00s (0:04:10)")
    assert s and s["passed"] == 3400 and s["deselected"] == 8264, s
    s = parse_summary("1 failed, 11662 passed, 5 skipped, 4 warnings in 1563.92s (0:26:03)")
    assert s and s["failed"] == 1 and s["seconds"] == 1563.92, s
    assert parse_summary("FAILED tests/x.py::t - assert 3 passed in 2s") is None
    assert parse_summary("nothing here") is None
    # the last matching line wins
    s = parse_summary("1 passed in 1.00s\nlater noise\n2 passed in 2.00s")
    assert s and s["passed"] == 2, s

    d = parse_durations(
        "45.89s call     tests/test_roundtrip_corpus.py::test_wurth_corpus_parse_budget\n"
        "7.97s call     tests/test_roundtrip_corpus.py::test_roundtrip_wurth_file"
        "[wurth/Connector_Wurth_WR-TBL.kicad_sym]\n"
        "2.10s setup    tests/test_commit_step.py::test_x[a b]\n"
        "=== slowest 50 durations ===\n"
    )
    assert len(d) == 3, d
    assert d[0] == (45.89, "call", "tests/test_roundtrip_corpus.py::test_wurth_corpus_parse_budget"), d
    assert d[1][2].endswith("[wurth/Connector_Wurth_WR-TBL.kicad_sym]"), d
    assert d[2] == (2.10, "setup", "tests/test_commit_step.py::test_x[a b]"), d

    assert _addopts_values(shlex.split("-ra --strict-markers -n 6 --dist worksteal -m 'not slow'")) == (6, "worksteal")
    assert _addopts_values(["-n4", "--dist=loadfile"]) == (4, "loadfile")
    assert _addopts_values(["-ra"]) == (None, None)
    assert parse_settings("6:worksteal,8:loadfile") == [(6, "worksteal"), (8, "loadfile")]
    assert "~" in _redact(str(Path.home()) + "\\x") and str(Path.home()) not in _redact(str(Path.home()))
    _self_test_choose()
    print("self-test: ok")
    return 0


def _self_test_choose() -> None:
    ref_counts = {"passed": 10, "skipped": 1, "failed": 0, "errors": 0, "xfailed": 0, "xpassed": 0}
    other = dict(ref_counts, passed=9)
    sel: list[str] = []

    def rec(kind, n=None, dist=None, wall=1.0, counts=None, exit_code=0, **extra):
        r = {"kind": kind, "selection": sel, "n": n, "dist": dist, "wall_s": wall,
             "counts": counts if counts is not None else ref_counts, "exit": exit_code, "note": ""}
        r.update(extra)
        return r

    serial = rec("serial", wall=100.0)
    assert same_counts(ref_counts, dict(ref_counts)) and not same_counts(ref_counts, other)
    assert not same_counts(None, ref_counts)
    assert half_bound(1754.32) == 877.16, half_bound(1754.32)
    # two matrix records with equal counts: the faster one
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 30.0)]
    assert choose_setting(recs, sel) == (6, "worksteal")
    # a record with other counts is ignored; a non-zero exit is ignored
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 10.0, counts=other),
            rec("matrix", 8, "worksteal", 5.0, exit_code=1)]
    assert choose_setting(recs, sel) == (4, "worksteal")
    # a setting with a failed tenrun record is dropped
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 30.0),
            rec("tenrun", 6, "worksteal", ok=False, half_ok=False)]
    assert choose_setting(recs, sel) == (4, "worksteal")
    # a failed tenrun followed by a passing tenrun of the same setting: the newer one wins, the setting is kept
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 30.0),
            rec("tenrun", 6, "worksteal", ok=False, half_ok=False),
            rec("tenrun", 6, "worksteal", ok=True, half_ok=True)]
    assert choose_setting(recs, sel) == (6, "worksteal")
    # a passing tenrun followed by a failed one drops it again
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 30.0),
            rec("tenrun", 6, "worksteal", ok=True, half_ok=True),
            rec("tenrun", 6, "worksteal", ok=False, half_ok=False)]
    assert choose_setting(recs, sel) == (4, "worksteal")
    # a failed tenrun of another setting does not touch this one
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 30.0),
            rec("tenrun", 4, "worksteal", ok=False, half_ok=False)]
    assert choose_setting(recs, sel) == (6, "worksteal")
    # a setting whose tenrun has ok true and half_ok false is kept
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 30.0),
            rec("tenrun", 6, "worksteal", ok=True, half_ok=False)]
    assert choose_setting(recs, sel) == (6, "worksteal")
    # a newer matrix record of the same setting replaces the older one
    recs = [serial, rec("matrix", 4, "worksteal", 40.0), rec("matrix", 6, "worksteal", 30.0),
            rec("matrix", 6, "worksteal", 50.0)]
    assert choose_setting(recs, sel) == (4, "worksteal")
    # ties go to the smaller n
    recs = [serial, rec("matrix", 8, "loadfile", 30.0), rec("matrix", 4, "worksteal", 30.0)]
    assert choose_setting(recs, sel) == (4, "worksteal")
    # no serial record gives None; another selection's serial does not count
    assert choose_setting([rec("matrix", 4, "worksteal", 40.0)], sel) is None
    assert choose_setting([dict(serial, selection=["x.py"]), rec("matrix", 4, "worksteal", 40.0)], sel) is None

    # verdict lines come only from the records
    base = {"counts": dict(ref_counts), "seconds": 1000.0, "durations": []}
    ten_ok = rec("tenrun", 6, "worksteal", ok=True, half_ok=True, runs_done=10, walls=[400.0] * 10,
                 max_wall=400.0, baseline_s=1000.0)
    text = build_report([serial, ten_ok], base)
    assert "TEST-05: met (slowest 400.0 s <= 500.00 s)" in text, text
    assert "TEST-08: met" in text and "TEST-04: not measured" in text, text
    ten_slow = dict(ten_ok, half_ok=False, max_wall=600.0, walls=[600.0] * 10)
    text = build_report([serial, ten_slow], base)
    assert "TEST-05: not met (slowest 600.0 s > 500.00 s)" in text and "TEST-08: met" in text, text
    ten_bad = dict(ten_ok, ok=False, reason="run 3 exited 1")
    text = build_report([serial, ten_bad], base)
    assert "TEST-05: not met" in text and "TEST-08: not met (run 3 exited 1)" in text, text
    choice = rec("choose", 6, "worksteal", wall_s=600.0, bound_s=500.0, half_ok=False)
    assert "(matrix estimate against half the baseline: missed;" in build_report([serial, choice], base)
    assert "TEST-05: not measured" in build_report([], None)


# -- Entry point ---------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", help="store and report folder (default: the phase folder)")
    common.add_argument("--note", default="", help="text stored in each record")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test", parents=[common])
    sub.add_parser("baseline", parents=[common])
    sub.add_parser("serial", parents=[common])
    p = sub.add_parser("full", parents=[common])
    p.add_argument("--n", type=int)
    p.add_argument("--dist")
    p = sub.add_parser("matrix", parents=[common])
    p.add_argument("--settings", help="for example 6:worksteal,8:loadfile")
    p = sub.add_parser("quick", parents=[common])
    p.add_argument("--runs", type=int, default=3)
    p = sub.add_parser("tenrun", parents=[common])
    p.add_argument("--runs", type=int, default=10)
    p = sub.add_parser("choose", parents=[common])
    p.add_argument("--check-pyproject", action="store_true")
    sub.add_parser("slow-coverage", parents=[common])
    return parser


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    selection: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        selection = argv[i + 1:]
        argv = argv[:i]
    args = build_parser().parse_args(argv)
    args.store = Path(args.out).resolve() if args.out else DEFAULT_STORE
    if args.command == "self-test":
        sys.exit(self_test())
    sys.exit(COMMANDS[args.command](args, selection))


if __name__ == "__main__":
    main()
