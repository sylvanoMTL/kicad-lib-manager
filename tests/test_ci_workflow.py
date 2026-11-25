"""Text checks of .github/workflows/ci.yml (Phase 16, D-20): no YAML library, only the lines that matter."""

import re

from runfixtures import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _position(text: str, needle: str) -> int:
    index = text.find(needle)
    assert index >= 0, f"{needle!r} not in the workflow"
    return index


def test_triggers_and_runner():
    text = _text()
    assert re.search(r"(?m)^on:\s*\[push, pull_request\]\s*$", text) or ("push:" in text and "pull_request:" in text)
    assert "runs-on: windows-latest" in text
    assert 'python-version: "3.14"' in text
    assert "fetch-depth: 0" in text
    assert "timeout-minutes: 30" in text


def test_read_only_permissions():
    text = _text()
    assert re.search(r"(?m)^permissions:\s*\n\s+contents: read\s*$", text)


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
