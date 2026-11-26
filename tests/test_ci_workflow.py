"""Text checks of .github/workflows/ci.yml (Phase 16, D-20): no YAML library, only the lines that matter."""

import re

from runfixtures import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _text() -> str:
    """The workflow without its comment lines: a commented-out line must not satisfy a check."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _position(text: str, needle: str) -> int:
    """Where the needle is; it must occur exactly once, so a second copy cannot stand in for the real step."""
    assert text.count(needle) == 1, f"{needle!r} must occur exactly once in the workflow, found {text.count(needle)}"
    return text.index(needle)


def _steps(text: str) -> list[str]:
    """The text of each list item (each step) of the workflow."""
    return re.split(r"(?m)^\s*- ", text)[1:]


def _step_with(text: str, needle: str) -> str:
    found = [step for step in _steps(text) if needle in step]
    assert len(found) == 1, f"{needle!r} must be in exactly one step, found {len(found)}"
    return found[0]


def test_triggers_and_runner():
    text = _text()
    assert re.search(r"(?m)^on:\s*\[push, pull_request\]\s*$", text) or (
        re.search(r"(?m)^\s+push:", text) and re.search(r"(?m)^\s+pull_request:", text)
    )
    assert len(re.findall(r"(?m)^\s*runs-on: windows-latest\s*$", text)) == 1
    assert len(re.findall(r"(?m)^\s*runs-on:", text)) == 1, "one job on one runner"
    assert len(re.findall(r"(?m)^\s*timeout-minutes: 30\s*$", text)) == 1
    # the Python version and the full history belong to the steps that use them
    assert re.search(r'(?m)^\s*python-version: "3\.14"\s*$', _step_with(text, "actions/setup-python@"))
    assert re.search(r"(?m)^\s*fetch-depth: 0\s*$", _step_with(text, "actions/checkout@"))


def test_read_only_permissions():
    text = _text()
    assert re.search(r"(?m)^permissions:\s*\n\s+contents: read\s*$", text)
    # no job- or step-level grant of write access anywhere
    assert not re.search(r"(?m)^\s*[\w-]+:\s*write\s*$", text)
    assert "write-all" not in text


def test_step_order():
    text = _text()
    autocrlf = _position(text, "git config --global core.autocrlf false")
    checkout = _position(text, "actions/checkout@")
    scan = _position(text, "python scripts/prepublish_scan.py --tree --history")
    install = _position(text, "python -m pip install -r requirements-dev.txt")
    pytest_run = _position(text, "python -m pytest --junitxml=junit.xml")
    budget = _position(text, "python scripts/check_skip_budget.py junit.xml --max-skips 10 --min-passed 3500")
    assert autocrlf < checkout < scan < install < pytest_run < budget


def test_nothing_risky():
    text = _text()
    for forbidden in ("pull_request_target", "--full", "secrets.", "KICAD_TEST_CORPUS"):
        assert forbidden not in text, forbidden
    for line in text.splitlines():
        if "uses:" in line:
            assert re.search(r"uses: actions/[a-z-]+@v\d+\s*$", line), line
