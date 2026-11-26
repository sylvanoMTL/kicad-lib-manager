#!/usr/bin/env python3
"""Pre-publish scan: find anything private or licence-restricted before a repository is published.

Usage:
    python scripts/prepublish_scan.py [--repo DIR] [--tree] [--history] [--path PREFIX ...]
        [--deny-emails-from-repo DIR ...] [--deny-terms-file FILE ...] [--corpus DIR ...]
        [--skip-rule NAME ...] [--list-allowed]

With neither --tree nor --history both run. --tree scans the working tree (tracked and untracked
files that are not ignored); --history scans every blob reachable from any ref, every commit
message and identity, every annotated tag (tagger and message) and every ref name. --path limits the tree scan to a file or folder.

Identity terms are never stored here: the owner's addresses come from --deny-emails-from-repo (the
commit addresses and user.email of another repository) or, when no deny flag is given, from the
scanned repository's local git config (prepublish.denyEmailsFromRepo); owner names come from an
untracked --deny-terms-file (or prepublish.denyTermsFile), one term per line. --corpus DIR adds the
copy check against the symbol and footprint files of a library collection and its vendor zips.

An inline marker on a line suppresses one rule on that line: the word "scan:" then "allow" then the
rule name. --list-allowed prints each suppressed hit (rule and place only) so a person can review them.

When neither source gives an owner address or term, one note line goes to stderr: the owner rules
then checked nothing (always so on CI, which has no local git config). The pre-push hook refuses a
push from a clone that has no prepublish.denyTermsFile unless PREPUBLISH_ALLOW_NO_DENY_LIST=1 is set.

Output: one "<rule><TAB><place>" line per finding, never the matched text. Exit code 0 when clean,
1 on any finding, 2 on a usage error (no repository, no commits to scan, an unreadable file).
Stdlib only; the script never imports the application package.
"""

import argparse
import hashlib
import io
import re
import subprocess
import sys
import threading
import zipfile
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

MAX_BLOB_BYTES = 20_000_000
BINARY_PROBE_BYTES = 8192
MAX_ZIP_MEMBER_BYTES = 5_000_000
FIXTURES_PREFIX = "tests/fixtures/"
NO_DENY_LIST_NOTE = "prepublish_scan: no owner deny list in use (the owner_email and owner_term rules checked nothing)"

ALLOWED_EMAILS = frozenset({"noreply@anthropic.com", "noreply@github.com", "git@github.com"})
ALLOWED_EMAIL_DOMAINS = frozenset({"example.invalid", "example.com", "example.org", "users.noreply.github.com"})

VENDOR_SUFFIXES = (
    ".zip",
    ".7z",
    ".rar",
    ".step",
    ".stp",
    ".wrl",
    ".igs",
    ".iges",
    ".pdf",
    ".kicad_sym",
    ".kicad_mod",
    ".kicad_pcb",
    ".kicad_sch",
    ".kicad_pro",
    ".lib",
    ".dcm",
    ".tar",
    ".gz",
    ".tgz",
    ".xz",
    ".bz2",
    ".stl",
    ".lbr",
    ".olb",
    ".bxl",
    ".epw",
    ".schdoc",
    ".pcbdoc",
    ".schlib",
    ".pcblib",
    ".intlib",
    ".xls",
    ".xlsx",
    ".csv",
)
# zip, STEP, gzip, 7z, PDF, RAR
VENDOR_MAGICS = (b"PK\x03\x04", b"ISO-10303-21", b"\x1f\x8b", b"7z\xbc\xaf\x27\x1c", b"%PDF-", b"Rar!")
# Under tests/fixtures/ only these two (small text parts the tests build on) are exempt, never an archive by magic
FIXTURE_SUFFIXES = (".kicad_sym", ".kicad_mod")

# Rules that run on every text line, in report order
TEXT_RULES = ("workstation_path", "owner_email", "email", "owner_term", "secret", "session_url")
ALL_RULES = (*TEXT_RULES, "vendor_file", "copied_content", "session_trailer", "commit_identity", "ref_name", "large_blob")

# The macOS and Linux home rules are built from pieces so this file never matches its own rules
_USERS = "Users"
_HOME = "home"
_PYTEST_OF = "pytest" + "-of-"

_WORKSTATION_PATTERNS = (
    # drive-letter path into a user or repository-clone folder, either slash style
    re.compile(r"(?i)\b[a-z]:[\\/]+(?:users|git_repo_clones)[\\/]"),
    # git-bash style
    re.compile(r"(?i)(?<![\w.])/[a-z]/(?:users|git_repo_clones)/"),
    # WSL mount of a drive
    re.compile(r"(?i)/mnt/[a-z]/(?:users|git_repo_clones)/"),
    # URL-encoded colon after the drive letter
    re.compile(r"(?i)[a-z]%3a[\\/]+(?:users|git_repo_clones)[\\/]"),
    # UNC share that holds a user folder
    re.compile(r"(?i)(?<![\w\\])\\\\[^\\\s]+\\[^\\\s]+\\users\\"),
    # macOS home
    re.compile(r"(?<![A-Za-z0-9_])/" + _USERS + r"/[^/\s]+/"),
    # Linux home other than the CI runner's
    re.compile(r"(?<![\w.])/" + _HOME + r"/(?!runner\b)[^/\s]+/"),
    # pytest temp folder of a person (not the CI runner's, not the export scrub's <user> placeholder)
    re.compile(_PYTEST_OF + r"(?!runner\b|<user>)[^\s\\/]+"),
)

_EMAIL_PATTERN = re.compile(
    r"(?<![\\\w.%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,8}\.[A-Za-z]{2,24}(?![\w-])"
)

_SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{50,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ"),
    re.compile(r"(?i)(?:api[_-]?key|secret|token|passw(?:or)?d)\s*[:=]\s*[\"'][A-Za-z0-9_\-/+=]{16,}[\"']"),
)

_SESSION_URL_PATTERN = re.compile(r"(?i)claude\.ai/code/session[_/-]?[A-Za-z0-9_-]{8,}")
_TRAILER_PATTERN = re.compile(r"(?i)^\s*Claude-Session:")
_REF_PATTERN = re.compile(r"(?:^|/)worktree-agent-")
_ESCAPE_PATTERN = re.compile(r"\\[nrt]")
_MARKER_PATTERN =re.compile(r"scan:\s*allow\s+([A-Za-z_][A-Za-z0-9_ ,]*)")

PATTERNS: dict[str, tuple[re.Pattern, ...]] = {
    "workstation_path": _WORKSTATION_PATTERNS,
    "email": (_EMAIL_PATTERN,),
    "secret": _SECRET_PATTERNS,
    "session_url": (_SESSION_URL_PATTERN,),
}


@dataclass(frozen=True)
class Finding:
    rule: str
    where: str


def format_finding(f: Finding) -> str:
    """One report line: the rule and the place, never the matched text."""
    return f"{f.rule}\t{f.where}"


@dataclass(frozen=True, eq=False)
class Rules:
    patterns: dict = field(default_factory=lambda: PATTERNS)
    deny_emails: frozenset = frozenset()
    deny_terms: tuple = ()
    corpus_windows: frozenset = frozenset()
    corpus_hashes: frozenset = frozenset()
    skipped: frozenset = frozenset()


def windows(text: str) -> set[tuple[str, str, str]]:
    """Every run of three consecutive stripped lines of at least 25 characters."""
    lines = [line.strip() for line in text.splitlines()]
    found = set()
    for i in range(len(lines) - 2):
        trio = (lines[i], lines[i + 1], lines[i + 2])
        if all(len(line) >= 25 for line in trio):
            found.add(trio)
    return found


def build_rules(
    deny_emails: Iterable[str] = (),
    deny_terms: Iterable[str] = (),
    corpus_texts: Iterable[str] = (),
    corpus_blobs: Iterable[bytes] = (),
    skipped: Iterable[str] = (),
) -> Rules:
    corpus_windows: set = set()
    for text in corpus_texts:
        corpus_windows |= windows(text)
    return Rules(
        deny_emails=frozenset(e.strip().casefold() for e in deny_emails if e.strip()),
        deny_terms=tuple(t.strip().casefold() for t in deny_terms if t.strip()),
        corpus_windows=frozenset(corpus_windows),
        corpus_hashes=frozenset(hashlib.sha256(b).hexdigest() for b in corpus_blobs if b),
        skipped=frozenset(skipped),
    )


def is_allowed_email(address: str) -> bool:
    address = address.casefold()
    return address in ALLOWED_EMAILS or address.rpartition("@")[2] in ALLOWED_EMAIL_DOMAINS


def _marked_rules(line: str) -> set[str]:
    """Rule names named by an inline allow marker on the line."""
    names: set[str] = set()
    for match in _MARKER_PATTERN.finditer(line):
        for token in re.split(r"[ ,]+", match.group(1).strip()):
            if token in ALL_RULES:
                names.add(token)
            else:
                break
    return names


def _unlisted_email(variants: list[str], rules: Rules) -> bool:
    """True when any text of the line holds an address that is neither allow-listed nor an owner address."""
    for text in variants:
        for match in rules.patterns["email"][0].finditer(text):
            address = match.group(0).casefold()
            if not (address in rules.deny_emails or is_allowed_email(address)):
                return True
    return False


def _line_hits(line: str, rules: Rules) -> list[str]:
    """Rule names that hit one line, each once, in report order."""
    hits: list[str] = []
    # A JSON or log line quotes a line break as backslash-n: the n would hide the start of a path or an address behind it
    variants = [line]
    if "\\" in line:
        unescaped = _ESCAPE_PATTERN.sub(" ", line)
        if unescaped != line:
            variants.append(unescaped)
    for pattern in rules.patterns["workstation_path"]:
        if any(pattern.search(text) for text in variants):
            hits.append("workstation_path")
            break
    folded = line.casefold()
    if rules.deny_emails and any(address in folded for address in rules.deny_emails):
        hits.append("owner_email")
    if _unlisted_email(variants, rules):
        hits.append("email")
    if rules.deny_terms and any(term in folded for term in rules.deny_terms):
        hits.append("owner_term")
    for pattern in rules.patterns["secret"]:
        if pattern.search(line):
            hits.append("secret")
            break
    if rules.patterns["session_url"][0].search(line):
        hits.append("session_url")
    return hits


def _decode(data: bytes) -> str:
    """Text of a blob, whatever its encoding.

    UTF-32 and UTF-16 (with or without a byte order mark; recognised by the share of NUL bytes) are decoded as
    such. Any other data with NUL bytes (a binary file, or a text file that starts with a NUL to hide from the
    scan) is read like `strings` does: the NULs become line breaks, so the text runs in it are still scanned.
    """
    if data[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        return data.decode("utf-32", errors="replace")
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    head = data[:BINARY_PROBE_BYTES]
    if b"\x00" in head:
        half = max(len(head) // 2, 1)
        if head[1::2].count(0) * 10 > half * 3:
            return data.decode("utf-16-le", errors="replace").replace("\x00", "")
        if head[0::2].count(0) * 10 > half * 3:
            return data.decode("utf-16-be", errors="replace").replace("\x00", "")
        return data.decode("utf-8", errors="replace").replace("\x00", "\n")
    return data.decode("utf-8", errors="replace")


def _scan_lines(text: str, where_of, rules: Rules, allowed: list[Finding] | None) -> list[Finding]:
    found: list[Finding] = []
    for number, line in enumerate(text.splitlines(), 1):
        hits = _line_hits(line, rules)
        if not hits:
            continue
        marked = _marked_rules(line) if "scan:" in line else set()
        for rule in hits:
            if rule in rules.skipped:
                continue
            finding = Finding(rule, where_of(number))
            if rule in marked:
                if allowed is not None:
                    allowed.append(finding)
            else:
                found.append(finding)
    return found


def _is_vendor_file(path: str, data: bytes) -> bool:
    """True for a licence-restricted vendor file: a vendor suffix or magic, except a FIXTURE_SUFFIXES file under tests/fixtures/."""
    if data.startswith(VENDOR_MAGICS):
        return True
    name = path.casefold()
    if name.endswith(FIXTURE_SUFFIXES) and path.startswith(FIXTURES_PREFIX):
        return False
    return name.endswith(VENDOR_SUFFIXES)


def _name_findings(name: str, where: str, rules: Rules) -> list[Finding]:
    """Text-rule findings for a file, folder or ref name: the name is published like the content."""
    return [Finding(rule, where) for rule in _line_hits(name, rules) if rule not in rules.skipped]


def scan_alias(path: str, data: bytes, rules: Rules) -> list[Finding]:
    """Findings for a further path a blob has in the history: the vendor-file decision and the name itself."""
    found = _name_findings(path, path, rules)
    if "vendor_file" not in rules.skipped and _is_vendor_file(path, data):
        found.append(Finding("vendor_file", path))
    return found


def scan_blob(path: str, data: bytes, rules: Rules, allowed: list[Finding] | None = None) -> list[Finding]:
    """Findings for one file or blob; hits an inline marker suppresses are appended to `allowed` when given."""
    found: list[Finding] = []

    def add(rule: str) -> None:
        if rule not in rules.skipped:
            found.append(Finding(rule, path))

    if _is_vendor_file(path, data):
        add("vendor_file")
    found.extend(_name_findings(path, path, rules))
    if len(data) > MAX_BLOB_BYTES:
        add("large_blob")
        return found
    if data and rules.corpus_hashes and hashlib.sha256(data).hexdigest() in rules.corpus_hashes:
        add("copied_content")
    text = _decode(data)
    if rules.corpus_windows and not windows(text).isdisjoint(rules.corpus_windows):
        if not any(f.rule == "copied_content" for f in found):
            add("copied_content")
    found.extend(_scan_lines(text, lambda n: f"{path}:{n}", rules, allowed))
    return found


def scan_message(sha: str, text: str, rules: Rules, allowed: list[Finding] | None = None, kind: str = "commit") -> list[Finding]:
    """Findings for one commit or tag message: the session trailer plus the text rules."""
    where = f"{kind}:{sha[:12]}"
    found: list[Finding] = []
    body: list[str] = []
    for line in text.splitlines():
        if _TRAILER_PATTERN.match(line):
            if "session_trailer" not in rules.skipped and Finding("session_trailer", where) not in found:
                found.append(Finding("session_trailer", where))
        else:
            body.append(line)
    found.extend(_scan_lines("\n".join(body), lambda n: where, rules, allowed))
    return _unique(found)


def scan_identity(sha: str, name: str, email: str, rules: Rules, kind: str = "commit") -> list[Finding]:
    """commit_identity when an author, committer or tagger address is not allow-listed, or is a deny email, or a name holds a deny term."""
    bad = email.casefold() in rules.deny_emails or not is_allowed_email(email)
    folded = name.casefold()
    bad = bad or any(term in folded for term in rules.deny_terms)
    if bad and "commit_identity" not in rules.skipped:
        return [Finding("commit_identity", f"{kind}:{sha[:12]}")]
    return []


def scan_ref(name: str, rules: Rules | None = None) -> list[Finding]:
    """ref_name for an agent branch, plus the text-rule findings for the name when rules are given (a pushed ref name is published)."""
    found = [Finding("ref_name", f"ref:{name}")] if _REF_PATTERN.search(name) else []
    if rules is not None:
        found.extend(_name_findings(name, f"ref:{name}", rules))
    return found


def _unique(findings: Iterable[Finding]) -> list[Finding]:
    return list(dict.fromkeys(findings))


# ── Reading the deny lists and the corpus ───────────────────────────────────────────────────────


class UsageError(Exception):
    """A problem with how the scan was called; main() reports it and exits 2."""


def _git(repo: Path | str, *args: str, input: bytes | None = None) -> bytes:
    """Run git in repo and return stdout; raise UsageError on a failure."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
            input=input,
            capture_output=True,
            check=False,
            stdin=None if input is not None else subprocess.DEVNULL,
        )
    except OSError as error:
        raise UsageError(f"cannot run git: {error}") from error
    if done.returncode != 0:
        reason = done.stderr.decode("utf-8", errors="replace").strip().splitlines()
        raise UsageError(f"git {args[0]} failed in {repo}: {reason[-1] if reason else 'no detail'}")
    return done.stdout


def _git_try(repo: Path | str, *args: str) -> str:
    """Like _git but an empty string when git fails (an unset config key, for example)."""
    try:
        return _git(repo, *args).decode("utf-8", errors="replace")
    except UsageError:
        return ""


def collect_deny_emails(repos: Iterable[Path | str]) -> set[str]:
    """Every commit address and user.email of the given repositories, minus the allow-listed ones."""
    found: set[str] = set()
    for repo in repos:
        log = _git(repo, "log", "--all", "--format=%ae%n%ce").decode("utf-8", errors="replace")
        found.update(line.strip().casefold() for line in log.splitlines() if line.strip())
        configured = _git_try(repo, "config", "user.email").strip().casefold()
        if configured:
            found.add(configured)
    return {address for address in found if not is_allowed_email(address)}


def read_terms(files: Iterable[Path | str]) -> list[str]:
    terms: list[str] = []
    for file in files:
        try:
            text = Path(file).read_text(encoding="utf-8")
        except OSError as error:
            raise UsageError(f"cannot read the deny file {file}: {error.strerror or error}") from error
        terms.extend(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
    return terms


def collect_corpus(dirs: Iterable[Path | str]) -> tuple[list[str], list[bytes]]:
    """Texts and bytes of every .kicad_sym / .kicad_mod under Custom and WurthElektronik, and of the same members of every vendor zip."""
    texts: list[str] = []
    blobs: list[bytes] = []

    def take(data: bytes) -> None:
        blobs.append(data)
        texts.append(data.decode("utf-8", errors="replace"))

    for root in map(Path, dirs):
        for sub in ("Custom", "WurthElektronik"):
            base = root / sub
            if not base.is_dir():
                continue
            for file in sorted(base.rglob("*")):
                if file.suffix.casefold() in (".kicad_sym", ".kicad_mod") and file.is_file():
                    try:
                        take(file.read_bytes())
                    except OSError:
                        continue
        examples = root / "downloaded_examples"
        if examples.is_dir():
            for archive_path in sorted(examples.glob("*.zip")):
                try:
                    with zipfile.ZipFile(archive_path) as archive:
                        for info in archive.infolist():
                            if info.filename.casefold().endswith((".kicad_sym", ".kicad_mod")) and info.file_size <= MAX_ZIP_MEMBER_BYTES:
                                take(archive.read(info))
                except (OSError, zipfile.BadZipFile):
                    continue
    return texts, blobs


# ── Walking git ─────────────────────────────────────────────────────────────────────────────────


def tree_files(repo: Path | str, prefixes: Sequence[str] = ()) -> list[str]:
    """Repository-relative paths of tracked and untracked files that are not ignored, limited to the prefixes."""
    raw = _git(repo, "ls-files", "-co", "--exclude-standard", "-z").decode("utf-8", errors="replace")
    paths = sorted({p for p in raw.split("\0") if p})
    if not prefixes:
        return paths
    wanted = [p.strip("/") for p in prefixes]
    return [p for p in paths if any(p == w or p.startswith(w + "/") for w in wanted)]


def history_commits(repo: Path | str) -> list[tuple[str, str, str, str, str, str]]:
    """(sha, author name, author email, committer name, committer email, message) of every commit reachable from any ref."""
    raw = _git(repo, "log", "--all", "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B%x01").decode("utf-8", errors="replace")
    commits = []
    for record in raw.split("\x01"):
        record = record.lstrip("\n")
        if not record.strip():
            continue
        parts = record.split("\0", 5)
        if len(parts) == 6:
            commits.append(tuple(parts))
    return commits


def history_refs(repo: Path | str) -> list[str]:
    out = _git(repo, "for-each-ref", "--format=%(refname)").decode("utf-8", errors="replace")
    return [line.strip() for line in out.splitlines() if line.strip()]


_TAGGER_PATTERN = re.compile(r"^tagger (.*?) ?<([^>]*)>", re.MULTILINE)


def history_tags(repo: Path | str) -> list[tuple[str, str, str, str]]:
    """(object id, tagger name, tagger email, message) of every annotated tag object reachable from any ref.

    Nested tags (a tag of a tag) are found too, because the object walk lists every tag object it passes.
    """
    listing = _git(repo, "rev-list", "--objects", "--all").decode("utf-8", errors="replace")
    shas = list(dict.fromkeys(row.partition(" ")[0] for row in listing.splitlines() if row.strip()))
    if not shas:
        return []
    kinds = _git(repo, "cat-file", "--batch-check=%(objecttype) %(objectname)", input="\n".join(shas).encode("ascii") + b"\n")
    tags: list[tuple[str, str, str, str]] = []
    for row in kinds.decode("utf-8", errors="replace").splitlines():
        kind, _, sha = row.partition(" ")
        if kind != "tag":
            continue
        raw = _git(repo, "cat-file", "tag", sha).decode("utf-8", errors="replace")
        head, _, message = raw.partition("\n\n")
        tagger = _TAGGER_PATTERN.search(head)
        name, email = (tagger.group(1), tagger.group(2)) if tagger else ("", "")
        tags.append((sha, name, email, message))
    return tags


def has_commits(repo: Path | str) -> bool:
    return bool(_git(repo, "rev-list", "--all", "-n", "1").strip())


def blob_paths(repo: Path | str) -> dict[str, list[str]]:
    """Every path each blob had in any commit reachable from any ref, by blob id (from the raw diff of every commit)."""
    raw = _git(repo, "log", "--all", "--raw", "--no-abbrev", "--no-renames", "-z", "--format=", "--root")
    tokens = raw.split(b"\0")
    found: dict[str, dict[str, None]] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i].lstrip(b"\n")
        if token.startswith(b":") and i + 1 < len(tokens):
            fields = token.split()
            if len(fields) >= 5 and fields[4] != b"D":
                found.setdefault(fields[3].decode("ascii"), {})[tokens[i + 1].decode("utf-8", errors="replace")] = None
            i += 2
        else:
            i += 1
    return {sha: list(paths) for sha, paths in found.items()}


def history_blobs(repo: Path | str) -> Iterator[tuple[str, bytes, list[str]]]:
    """Every blob reachable from any ref once, as (a path it had, its bytes, its other paths), through one git cat-file --batch process.

    A blob over MAX_BLOB_BYTES is cut at one byte past the cap (enough for scan_blob to report large_blob).
    """
    listing = _git(repo, "rev-list", "--objects", "--all").decode("utf-8", errors="replace")
    paths: dict[str, str] = {}
    for row in listing.splitlines():
        sha, _, path = row.partition(" ")
        if path and sha not in paths:
            paths[sha] = path
    if not paths:
        return
    aliases = blob_paths(repo)
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    def feed() -> None:
        try:
            for sha in paths:
                process.stdin.write(sha.encode("ascii") + b"\n")
            process.stdin.close()
        except OSError:
            pass

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    out = process.stdout
    try:
        while True:
            header = out.readline()
            if not header:
                break
            fields = header.split()
            if len(fields) < 3:
                continue  # "<sha> missing"
            sha, kind, size = fields[0].decode("ascii"), fields[1], int(fields[2])
            keep = min(size, MAX_BLOB_BYTES + 1) if kind == b"blob" else 0
            data = out.read(keep)
            remaining = size - keep
            while remaining > 0:
                chunk = out.read(min(remaining, 1 << 20))
                if not chunk:
                    break
                remaining -= len(chunk)
            out.read(1)  # the newline after the content
            if kind == b"blob":
                first = paths[sha]
                yield first, data, [other for other in aliases.get(sha, ()) if other != first]
    finally:
        if process.stdout:
            process.stdout.close()
        process.wait()
        writer.join(timeout=5)


# ── Command line ────────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prepublish_scan.py", description="Scan a repository for private or licence-restricted content before it is published.")
    p.add_argument("--repo", help="repository to scan (default: the one around the working directory)")
    p.add_argument("--tree", action="store_true", help="scan the working tree")
    p.add_argument("--history", action="store_true", help="scan every blob, commit message, identity and ref name")
    p.add_argument("--path", action="append", default=[], metavar="PREFIX", help="limit the tree scan to this file or folder (repeatable)")
    p.add_argument("--deny-emails-from-repo", action="append", default=[], metavar="DIR", help="treat every commit address of this repository as the owner's (repeatable)")
    p.add_argument("--deny-terms-file", action="append", default=[], metavar="FILE", help="file with one owner term per line (repeatable)")
    p.add_argument("--corpus", action="append", default=[], metavar="DIR", help="library collection to check for copied text (repeatable)")
    p.add_argument("--skip-rule", action="append", default=[], metavar="NAME", help="turn a rule off (repeatable)")
    p.add_argument("--list-allowed", action="store_true", help="also print every hit an inline marker suppressed")
    return p


def _resolve_repo(arg: str | None) -> Path:
    where = arg or "."
    if arg and not Path(arg).is_dir():
        raise UsageError(f"not a folder: {arg}")
    top = _git(where, "rev-parse", "--show-toplevel").decode("utf-8", errors="replace").strip()
    if not top:
        raise UsageError("no git repository here")
    return Path(top)


def _config_values(repo: Path, key: str) -> list[str]:
    return [v.strip() for v in _git_try(repo, "config", "--get-all", key).splitlines() if v.strip()]


def _build_rules(args, repo: Path) -> Rules:
    deny_repos = list(args.deny_emails_from_repo)
    term_files = list(args.deny_terms_file)
    if not deny_repos and not term_files:
        deny_repos = _config_values(repo, "prepublish.denyEmailsFromRepo")
        term_files = _config_values(repo, "prepublish.denyTermsFile")
    emails = collect_deny_emails(deny_repos)
    terms = read_terms(term_files)
    texts, blobs = collect_corpus(args.corpus)
    if not emails and not terms:
        # "clean" must not claim more than was checked: the owner-specific rules had nothing to match
        print(NO_DENY_LIST_NOTE, file=sys.stderr)
    unknown = [r for r in args.skip_rule if r not in ALL_RULES]
    if unknown:
        raise UsageError(f"unknown rule name: {unknown[0]}")
    return build_rules(emails, terms, texts, blobs, args.skip_rule)


def run(args) -> tuple[list[Finding], list[Finding], tuple[int, int, int]]:
    repo = _resolve_repo(args.repo)
    do_tree = args.tree or not args.history
    do_history = args.history or not args.tree
    rules = _build_rules(args, repo)
    if do_history and not has_commits(repo):
        raise UsageError("nothing to scan: the repository has no commits")
    findings: list[Finding] = []
    allowed: list[Finding] = []
    files = blobs = commits = 0
    if do_tree:
        for path in tree_files(repo, args.path):
            full = repo / path
            if not full.is_file() or full.is_symlink():
                continue
            try:
                data = full.read_bytes()
            except OSError:
                continue
            files += 1
            findings.extend(scan_blob(path, data, rules, allowed))
    if do_history:
        for path, data, others in history_blobs(repo):
            blobs += 1
            findings.extend(scan_blob(path, data, rules, allowed))
            for other in others:
                findings.extend(scan_alias(other, data, rules))
        for sha, an, ae, cn, ce, message in history_commits(repo):
            commits += 1
            findings.extend(scan_identity(sha, an, ae, rules))
            findings.extend(scan_identity(sha, cn, ce, rules))
            findings.extend(scan_message(sha, message, rules, allowed))
        for sha, name, email, message in history_tags(repo):
            if email:
                findings.extend(scan_identity(sha, name, email, rules, "tag"))
            findings.extend(scan_message(sha, message, rules, allowed, "tag"))
        for ref in history_refs(repo):
            findings.extend(scan_ref(ref, rules))
    return _unique(findings), _unique(allowed), (files, blobs, commits)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, io.UnsupportedOperation):
            pass
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return int(stop.code) if isinstance(stop.code, int) else 2
    try:
        findings, allowed, (files, blobs, commits) = run(args)
    except UsageError as error:
        print(f"prepublish_scan: {error}", file=sys.stderr)
        return 2
    for finding in findings:
        print(format_finding(finding))
    if args.list_allowed:
        for finding in allowed:
            print(f"allowed-by-marker\t{finding.rule}\t{finding.where}")
        print(f"prepublish_scan: {len(allowed)} allowed by marker")
    if findings:
        print(f"prepublish_scan: {len(findings)} finding(s)")
        return 1
    print(f"prepublish_scan: clean ({files} files, {blobs} blobs, {commits} commits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
