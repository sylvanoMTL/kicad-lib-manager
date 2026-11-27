"""repo_info: the one unauthenticated GitHub lookup of Add by URL (Phase 17 plan 07; D-04, D-23, CAT-03, CAT-11).

No network: every test hands repo_info an `opener` stand-in that returns (status, body) or raises.
"""

import json
import socket
import urllib.error
import urllib.request

import pytest

from kicad_lib_manager.catalog import githubapi
from kicad_lib_manager.catalog.githubapi import RepoInfo, repo_info
from kicad_lib_manager.models import Issue, Severity

NOT_FOUND_TEXT = "GitHub could not find this repository, or it is private. The catalog only adds public repositories."

GOOD = {
    "full_name": "a/b",
    "size": 70000,
    "default_branch": "main",
    "license": {"spdx_id": "MIT"},
    "private": False,
    "archived": False,
}


def _body(**changes) -> bytes:
    data = dict(GOOD)
    data.update(changes)
    return json.dumps(data).encode("utf-8")


def _opener(status=200, body=b"", *, raises=None, seen=None):
    def opener(request, timeout):
        if seen is not None:
            seen.append((request, timeout))
        if raises is not None:
            raise raises
        return status, body

    return opener


def _issue(result, code: str) -> Issue:
    assert isinstance(result, Issue), result
    assert result.code == code, result
    assert result.severity is Severity.ERROR
    return result


def test_a_good_answer_gives_the_repository_facts():
    info = repo_info("a", "b", opener=_opener(200, _body()))
    assert info == RepoInfo("a/b", 70000, "main", "MIT", False, False)


def test_no_licence_gives_none_and_noassertion_stays():
    assert repo_info("a", "b", opener=_opener(200, _body(license=None))).spdx is None
    assert repo_info("a", "b", opener=_opener(200, _body(license={"spdx_id": "NOASSERTION"}))).spdx == "NOASSERTION"
    assert repo_info("a", "b", opener=_opener(200, _body(license={"spdx_id": None}))).spdx is None


def test_the_request_is_unauthenticated_with_a_generic_user_agent():
    seen = []
    repo_info("Some-Owner", "the.repo_x", opener=_opener(200, _body(), seen=seen))
    ((request, timeout),) = seen
    assert request.full_url == "https://api.github.com/repos/Some-Owner/the.repo_x"
    headers = {k.lower(): v for k, v in request.header_items()}
    assert "authorization" not in headers and "cookie" not in headers
    assert headers["user-agent"] == "kicad-lib-manager"
    assert headers["accept"] == "application/vnd.github+json"
    assert headers["x-github-api-version"] == "2022-11-28"
    assert request.get_method() == "GET" and request.data is None
    assert timeout == githubapi.API_TIMEOUT


def test_not_found_has_the_plain_text():
    result = _issue(repo_info("a", "b", opener=_opener(404, b"{}")), "api.not_found")
    assert result.text == NOT_FOUND_TEXT


def test_a_private_repository_is_not_found():
    result = _issue(repo_info("a", "b", opener=_opener(200, _body(private=True))), "api.not_found")
    assert result.text == NOT_FOUND_TEXT


@pytest.mark.parametrize("status", [403, 429, 500, 301, 204])
def test_other_statuses_give_unknown(status):
    _issue(repo_info("a", "b", opener=_opener(status, _body())), "api.unknown")


def test_a_timeout_gives_unknown_with_the_slow_text():
    result = _issue(repo_info("a", "b", opener=_opener(raises=socket.timeout("slow"))), "api.unknown")
    assert result.text == "GitHub took too long to answer. Try again later."
    _issue(repo_info("a", "b", opener=_opener(raises=TimeoutError())), "api.unknown")


def test_an_unreachable_host_gives_unknown_with_the_offline_text():
    result = _issue(repo_info("a", "b", opener=_opener(raises=urllib.error.URLError("no route"))), "api.unknown")
    assert result.text == "GitHub could not be reached. Check your internet connection, then try again."
    _issue(repo_info("a", "b", opener=_opener(raises=OSError("boom"))), "api.unknown")


@pytest.mark.parametrize(
    "body",
    [b"not json", b"\xff\xfe", b"[]", b"null", b'"text"', b"{" * 5000, b""],
)
def test_bad_json_gives_unknown(body):
    _issue(repo_info("a", "b", opener=_opener(200, body)), "api.unknown")


def test_a_body_over_256_kb_gives_unknown():
    assert githubapi.MAX_API_BYTES == 256 * 1024
    big = _body(description="x" * (githubapi.MAX_API_BYTES + 10))
    _issue(repo_info("a", "b", opener=_opener(200, big)), "api.unknown")
    just_under = _body()
    assert len(just_under) < githubapi.MAX_API_BYTES
    assert isinstance(repo_info("a", "b", opener=_opener(200, just_under)), RepoInfo)


@pytest.mark.parametrize(
    "changes",
    [
        {"size": "big"},
        {"size": True},
        {"size": -1},
        {"size": 1.5},
        {"full_name": 5},
        {"default_branch": None},
        {"default_branch": ["main"]},
        {"license": "MIT"},
        {"license": {"spdx_id": 7}},
        {"private": "no"},
        {"archived": 1},
    ],
)
def test_a_field_of_the_wrong_type_gives_unknown(changes):
    _issue(repo_info("a", "b", opener=_opener(200, _body(**changes))), "api.unknown")


@pytest.mark.parametrize("missing", ["full_name", "size", "default_branch"])
def test_a_missing_required_field_gives_unknown(missing):
    data = dict(GOOD)
    del data[missing]
    _issue(repo_info("a", "b", opener=_opener(200, json.dumps(data).encode())), "api.unknown")


@pytest.mark.parametrize("owner, repo", [("", "b"), ("a", ""), ("a/b", "c"), ("a", "../b"), ("a b", "c"), ("a", "b?x=1")])
def test_a_name_that_is_not_a_repository_name_never_reaches_the_network(owner, repo):
    seen = []
    _issue(repo_info(owner, repo, opener=_opener(200, _body(), seen=seen)), "api.unknown")
    assert seen == []


def test_the_source_never_names_an_authorization_header():
    text = githubapi.__file__
    with open(text, encoding="utf-8") as handle:
        assert "authorization" not in handle.read().casefold()


# -- the default opener and its redirect rule ----------------------------------------


def _redirect(newurl: str):
    handler = githubapi._SameHostRedirect()
    request = urllib.request.Request("https://api.github.com/repos/a/b")
    return handler.redirect_request(request, None, 301, "Moved", {}, newurl)


def test_a_redirect_inside_the_api_host_is_followed():
    assert _redirect("https://api.github.com/repositories/42") is not None


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example/x",
        "http://api.github.com/repos/a/b",
        "https://api.github.com.evil.example/x",
        "https://api.github.com@evil.example/x",
        "file:///etc/passwd",
        "https://github.com/a/b",
    ],
)
def test_a_redirect_anywhere_else_is_refused(target):
    assert _redirect(target) is None


def test_an_http_error_from_the_default_opener_is_an_unknown_answer(monkeypatch):
    class Failing:
        def open(self, request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 403, "rate limit", {}, None)

    monkeypatch.setattr(githubapi, "_build_opener", lambda: Failing())
    _issue(repo_info("a", "b"), "api.unknown")
