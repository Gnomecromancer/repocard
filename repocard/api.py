"""Fetch repo data from GitHub API (unauthenticated, 60 req/hr limit)."""

from __future__ import annotations
import json
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


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def fetch(owner: str, repo: str) -> RepoData:
    data = _get(f"{_BASE}/repos/{owner}/{repo}")
    langs = _get(f"{_BASE}/repos/{owner}/{repo}/languages")

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
