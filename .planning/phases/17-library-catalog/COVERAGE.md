# API Coverage — GitHub (REST API and git over HTTPS)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

Phase 17 integrates two GitHub surfaces: one unauthenticated REST endpoint (repository metadata for Add by URL, D-04) and git's smart HTTP protocol against github.com (clone, fetch, ls-remote through the hardened runner, CAT-11). The capability surface below is the part of GitHub a library catalog could use.

| capability | decision | reason |
|---|---|---|
| repos.get (size, default branch, licence, private, archived) | INTEGRATE | |
| git ls-remote (branch heads, default branch through --symref) | INTEGRATE | |
| git shallow clone (depth 1, single branch, no tags) | INTEGRATE | |
| git shallow fetch of the recorded branch | INTEGRATE | |
| repos.getLicense (licence text through the API) | OPT-OUT | not needed: the licence file is read from the downloaded copy (D-04), which saves a call against the 60 per hour limit |
| repos.getContent and the git trees API (browse files before download) | OPT-OUT | not needed: every check runs on the staging download (D-04, D-23) |
| repos.listBranches and getBranch | OPT-OUT | not needed: ls-remote gives the branch head without the API rate limit (D-12) |
| repos.listCommits and compareCommits (changes between versions) | OPT-OUT | not needed: the Update preview is computed locally from the fetched commit (D-08) |
| repos.listTags and releases (pin a library to a tag or release) | OPT-OUT | explicitly out of scope: pinning to a tag or commit is a deferred idea in 17-CONTEXT.md |
| search.repos (discover KiCad libraries) | OPT-OUT | not needed: the curated list plus Add by URL cover CAT-01 and CAT-03; a remote list is FUT-04 |
| conditional requests (ETag, 304) | OPT-OUT | not needed: the update check uses ls-remote, not the API (D-12) |
| rate_limit endpoint | OPT-OUT | not needed: a rate-limited answer is shown as unknown and never blocks an Add (D-04) |
| authentication (tokens, OAuth, GitHub Apps, credential helpers) | OPT-OUT | explicitly out of scope: public repositories only, credentials are refused (CAT-03, CAT-11) |
| private repositories | OPT-OUT | explicitly out of scope: refused with a message (CAT-03) |
| Git LFS batch API | OPT-OUT | explicitly out of scope: libraries that keep files in Git LFS are refused (D-13) |
| write operations (push, issues, forks, pull requests) | OPT-OUT | not needed: catalog libraries are read-only managed copies (D-07) |
| other hosts (GitLab, plain git URLs) | OPT-OUT | explicitly out of scope: FUT-03 |
