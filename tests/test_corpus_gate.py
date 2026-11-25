"""Meta-tests for the corpus and needs_kicad gate (Phase 16, SPLIT-04): child pytest runs, none creates a git repository.

Every case sets both gate variables explicitly (blank closes a gate), so the result does not depend on whether the
machine running them has a KiCad install or a collection.
"""

from pathlib import Path

from runfixtures import run_pytest, write_tree

_CORPUS_LINE = "deselected: 1 corpus (set KICAD_TEST_CORPUS to a collection folder to run them)"
_KICAD_LINE = "deselected: 1 needs_kicad (no KiCad install found)"

_CORPUS_TEST = (
    "import os\n"
    "import pytest\n\n\n"
    "@pytest.mark.corpus\n"
    "def test_needs_the_collection():\n"
    "    open(os.environ['GATE_MARKER'], 'w').write('ran')\n"
)
_PLAIN_TEST = "def test_plain():\n    pass\n"
_KICAD_TEST = "import pytest\n\n\n@pytest.mark.needs_kicad\ndef test_needs_kicad():\n    pass\n"


def _tail(done) -> str:
    return (done.stdout + done.stderr)[-3000:]


def _collection(root: Path) -> Path:
    (root / "Custom" / "Symbols").mkdir(parents=True)
    return root


def _run(tmp_path, files, *args, corpus="", hide="", extra=None):
    run_dir = write_tree(tmp_path / "run", files)
    env = {
        "KICAD_TEST_CORPUS": corpus,
        "KICAD_TEST_HIDE_KICAD": hide,
        "GATE_MARKER": str(tmp_path / "marker.txt"),
    }
    env.update(extra or {})
    return run_pytest(run_dir, *args, basetemp=tmp_path / "bt", env=env)


def test_corpus_closed_deselects_with_a_count(tmp_path):
    """With no corpus the marked test is deselected (not skipped, not run) and the run says how many."""
    done = _run(tmp_path, {"test_corpus.py": _CORPUS_TEST, "test_plain.py": _PLAIN_TEST}, "-n", "2")

    assert done.returncode == 0, _tail(done)
    assert "1 passed" in done.stdout, _tail(done)
    assert _CORPUS_LINE in done.stdout, _tail(done)
    assert not (tmp_path / "marker.txt").exists()
    assert "skipped" not in done.stdout, _tail(done)


def test_counts_are_the_same_with_and_without_workers(tmp_path):
    """Edge ordering: the printed line is identical with -n 2 workers and with -n 0."""
    files = {"test_corpus.py": _CORPUS_TEST, "test_plain.py": _PLAIN_TEST}
    with_workers = _run(tmp_path / "a", files, "-n", "2")
    serial = _run(tmp_path / "b", files, "-n", "0")

    for done in (with_workers, serial):
        assert done.returncode == 0, _tail(done)
        assert _CORPUS_LINE in done.stdout, _tail(done)
    lines = [
        [line for line in done.stdout.splitlines() if line.startswith("deselected:")] for done in (with_workers, serial)
    ]
    assert lines[0] == lines[1] == [_CORPUS_LINE]


def test_blank_corpus_is_unset(tmp_path):
    """Edge empty: a blank (spaces only) KICAD_TEST_CORPUS behaves as unset, not as a wrong folder."""
    done = _run(tmp_path, {"test_corpus.py": _CORPUS_TEST, "test_plain.py": _PLAIN_TEST}, "-n", "0", corpus="   ")

    assert done.returncode == 0, _tail(done)
    assert _CORPUS_LINE in done.stdout, _tail(done)
    assert "is not a library collection" not in (done.stdout + done.stderr)


def test_wrong_corpus_is_a_usage_error(tmp_path):
    """A corpus folder that does not exist, or has no Custom/, stops the run with pytest's usage error."""
    files = {"test_plain.py": _PLAIN_TEST}
    missing = tmp_path / "nope"
    no_custom = tmp_path / "empty"
    no_custom.mkdir()

    for number, folder in enumerate((missing, no_custom)):
        done = _run(tmp_path / f"case{number}", files, "-n", "0", corpus=str(folder))

        assert done.returncode == 4, _tail(done)
        assert f"KICAD_TEST_CORPUS={str(folder)!r} is not a library collection" in (done.stdout + done.stderr), _tail(done)


def test_open_corpus_runs_corpus_tests(tmp_path):
    """With a collection named, the corpus test runs and nothing is deselected."""
    collection = _collection(tmp_path / "collection")
    done = _run(
        tmp_path, {"test_corpus.py": _CORPUS_TEST, "test_plain.py": _PLAIN_TEST}, "-n", "0", corpus=str(collection)
    )

    assert done.returncode == 0, _tail(done)
    assert "2 passed" in done.stdout, _tail(done)
    assert (tmp_path / "marker.txt").read_text(encoding="utf-8") == "ran"
    assert "deselected:" not in done.stdout, _tail(done)


def test_guard_watches_the_corpus_custom(tmp_path):
    """A test that writes into <corpus>/Custom fails the run through the live-Custom guard."""
    collection = _collection(tmp_path / "collection")
    writer = (
        "import os\n"
        "import pytest\n"
        "from pathlib import Path\n\n\n"
        "@pytest.mark.corpus\n"
        "def test_writes_the_collection():\n"
        "    (Path(os.environ['KICAD_TEST_CORPUS']) / 'Custom' / 'Symbols' / 'new.kicad_sym').write_text('x')\n"
    )
    done = _run(tmp_path, {"test_writer.py": writer}, "-n", "0", corpus=str(collection))

    assert done.returncode != 0, _tail(done)
    assert "the test run changed the live Custom/ folder:" in done.stdout, _tail(done)
    assert "Symbols/new.kicad_sym" in done.stdout, _tail(done)


def test_hidden_kicad_deselects_needs_kicad(tmp_path):
    """KICAD_TEST_HIDE_KICAD=1 deselects needs_kicad tests, and the scanner finds no KiCad without a base."""
    hidden = (
        "from kicad_lib_manager.library_scanner import find_kicad_footprint_dir\n\n\n"
        "def test_no_kicad():\n"
        "    assert find_kicad_footprint_dir() is None\n"
    )
    done = _run(tmp_path, {"test_kicad.py": _KICAD_TEST, "test_hidden.py": hidden}, "-n", "2", hide="1")

    assert done.returncode == 0, _tail(done)
    assert "1 passed" in done.stdout, _tail(done)
    assert _KICAD_LINE in done.stdout, _tail(done)


def test_wurth_implies_corpus(tmp_path):
    """A wurth test is also corpus (and slow): with --full and no corpus it is deselected as corpus, not run."""
    wurth = (
        "import os\n"
        "import pytest\n\n\n"
        "@pytest.mark.wurth\n"
        "def test_wurth_corpus():\n"
        "    open(os.environ['GATE_MARKER'], 'w').write('ran')\n"
    )
    done = _run(tmp_path, {"test_wurth.py": wurth}, "-n", "0", "--full")

    assert _CORPUS_LINE in done.stdout, _tail(done)
    assert not (tmp_path / "marker.txt").exists()
    assert "1 passed" not in done.stdout, _tail(done)


def test_both_counts_print(tmp_path):
    """One corpus and one needs_kicad test with both gates closed print both lines."""
    done = _run(
        tmp_path,
        {"test_corpus.py": _CORPUS_TEST, "test_kicad.py": _KICAD_TEST, "test_plain.py": _PLAIN_TEST},
        "-n",
        "2",
        hide="1",
    )

    assert done.returncode == 0, _tail(done)
    assert _CORPUS_LINE in done.stdout, _tail(done)
    assert _KICAD_LINE in done.stdout, _tail(done)
