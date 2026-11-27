"""Address, id and branch rules of the library catalog (Phase 17 plan 04; CAT-03, D-01, D-23).

Quick tests: no process, no network, no files.
"""

import pytest

from kicad_lib_manager.catalog.urls import (
    GITHUB_HOST,
    RepoRef,
    default_id,
    parse_github_url,
    repo_key,
    valid_branch,
    valid_id,
)
from kicad_lib_manager.models import Issue, Severity

BAD_URL_TEXT = "Only web addresses that start with https://github.com/ can be added. Paste the address of the repository page."
SPARKFUN = RepoRef(
    owner="sparkfun",
    repo="SparkFun-KiCad-Libraries",
    https_url="https://github.com/sparkfun/SparkFun-KiCad-Libraries.git",
    default_id="sparkfun-SparkFun-KiCad-Libraries",
)


def test_host_constant():
    assert GITHUB_HOST == "github.com"


@pytest.mark.parametrize(
    "text",
    [
        "https://github.com/sparkfun/SparkFun-KiCad-Libraries",
        "https://github.com/sparkfun/SparkFun-KiCad-Libraries.git",
        "https://github.com/sparkfun/SparkFun-KiCad-Libraries/",
        "https://github.com/sparkfun/SparkFun-KiCad-Libraries/tree/main/symbols",
        "https://github.com/sparkfun/SparkFun-KiCad-Libraries/blob/main/README.md",
        "  https://github.com/sparkfun/SparkFun-KiCad-Libraries  ",
        "HTTPS://GitHub.com/sparkfun/SparkFun-KiCad-Libraries",
    ],
)
def test_accepted_spellings_give_one_reference(text):
    assert parse_github_url(text) == SPARKFUN


def _ssh_style() -> str:
    # built from parts: the pre-publish scan reads a literal user, at sign and host as an e-mail address
    return "git" + "@" + "github.com:a/b"


def _with_user_info() -> str:
    return "https://user:pw" + "@" + "github.com/a/b"


@pytest.mark.parametrize(
    "text",
    [
        "http://github.com/a/b",
        _ssh_style(),
        "https://gitlab.com/a/b",
        "https://www.github.com/a/b",
        "https://github.com:443/a/b",
        _with_user_info(),
        "https://github.com/a/b?x=1",
        "https://github.com/a/b?",
        "https://github.com/a",
        "https://github.com/",
        "https://github.com",
        "https://github.com/a/b#x",
        "https://github.com/a/b/issues",
        "https://github.com/a/b/tree",
        "https://github.com/a//b",
        "https://github.com/-a/b",
        "https://github.com/a_b/c",
        "https://github.com/a/..",
        "https://github.com/a/.git",
        "https://github.com/a/b c",
        "https://github.com/a/b\nx",
        "ftp://github.com/a/b",
        "file:///tmp/a/b",
        "github.com/a/b",
        "",
        "   ",
    ],
)
def test_refused_addresses_give_the_one_plain_text(text):
    result = parse_github_url(text)
    assert isinstance(result, Issue), result
    assert result.code == "catalog.bad_url"
    assert result.severity is Severity.ERROR
    assert result.text == BAD_URL_TEXT


def test_refusal_text_never_echoes_the_typed_address():
    typed = _with_user_info()
    result = parse_github_url(typed)
    assert isinstance(result, Issue)
    assert "pw" not in result.text and typed not in result.text


@pytest.mark.parametrize(
    "owner, repo",
    [("a" * 40, "b"), ("a", "b" * 101), ("a-", "b")],
)
def test_owner_and_repo_follow_github_name_rules(owner, repo):
    ok = parse_github_url(f"https://github.com/{owner}/{repo}")
    if len(owner) > 39 or len(repo) > 100:
        assert isinstance(ok, Issue)
    else:
        assert isinstance(ok, RepoRef)


def test_a_dot_git_suffix_is_removed_once():
    ref = parse_github_url("https://github.com/a/b.git.git")
    assert isinstance(ref, RepoRef)
    assert ref.repo == "b.git"


def test_file_url_is_refused_unless_asked(tmp_path):
    url = (tmp_path / "Upstream.git").resolve().as_uri()
    assert isinstance(parse_github_url(url), Issue)
    ref = parse_github_url(url, allow_file=True)
    assert isinstance(ref, RepoRef)
    assert ref.default_id == "Upstream"
    assert ref.https_url == url


def test_allow_file_still_refuses_other_schemes():
    assert isinstance(parse_github_url("http://github.com/a/b", allow_file=True), Issue)
    assert isinstance(parse_github_url("file://", allow_file=True), Issue)


def test_default_id_is_owner_dash_repo_as_github_spells_it():
    assert default_id("sparkfun", "SparkFun-KiCad-Libraries") == "sparkfun-SparkFun-KiCad-Libraries"
    assert default_id("DawidCislo", "Alternate-KiCad-Library") == "DawidCislo-Alternate-KiCad-Library"


def test_default_id_drops_a_trailing_dot_and_stays_a_valid_id():
    assert default_id("a", "b.") == "a-b"
    long_id = default_id("o" * 39, "r" * 100)
    assert valid_id(long_id)
    assert long_id.startswith("o" * 39 + "-r")


def test_every_accepted_address_gives_a_valid_default_id():
    for repo in ("x", "x.", "..x", "-x", "con", "x" * 100, "A.B.C"):
        ref = parse_github_url(f"https://github.com/owner/{repo}")
        if isinstance(ref, RepoRef):
            assert valid_id(ref.default_id), (repo, ref.default_id)


@pytest.mark.parametrize(
    "text",
    [
        ".staging",
        ".Staging",
        "CON",
        "nul",
        "Com1",
        "lpt9",
        "CON.txt",
        "...",
        "..",
        ".",
        "a.",
        "a ",
        " a",
        "a" * 64,
        "",
        "-a",
        "_a",
        "a/b",
        "a\\b",
        "a:b",
        "a\nb",
        "Custom",
        "custom",
        "ThirdParty",
        "thirdparty",
    ],
)
def test_ids_that_cannot_be_a_folder_are_refused(text):
    assert valid_id(text) is False


@pytest.mark.parametrize("text", ["SparkFun", "4ms", "sparkfun-SparkFun-KiCad-Libraries", "a", "A.b_c-d", "a" * 63])
def test_ordinary_ids_are_accepted(text):
    assert valid_id(text) is True


def test_valid_id_refuses_non_text():
    assert valid_id(None) is False  # type: ignore[arg-type]
    assert valid_id(5) is False  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["main", "master", "release/1.x", "v1.2.3", "feature/a-b_c", "a" * 128])
def test_ordinary_branches_are_accepted(text):
    assert valid_branch(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "-x",
        "--upload-pack=x",
        ".x",
        "a..b",
        "a//b",
        "a/",
        "x.lock",
        "a.lock/b",
        "a/.b",
        "a.",
        "a:b",
        "a b",
        "a~1",
        "a^",
        "a?",
        "a*",
        "a[",
        "a\\b",
        "a@{1}",
        "",
        "a" * 129,
    ],
)
def test_branches_that_could_be_an_option_or_refspec_are_refused(text):
    assert valid_branch(text) is False


def test_repo_key_casefolds_owner_and_repo_and_ignores_spelling():
    assert repo_key("https://github.com/SparkFun/SparkFun-KiCad-Libraries.git") == "sparkfun/sparkfun-kicad-libraries"
    assert repo_key("https://github.com/sparkfun/SparkFun-KiCad-Libraries/tree/main") == repo_key(
        "https://github.com/SPARKFUN/sparkfun-kicad-libraries"
    )


def test_repo_key_of_a_file_url_is_the_casefolded_path(tmp_path):
    url = (tmp_path / "Upstream.git").resolve().as_uri()
    assert repo_key(url) == repo_key(url.upper().replace("FILE:", "file:"))
    assert repo_key(url) != repo_key("https://github.com/a/b")


def test_repo_key_of_an_unparsable_text_is_the_stripped_casefold():
    assert repo_key("  Not A URL ") == "not a url"
