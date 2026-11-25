#!/usr/bin/env python3
"""Skip budget: fail a test run that skipped too much, passed too little or failed anything.

Usage:
    python scripts/check_skip_budget.py JUNIT --max-skips N --min-passed M

Reads the junit XML pytest wrote (--junitxml) and adds up tests, skipped, failures and errors over
the top-level test suites (the root testsuite, or the testsuite children of a testsuites root).
passed = tests - skipped - failures - errors. The run fails (exit 1) when skipped is above N, when
passed is below M (so a mass deselection cannot look green: zero tests fail the floor), or when
anything failed or errored. A missing or unparsable file exits 2.
Tests deselected by a marker are not in the junit file and do not count as skips.
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path


class BudgetError(Exception):
    """The junit file cannot be used; main() reports it and exits 2."""


def read_totals(path: Path) -> tuple[int, int, int, int]:
    """(tests, skipped, failures, errors) summed over the top-level test suites of a junit file."""
    try:
        root = ET.parse(path).getroot()
    except OSError as error:
        raise BudgetError(f"cannot read {path}: {error.strerror or error}") from error
    except ET.ParseError as error:
        raise BudgetError(f"{path} is not valid XML: {error}") from error
    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    else:
        raise BudgetError(f"{path} is not a junit file (root element {root.tag!r})")
    totals = [0, 0, 0, 0]
    for suite in suites:
        for index, name in enumerate(("tests", "skipped", "failures", "errors")):
            try:
                totals[index] += int(suite.get(name, "0"))
            except ValueError as error:
                raise BudgetError(f"{path} has a non-numeric {name} count") from error
    return totals[0], totals[1], totals[2], totals[3]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_skip_budget.py", description="Check a junit file against a skip ceiling and a passed floor.")
    parser.add_argument("junit", type=Path, help="junit XML written by pytest --junitxml")
    parser.add_argument("--max-skips", type=int, required=True, help="most skipped tests allowed")
    parser.add_argument("--min-passed", type=int, required=True, help="fewest passed tests allowed")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return int(stop.code) if isinstance(stop.code, int) else 2
    try:
        tests, skipped, failures, errors = read_totals(args.junit)
    except BudgetError as error:
        print(f"check_skip_budget: {error}", file=sys.stderr)
        return 2
    passed = tests - skipped - failures - errors
    print(f"skip budget: {passed} passed, {skipped} skipped (max {args.max_skips}), {failures} failed, {errors} errors")
    problems = []
    if skipped > args.max_skips:
        problems.append(f"{skipped} skipped (max {args.max_skips})")
    if passed < args.min_passed:
        problems.append(f"{passed} passed (min {args.min_passed})")
    if failures + errors > 0:
        problems.append(f"{failures} failed and {errors} errors")
    for problem in problems:
        print(f"skip budget: FAILED: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
