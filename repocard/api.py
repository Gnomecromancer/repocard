"""Fetch repo data from GitHub API (unauthenticated, 60 req/hr limit)."""

from __future__ import annotations
import json
import re
import urllib.request
from dataclasses import dataclass, field


_BASE = "https://api.github.com"


@dataclass
class RepoData:
    owner: str
    name: str
    full_name: str
    description: str
    stars: int
    forks: int
    watchers: int
    open_issues: int
    language: str | None
    topics: list[str]
    languages: dict[str, int]  # name → bytes
    url: str
    is_fork: bool
    license_name: str | None


def _get(url: str, token: str | None = None) -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _get_with_headers(url: str, token: str | None = None) -> tuple[dict | list, dict]:
    """Return (body, response_headers) for endpoints that need Link pagination."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read())
        resp_headers = dict(r.headers)
    return body, resp_headers


def _parse_next_link(link_header: str | None) -> str | None:
    """Extract the 'next' URL from a GitHub Link header, or None if absent."""
    if not link_header:
        return None
    for part in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="next"', part.strip())
        if match:
            return match.group(1)
    return None


def fetch(owner: str, repo: str, token: str | None = None) -> RepoData:
    data = _get(f"{_BASE}/repos/{owner}/{repo}", token=token)
    langs = _get(f"{_BASE}/repos/{owner}/{repo}/languages", token=token)

    lic = data.get("license") or {}
    return RepoData(
        owner=data["owner"]["login"],
        name=data["name"],
        full_name=data["full_name"],
        description=data.get("description") or "",
        stars=data["stargazers_count"],
        forks=data["forks_count"],
        watchers=data["subscribers_count"],
        open_issues=data["open_issues_count"],
        language=data.get("language"),
        topics=data.get("topics", []),
        languages=langs,
        url=data["html_url"],
        is_fork=data["fork"],
        license_name=lic.get("spdx_id") or lic.get("name"),
    )


def fetch_all_repos(
    owner: str,
    token: str | None = None,
    include_forks: bool = False,
) -> list[RepoData]:
    """Fetch all public repos for *owner*, following pagination via Link header.

    Forks are skipped unless *include_forks* is True.  Repos whose language
    endpoint fails are skipped with a warning printed to stderr.
    """
    import sys

    repos: list[RepoData] = []
    url: str | None = f"{_BASE}/users/{owner}/repos?per_page=100&type=public"

    while url:
        page_data, resp_headers = _get_with_headers(url, token=token)
        assert isinstance(page_data, list)
        url = _parse_next_link(resp_headers.get("Link") or resp_headers.get("link"))

        for item in page_data:
            if item.get("fork") and not include_forks:
                continue
            repo_name = item["name"]
            try:
                langs = _get(
                    f"{_BASE}/repos/{owner}/{repo_name}/languages", token=token
                )
            except Exception as exc:
                print(
                    f"warning: could not fetch languages for {owner}/{repo_name}: {exc}",
                    file=sys.stderr,
                )
                langs = {}

            lic = item.get("license") or {}
            repos.append(
                RepoData(
                    owner=item["owner"]["login"],
                    name=item["name"],
                    full_name=item["full_name"],
                    description=item.get("description") or "",
                    stars=item["stargazers_count"],
                    forks=item["forks_count"],
                    watchers=item["subscribers_count"],
                    open_issues=item["open_issues_count"],
                    language=item.get("language"),
                    topics=item.get("topics", []),
                    languages=langs,
                    url=item["html_url"],
                    is_fork=item["fork"],
                    license_name=lic.get("spdx_id") or lic.get("name"),
                )
            )

    return repos
