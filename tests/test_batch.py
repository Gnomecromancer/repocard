"""Tests for the batch command and fetch_all_repos — no real network calls."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from repocard.api import RepoData, _parse_next_link, fetch_all_repos
from repocard.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_payload(name: str, owner: str = "alice", fork: bool = False) -> dict:
    """Minimal GitHub API list-repos payload entry."""
    return {
        "name": name,
        "full_name": f"{owner}/{name}",
        "description": f"{name} description",
        "stargazers_count": 10,
        "forks_count": 2,
        "subscribers_count": 1,
        "open_issues_count": 0,
        "language": "Python",
        "topics": [],
        "html_url": f"https://github.com/{owner}/{name}",
        "fork": fork,
        "license": {"spdx_id": "MIT", "name": "MIT License"},
        "owner": {"login": owner},
    }


def _make_repo(name: str = "myrepo", owner: str = "alice", fork: bool = False) -> RepoData:
    return RepoData(
        owner=owner, name=name, full_name=f"{owner}/{name}",
        description="test", stars=10, forks=2, watchers=1, open_issues=0,
        language="Python", topics=[], languages={"Python": 5000},
        url=f"https://github.com/{owner}/{name}", is_fork=fork, license_name="MIT",
    )


# ---------------------------------------------------------------------------
# Unit tests for _parse_next_link
# ---------------------------------------------------------------------------

def test_parse_next_link_present():
    header = '<https://api.github.com/users/alice/repos?page=2>; rel="next", <https://api.github.com/users/alice/repos?page=3>; rel="last"'
    assert _parse_next_link(header) == "https://api.github.com/users/alice/repos?page=2"


def test_parse_next_link_absent():
    header = '<https://api.github.com/users/alice/repos?page=1>; rel="first"'
    assert _parse_next_link(header) is None


def test_parse_next_link_none():
    assert _parse_next_link(None) is None


# ---------------------------------------------------------------------------
# Unit tests for fetch_all_repos
# ---------------------------------------------------------------------------

def _urlopen_side_effect(pages: list[list[dict]], langs: dict | None = None):
    """
    Build a side-effect for urllib.request.urlopen that:
      - Returns paginated repo lists for /users/.*/repos URLs
      - Returns language dicts for /repos/.*/languages URLs
      Link headers are synthesised for all pages except the last.
    """
    if langs is None:
        langs = {"Python": 5000}

    call_tracker = {"repo_page": 0}

    def side_effect(req, timeout=10):
        url = req.full_url

        if "/languages" in url:
            body = json.dumps(langs).encode()
            mock_resp = MagicMock()
            mock_resp.read.return_value = body
            mock_resp.headers = {}
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        # Repo list page
        idx = call_tracker["repo_page"]
        call_tracker["repo_page"] += 1
        page_data = pages[idx] if idx < len(pages) else []

        body = json.dumps(page_data).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = body

        # Build Link header
        if idx + 1 < len(pages):
            next_url = f"https://api.github.com/users/alice/repos?page={idx + 2}"
            link = f'<{next_url}>; rel="next"'
        else:
            link = None

        mock_resp.headers = {"link": link} if link else {}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    return side_effect


def test_fetch_all_repos_single_page():
    pages = [[_repo_payload("alpha"), _repo_payload("beta")]]
    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect(pages)):
        repos = fetch_all_repos("alice")
    assert len(repos) == 2
    assert repos[0].name == "alpha"
    assert repos[1].name == "beta"


def test_fetch_all_repos_multi_page():
    pages = [
        [_repo_payload("repo1"), _repo_payload("repo2")],
        [_repo_payload("repo3")],
    ]
    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect(pages)):
        repos = fetch_all_repos("alice")
    assert len(repos) == 3
    assert {r.name for r in repos} == {"repo1", "repo2", "repo3"}


def test_fetch_all_repos_skips_forks_by_default():
    pages = [[_repo_payload("owned"), _repo_payload("forked", fork=True)]]
    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect(pages)):
        repos = fetch_all_repos("alice")
    assert len(repos) == 1
    assert repos[0].name == "owned"


def test_fetch_all_repos_include_forks():
    pages = [[_repo_payload("owned"), _repo_payload("forked", fork=True)]]
    with patch("urllib.request.urlopen", side_effect=_urlopen_side_effect(pages)):
        repos = fetch_all_repos("alice", include_forks=True)
    assert len(repos) == 2


def test_fetch_all_repos_language_failure_skips_repo(capsys):
    """A languages fetch error should emit a warning but not abort."""
    pages = [[_repo_payload("good"), _repo_payload("bad")]]

    call_tracker = {"repo_page": 0, "lang_call": 0}

    def side_effect(req, timeout=10):
        url = req.full_url
        if "/languages" in url:
            call_tracker["lang_call"] += 1
            if call_tracker["lang_call"] == 2:
                raise OSError("network failure")
            body = json.dumps({"Python": 5000}).encode()
            mock_resp = MagicMock()
            mock_resp.read.return_value = body
            mock_resp.headers = {}
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        idx = call_tracker["repo_page"]
        call_tracker["repo_page"] += 1
        page_data = pages[idx] if idx < len(pages) else []
        body = json.dumps(page_data).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.headers = {}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=side_effect):
        repos = fetch_all_repos("alice")

    # Both repos still returned (bad one gets empty languages dict)
    assert len(repos) == 2
    assert repos[1].languages == {}
    captured = capsys.readouterr()
    assert "warning" in captured.err


# ---------------------------------------------------------------------------
# Integration tests for the `batch` CLI command
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_repos():
    return [_make_repo("alpha"), _make_repo("beta")]


def test_batch_writes_svgs(tmp_path, fake_repos):
    runner = CliRunner()
    with patch("repocard.cli.fetch_all_repos", return_value=fake_repos):
        result = runner.invoke(
            main,
            ["batch", "alice", "--output-dir", str(tmp_path)],
        )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "alpha.svg").exists()
    assert (tmp_path / "beta.svg").exists()
    assert "<svg" in (tmp_path / "alpha.svg").read_text(encoding="utf-8")


def test_batch_prints_progress(tmp_path, fake_repos):
    runner = CliRunner()
    with patch("repocard.cli.fetch_all_repos", return_value=fake_repos):
        result = runner.invoke(
            main,
            ["batch", "alice", "--output-dir", str(tmp_path)],
        )
    assert "alice/alpha" in result.output
    assert "alice/beta" in result.output


def test_batch_creates_output_dir(tmp_path, fake_repos):
    new_dir = tmp_path / "nested" / "cards"
    runner = CliRunner()
    with patch("repocard.cli.fetch_all_repos", return_value=fake_repos):
        result = runner.invoke(
            main,
            ["batch", "alice", "--output-dir", str(new_dir)],
        )
    assert result.exit_code == 0
    assert new_dir.is_dir()


def test_batch_no_repos(tmp_path):
    runner = CliRunner()
    with patch("repocard.cli.fetch_all_repos", return_value=[]):
        result = runner.invoke(
            main,
            ["batch", "alice", "--output-dir", str(tmp_path)],
        )
    assert result.exit_code == 0
    assert "nothing to do" in result.output


def test_batch_api_error_exits_nonzero(tmp_path):
    runner = CliRunner()
    with patch("repocard.cli.fetch_all_repos", side_effect=RuntimeError("rate limited")):
        result = runner.invoke(
            main,
            ["batch", "alice", "--output-dir", str(tmp_path)],
        )
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "error" in (result.exception and str(result.exception) or "")


def test_batch_include_forks_flag(tmp_path):
    runner = CliRunner()
    with patch("repocard.cli.fetch_all_repos", return_value=[_make_repo("myfork", fork=True)]) as mock_fn:
        result = runner.invoke(
            main,
            ["batch", "alice", "--output-dir", str(tmp_path), "--include-forks"],
        )
    assert result.exit_code == 0
    mock_fn.assert_called_once_with("alice", token=None, include_forks=True)


def test_batch_token_passed_through(tmp_path, fake_repos):
    runner = CliRunner()
    with patch("repocard.cli.fetch_all_repos", return_value=fake_repos) as mock_fn:
        result = runner.invoke(
            main,
            ["batch", "alice", "--output-dir", str(tmp_path), "--token", "ghp_test"],
        )
    assert result.exit_code == 0
    mock_fn.assert_called_once_with("alice", token="ghp_test", include_forks=False)


def test_batch_skips_render_failure(tmp_path):
    """If render_svg raises for one repo, it should be skipped; others succeed."""
    repos = [_make_repo("good"), _make_repo("bad")]
    runner = CliRunner()

    original_render = None

    def flaky_render(data):
        if data.name == "bad":
            raise ValueError("render exploded")
        import importlib
        render_mod = importlib.import_module("repocard.render")
        return render_mod.render_svg(data)

    with patch("repocard.cli.fetch_all_repos", return_value=repos):
        with patch("repocard.cli.render_svg", side_effect=flaky_render):
            result = runner.invoke(
                main,
                ["batch", "alice", "--output-dir", str(tmp_path)],
            )

    assert result.exit_code == 0
    assert (tmp_path / "good.svg").exists()
    assert not (tmp_path / "bad.svg").exists()
    assert "warning" in result.output.lower() or "skipping" in result.output.lower()
