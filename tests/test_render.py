"""Unit tests for SVG rendering — no network calls."""
from repocard.api import RepoData
from repocard.render import render_svg


def _make_repo(**kwargs) -> RepoData:
    defaults = dict(
        owner="alice",
        name="myrepo",
        full_name="alice/myrepo",
        description="A test repo",
        stars=42,
        forks=7,
        watchers=3,
        open_issues=1,
        language="Python",
        topics=["python", "testing"],
        languages={"Python": 9000, "Shell": 500},
        url="https://github.com/alice/myrepo",
        is_fork=False,
        license_name="MIT",
    )
    defaults.update(kwargs)
    return RepoData(**defaults)


def test_svg_is_valid_xml():
    import xml.etree.ElementTree as ET
    repo = _make_repo()
    svg = render_svg(repo)
    ET.fromstring(svg)  # raises if invalid XML


def test_svg_contains_repo_name():
    repo = _make_repo()
    svg = render_svg(repo)
    assert "alice/myrepo" in svg


def test_svg_contains_description():
    repo = _make_repo(description="Hello world repo")
    svg = render_svg(repo)
    assert "Hello world repo" in svg


def test_svg_contains_stars():
    repo = _make_repo(stars=1234)
    svg = render_svg(repo)
    assert "1234" in svg


def test_svg_language_bar_present():
    repo = _make_repo(languages={"Python": 8000, "JavaScript": 2000})
    svg = render_svg(repo)
    assert "Python" in svg
    assert "JavaScript" in svg


def test_svg_topics_present():
    repo = _make_repo(topics=["cli", "terminal"])
    svg = render_svg(repo)
    assert "cli" in svg
    assert "terminal" in svg


def test_svg_empty_description():
    repo = _make_repo(description="")
    svg = render_svg(repo)
    assert "<svg" in svg


def test_svg_no_languages():
    repo = _make_repo(languages={})
    svg = render_svg(repo)
    assert "<svg" in svg


def test_svg_fork_notice():
    repo = _make_repo(is_fork=True)
    svg = render_svg(repo)
    assert "fork" in svg


def test_svg_license_shown():
    repo = _make_repo(license_name="Apache-2.0")
    svg = render_svg(repo)
    assert "Apache-2.0" in svg


def test_html_special_chars_escaped():
    repo = _make_repo(description='A & B <test> "quoted"')
    svg = render_svg(repo)
    assert "&amp;" in svg
    assert "&lt;" in svg
    assert "&quot;" in svg
