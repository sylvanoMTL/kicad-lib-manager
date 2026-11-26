#!/usr/bin/env python3
"""Resolved-URI proof that KiCad keeps working across the repo split (Phase 16, D-22).

Reads KiCad's global sym-lib-table and fp-lib-table (and kicad_common.json environment.vars),
expands every ${VAR} in every library URI, records whether the resolved path exists, and writes
a JSON snapshot in which the library root is the placeholder <LIB>. Taken before and after the
cutover, two snapshots compare identical only when no entry changed and none is missing.
An entry KiCad has disabled (`(disabled)`) is never loaded, so a gone file behind it is listed
as a note and not counted as missing; a change of the disabled flag is still a difference.

Variable precedence (lowest to highest): the process environment, environment.vars of
kicad_common.json, then --var. KiCad may prefer a variable set in the operating system over the
config file, which is the reverse of the first two steps, so take both snapshots of a proof from the
same shell, or pass --no-env to ignore the process environment. A snapshot holds every resolved path
that is not under the library root as written (an install or user folder, for instance): --redact-home
replaces the user's home folder in it with <HOME> (both snapshots of a proof must use the same flag).

Nothing here writes KiCad's folder: the tables are opened read-only and the one output file is
the --out path. The script is stdlib only and never imports the app it is proving unchanged.

Usage:
    python scripts/split/uri_diff.py vars [--config-dir DIR]
    python scripts/split/uri_diff.py snapshot --tables-dir DIR [--config-dir DIR]
        [--var NAME=VALUE ...] [--lib-root DIR] [--no-env] [--redact-home] --out FILE
    python scripts/split/uri_diff.py compare BEFORE AFTER

Exit codes: 0 success, 1 compare found a difference or a missing entry, 2 unusable input.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LIB = "<LIB>"
TABLES = ("sym-lib-table", "fp-lib-table")
VAR_NAMES = ("KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR")
# the row fields compare looks at (name and table are the key)
_COMPARED = ("type", "uri", "resolved", "expanded", "exists", "disabled")

_VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+)*")
_VAR_RE = re.compile(r"\$\{([^}]*)\}|\$\(([^)]*)\)")
_ESCAPES = {"n": "\n", "r": "\r", "t": "\t"}


@dataclass(frozen=True)
class Entry:
    table: str
    name: str
    type: str
    uri: str
    disabled: bool = False


# -- parsing ------------------------------------------------------------------------------------


def _tokens(text: str):
    """Yield (kind, value): kind is "(", ")", "str" (a quoted string, unescaped) or "atom"."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            yield c, c
            i += 1
        elif c == '"':
            i += 1
            chars: list[str] = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    i += 1
                    chars.append(_ESCAPES.get(text[i], text[i]))
                else:
                    chars.append(text[i])
                i += 1
            i += 1  # the closing quote
            yield "str", "".join(chars)
        else:
            start = i
            while i < n and text[i] not in ' \t\r\n()"':
                i += 1
            yield "atom", text[start:i]


def _parse_sexpr(text: str) -> list:
    """Nested lists whose leaves are strings; an unbalanced tail is closed rather than refused."""
    root: list = []
    stack = [root]
    for kind, value in _tokens(text):
        if kind == "(":
            child: list = []
            stack[-1].append(child)
            stack.append(child)
        elif kind == ")":
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].append(value)
    return root


def _lib_lists(node: list):
    for child in node:
        if isinstance(child, list):
            if child and child[0] == "lib":
                yield child
            else:
                yield from _lib_lists(child)


def parse_table(text: str, table: str) -> list[Entry]:
    """Every (lib (name ...)(type ...)(uri ...)) entry of a lib table, in file order.

    Fields may come in any order; a missing field is "". Quoted strings are unescaped, so a
    name holding \\" or a URI holding \\\\ reads back as KiCad meant it.
    """
    entries = []
    for lib in _lib_lists(_parse_sexpr(text)):
        fields = {"name": "", "type": "", "uri": ""}
        disabled = False
        for child in lib[1:]:
            if isinstance(child, list) and len(child) >= 2 and child[0] in fields and isinstance(child[1], str):
                fields[child[0]] = child[1]
            elif isinstance(child, list) and child and child[0] == "disabled":
                disabled = True
        entries.append(Entry(table, fields["name"], fields["type"], fields["uri"], disabled))
    return entries


# -- KiCad's configuration ----------------------------------------------------------------------


def _config_base() -> Path | None:
    """The folder that holds KiCad's version folders on this platform."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) / "kicad" if appdata else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / "kicad"
    return Path.home() / ".config" / "kicad"


def find_config_dir() -> Path | None:
    """The newest numeric version folder (such as 10.0) under KiCad's config folder, or None."""
    base = _config_base()
    if base is None:
        return None
    try:
        found = [
            (tuple(int(part) for part in d.name.split(".")), d.name, d)
            for d in base.iterdir()
            if _VERSION_RE.fullmatch(d.name) and d.is_dir()
        ]
    except OSError:
        return None
    if not found:
        return None
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return found[0][2]


def read_vars(config_dir: Path) -> dict[str, str]:
    """environment.vars of kicad_common.json; a null, missing or unreadable file gives {}."""
    try:
        data = json.loads((Path(config_dir) / "kicad_common.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    environment = data.get("environment") if isinstance(data, dict) else None
    found = environment.get("vars") if isinstance(environment, dict) else None
    if not isinstance(found, dict):
        return {}
    return {str(key): value for key, value in found.items() if isinstance(value, str)}


# -- resolving ----------------------------------------------------------------------------------


def expand(uri: str, variables: dict[str, str]) -> tuple[str, bool]:
    """Replace ${NAME} and $(NAME) from variables; True when no variable is left unresolved."""
    unresolved = False

    def swap(match: re.Match) -> str:
        nonlocal unresolved
        name = match.group(1) if match.group(1) is not None else match.group(2)
        if name in variables:
            return variables[name]
        unresolved = True
        return match.group(0)

    return _VAR_RE.sub(swap, uri), not unresolved


def _slashes(path: str) -> str:
    return path.replace("\\", "/")


def normalise(path: str, root: str | None) -> str:
    """Forward slashes, with the library root replaced by <LIB> on a whole path segment only.

    Case is ignored on Windows. With root /x/Libs, /x/Libs/a becomes <LIB>/a and /x/Libs-old/a is
    left as written.
    """
    text = _slashes(path)
    if not root:
        return text
    base = _slashes(root).rstrip("/")
    if not base:
        return text
    fold = str.lower if sys.platform == "win32" else str
    if fold(text) == fold(base):
        return LIB
    if fold(text).startswith(fold(base) + "/"):
        return LIB + text[len(base):]
    return text


def _exists(resolved: str) -> bool:
    try:
        return Path(resolved).exists()
    except (OSError, ValueError):
        return False


def snapshot(tables_dir: Path, *, variables: dict[str, str], lib_root: str | Path | None) -> dict:
    """The resolved-URI snapshot of the tables found in tables_dir (read only).

    Keys: lib_root (<LIB> or None), vars (KICAD_LIB_GITHUB and CUSTOM_3DMODEL_DIR, normalised),
    entries (sorted by table, name; table, name, type, uri, resolved, expanded, exists, disabled),
    duplicates, missing and disabled_missing. An entry is missing when its URI expanded fully, the
    path does not exist and KiCad has not disabled it; a disabled one goes to disabled_missing.
    """
    root = str(lib_root) if lib_root else None
    entries: list[Entry] = []
    for table in TABLES:
        try:
            text = (Path(tables_dir) / table).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        entries.extend(parse_table(text, table))
    rows = []
    for entry in entries:
        resolved, expanded = expand(entry.uri, variables)
        rows.append(
            {
                "table": entry.table,
                "name": entry.name,
                "type": entry.type,
                "uri": normalise(entry.uri, root),
                "resolved": normalise(resolved, root),
                "expanded": expanded,
                "exists": expanded and _exists(resolved),
                "disabled": entry.disabled,
            }
        )
    rows.sort(key=lambda row: (row["table"], row["name"], row["uri"]))
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        counts[(row["table"], row["name"])] = counts.get((row["table"], row["name"]), 0) + 1
    return {
        "lib_root": LIB if root else None,
        "vars": {name: normalise(variables[name], root) if name in variables else None for name in VAR_NAMES},
        "entries": rows,
        "duplicates": [{"table": t, "name": n, "count": c} for (t, n), c in counts.items() if c > 1],
        "missing": [
            {"table": row["table"], "name": row["name"], "resolved": row["resolved"]} for row in _missing_rows(rows)
        ],
        "disabled_missing": [
            {"table": row["table"], "name": row["name"], "resolved": row["resolved"]}
            for row in _missing_rows(rows, disabled=True)
        ],
    }


# -- comparing ----------------------------------------------------------------------------------


def _groups(snap: dict) -> dict[tuple[str, str], list[dict]]:
    found: dict[tuple[str, str], list[dict]] = {}
    for row in snap.get("entries", []):
        found.setdefault((row["table"], row["name"]), []).append(row)
    return found


def _missing_rows(rows: list[dict], *, disabled: bool = False) -> list[dict]:
    """Rows whose URI expanded fully and whose path is gone: the enabled ones, or with disabled=True
    the ones KiCad has disabled (never loaded, so a note only)."""
    return [
        row
        for row in rows
        if row.get("expanded") and not row.get("exists") and bool(row.get("disabled", False)) == disabled
    ]


def compare(a: dict, b: dict) -> list[str]:
    """Differences between two snapshots; an empty list means identical lists and nothing missing."""
    lines: list[str] = []
    groups_a, groups_b = _groups(a), _groups(b)
    for key in sorted(set(groups_a) | set(groups_b)):
        table, name = key
        rows_a, rows_b = groups_a.get(key, []), groups_b.get(key, [])
        for row in rows_a[len(rows_b):]:
            lines.append(f"removed: {table} {name} ({row['uri']})")
        for row in rows_b[len(rows_a):]:
            lines.append(f"added: {table} {name} ({row['uri']})")
        for old, new in zip(rows_a, rows_b):
            for field in _COMPARED:
                # snapshots written before the disabled field existed read as enabled
                default = False if field == "disabled" else None
                if old.get(field, default) != new.get(field, default):
                    lines.append(
                        f"changed: {table} {name}: {field} {old.get(field, default)!r} -> {new.get(field, default)!r}"
                    )
    for label, snap in (("before", a), ("after", b)):
        for row in _missing_rows(snap.get("entries", [])):
            lines.append(f"missing ({label}): {row['table']} {row['name']} -> {row['resolved']}")
    return lines


def _disabled_notes(a: dict, b: dict) -> list[str]:
    """One note line per disabled entry whose file is gone; never counted as a difference."""
    return [
        f"note: disabled, file not found ({label}): {row['table']} {row['name']} -> {row['resolved']}"
        for label, snap in (("before", a), ("after", b))
        for row in _missing_rows(snap.get("entries", []), disabled=True)
    ]


def _var_notes(a: dict, b: dict) -> list[str]:
    notes = []
    for name in VAR_NAMES:
        old, new = a.get("vars", {}).get(name), b.get("vars", {}).get(name)
        if old != new:
            notes.append(f"note: {name} was {old!r} and is {new!r}")
    return notes


# -- command line -------------------------------------------------------------------------------


def _read_snapshot(path: str) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"uri_diff: cannot read the snapshot {path}: {error}")
        return None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        print(f"uri_diff: {path} is not a uri_diff snapshot")
        return None
    return data


def _cmd_vars(args: argparse.Namespace) -> int:
    config_dir = Path(args.config_dir) if args.config_dir else find_config_dir()
    if config_dir is None:
        print("uri_diff: no KiCad configuration folder found; pass --config-dir")
        return 2
    found = read_vars(config_dir)
    print(f"uri_diff: kicad_common.json in {config_dir}")
    for name in VAR_NAMES:
        print(f"{name}: {found.get(name, 'not set')}")
    return 0


def redact_home(value, home: str):
    """The value with the folder `home` replaced by <HOME> in every string (lists and dicts are walked).

    Matches on a whole path segment, forward slashes, ignoring case on Windows.
    """
    if isinstance(value, dict):
        return {key: redact_home(item, home) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_home(item, home) for item in value]
    if not isinstance(value, str) or not home:
        return value
    base = _slashes(home).rstrip("/")
    if not base:
        return value
    flags = re.IGNORECASE if sys.platform == "win32" else 0
    return re.sub("(?<![^/])" + re.escape(base) + "(?=/|$)", "<HOME>", value, flags=flags)


def _parse_vars(items: list[str]) -> dict[str, str] | None:
    found = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name:
            print(f"uri_diff: --var wants NAME=VALUE, got {item!r}")
            return None
        found[name] = value
    return found


def _cmd_snapshot(args: argparse.Namespace) -> int:
    tables_dir = Path(args.tables_dir)
    config_dir = Path(args.config_dir) if args.config_dir else tables_dir
    flag_vars = _parse_vars(args.var)
    if flag_vars is None:
        return 2
    # lowest to highest priority: the process environment (unless --no-env), environment.vars, then --var
    variables = {**({} if args.no_env else os.environ), **read_vars(config_dir), **flag_vars}
    lib_root = args.lib_root or variables.get("KICAD_LIB_GITHUB")
    out = Path(args.out)
    protected = {(tables_dir / name).resolve() for name in TABLES} | {(config_dir / "kicad_common.json").resolve()}
    if out.resolve() in protected:
        print(f"uri_diff: --out would overwrite {out}, one of the files this command only reads")
        return 2
    snap = snapshot(tables_dir, variables=variables, lib_root=lib_root)
    if not snap["entries"]:
        print(f"uri_diff: no library entry in sym-lib-table or fp-lib-table under {tables_dir}")
        return 2
    if args.redact_home:
        snap = redact_home(snap, str(Path.home()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    for item in snap["duplicates"]:
        print(f"uri_diff: duplicate name in {item['table']}: {item['name']} ({item['count']} entries)")
    print(f"uri_diff: {len(snap['entries'])} entries, {len(snap['missing'])} missing")
    for item in snap["missing"]:
        print(f"  missing: {item['table']} {item['name']} -> {item['resolved']}")
    for item in snap["disabled_missing"]:
        print(f"  disabled, file not found: {item['table']} {item['name']} -> {item['resolved']}")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    before, after = _read_snapshot(args.before), _read_snapshot(args.after)
    if before is None or after is None:
        return 2
    lines = compare(before, after)
    notes = [*_var_notes(before, after), *_disabled_notes(before, after)]
    if not lines:
        for note in notes:
            print(note)
        print(f"uri_diff: identical, {len(before['entries'])} entries, 0 missing")
        return 0
    for line in (*lines, *notes):
        print(line)
    print(f"uri_diff: {len(lines)} difference(s) between {args.before} and {args.after}")
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolved-URI snapshot and compare of KiCad's global library tables")
    sub = parser.add_subparsers(dest="command", required=True)
    p_vars = sub.add_parser("vars", help="print KICAD_LIB_GITHUB and CUSTOM_3DMODEL_DIR from kicad_common.json")
    p_vars.add_argument("--config-dir", help="KiCad's version folder (default: the newest one found)")
    p_snap = sub.add_parser("snapshot", help="resolve every table URI and write a JSON snapshot")
    p_snap.add_argument("--tables-dir", required=True, help="folder holding sym-lib-table and fp-lib-table (read only)")
    p_snap.add_argument("--config-dir", help="folder holding kicad_common.json (default: --tables-dir)")
    p_snap.add_argument("--var", action="append", default=[], metavar="NAME=VALUE", help="set a variable; beats kicad_common.json and the environment")
    p_snap.add_argument("--lib-root", help="library root written as <LIB> (default: the expanded KICAD_LIB_GITHUB)")
    p_snap.add_argument("--no-env", action="store_true", help="ignore the process environment (only kicad_common.json and --var give variables)")
    p_snap.add_argument("--redact-home", action="store_true", help="write the user's home folder as <HOME> in the snapshot")
    p_snap.add_argument("--out", required=True, help="the snapshot file to write")
    p_cmp = sub.add_parser("compare", help="exit 0 only when both snapshots list the same entries with none missing")
    p_cmp.add_argument("before")
    p_cmp.add_argument("after")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return {"vars": _cmd_vars, "snapshot": _cmd_snapshot, "compare": _cmd_compare}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
