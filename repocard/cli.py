"""
repocard CLI.

    repocard generate owner/repo [--output card.svg]
    repocard generate owner/repo --png --output card.png
"""
from __future__ import annotations
import sys
from pathlib import Path

import click

from . import __version__
from .api import fetch, fetch_all_repos
from .render import render_svg


@click.group()
@click.version_option(__version__)
def main():
    """repocard — generate stat cards for GitHub repos."""


@main.command()
@click.argument("repo_slug", metavar="OWNER/REPO")
@click.option(
    "--output", "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output path. Defaults to <repo>.svg (or .png with --png).",
)
@click.option(
    "--png",
    is_flag=True,
    help="Render to PNG via Pillow+cairosvg (requires cairosvg).",
)
def generate(repo_slug: str, output: Path | None, png: bool):
    """
    Generate a stat card for OWNER/REPO.

    \b
    Examples:
        repocard generate torvalds/linux
        repocard generate psf/requests --output requests_card.svg
        repocard generate Gnomecromancer/tapegif --png
    """
    if "/" not in repo_slug:
        click.echo("Error: OWNER/REPO must contain a slash (e.g. torvalds/linux)", err=True)
        sys.exit(1)

    owner, repo = repo_slug.split("/", 1)
    click.echo(f"fetching {repo_slug} …")

    try:
        data = fetch(owner, repo)
    except Exception as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)

    svg = render_svg(data)

    if png:
        try:
            import cairosvg
        except ImportError:
            click.echo(
                "cairosvg is required for PNG output: pip install cairosvg",
                err=True,
            )
            sys.exit(1)
        out = output or Path(f"{repo}.png")
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out))
    else:
        out = output or Path(f"{repo}.svg")
        out.write_text(svg, encoding="utf-8")

    click.echo(f"saved {out}")


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", "-p", default=8765, show_default=True)
@click.option("--ttl", default=300, show_default=True, help="Cache TTL in seconds.")
@click.option("--token", default=None, envvar="GITHUB_TOKEN",
              help="GitHub token for higher rate limits.")
def serve(host: str, port: int, ttl: int, token: str | None):
    """
    Run a local card server. Serve cards at http://host:port/{owner}/{repo}.

    Useful for live README badges (star counts update automatically).

    \b
    Example:
        repocard serve --port 8765
        # Then in your README:
        # ![card](http://localhost:8765/psf/requests)
    """
    import time
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    _cache: dict[str, tuple[str, float]] = {}
    _lock = threading.Lock()

    def _get_svg(owner: str, repo: str) -> str:
        key = f"{owner}/{repo}"
        now = time.time()
        with _lock:
            if key in _cache:
                svg, ts = _cache[key]
                if now - ts < ttl:
                    return svg

        data = fetch(owner, repo)
        svg = render_svg(data)
        with _lock:
            _cache[key] = (svg, time.time())
        return svg

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            click.echo(f"{self.address_string()} {fmt % args}")

        def do_GET(self):
            parts = self.path.strip("/").split("/")
            if len(parts) != 2 or not all(parts):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Expected /owner/repo")
                return

            owner, repo = parts
            try:
                svg = _get_svg(owner, repo)
            except Exception as e:
                self.send_response(502)
                self.end_headers()
                self.wfile.write(str(e).encode())
                return

            body = svg.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Cache-Control", f"public, max-age={ttl}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((host, port), Handler)
    click.echo(f"repocard server listening on http://{host}:{port}/")
    click.echo(f"  embed in README: ![card](http://{host}:{port}/owner/repo)")
    click.echo("  Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nstopped")


@main.command()
@click.argument("owner")
@click.option(
    "--output-dir", "-d",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory to write SVG files into.",
)
@click.option(
    "--token", default=None, envvar="GITHUB_TOKEN",
    help="GitHub token for higher rate limits.",
)
@click.option(
    "--include-forks",
    is_flag=True,
    default=False,
    help="Also generate cards for forked repos (skipped by default).",
)
def batch(owner: str, output_dir: Path, token: str | None, include_forks: bool):
    """
    Generate SVG cards for all public repos owned by OWNER.

    \b
    Examples:
        repocard batch torvalds --output-dir ./cards
        repocard batch psf --output-dir /tmp/psf-cards --include-forks
        repocard batch Gnomecromancer --output-dir ./out --token $GITHUB_TOKEN
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"fetching repos for {owner} …")
    try:
        repos = fetch_all_repos(owner, token=token, include_forks=include_forks)
    except Exception as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)

    if not repos:
        click.echo("no repos found (nothing to do)")
        return

    click.echo(f"generating cards for {len(repos)} repo(s)…")
    errors = 0
    for repo in repos:
        out_path = output_dir / f"{repo.name}.svg"
        try:
            svg = render_svg(repo)
            out_path.write_text(svg, encoding="utf-8")
            click.echo(f"  {repo.full_name} → {out_path}")
        except Exception as e:
            click.echo(f"  warning: skipping {repo.full_name}: {e}", err=True)
            errors += 1

    done = len(repos) - errors
    click.echo(f"done — {done}/{len(repos)} cards written to {output_dir}")
