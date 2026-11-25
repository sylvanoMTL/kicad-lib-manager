"""Tests for scripts/check_skip_budget.py, the junit skip ceiling and passed floor (Phase 16, D-19)."""

import importlib.util
import sys

from runfixtures import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "check_skip_budget.py"


def _load_script():
    """Load the script by path: a `scripts` package on sys.path could be shadowed by an installed one."""
    spec = importlib.util.spec_from_file_location("check_skip_budget", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_skip_budget"] = module
    spec.loader.exec_module(module)
    return module


budget = _load_script()


def junit(tmp_path, tests=0, skipped=0, failures=0, errors=0, wrapped=False) -> str:
    suite = f'<testsuite name="pytest" errors="{errors}" failures="{failures}" skipped="{skipped}" tests="{tests}" time="1.0"/>'
    text = '<?xml version="1.0" encoding="utf-8"?>' + (f"<testsuites>{suite}</testsuites>" if wrapped else suite)
    path = tmp_path / "junit.xml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def run(path: str, max_skips: int = 10, min_passed: int = 3500) -> int:
    return budget.main([path, "--max-skips", str(max_skips), "--min-passed", str(min_passed)])


def test_exactly_at_the_ceiling_passes(tmp_path, capsys):
    assert run(junit(tmp_path, tests=3510, skipped=10)) == 0
    assert "10 skipped (max 10)" in capsys.readouterr().out


def test_one_over_the_ceiling_fails(tmp_path, capsys):
    assert run(junit(tmp_path, tests=3511, skipped=11)) == 1
    assert "11 skipped (max 10)" in capsys.readouterr().out


def test_floor_boundary(tmp_path):
    assert run(junit(tmp_path, tests=3500)) == 0
    assert run(junit(tmp_path, tests=3499)) == 1
    assert run(junit(tmp_path, tests=3600, skipped=101), max_skips=200) == 1  # 3499 passed


def test_zero_tests_fail_the_floor(tmp_path):
    assert run(junit(tmp_path, tests=0)) == 1


def test_failures_fail(tmp_path):
    assert run(junit(tmp_path, tests=4000, failures=1)) == 1
    assert run(junit(tmp_path, tests=4000, errors=1)) == 1


def test_missing_or_bad_junit(tmp_path, capsys):
    assert run(str(tmp_path / "missing.xml")) == 2
    assert "check_skip_budget:" in capsys.readouterr().err
    bad = tmp_path / "bad.xml"
    bad.write_text("<testsuite", encoding="utf-8")
    assert run(str(bad)) == 2
    assert "check_skip_budget:" in capsys.readouterr().err
    other = tmp_path / "other.xml"
    other.write_text("<html/>", encoding="utf-8")
    assert run(str(other)) == 2


def test_testsuites_wrapper_is_summed(tmp_path, capsys):
    text = (
        "<testsuites>"
        '<testsuite tests="2000" skipped="4" failures="0" errors="0"/>'
        '<testsuite tests="1510" skipped="6" failures="0" errors="0"/>'
        "</testsuites>"
    )
    path = tmp_path / "junit.xml"
    path.write_text(text, encoding="utf-8")
    assert run(str(path)) == 0
    assert "3500 passed, 10 skipped (max 10)" in capsys.readouterr().out
    assert run(junit(tmp_path, tests=3510, skipped=10, wrapped=True)) == 0
