"""Tests for scripts/prepublish_scan.py, the pre-publish scan (Phase 16, D-09, D-10).

Every planted violation below is assembled from pieces at run time, so this file's own text scans
clean with every rule of the script it tests.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from gitfixtures import GIT, requires_git
from runfixtures import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "prepublish_scan.py"


def _load_script():
    """Load the script by path: a `scripts` package on sys.path could be shadowed by an installed one."""
    spec = importlib.util.spec_from_file_location("prepublish_scan", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["prepublish_scan"] = module
    spec.loader.exec_module(module)
    return module


scan = _load_script()
Finding = scan.Finding


def blob(path: str, text: str, rules=None, allowed=None) -> list:
    return scan.scan_blob(path, text.encode("utf-8"), rules or scan.build_rules(), allowed)


def rule_names(findings) -> list[str]:
    return sorted(f.rule for f in findings)


# Pieces of planted text, joined at run time
SLASH = "/"
BACKSLASH = "\\"


def drive_path(letter: str, folder: str, sep: str) -> str:
    return letter + ":" + sep + folder + sep + "someone" + sep + "file.txt"


def test_workstation_paths_are_found():
    samples = [
        drive_path("C", "Users", SLASH),
        drive_path("C", "Users", BACKSLASH),
        drive_path("D", "Git_Repo_Clones", SLASH),
        drive_path("d", "git_repo_clones", BACKSLASH),
        SLASH + "c" + SLASH + "Users" + SLASH + "someone" + SLASH + "file.txt",
        SLASH + "Users" + SLASH + "someone" + SLASH + "file.txt",
        SLASH + "home" + SLASH + "someone" + SLASH + "file.txt",
        "pytest" + "-of-" + "someone" + SLASH + "test_x0",
    ]
    for sample in samples:
        assert blob("a.txt", "value = " + sample) == [Finding("workstation_path", "a.txt:1")], sample
    # the CI runner's folder, and the placeholder the export scrub writes (scripts/split/scrub.py)
    for clean in (
        SLASH + "home" + SLASH + "runner" + SLASH + "work" + SLASH + "x",
        "pytest" + "-of-" + "runner",
        "pytest" + "-of-" + "<user>" + SLASH + "pytest-3",
    ):
        assert blob("a.txt", "value = " + clean) == [], clean


def test_owner_email_and_terms():
    address = "ow" + "ner" + "@" + "priv" + ".test"
    term = "Zorblax" + "Quux"
    rules = scan.build_rules(deny_emails=[address], deny_terms=[term])
    found = blob("a.txt", "first line\ncontact " + address.upper() + " now", rules)
    assert found == [Finding("owner_email", "a.txt:2")]
    found = blob("b.txt", "by " + term.lower() + "\n", rules)
    assert found == [Finding("owner_term", "b.txt:1")]
    for f in blob("a.txt", address + " " + term, rules):
        text = scan.format_finding(f)
        assert address not in text.lower() and term.lower() not in text.lower()
        assert text == f.rule + "\t" + f.where


def test_generic_emails():
    other = "pe" + "rson" + "@" + "mail" + ".test"
    assert blob("a.txt", "x " + other) == [Finding("email", "a.txt:1")]
    allowed = [
        "someone@example.invalid",
        "someone@example.com",
        "someone@example.org",
        "12345+handle@users.noreply.github.com",
        "noreply@anthropic.com",
        "noreply@github.com",
        "git@github.com",
    ]
    for address in allowed:
        assert blob("a.txt", "x " + address + " y") == [], address
    # A backslash-n before a decorator is not an address, and neither is a package pin
    assert blob("a.txt", "text\\n@pytest.mark.not_registered") == []
    assert blob("a.txt", "pyside6@6.12.0") == []


def test_vendor_files():
    suffixes = (".zip .stp .step .wrl .kicad_sym .kicad_mod .kicad_pcb .kicad_sch .kicad_pro .lib .dcm .pdf .igs .iges .7z .rar").split()
    rules = scan.build_rules()
    for suffix in suffixes:
        assert scan.scan_blob("parts/x" + suffix, b"text", rules) == [Finding("vendor_file", "parts/x" + suffix)], suffix
    assert scan.scan_blob("parts/X.STEP", b"text", rules) == [Finding("vendor_file", "parts/X.STEP")]
    assert scan.scan_blob("data/a.bin", b"PK\x03\x04rest", rules) == [Finding("vendor_file", "data/a.bin")]
    assert scan.scan_blob("data/a.txt", b"ISO-10303-21;\nHEADER;", rules) == [Finding("vendor_file", "data/a.txt")]
    # The same bytes inside a literal of a source file are not a file header
    assert scan.scan_blob("src/m.py", b'MAGIC = b"PK\\x03\\x04"\nSTEP = b"ISO-10303-21"\n', rules) == []
    assert scan.scan_blob("tests/fixtures/z.bin", b"PK\x03\x04rest", rules) == []


def test_fixtures_exemption_is_a_whole_segment():
    rules = scan.build_rules()
    assert scan.scan_blob("tests/fixtures/sexpr/a.kicad_mod", b"x", rules) == []
    assert scan.scan_blob("tests/fixtures_extra/a.kicad_mod", b"x", rules) == [
        Finding("vendor_file", "tests/fixtures_extra/a.kicad_mod")
    ]
    assert scan.scan_blob("tests/fixtures", b"PK\x03\x04", rules) == [Finding("vendor_file", "tests/fixtures")]


def test_copied_content():
    shared = [
        "(property \"Reference\" \"U\" (at 0 0 0))",
        "(property \"Value\" \"ABC123\" (at 0 2 0))",
        "(property \"Footprint\" \"Lib:Name\" (at 0 4 0))",
    ]
    corpus = "(symbol \"ABC123\"\n" + "\n".join("  " + line for line in shared) + "\n  (pin_names)\n"
    rules = scan.build_rules(corpus_texts=[corpus])
    assert len(scan.windows(corpus)) >= 1
    text = "header\n" + "\n".join(shared) + "\nfooter\n"
    assert blob("x/a.txt", text, rules) == [Finding("copied_content", "x/a.txt")]
    two = "header\n" + "\n".join(shared[:2]) + "\n(something quite different here at all)\n"
    assert blob("x/a.txt", two, rules) == []
    short = "\n".join(["short one", "short two", "short three", "short four"])
    assert blob("x/a.txt", short, scan.build_rules(corpus_texts=[short])) == []
    identical = b"tiny"
    rules = scan.build_rules(corpus_blobs=[identical])
    assert scan.scan_blob("x/b.txt", identical, rules) == [Finding("copied_content", "x/b.txt")]
    assert scan.scan_blob("x/b.txt", identical + b"!", rules) == []


def test_secrets():
    pad = "A1b2C3d4" * 6
    samples = [
        "gh" + "p_" + pad[:36],
        "github" + "_pat_" + pad[:50] + "_x",
        "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "-----BEGIN " + "RSA PRIVATE KEY" + "-----",
        "xo" + "xb-" + "1234567890-abcdef",
        "AI" + "za" + pad[:35],
        "sk-" + "ant-" + pad[:30],
        "ey" + "J" + pad[:12] + ".ey" + "J" + pad[:12],
        "api_key" + " = " + '"' + pad[:20] + '"',
    ]
    for sample in samples:
        assert blob("a.txt", "line " + sample + " end") == [Finding("secret", "a.txt:1")], sample
    marked = "api_key" + " = " + '"' + pad[:20] + '"' + "  # scan: allow " + "secret"
    assert blob("a.txt", marked) == []
    both = drive_path("C", "Users", SLASH) + " " + marked
    assert blob("a.txt", both) == [Finding("workstation_path", "a.txt:1")]
    assert blob("a.txt", 'name = "short"') == []


def test_session_url_and_trailer():
    url = "https://claude.ai/code/" + "session_" + "01ABCDEFGHIJKLMN"
    assert blob("notes.md", "see " + url) == [Finding("session_url", "notes.md:1")]
    rules = scan.build_rules()
    sha = "a" * 40
    trailer = "Claude-Session" + ": abc123"
    assert scan.scan_message(sha, "feat: x\n\n" + trailer + "\n", rules) == [Finding("session_trailer", "commit:" + "a" * 12)]
    assert scan.scan_message(sha, "feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n", rules) == []


def test_identity_and_refs():
    rules = scan.build_rules()
    sha = "b" * 40
    outsider = "dev" + "@" + "corp" + ".test"
    assert scan.scan_identity(sha, "dev", outsider, rules) == [Finding("commit_identity", "commit:" + "b" * 12)]
    assert scan.scan_identity(sha, "dev", "123+dev@users.noreply.github.com", rules) == []
    assert scan.scan_identity(sha, "dev", "noreply@github.com", rules) == []
    denied = scan.build_rules(deny_terms=["Zorblax" + "Quux"])
    assert scan.scan_identity(sha, "zorblaxquux dev", "123+dev@users.noreply.github.com", denied) == [
        Finding("commit_identity", "commit:" + "b" * 12)
    ]
    assert scan.scan_ref("refs/heads/worktree-agent-x") == [Finding("ref_name", "ref:refs/heads/worktree-agent-x")]
    assert scan.scan_ref("refs/heads/main") == []
    assert scan.scan_ref("refs/heads/feature/worktree-agent-y") == [
        Finding("ref_name", "ref:refs/heads/feature/worktree-agent-y")
    ]


def test_public_part_numbers_are_allowed():
    text = "Part CSD85301Q2 and USB4145-03-0170-C in Atomic_Transistor_FET and Atomic_Connector"
    assert blob("a.txt", text) == []


def test_large_blob(monkeypatch):
    monkeypatch.setattr(scan, "MAX_BLOB_BYTES", 50)
    secret_line = ("api_key" + " = " + '"' + "A1b2C3d4" * 3 + '"').encode()
    data = secret_line + b"\n" + b"a" * 60
    assert scan.scan_blob("big.txt", data, scan.build_rules()) == [Finding("large_blob", "big.txt")]
    assert scan.MAX_BLOB_BYTES == 50


def test_allowed_hits_are_listed():
    secret = "api_key" + " = " + '"' + "A1b2C3d4" * 3 + '"'
    text = "fine line\n" + secret + "  # scan: allow " + "secret" + "\nplain line  # scan: allow " + "secret" + "\n"
    allowed: list = []
    assert blob("x.py", text, allowed=allowed) == []
    assert allowed == [Finding("secret", "x.py:2")]
    # Without the list the behaviour is the same
    assert blob("x.py", text) == []
    # A marker for another rule does not suppress
    other = secret + "  # scan: allow " + "workstation_path"
    allowed = []
    assert blob("x.py", other, allowed=allowed) == [Finding("secret", "x.py:1")]
    assert allowed == []


def test_skip_rule_turns_a_rule_off():
    rules = scan.build_rules(skipped=["workstation_path"])
    assert blob("a.txt", drive_path("C", "Users", SLASH), rules) == []


def test_corpus_collection_reads_text_and_zip_members(tmp_path):
    (tmp_path / "Custom").mkdir()
    (tmp_path / "Custom" / "a.kicad_sym").write_text("one line of text that is long enough\n", encoding="utf-8")
    (tmp_path / "downloaded_examples").mkdir()
    import zipfile

    with zipfile.ZipFile(tmp_path / "downloaded_examples" / "v.zip", "w") as archive:
        archive.writestr("pkg/b.kicad_mod", "member text that is also long enough\n")
        archive.writestr("pkg/readme.txt", "ignored member text\n")
    texts, blobs = scan.collect_corpus([tmp_path])
    assert any("one line of text" in t for t in texts)
    assert any("member text" in t for t in texts)
    assert not any("ignored member" in t for t in texts)
    assert len(blobs) == 2


def test_usage_errors(tmp_path, capsys):
    assert scan.main(["--repo", str(tmp_path / "missing")]) == 2
    assert "prepublish_scan:" in capsys.readouterr().err
    assert scan.main(["--deny-terms-file", str(tmp_path / "nope.txt"), "--repo", str(REPO_ROOT)]) == 2
    assert "prepublish_scan:" in capsys.readouterr().err


# ── Git walk (slow: creates real repositories) ───────────────────────────────────────────────────

ENV_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")


def _git_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="dev",
        GIT_AUTHOR_EMAIL="1+dev@users.noreply.github.com",
        GIT_COMMITTER_NAME="dev",
        GIT_COMMITTER_EMAIL="1+dev@users.noreply.github.com",
    )
    return env


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run([GIT, *args], cwd=repo, env=_git_env(), capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout


def _scan(repo: Path, *args: str):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
        env=_git_env(),
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    return done.returncode, (done.stdout + done.stderr)


@pytest.mark.slow
@requires_git
def test_exit_codes_and_output(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    planted = drive_path("C", "Users", SLASH).replace("someone", "zq9plant")
    (repo / "notes.txt").write_text("path = " + planted + "\n", encoding="utf-8")
    _git(repo, "add", "notes.txt")
    _git(repo, "commit", "-q", "-m", "add notes\n\n" + "Claude-Session" + ": abc123")
    _git(repo, "branch", "worktree-agent-x")

    code, out = _scan(repo)
    assert code == 1, out
    lines = [line for line in out.splitlines() if "\t" in line]
    assert len(lines) == 3, out
    assert sorted(line.split("\t")[0] for line in lines) == ["ref_name", "session_trailer", "workstation_path"]
    assert "zq9plant" not in out
    assert "prepublish_scan: 3 finding(s)" in out.splitlines()[-1]

    # Rewrite the history clean: one orphan commit, the old branches gone
    _git(repo, "checkout", "-q", "--orphan", "clean")
    _git(repo, "rm", "-q", "-rf", ".")
    (repo / "clean.txt").write_text("nothing private here\n", encoding="utf-8")
    _git(repo, "add", "clean.txt")
    _git(repo, "commit", "-q", "-m", "clean start")
    _git(repo, "branch", "-q", "-D", "main", "worktree-agent-x")
    code, out = _scan(repo)
    assert code == 0, out
    assert out.splitlines()[-1].startswith("prepublish_scan: clean"), out

    # A marked line is allowed; only --list-allowed shows it
    marked = "api_key" + " = " + '"' + "A1b2C3d4" * 3 + '"' + "  # scan: allow " + "secret"
    (repo / "fixture.py").write_text(marked + "\n", encoding="utf-8")
    _git(repo, "add", "fixture.py")
    _git(repo, "commit", "-q", "-m", "add fixture")
    code, out = _scan(repo)
    assert code == 0, out
    assert [line for line in out.splitlines() if line.strip()][:-1] == []
    assert out.splitlines()[-1].startswith("prepublish_scan: clean")
    code, out = _scan(repo, "--list-allowed")
    assert code == 0, out
    lines = out.splitlines()
    assert "allowed-by-marker\tsecret\tfixture.py:1" in lines, out
    assert "prepublish_scan: 1 allowed by marker" in lines, out
    assert lines[-1].startswith("prepublish_scan: clean")
    assert lines.index("prepublish_scan: 1 allowed by marker") < len(lines) - 1
    assert "A1b2C3d4" not in out

    # No commits, nothing to scan
    empty = tmp_path / "empty"
    empty.mkdir()
    _git(empty, "init", "-q", "-b", "main")
    code, out = _scan(empty, "--history")
    assert code == 2, out
    assert "nothing to scan: the repository has no commits" in out
