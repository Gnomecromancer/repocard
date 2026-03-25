"""Tests for the serve command HTTP handler — no real GitHub calls."""
import threading
import time
import urllib.request
from unittest.mock import patch

from repocard.api import RepoData


def _fake_repo(owner="alice", repo="myrepo") -> RepoData:
    return RepoData(
        owner=owner, name=repo, full_name=f"{owner}/{repo}",
        description="test", stars=1, forks=0, watchers=0, open_issues=0,
        language="Python", topics=[], languages={"Python": 1000},
        url="https://github.com/alice/myrepo", is_fork=False, license_name="MIT",
    )


def _start_server(port: int):
    """Start repocard serve in a thread, patch fetch to avoid network."""
    from repocard.cli import main
    from click.testing import CliRunner

    runner = CliRunner()
    t = threading.Thread(
        target=lambda: runner.invoke(main, ["serve", "--port", str(port), "--host", "127.0.0.1"]),
        daemon=True,
    )
    t.start()
    time.sleep(0.3)  # let server bind


def test_serve_returns_svg():
    port = 19765
    with patch("repocard.cli.fetch", return_value=_fake_repo()):
        _start_server(port)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/alice/myrepo", timeout=3)
        assert resp.status == 200
        assert "svg" in resp.headers.get("Content-Type", "")
        body = resp.read().decode()
        assert "<svg" in body
        assert "alice/myrepo" in body


def test_serve_bad_path_returns_400():
    import urllib.error
    port = 19766
    with patch("repocard.cli.fetch", return_value=_fake_repo()):
        _start_server(port)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/badpath", timeout=3)
            assert False, "expected error"
        except urllib.error.HTTPError as e:
            assert e.code == 400
