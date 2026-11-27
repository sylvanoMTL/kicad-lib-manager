"""Catalog library path variables go through the same old -> new confirmation as the app's own two (CAT-06).

Nothing here touches the real %APPDATA% KiCad config or the real backup folder: every call passes
config_base, backup_root and running.
"""

import json

import pytest

from kicad_lib_manager import library_scanner
from kicad_lib_manager.library_scanner import ConfirmAnswer


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "my repo"
    path.mkdir()
    return path


@pytest.fixture
def cfg(tmp_path):
    base = tmp_path / "kicad_cfg"
    base.mkdir()
    return base


@pytest.fixture
def backups(tmp_path):
    return tmp_path / "backups"


def _own(repo):
    text = str(repo).replace("\\", "/")
    return {"KICAD_LIB_GITHUB": text, "CUSTOM_3DMODEL_DIR": f"{text}/Custom/3DModels"}


def _extras(repo):
    text = str(repo).replace("\\", "/")
    return {
        "WE_3DMODEL_DIR": f"{text}/ThirdParty/WurthElektronik/3dmodels",
        "A_DIR": f"{text}/ThirdParty/A",
    }


def _write(base, obj, version="10.0"):
    folder = base / version
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "kicad_common.json"
    path.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return path


def _sync(repo, cfg, backups, *, extra_vars=None, confirm=lambda changes: True, running=lambda: []):
    return library_scanner.sync_kicad_path_vars(
        repo, config_base=cfg, backup_root=backups, running=running, confirm=confirm, extra_vars=extra_vars
    )


def _recorder(answer=True):
    calls = []

    def confirm(changes):
        calls.append(changes)
        return answer

    confirm.calls = calls
    return confirm


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _backup_files(backups):
    folder = backups / "kicad_common" / "10.0"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


# ── reading the current variables ────────────────────────────────────

def test_current_path_vars_of_the_newest_version(cfg):
    _write(cfg, {"environment": {"vars": {"OLD": "x"}}}, "9.0")
    path = _write(cfg, {"environment": {"vars": {"A_DIR": "C:/a", "B": "b"}}}, "10.0")
    before = path.read_bytes()

    assert library_scanner.current_path_vars(config_base=cfg) == {"A_DIR": "C:/a", "B": "b"}
    assert path.read_bytes() == before


def test_current_path_vars_with_no_vars_is_empty(cfg):
    _write(cfg, {"environment": {"vars": None}})

    assert library_scanner.current_path_vars(config_base=cfg) == {}


def test_current_path_vars_is_none_without_a_readable_config(cfg, tmp_path):
    assert library_scanner.current_path_vars(config_base=tmp_path / "nowhere") is None
    assert library_scanner.current_path_vars(config_base=cfg) is None
    (cfg / "10.0").mkdir()
    assert library_scanner.current_path_vars(config_base=cfg) is None
    (cfg / "10.0" / "kicad_common.json").write_bytes(b'{"environment": ')
    assert library_scanner.current_path_vars(config_base=cfg) is None
    (cfg / "10.0" / "kicad_common.json").write_bytes(b'{"environment": {"vars": "x"}}')
    assert library_scanner.current_path_vars(config_base=cfg) is None


# ── the confirmation ─────────────────────────────────────────────────

def test_confirm_lists_own_variables_first_then_catalog_variables_by_name(repo, cfg, backups):
    _write(cfg, {"environment": {"vars": None}})
    confirm = _recorder(False)

    _sync(repo, cfg, backups, extra_vars=_extras(repo), confirm=confirm)

    assert len(confirm.calls) == 1
    assert [c[0] for c in confirm.calls[0]] == ["KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR", "A_DIR", "WE_3DMODEL_DIR"]
    assert confirm.calls[0][2] == ("A_DIR", None, _extras(repo)["A_DIR"])


def test_only_the_catalog_variables_are_listed_when_the_own_ones_are_right(repo, cfg, backups):
    _write(cfg, {"environment": {"vars": _own(repo)}})
    confirm = _recorder(False)

    _sync(repo, cfg, backups, extra_vars=_extras(repo), confirm=confirm)

    assert [c[0] for c in confirm.calls[0]] == ["A_DIR", "WE_3DMODEL_DIR"]


def test_a_decline_writes_nothing(repo, cfg, backups):
    path = _write(cfg, {"environment": {"vars": None}})
    before = path.read_bytes()

    issues = _sync(repo, cfg, backups, extra_vars=_extras(repo), confirm=_recorder(False))

    assert _codes(issues, "config.declined")
    assert path.read_bytes() == before
    assert _backup_files(backups) == []


def test_no_confirm_writes_nothing(repo, cfg, backups):
    path = _write(cfg, {"environment": {"vars": _own(repo)}})
    before = path.read_bytes()

    issues = library_scanner.sync_kicad_path_vars(
        repo, config_base=cfg, backup_root=backups, running=lambda: [], extra_vars=_extras(repo)
    )

    assert _codes(issues, "config.confirm_required")
    assert path.read_bytes() == before


def test_a_yes_writes_all_variables_after_one_backup_and_keeps_every_other_key(repo, cfg, backups):
    original = {
        "appearance": {"theme": "dark"},
        "environment": {"vars": {"KEEP_ME": "k", "A_DIR": "C:/old"}},
        "system": {"language": "Default"},
    }
    path = _write(cfg, original)
    before = path.read_bytes()

    issues = _sync(repo, cfg, backups, extra_vars=_extras(repo))

    assert _codes(issues, "config.written")
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["environment"]["vars"] == {"KEEP_ME": "k", **_own(repo), **_extras(repo)}
    assert written["appearance"] == original["appearance"] and written["system"] == original["system"]
    assert _backup_files(backups) == ["kicad_common.json_backup_1"]
    assert (backups / "kicad_common" / "10.0" / "kicad_common.json_backup_1").read_bytes() == before
    assert any("A_DIR" in i.text and "C:/old" in i.text for i in _codes(issues, "config.var_set"))


def test_an_extra_can_never_replace_the_apps_own_variables(repo, cfg, backups):
    path = _write(cfg, {"environment": {"vars": None}})
    confirm = _recorder()

    _sync(repo, cfg, backups, extra_vars={"KICAD_LIB_GITHUB": "C:/evil", "CUSTOM_3DMODEL_DIR": "C:/evil", **_extras(repo)},
          confirm=confirm)

    vars_ = json.loads(path.read_text(encoding="utf-8"))["environment"]["vars"]
    assert vars_["KICAD_LIB_GITHUB"] == _own(repo)["KICAD_LIB_GITHUB"]
    assert vars_["CUSTOM_3DMODEL_DIR"] == _own(repo)["CUSTOM_3DMODEL_DIR"]
    assert [c[0] for c in confirm.calls[0]] == ["KICAD_LIB_GITHUB", "CUSTOM_3DMODEL_DIR", "A_DIR", "WE_3DMODEL_DIR"]


def test_a_value_equal_to_the_desired_text_gives_no_change_and_no_question(repo, cfg, backups):
    path = _write(cfg, {"environment": {"vars": {**_own(repo), **_extras(repo)}}})
    before = path.read_bytes()
    confirm = _recorder()

    issues = _sync(repo, cfg, backups, extra_vars=_extras(repo), confirm=confirm)

    assert confirm.calls == []
    assert [i.code for i in issues] == ["config.var_ok"] * 4
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", [lambda v: v.replace("/", "\\"), lambda v: v.upper()])
def test_a_value_differing_only_in_slashes_or_case_is_offered_as_a_change(repo, cfg, backups, change):
    extras = _extras(repo)
    _write(cfg, {"environment": {"vars": {**_own(repo), **{k: change(v) for k, v in extras.items()}}}})
    confirm = _recorder(False)

    _sync(repo, cfg, backups, extra_vars=extras, confirm=confirm)

    assert [c[0] for c in confirm.calls[0]] == ["A_DIR", "WE_3DMODEL_DIR"]


def test_the_worktree_refusal_still_applies(repo, cfg, backups):
    (repo / ".git").write_text("gitdir: elsewhere\n")
    path = _write(cfg, {"environment": {"vars": None}})
    before = path.read_bytes()
    confirm = _recorder()

    issues = _sync(repo, cfg, backups, extra_vars=_extras(repo), confirm=confirm)

    assert _codes(issues, "config.worktree_refused")
    assert confirm.calls == []
    assert path.read_bytes() == before


def test_kicad_running_is_asked_once_before_the_confirmation_and_retry_writes_nothing(repo, cfg, backups):
    path = _write(cfg, {"environment": {"vars": None}})
    before = path.read_bytes()
    order = []

    def running():
        order.append("running")
        return ["kicad.exe"]

    def confirm(changes):
        order.append("confirm")
        return ConfirmAnswer.RETRY

    issues = _sync(repo, cfg, backups, extra_vars=_extras(repo), confirm=confirm, running=running)

    assert order == ["running", "confirm"]
    assert _codes(issues, "config.retry")
    assert path.read_bytes() == before
    assert _backup_files(backups) == []


def test_without_extras_nothing_changes(repo, cfg, backups):
    path = _write(cfg, {"environment": {"vars": _own(repo)}})
    before = path.read_bytes()
    confirm = _recorder()

    issues = _sync(repo, cfg, backups, confirm=confirm)

    assert confirm.calls == []
    assert [i.code for i in issues] == ["config.var_ok"] * 2
    assert path.read_bytes() == before


# ── would_change_path_vars ───────────────────────────────────────────

def test_would_change_with_extras_is_true_only_when_one_value_differs(repo, cfg):
    extras = _extras(repo)
    _write(cfg, {"environment": {"vars": {**_own(repo), **extras}}})

    assert library_scanner.would_change_path_vars(repo, config_base=cfg, extra_vars=extras) is False
    assert library_scanner.would_change_path_vars(repo, config_base=cfg) is False

    _write(cfg, {"environment": {"vars": {**_own(repo), **extras, "A_DIR": "C:/elsewhere"}}})
    assert library_scanner.would_change_path_vars(repo, config_base=cfg, extra_vars=extras) is True
    assert library_scanner.would_change_path_vars(repo, config_base=cfg) is False

    path = _write(cfg, {"environment": {"vars": _own(repo)}})
    before = path.read_bytes()
    assert library_scanner.would_change_path_vars(repo, config_base=cfg, extra_vars=extras) is True
    assert path.read_bytes() == before  # the probe never writes
